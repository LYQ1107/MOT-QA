"""Apply registered dev-only selection rules; freeze once before full retracking."""
import argparse
import hashlib
import json
from pathlib import Path

from rule_prediction import PARAMETERS
from run_stage3_masa import ROOT,now


def load(name):return json.loads((ROOT/name).read_text())


def save_new(name,value):
    path=ROOT/name;path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as stream:json.dump(value,stream,ensure_ascii=False,indent=2);stream.write('\n')
    path.chmod(0o444)
    return path


def metric(label):
    result=load('results/improvement/dev/'+label+'/metrics.json')
    assert result['scope']=='dev' and result['test_accuracy_computed'] is False
    primary=result['groups']['main_trackable']
    assert primary['total']==70
    return result,primary


def rank(primary):return primary['correct'],primary['covered']


def main(args):
    plan=load('results/improvement_plan_locked.json')
    if args.stage=='memory':
        rows=[]
        for memory in plan['memory_candidates']:
            label=f'memo{memory}_original';result,primary=metric(label)
            proxy=load(f'results/improvement/dev/memo{memory}_proxy.json')
            rows.append(dict(memory=memory,label=label,primary=primary,all=result['groups']['all'],proxy={k:v for k,v in proxy.items() if k!='rows'}))
        # Proxy key is the registered missing-as-failure fixed-window measure.
        def key(row):
            proxy=row['proxy'];value=proxy['selection_proxy']
            return (*rank(row['primary']),-value,-row['memory'])
        chosen=max(rows,key=key)
        save_new('results/improvement/dev/memory_selection.json',dict(selected_at=now(),scope='dev',
                 rule=plan['selection_order']+['lower fixed-window fresh-ID/missing proxy','smaller memory'],
                 candidates=rows,selected_memory=chosen['memory'],selected_label=chosen['label'],test_accuracy_read=False))
        print(json.dumps(dict(stage='memory',selected_memory=chosen['memory'],primary=chosen['primary'])))
    elif args.stage=='filter':
        memory=load('results/improvement/dev/memory_selection.json')['selected_memory']
        rows=[]
        for suffix in ('short_weak','short_weak_top5','short_weak_top10'):
            label=f'memo{memory}_{suffix}';result,primary=metric(label)
            row=dict(label=label,filter=result['filter'],primary=primary,all=result['groups']['all'])
            if suffix!='short_weak':row['lengths']=load('results/improvement/dev/'+label+'/lengths.json')
            rows.append(row)
        eligible=[r for r in rows if 'lengths' in r and r['lengths']['text_limits_met']]
        if not eligible:
            label=f'memo{memory}_short_weak_top3';result,primary=metric(label)
            row=dict(label=label,filter=result['filter'],primary=primary,all=result['groups']['all'],
                     lengths=load('results/improvement/dev/'+label+'/lengths.json'))
            rows.append(row);assert row['lengths']['text_limits_met'],'Registered fallback fails dev text constraints'
            eligible=[row]
        chosen=max(eligible,key=lambda row:(*rank(row['primary']),-row['filter']['top_k']))
        save_new('results/improvement/dev/filter_selection.json',dict(selected_at=now(),scope='dev',
                 candidates=[{k:v for k,v in r.items() if k!='lengths'}|({'text':r['lengths']['groups']['dev']['track_text_tokens'],'text_limits_met':r['lengths']['text_limits_met']} if 'lengths' in r else {}) for r in rows],
                 selected_filter=chosen['filter'],selected_label=chosen['label'],test_accuracy_read=False))
        print(json.dumps(dict(stage='filter',filter=chosen['filter'],primary=chosen['primary'])))
    elif args.stage=='event':
        selected=load('results/improvement/dev/filter_selection.json');rows=[]
        for label in (selected['selected_label'],selected['selected_label']+'_public'):
            result,primary=metric(label)
            rows.append(dict(label=label,event_mode=result['event_mode'],primary=primary,all=result['groups']['all']))
        chosen=max(rows,key=lambda row:(*rank(row['primary']),row['event_mode']=='public_3fps_min2_confirm2'))
        save_new('results/improvement/dev/event_selection.json',dict(selected_at=now(),scope='dev',candidates=rows,
                 selected_event=chosen['event_mode'],selected_label=chosen['label'],test_accuracy_read=False))
        print(json.dumps(dict(stage='event',event=chosen['event_mode'],primary=chosen['primary'])))
    else:
        memory=load('results/improvement/dev/memory_selection.json');fil=load('results/improvement/dev/filter_selection.json')
        event=load('results/improvement/dev/event_selection.json')
        label=event['selected_label'];selected,primary=metric(label)
        lengths=load('results/improvement/dev/'+fil['selected_label']+'/lengths.json')
        assert lengths['text_limits_met']
        split_sha=hashlib.sha256((ROOT/'results/dev_test_split_locked.json').read_bytes()).hexdigest()
        prereg_sha=hashlib.sha256((ROOT/'results/trackable_subset_preregistered.json').read_bytes()).hexdigest()
        assert split_sha==plan['split_sha256'] and prereg_sha==plan['preregistration_sha256']
        source=load('tracks/raw/charades_DOUFF.json')['tracker_parameters']
        source['memo_tracklet_frames']=memory['selected_memory']
        maximum_queries=max(len(q['queries']) for q in load('results/stage3_extracted_queries.json'))
        conservative_context_bound=32*26*26+maximum_queries*12000+4096+1024
        assert conservative_context_bound<=65536
        sources=['run_masa_improvement.py','improvement_facts.py','improvement_events.py','rule_prediction.py',
                 'track_facts.py','stage3_text.py','finalize_improvement_v1.py','measure_improvement_lengths.py']
        frozen=dict(version=1,frozen_at=now(),split_sha256=split_sha,preregistration_sha256=prereg_sha,
           selection_scope='development only, 138 videos / 147 QA, primary objective 70 main-trackable QA',
           prior_exposure='The accepted original stage-three report contained full-set results before the video split. No new test rule scores were used for this round.',
           tracking=dict(model='MASA-GroundingDINO unified',code_commit='c5472b9c7615f35abdf1188cb1a0c5408fe50d66',
             weights='models/MASA/gdino_masa.pth',weights_hf_revision='25ed372c47f2c46cf36fd446d1b657b656bc7ea9',
             config='upstream/masa/configs/masa-gdino/masa_gdino_swinb_inference.py',
             language_model='models/MASA/bert-base-uncased',memo_tracklet_frames=memory['selected_memory'],
             fps=5,seed=42,score_threshold=0.2,fp16=True,unified=True,custom_entities=True,
             text_separator=' . ',sam_mask=False,sam2_or_sam3_used=False,native_scores_preserved=True,
             reset_tracker_and_all_detector_text_caches_per_video=True,native_tracker=source),
           filter=fil['selected_filter'],
           serialization=dict(format='original raw facts, retained native IDs; no inferred answers',
              max_tracks_per_query=fil['selected_filter']['top_k'],visible_interval_gap_seconds=0.5,
              coordinates='normalized box centers, two decimal places',times='seconds, one decimal place',
              retain_all_intervals_of_kept_tracks=True,
              omitted_line='Note: {N} additional short, low-confidence, or lower-ranked tracks were omitted.',
              text_target_p95_tokens=8000,text_target_max_tokens=12000,b2_area_ratios='deferred, separate optional exploratory variant'),
           rule=dict(event_mode=event['selected_event'],geometry_parameters=PARAMETERS,
              active_event_protocol=(dict(grid_fps=5,visible_observation_gap_seconds=0.5,terminal_absence_seconds=0.5)
                  if event['selected_event']=='legacy_gap_0.5' else
                  dict(grid_fps=3,source_frame_index='floor(j*5/3+0.5)',minimum_absent_samples=2,
                       reappearance_consecutive_visible_samples=2,onset='first absent grid tick',
                       return_time='first visible tick of the confirmed return',max_sample_time_offset_seconds=1/15)),
              public_definition_candidate=plan['public_event_reference'],
              unsupported='partial occlusion and abrupt state changes remain unsupported',
              numerical='raw 0/1 are retained, covered, illegal, and wrong under official parsing; >=5 maps to 5 or more',
              coverage='an answer is returned; all-scope accuracy counts abstentions/invalid parses wrong'),
           service_context=dict(max_model_len=65536,all_future_conditions_same=True,
              reason='Conservative common bound: 32 images each at most 26*26 tokens, each possible donor block budgeted at 12000 tokens, 4096 common-text reserve and 1024 generation reserve; 32768 does not cover this bound.',
              maximum_queries_per_question=maximum_queries,conservative_input_generation_bound=conservative_context_bound,model_max_position_embeddings=128000,
              image_processor=lengths['image_processor_class'],processor_kwargs_overrides=None,
              main_generation_tokens=dict(normal=64,ordering=256),supplement_generation_length_reserve=1024),
           future_input=dict(official_prompt_and_parser=True,sampling='floor(i*N/32), official short-video branch',
              frames=32,long_edge_max=720,jpeg_quality=85,temperature=0,seed=42,
              timestamps='official sample index / original FPS, formatted to 0.001 seconds, after frames in every condition',
              evidence='insert immediately before Question:; A empty, B original 7.3 preface plus facts, C original 7.4, D original 7.5',
              metadata_as_input=False,numerical_guided_choice='separate diagnostic reruns in all four conditions only; not main strict result'),
           dev_selected_label=label,dev_primary_result=primary,
           selection_artifacts=['results/improvement/dev/memory_selection.json','results/improvement/dev/filter_selection.json','results/improvement/dev/event_selection.json'],
           source_sha256={s:hashlib.sha256((ROOT/'src'/s).read_bytes()).hexdigest() for s in sources},
           final_retracking='all 689 videos recomputed in tracks/v1/raw after this freeze; development trial raw outputs not reused',
           preregistered_subset_changed=False,stage_four_inference_authorized=False)
        path=save_new('results/frozen_config_v1.json',frozen)
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        save_new('logs/frozen_config_v1_lock.json',dict(locked_at=now(),path=str(path),sha256=digest,immutable=True))
        print(json.dumps(dict(status='FROZEN',sha256=digest,memory=memory['selected_memory'],filter=fil['selected_filter'],event=event['selected_event'],dev_primary=primary)))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['memory','filter','event','freeze'],required=True)
    main(parser.parse_args())
