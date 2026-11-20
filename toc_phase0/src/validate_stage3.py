"""Numerical-result integrity checks after tracking, serialization and scoring."""
from collections import Counter,defaultdict
import hashlib
import json
import math

from run_stage3_masa import ROOT,now,write_json


def main():
    tasks=json.loads((ROOT/'results/stage3_tracking_tasks.json').read_text())
    sizes={r['video_id']:r for r in json.loads((ROOT/'results/stage3_resampling_receipt.json').read_text())['rows']}
    index=json.loads((ROOT/'results/stage3_track_index.json').read_text())
    index_map={(r['video_id'],r['query']):r for r in index}
    frozen=json.loads((ROOT/'results/stage3_tracker_frozen.json').read_text())
    threshold=frozen['output_score_threshold']
    total_frames=total_instances=filtered_instances=0
    empty=0;label_changes=[];confidences=Counter();physical_gpu_videos=Counter()
    for task in tasks:
        video_id=task['video_id']
        raw=json.loads((ROOT/'tracks/raw'/(video_id+'.json')).read_text())
        physical_gpu_videos[str(raw['physical_gpu']['physical_index'])]+=1
        assert raw['complete'] and raw['video_id']==video_id and raw['queries']==task['queries']
        assert raw['fps']==5 and raw['fp16'] and raw['unified'] and not raw['sam_mask'] and not raw['sam2_or_sam3_used'] and raw['text_cache_reset_per_video']
        assert raw['frame_count']==len(raw['frames'])==sizes[video_id]['frame_count']
        ids=defaultdict(set);expected=Counter()
        for frame_id,frame in enumerate(raw['frames']):
            assert frame['frame_id']==frame_id and abs(frame['timestamp_seconds']-frame_id/5)<1e-8
            seen=set()
            for det in frame['instances']:
                q=det['query_index'];key=(q,det['track_id'])
                assert 0<=q<len(task['queries']) and det['track_id']>=0 and key not in seen
                seen.add(key);ids[det['track_id']].add(q)
                assert all(math.isfinite(v) for v in det['box_xyxy'])
                x1,y1,x2,y2=det['box_xyxy'];assert x1<=x2 and y1<=y2
                assert math.isfinite(det['confidence']) and 0<=det['confidence']<=1
                total_instances+=1
                confidences[str(min(9,int(det['confidence']*10)))]+=1
                if det['confidence']>=threshold:expected[q]+=1
        for tid,labels in ids.items():
            if len(labels)>1:label_changes.append(dict(video_id=video_id,track_id=tid,query_indices=sorted(labels)))
        for q,phrase in enumerate(task['queries']):
            row=index_map[(video_id,phrase)]
            doc=json.loads(open(row['json_path']).read())
            assert doc['query']==phrase and doc['frame_count']==raw['frame_count'] and doc['score_threshold']==threshold
            actual=sum(len(t['observations']) for t in doc['tracks'])
            assert actual==row['observations']==expected[q]
            assert all(p['confidence']>=threshold for t in doc['tracks'] for p in t['observations'])
            assert open(row['text_path']).read().startswith('[Tracking results]')
            filtered_instances+=actual;empty+=not doc['tracks']
        total_frames+=raw['frame_count']
    assert len(tasks)==689 and len(index)==len(index_map)==899
    inputs=[json.loads(s) for s in (ROOT/'results/stage3_visible_inputs.jsonl').read_text().splitlines()]
    predictions=[json.loads(s) for s in (ROOT/'results/stage3_rule_predictions.jsonl').read_text().splitlines()]
    assert len(predictions)==len({r['qa_id'] for r in predictions})==749
    assert {r['qa_id'] for r in predictions}=={r['qa_id'] for r in inputs}
    assert all('metadata' not in r and 'correct_answer' not in r for r in inputs)
    registered=ROOT/'results/trackable_subset_preregistered.json'
    lock=json.loads((ROOT/'logs/trackable_subset_lock.json').read_text())
    digest=hashlib.sha256(registered.read_bytes()).hexdigest()
    assert digest=='4a4d1fdbb57158696986a99130d0a4e2ba27a51c73776c813347829d4b9a2593'
    assert registered.stat().st_mode&0o222==0
    result=dict(status='STAGE3_INTEGRITY_PASSED',checked_at=now(),videos=689,query_pairs=899,
                questions=749,frames=total_frames,raw_observations=total_instances,filtered_observations=filtered_instances,
                empty_video_query_pairs=empty,confidence_decile_counts=dict(confidences),
                native_ids_with_multiple_query_labels=label_changes,
                physical_gpu_video_counts=dict(physical_gpu_videos),
                preregistration_unchanged=True,preregistration_sha256=digest,
                complete_rule_prediction_denominator=True,truth_metadata_in_tracking_or_rule_inputs=False)
    write_json(ROOT/'results/stage3_integrity.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='native_ids_with_multiple_query_labels'},indent=2))


if __name__=='__main__':main()
