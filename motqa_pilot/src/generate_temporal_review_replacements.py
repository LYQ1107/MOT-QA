"""Replace three moving-camera path-length designs with reappearance-order questions."""
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import copy
import math
import random

import numpy as np
import generate_question_review as base
from question_design_eligibility import camera_motion_exclusion_reason

ROOT=base.ROOT
OUT=ROOT/'results/question_review_replacements'
RNG=random.Random(42)


def eligible_returns(key):
    return [e for e in base.EVENTS[key] if e['type']=='reappears'
            and (key[0]=='SportsMOT' or e['previous_disappearance_type']=='becomes_occluded')]


def box_anchor(key,event,latest):
    a=base.scene(key);m=base.META[key];tid=event['gt_id'];i=a['axis'][tid]
    high=min(latest,event['evidence_frames'][0])
    low=max(m['eligible_source_window_1based'][0],event['frame']-int(22*m['fps']))
    frames=np.flatnonzero(a['visible'][i,low-1:high])+low
    # Search actual visible source frames, newest first. Geometry is unchanged.
    for frame in frames[::-max(1,int(m['fps']/5))]:
        r=base.make_ref(key,tid,int(frame),'box')
        if r is not None:return r
    return None


def choose(dataset,kind,reuse):
    if kind=='appearance':
        primary=[((x['dataset'],x['sequence']),x['gt_id'],base.make_ref((x['dataset'],x['sequence']),x['gt_id'],x['reference_frame'],'appearance',x))
                 for x in base.read_jsonl(ROOT/'results/review/appearance_reference_pool_user_verified.jsonl') if x['dataset']==dataset]
    else:
        primary=[(key,tid,None) for key,m in base.META.items() if key[0]==dataset and m['eligible_source_window_1based']
                 for tid in sorted({e['gt_id'] for e in eligible_returns(key)})]
    RNG.shuffle(primary)
    attempts=0
    for key,tid,fixed in primary:
        if reuse[(*key,tid)]>=3:continue
        m=base.META[key];fps=m['fps'];ev=eligible_returns(key)
        first=[e for e in ev if e['gt_id']==tid];RNG.shuffle(first)
        for ea in first:
            others=[e for e in ev if e['gt_id']!=tid and reuse[(*key,e['gt_id'])]<3
                    and .8*fps<=abs(e['frame']-ea['frame'])<=12*fps]
            RNG.shuffle(others)
            for eb in others:
                attempts+=1;earliest=min(ea['frame'],eb['frame']);latest=earliest-math.ceil(3*fps)
                ra=copy.deepcopy(fixed) if fixed else box_anchor(key,ea,latest)
                if ra is None or ra['frame']>latest:continue
                rb=box_anchor(key,eb,latest)
                if rb is None:continue
                start=max(ra['frame'],rb['frame'])+math.ceil(3*fps)
                end=min(m['eligible_source_window_1based'][1],max(ea['frame'],eb['frame'])+math.ceil(.75*fps))
                if end-min(ra['frame'],rb['frame'])>24*fps:continue
                actual=[]
                for t in [tid,eb['gt_id']]:
                    events=sorted([e for e in ev if e['gt_id']==t and start<=e['frame']<=end],key=lambda e:e['frame'])
                    if not events:break
                    actual.append(events[0])
                if len(actual)!=2 or [e['frame'] for e in actual]!=[ea['frame'],eb['frame']]:continue
                for role,r in zip('AB',[ra,rb]):r['role']=role
                winner=0 if ea['frame']<eb['frame'] else 1
                overlap=base.partners(key,tid,min(ra['frame'],rb['frame']),end)[eb['gt_id']]
                return key,[ra,rb],actual,start,end,winner,bool(overlap),attempts
    raise RuntimeError(f'No valid temporal replacement for {dataset}/{kind} after {attempts} event pairs')


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    accepted=base.read_jsonl(ROOT/'data/question_review_user_passed_17.jsonl')
    held=base.read_jsonl(ROOT/'data/question_review_camera_revision_3.jsonl')
    reuse=Counter((q['dataset'],q['sequence'],t) for q in accepted for t in q['reference']['target_ids'])
    original_path=ROOT/'data/question_review_candidates_20.jsonl';accepted_path=ROOT/'data/question_review_user_passed_17.jsonl'
    originals={str(p):base.sha(p) for p in [original_path,accepted_path,ROOT/'results/generation_config_locked.json']}
    protocol={'recorded_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'seed':42,
              'scope':'Three new O5 temporal-order designs replace original4/5/17;17human-passed designs remain byte-identical.',
              'source_hashes':originals,'event':'first reappearance within the explicit query interval after an absence strictly longer than1second',
              'return_order_min_separation_s':.8,'reference_to_query_start_min_s':3,
              'maximum_event_pair_separation_s':12,'maximum_reference_to_query_end_s':24,
              'box_gates':'unchanged frozen box-reference geometry','human_appearance':'only passed exact phrase/identity/reference instant',
              'identity_scope':'DanceTrack/MOT17 use internal occlusion returns only; SportsMOT uses publisher same-ID returns, with no cause question',
              'answer':'compare first eligible reappearance source-frame indices; no path length, speed, homography or physical distance estimated',
              'visibility_semantics':'Use the locked per-dataset visible mask. Wording refers to being clearly visible again, without claiming full occlusion; MOT17 uses its existing visibility>=0.25 convention.',
              'human_verdict_for_new_questions':None,'full900_completed':False,'new_model_calls':0,'new_tracker_runs':0}
    base.dump(OUT/'protocol.json',protocol)
    replacements=[];base.RNG.seed(42)
    for old in held:
        key,refs,events,start,end,winner,conf,attempts=choose(old['dataset'],old['reference']['type'],reuse)
        m=base.META[key];fps=m['fps'];a=base.scene(key);tids=[r['target_id'] for r in refs]
        confusion={'gt_id':tids[1],'answer_index':1-winner,'method':'swap_two_identities_that_overlap_before_query_end'} if conf else None
        en,zh,answer,provenance=base.options(['Person A','Person B'],['人物 A','人物 B'],winner,confusion)
        frames={start,end,*[r['frame'] for r in refs]}
        for e in events:frames.update([e['evidence_frames'][0],e['evidence_frames'][0]+1,e['frame']])
        i=a['axis'][tids[0]];vv=a['visible'][i,min(r['frame'] for r in refs)-1:end];edges=np.flatnonzero(np.diff(np.r_[False,~vv,False].astype(int)));gaps=(edges[1::2]-edges[::2])/fps
        detail={'comparison_event':'first_reappearance_after_long_gap',
                'events_by_role':dict(zip('AB',events)),
                'event_frames_by_role':{role:e['frame'] for role,e in zip('AB',events)},
                'event_times_by_role_s':{role:e['time_s'] for role,e in zip('AB',events)},'earlier_role':'AB'[winner]}
        q={'qa_id':old['qa_id']+'_temporal_v2','review_index':old['review_index'],
           'replacement_index':len(replacements)+1,'replaces_qa_id':old['qa_id'],'status':'REPLACEMENT_AWAITING_HUMAN_REVIEW',
           'dataset':key[0],'sequence':key[1],'source_split':m['source_split'],'fps':fps,'video_duration_s':m['frames']/fps,
           'question':f'Between {(start-1)/fps:.3f} and {(end-1)/fps:.3f} s, A and B each become clearly visible again after a visibility gap of more than one second. Comparing their first such returns within this interval, who becomes clearly visible again earlier?',
           'question_zh':f'在 {(start-1)/fps:.3f}–{(end-1)/fps:.3f} 秒内，人物 A 和 B 都发生过持续超过 1 秒的可见性间断。比较两人在该区间中第一次重新清晰可见的时刻，谁更早？',
           'format':'multiple_choice','options':en,'options_zh':zh,'answer':answer,'option_provenance':provenance,
           'reference':{'type':old['reference']['type'],'persons':refs,'target_ids':tids,'t_ref_s':refs[0]['t_ref_s']},
           'operations':['O5'],'operation_name':'O5','split_role':'regular','has_confusion_option':conf,
           'template_id':'O5_first_reappearance_order_camera_revision_v2','identity_risk':False,
           'evidence':{'gt_ids':tids,'target_ids':tids,'role_mapping':{str(t):role for t,role in zip(tids,'AB')},
                       'source_window_1based':m['eligible_source_window_1based'],'query_start_frame':start,'query_end_frame':end,
                       'time_spans_s':[[(start-1)/fps,(end-1)/fps]],'keyframes_1based':sorted(frames),
                       'selected_events':events,'confusion':confusion,'gt_detail':detail},
           'difficulty':{'n_crossings':sum(1 for e in base.OVERLAPS[key] if tids[0] in e['gt_ids'] and e['crossing_status']=='crossed' and e['crossing_eligible_source'] and e['before_frame']>=min(r['frame'] for r in refs) and e['after_frame']<=end),
                         'max_gap_s':float(max(gaps,default=0)),'density':float(a['visible'][:,min(r['frame'] for r in refs)-1:end].sum(axis=0).mean()),
                         'appearance_similarity':None,'appearance_similarity_status':'pending_public_feature_model_before_full_batch',
                         'needs_visual_grounding':old['reference']['type']!='position','camera_motion':m['camera_motion']},
           'license_registry':'logs/licenses.md','source_gt_sha256':m['source_gt_sha256'],'unified_gt_sha256':m['npz_sha256']}
        assert camera_motion_exclusion_reason(q) is None
        for t in tids:reuse[(*key,t)]+=1
        replacements.append(q)
        print(f'GENERATED_REPLACEMENT original#{old["review_index"]} {key} times={detail["event_times_by_role_s"]} attempts={attempts}',flush=True)
    assert len(replacements)==3 and max(reuse.values())<=3
    path=ROOT/'data/question_review_temporal_replacements_3.jsonl'
    path.write_text(''.join(__import__('json').dumps(q,ensure_ascii=False)+'\n' for q in replacements))
    assert all(base.sha(Path(p))==h for p,h in originals.items())
    summary={'generated_at':protocol['recorded_at'],'count':3,'questions':str(path),'questions_sha256':base.sha(path),
             'replacement_for_indices':[q['review_index'] for q in replacements],'operation':'O5 temporal reappearance order',
             'accepted17_unchanged':True,'max_combined_target_identity_reuse':max(reuse.values()),
             'combined20_confusion_coverage':sum(q['has_confusion_option'] for q in accepted+replacements)/20,
             'new_model_calls':0,'new_tracker_runs':0,'full900_completed':False}
    assert summary['combined20_confusion_coverage']>=.7
    base.dump(OUT/'summary.json',summary)
    print(__import__('json').dumps(summary,ensure_ascii=False))


if __name__=='__main__':main()
