"""Check replacement order answers directly against original released GT."""
from collections import Counter
import numpy as np
from audit_question_review_gt import raw
from generate_question_review import ROOT, META, dump, read_jsonl
from question_design_eligibility import camera_motion_exclusion_reason


def main():
    qs=read_jsonl(ROOT/'data/question_review_temporal_replacements_3.jsonl')
    approved={r['review_id']:r for r in read_jsonl(ROOT/'results/review/appearance_reference_pool_user_verified.jsonl')}
    accepted=read_jsonl(ROOT/'data/question_review_user_passed_17.jsonl');checks=[]
    for q in qs:
        key=(q['dataset'],q['sequence']);m=META[key];ids,ix,boxes,visible,centers=raw(key)
        ev=q['evidence'];start=ev['query_start_frame'];end=ev['query_end_frame'];returns={}
        assert m['eligible_source_window_1based'][0]<=min(r['frame'] for r in q['reference']['persons'])<=start<end<=m['eligible_source_window_1based'][1]
        for role,r in zip('AB',q['reference']['persons']):
            tid=r['target_id'];v=visible[ix[tid]];fs=np.flatnonzero(v)
            candidates=[]
            for left,right in zip(fs[:-1],fs[1:]):
                if (right-left-1)/m['fps']>1 and start<=right+1<=end:candidates.append((int(left)+1,int(right)+1))
            assert candidates
            left,right=candidates[0];returns[role]=right
            selected=ev['gt_detail']['events_by_role'][role]
            assert right==selected['frame'] and selected['evidence_frames']==[left,right]
            assert not v[left:right-1].any() and v[left-1] and v[right-1]
            assert start-r['frame']>=3*m['fps'] and v[r['frame']-1]
            if key[0] in ['DanceTrack','MOT17']:
                x,y,w,h=boxes[ix[tid],left-1]
                assert min(x/m['width'],(m['width']-x-w)/m['width'],y/m['height'],(m['height']-y-h)/m['height'])>=.02
            if r['type']=='appearance':
                human=approved[r['review_id']]
                assert (human['dataset'],human['sequence'],human['gt_id'],human['reference_frame'],human['text'])==(*key,tid,r['frame'],r['text'])
            else:
                b=boxes[ix[tid],r['frame']-1];x,y,w,h=b
                inside=max(0,min(x+w,m['width'])-max(x,0))*max(0,min(y+h,m['height'])-max(y,0))/(w*h)
                assert inside>=.95 and w>=16 and h>=48
        earlier=min(returns,key=returns.get)
        assert abs(returns['A']-returns['B'])/m['fps']>=.8
        assert q['options'][q['answer']]=='Person '+earlier
        assert 'path_lengths_diagonals' not in ev['gt_detail'] and camera_motion_exclusion_reason(q) is None
        checks.append({'qa_id':q['qa_id'],'original_index':q['review_index'],'raw_GT_first_return_frames':returns,'earlier_role':earlier,'status':'PASSED'})
    reuse=Counter((q['dataset'],q['sequence'],t) for q in accepted+qs for t in q['reference']['target_ids'])
    assert len(qs)==3 and max(reuse.values())<=3
    dump(ROOT/'results/question_review_replacements/raw_gt_answer_audit.json',{
        'status':'PASSED','verified_questions':3,'method':'derive visible-frame gaps and first-return frame order directly from original GT text; per-dataset visibility convention unchanged','checks':checks})
    print('ORIGINAL_GT_TEMPORAL_ORDER_VERIFIED',len(checks))


if __name__=='__main__':main()
