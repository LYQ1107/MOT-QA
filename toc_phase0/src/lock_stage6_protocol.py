"""Lock the user-approved40-image protocol and all602 initial prompts before models."""
from stage6_common import *
from stage6_tools import Tools


def main():
    verify_stage5()
    assert not (ROOT/'results/stage6_protocol_locked.json').exists()
    from transformers import AutoProcessor
    import numpy as np
    processor=AutoProcessor.from_pretrained(ROOT/'models/Qwen2.5-VL-7B-Instruct',local_files_only=True)
    split=read(ROOT/'results/dev_test_split_locked.json');ids=set(split['test_qa_ids'])
    visible=sorted([q for q in rows(ROOT/'results/stage3_visible_inputs.jsonl') if q['qa_id'] in ids],key=lambda q:q['qa_id'])
    assert len(visible)==602 and sum(q['format']=='numerical' for q in visible)==242
    old={p['qa_id']:p for p in rows(ROOT/'results/stage4/prompts/A.jsonl')}
    image_tokens={p['qa_id']:p['image_tokens'] for p in read(ROOT/'results/v1_input_lengths.json')['rows']}
    demos=read(ROOT/'results/stage6_demonstrations_locked.json')['examples']
    demo_messages=[m for example in demos for m in example['messages']]
    tools=Tools();artifacts=[];lengths=[]
    def count(messages,image_total,image_count):
        normalized=[]
        for message in messages:
            content=message['content']
            if isinstance(content,list):content=[dict(type='image') if b['type']=='image_path' else b for b in content]
            normalized.append(dict(role=message['role'],content=content))
        rendered=processor.apply_chat_template(normalized,tokenize=False,add_generation_prompt=True)
        return len(processor.tokenizer.encode(rendered,add_special_tokens=False))+image_total-image_count
    for condition in ['T-none','T0','T1']:
        ps=[]
        for item in visible:
            qid=item['qa_id'];stamp=old[qid]['user'].split('\n',1)[0]
            messages=[dict(role='system',content=SYSTEM)]+(demo_messages if condition=='T1' else [])+[initial_message(item,stamp,condition)]
            expected=count(messages,image_tokens[qid],32)
            bounds=[]
            for name in tools.names[item['video_id']]:
                for shuffled in (False,True):
                    doc=tools.document(item['video_id'],name,shuffled)
                    from stage5_representations import select,b_main,b_events
                    sel=select(doc)
                    for text in [b_main(doc,sel),b_events(doc,sel)[0]]:
                        bounds.append(len(processor.tokenizer.encode(text,add_special_tokens=False)))
            # Each new image <=720x720 => at most676 merged tokens;
            # conservative extra look allowance includes minimum-pixel rounding.
            per_call=max(max(bounds,default=0),1600)+256
            upper=expected+2048+4*per_call+512
            assert upper<=65536,(qid,upper)
            p=dict(qa_id=qid,video_id=item['video_id'],format=item['format'],condition=condition,messages=messages,
                   expected_initial_prompt_tokens=expected,conservative_full_context_upper_bound=upper,
                   initial_messages_sha256=digest(messages),max_total_generation_tokens=2048)
            ps.append(p);lengths.append(dict(qa_id=qid,condition=condition,initial=expected,conservative_full=upper))
        path=ROOT/'results/stage6/prompts'/f'{condition}.jsonl';write_rows(path,ps);path.chmod(0o444)
        artifacts.append(dict(path=str(path),sha256=sha(path)))
    protocol=dict(created_at=now(),before_any_stage6_inference=True,
        hypotheses_sha256=sha(ROOT/'results/stage6_hypotheses_preregistered.json'),
        demonstrations_sha256=sha(ROOT/'results/stage6_demonstrations_locked.json'),
        frozen_config_sha256=sha(ROOT/'results/frozen_config_v1.json'),
        d_assignments_sha256=sha(ROOT/'results/stage4_D_assignments_locked.json'),
        user_approved_image_count_limit=40,original32_frames_preserved=True,
        image_count_authorization='User explicitly selected uniform40 limit, preserving original32 frames; other server args unchanged.',
        system=SYSTEM,tool_descriptions=DESCRIPTIONS,no_tools_text=NO_TOOLS,
        tool_policy=dict(max_calls=4,max_turns=5,total_generation_tokens=2048,temperature=0,seed=42,
            call_parsing='Custom one tagged JSON object per turn; malformed attempts consume call budget. Never use vLLM tool parser.',
            execution='Tool response is the next user message; after4 attempts request direct final answer; exhausted generation or bad parse wrong.',
            matching='NFKC, casefold, collapse whitespace then exact; no fuzzy/plural/synonym mapping',
            images='Initial32 JPEG bytes/order unchanged; look returns1or2 additional images, all retained,<=40; crop pad30%eachside, JPEG85; full thumbnail360, crop720',
            nearest_frame='Nearest5fps index with exact half-frame ties going to earlier index; clamp to available video frames',
            shuffle='Use the exact Stage4D donor or saved per-track tile permutation; project to frozen representative/timeline. Look crops current video with shuffled normalized boxes.'),
        guided_count=dict(tool_turn_regex=TOOL_OR_FINAL_REGEX,final_only_regex=FINAL_REGEX,
            bad_words=['<|endoftext|>'],meaning='Allow free reasoning and optional custom tool call, constrain only finalAnswer to2/3/4/5 or more. After call budget only final grammar.',
            cpu_xgrammar_regression='Compiled both grammars; bare and reasoning answers accepted; illegal2.0 rejected; toolcall accepted only by tool grammar.'),
        server=dict(max_model_len=65536,max_num_seqs=8,max_num_batched_tokens=32768,gpu_memory_utilization=.65,
                    dtype='bfloat16',seed=42,tensor_parallel_size=1,enforce_eager=True,image_limit=40,width=720,height=720,video_limit=0,
                    generation_config='auto; base checkpoint repetition_penalty1.05 unchanged',
                    trained_evaluation='Same server flags; add only LoRA loading flags required for rank8 adapter. Stage5B-events exact prompts,1024token max.'),
        training_api='LlamaFactory0.9.3 run_exp, bypass unused CLI chat/vLLM imports; separate trainingvenv; finalsecond-epoch adapter',
        prompts=artifacts,source_sha256={f:sha(ROOT/'src'/f) for f in ['stage6_common.py','stage6_tools.py','stage6_synthetic.py']},
        context_statistics={c:{k:dict(median=float(np.median([r[k] for r in lengths if r['condition']==c])),
              p95=float(np.percentile([r[k] for r in lengths if r['condition']==c],95)),maximum=max(r[k] for r in lengths if r['condition']==c))
              for k in ['initial','conservative_full']} for c in ['T-none','T0','T1']},
        no_tracking_rerun=True,bench_labels_in_tools_or_training=False)
    lock=immutable(ROOT/'results/stage6_protocol_locked.json',protocol)
    write(ROOT/'results/stage6_initial_input_lengths.json',dict(created_at=now(),rows=lengths,statistics=protocol['context_statistics']))
    with (ROOT/'logs/downloads.md').open('a') as stream:
        commit=__import__('subprocess').check_output(['git','-C',str(ROOT/'upstream/LLaMA-Factory'),'rev-parse','HEAD'],text=True).strip()
        stream.write('\n## Stage6 LlamaFactory\n\n- DirectGitHub clone succeeded, no proxy: https://github.com/hiyouga/LLaMA-Factory.git tagv0.9.3 commit `'+commit+'`.\n'
            '- Training venv inherits existingTorch2.9.1 binaries; local Transformers4.52.4/PEFT0.15.2/datasets3.6.0/accelerate1.7.0/TRL0.9.6. No vLLM environment mutations. Install logs:logs/stage6_train_environment_install.log.\n'
            '- PyArrow26 requiredNumPy2, conflicting with LlamaFactory NumPy<2; pinPyArrow19.0.1. ExistingCLI unnecessarily imports inheritedvLLM0.16 with oldTransformers; use supported trainingAPI, no chat engine.\n')
    print(__import__('json').dumps(dict(status='LOCKED_BEFORE_INFERENCE',lock=lock,context=protocol['context_statistics']),ensure_ascii=False))


if __name__=='__main__':main()
