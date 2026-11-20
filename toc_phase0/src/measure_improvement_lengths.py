"""CPU-only exact Qwen image-grid/text lengths; no model inference or answers."""
import argparse
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image
from transformers import AutoProcessor

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'upstream/toc_bench'))
from eval_runner import build_prompt,get_max_tokens

TRACKER_PREFACE=('An object tracker was run on the full video at 5 fps. Its output is below.\n'
 'The tracker sees every frame, while you only see 32 sampled frames, so use\n'
 'the tracks as evidence about when objects appear, disappear and reappear.\n'
 'The tracker can make mistakes (fragmented tracks, identity switches, false\n'
 'detections); check the tracks against the frames when they conflict.\n\n')
PLACEHOLDER='An object tracker was run on the full video at 5 fps.\n[Tracking output omitted]\n'


def distribution(values):
    values=np.asarray(values,dtype=np.int64)
    return dict(n=len(values),minimum=int(values.min()),median=float(np.percentile(values,50)),
                p90=float(np.percentile(values,90)),p95=float(np.percentile(values,95)),
                p99=float(np.percentile(values,99)),maximum=int(values.max()),mean=float(values.mean()))


def main(args):
    split_path=ROOT/'results/dev_test_split_locked.json'
    split=json.loads(split_path.read_text())
    lock=json.loads((ROOT/'logs/dev_test_split_lock.json').read_text())
    assert hashlib.sha256(split_path.read_bytes()).hexdigest()==lock['sha256']
    if args.scope=='all':
        frozen_path=ROOT/'results/frozen_config_v1.json'
        frozen_lock=json.loads((ROOT/'logs/frozen_config_v1_lock.json').read_text())
        assert hashlib.sha256(frozen_path.read_bytes()).hexdigest()==frozen_lock['sha256']
        frozen=json.loads(frozen_path.read_text())
    visible=[json.loads(s) for s in (ROOT/'results/stage3_visible_inputs.jsonl').read_text().splitlines()]
    if args.scope=='dev':visible=[q for q in visible if q['qa_id'] in set(split['dev_qa_ids'])]
    qa_ids={q['qa_id'] for q in visible}
    queries={r['qa_id']:r['queries'] for r in json.loads((ROOT/'results/stage3_extracted_queries.json').read_text()) if r['qa_id'] in qa_ids}
    index=json.loads(Path(args.index).read_text())
    videos={q['video_id'] for q in visible}
    index=[r for r in index if r['video_id'] in videos]
    texts={(r['video_id'],r['query']):Path(r['text_path']).read_text() for r in index}
    processor=AutoProcessor.from_pretrained(ROOT/'models/Qwen2.5-VL-7B-Instruct',local_files_only=True)
    tokenizer=processor.tokenizer
    def count(text):return len(tokenizer.encode(text,add_special_tokens=False))
    query_lengths={key:count(text) for key,text in texts.items()}
    largest_key=max(query_lengths,key=query_lengths.get)

    @lru_cache(maxsize=None)
    def images(video):
        cache=ROOT/'frames_cache/official32'/video
        sample=json.loads((cache/'sampling.json').read_text())
        assert sample['sampled_count']==sample['expected_count']==min(32,sample['total_frames'])
        if sample['total_frames']>32:
            assert sample['sample_indices']==[int(i*sample['total_frames']/32) for i in range(32)]
        sizes=[]
        for name in sample['jpeg_files']:
            with Image.open(cache/name) as image:sizes.append((image.height,image.width))
        data=processor._get_num_multimodal_tokens(image_sizes=sizes)
        tokens=list(map(int,data['num_image_tokens']))
        assert len(tokens)==sample['sampled_count']
        return sample,tokens,sizes

    # Check installed processor's shape shortcut against actual pixel processing.
    validation_source=ROOT/'results/improvement/dev/memo10_original/lengths.json'
    checked=[];seen=set()
    if validation_source.exists():
        prior=json.loads(validation_source.read_text())
        assert prior['image_processor_class']==type(processor.image_processor).__name__
        checked=prior['pixel_shape_validation']
    for video in ([] if checked else sorted(videos)):
        sample,tokens,sizes=images(video)
        shape=sizes[0]
        if shape in seen:continue
        seen.add(shape)
        path=ROOT/'frames_cache/official32'/video/sample['jpeg_files'][0]
        with Image.open(path) as image:
            feature=processor.image_processor(images=[image.convert('RGB')],return_tensors='pt')
            grid=feature['image_grid_thw'][0]
            actual=int(grid.prod().item()//processor.image_processor.merge_size**2)
            single=processor.apply_chat_template([dict(role='user',content=[dict(type='image'),dict(type='text',text='Frame.')])],tokenize=False,add_generation_prompt=True)
            actual_input=processor(images=[image.convert('RGB')],text=[single],return_tensors='pt')
            expected_input=count(single)+actual-1
            assert actual_input['input_ids'].shape[-1]==expected_input
        assert actual==tokens[0],(video,shape,actual,tokens[0])
        checked.append(dict(video_id=video,shape_hw=list(shape),grid_thw=list(map(int,grid)),predicted_tokens=tokens[0],actual_tokens=actual,expanded_prompt_tokens=expected_input))
        if len(checked)>=8:break

    def rendered_length(item,frame_count,image_tokens,stamp_text,evidence):
        system,user=build_prompt(item)
        if evidence:user=user.replace('Question:',evidence+'\nQuestion:',1)
        text=stamp_text+'\n'+user
        messages=[dict(role='system',content=system),dict(role='user',content=[{'type':'image'} for _ in range(frame_count)]+[dict(type='text',text=text)])]
        rendered=processor.apply_chat_template(messages,tokenize=False,add_generation_prompt=True)
        placeholder_count=rendered.count(processor.image_token)
        assert placeholder_count==frame_count
        return count(rendered)+sum(image_tokens)-placeholder_count

    rows=[]
    for item in visible:
        video=item['video_id'];sample,image_tokens,_=images(video)
        stamps=[idx/sample['fps'] for idx in sample['sample_indices']]
        assert np.allclose(stamps,sample['sample_timestamps_s'])
        stamp_text='The frames above were sampled at these times (seconds): '+', '.join(f'{t:.3f}' for t in stamps)+'.'
        track='\n'.join(texts[(video,q)] for q in queries[item['qa_id']])
        base=dict(item=item,frame_count=len(image_tokens),image_tokens=image_tokens,stamp_text=stamp_text)
        lengths={
          'A':rendered_length(**base,evidence=''),
          'B':rendered_length(**base,evidence=TRACKER_PREFACE+track),
          'C':rendered_length(**base,evidence=PLACEHOLDER)}
        # D donors are not assigned in this stage. Any eligible donor block is
        # bounded by the largest observed query block; extra boundary slack.
        d_bound=rendered_length(**base,evidence=TRACKER_PREFACE)+sum(query_lengths[largest_key]+64 for _ in queries[item['qa_id']])
        lengths['D_upper_bound']=max(lengths['B'],d_bound)
        budget=get_max_tokens(item['format'])
        rows.append(dict(qa_id=item['qa_id'],video_id=video,split='dev' if item['qa_id'] in set(split['dev_qa_ids']) else 'test',
                         query_count=len(queries[item['qa_id']]),track_text_tokens=count(track),image_tokens=sum(image_tokens),
                         complete_input_tokens=lengths,generation_budget=budget,
                         max_input_plus_official_generation=max(lengths.values())+budget,
                         max_input_plus_supplement_reserve=max(lengths.values())+1024))
    text_stats=distribution([r['track_text_tokens'] for r in rows])
    groups={}
    for name,subset in [('all',rows),('dev',[r for r in rows if r['split']=='dev']),('test',[r for r in rows if r['split']=='test'])]:
        if not subset:continue
        groups[name]=dict(questions=len(subset),track_text_tokens=distribution([r['track_text_tokens'] for r in subset]),
                         image_tokens=distribution([r['image_tokens'] for r in subset]),
                         complete_input_tokens={c:distribution([r['complete_input_tokens'][c] for r in subset]) for c in rows[0]['complete_input_tokens']},
                         input_plus_official_generation=distribution([r['max_input_plus_official_generation'] for r in subset]),
                         input_plus_supplement_reserve=distribution([r['max_input_plus_supplement_reserve'] for r in subset]))
    max_required=max(r['max_input_plus_supplement_reserve'] for r in rows)
    candidates=json.loads((ROOT/'results/improvement_plan_locked.json').read_text())['service_context_candidates']
    context=next((n for n in candidates if n>=max_required),None)
    config=json.loads((ROOT/'models/Qwen2.5-VL-7B-Instruct/config.json').read_text())
    assert context is not None and context<=config['max_position_embeddings'],max_required
    minimum_fitting_context=context
    if args.scope=='all':
        context=frozen['service_context']['max_model_len']
        assert max_required<=context,(max_required,context)
    result=dict(scope=args.scope,index=str(Path(args.index).resolve()),no_inference=True,answers_or_metadata_read=False,
                split_sha256=lock['sha256'],processor_class=type(processor).__name__,image_processor_class=type(processor.image_processor).__name__,
                pixel_shape_validation=checked,query_text_tokens=distribution(list(query_lengths.values())),groups=groups,
                pixel_shape_validation_source=str(validation_source),
                text_limits_met=text_stats['p95']<=8000 and text_stats['maximum']<=12000,
                selected_service_max_model_len=context,minimum_fitting_context=minimum_fitting_context,model_supported_context=config['max_position_embeddings'],
                worst_case_query=dict(video_id=largest_key[0],query=largest_key[1],tokens=query_lengths[largest_key]),
                d_bound='largest query block tokens per required query plus 64 boundary tokens per block and exact common prompt/image tokens; no donor assignment or inference',
                timestamp_precision_seconds=0.001,supplement_generation_reserve=1024,rows=rows)
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(scope=args.scope,questions=len(rows),query_pairs=len(index),text=text_stats,limits_met=result['text_limits_met'],context=context,max_input_generation=max_required,pixel_shape_checks=len(checked))))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--scope',choices=['dev','all'],required=True)
    parser.add_argument('--index',required=True);parser.add_argument('--output',required=True);main(parser.parse_args())
