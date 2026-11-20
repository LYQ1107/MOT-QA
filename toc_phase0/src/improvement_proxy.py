"""Fixed development reacquisition windows, not ground-truth occlusion labels."""
import argparse
from collections import defaultdict
import json
import math

from rule_prediction import area,near_edge,representative
from run_stage3_masa import ROOT,now,write_json
from track_facts import center,query_document,visible_segments


def registry():
    path=ROOT/'results/improvement_dev_reacquisition_windows.json'
    if path.exists():return json.loads(path.read_text())
    split=json.loads((ROOT/'results/dev_test_split_locked.json').read_text())
    rows=[]
    for video in split['dev_video_ids']:
        raw=json.loads((ROOT/'tracks/raw'/(video+'.json')).read_text())
        for q,query in enumerate(raw['queries']):
            doc=query_document(raw,q,.2);segments=visible_segments(representative(doc))
            for before,after in zip(segments,segments[1:]):
                a,b=before[-1],after[0];hidden_frames=b['frame_id']-a['frame_id']-1
                if hidden_frames<4 or b['timestamp_seconds']-a['timestamp_seconds']>10:continue
                if len(before)<4 or len(after)<4:continue
                if any(y['frame_id']-x['frame_id']!=1 for x,y in zip(before[-4:],before[-3:])):continue
                if any(y['frame_id']-x['frame_id']!=1 for x,y in zip(after[:3],after[1:4])):continue
                if near_edge(a,doc) or near_edge(b,doc):continue
                if math.dist(center(a,doc['width'],doc['height']),center(b,doc['width'],doc['height']))>.25:continue
                ratio=area(a,doc['width'],doc['height'])/area(b,doc['width'],doc['height'])
                if not 1/3<=ratio<=3:continue
                rows.append(dict(case_id=f'{video}_q{q}_f{a["frame_id"]}_{b["frame_id"]}',video_id=video,query=query,
                                 before_frame=a['frame_id'],after_frame=b['frame_id'],before_box=a['box_xyxy'],after_box=b['box_xyxy']))
    result=dict(created_at=now(),scope='dev',source_memory=10,answers_read=False,
                definition='fixed geometry-qualified visibility/reacquisition windows from accepted memo10 development outputs; physical occlusion is not independently established',
                parameters=dict(score_threshold=.2,min_hidden_5fps_frames=4,max_gap_seconds=10,
                                min_consecutive_visible_before_and_after=4,max_center_distance=.25,max_area_ratio=3,edge_margin=.05,match_iou=.3),
                selection_proxy='(fresh IDs plus unjudgeable windows)/all fixed windows; missing matches are not counted as preserved identity',rows=rows)
    with path.open('x') as stream:json.dump(result,stream,ensure_ascii=False,indent=2);stream.write('\n')
    path.chmod(0o444)
    return result


def iou(a,b):
    overlap=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    aa=max(0,a[2]-a[0])*max(0,a[3]-a[1]);bb=max(0,b[2]-b[0])*max(0,b[3]-b[1])
    return overlap/(aa+bb-overlap) if aa+bb>overlap else 0


def evaluate(memory):
    registered=registry();split=json.loads((ROOT/'results/dev_test_split_locked.json').read_text())
    windows=defaultdict(list)
    for row in registered['rows']:windows[row['video_id']].append(row)
    rows=[];track_counts=[];coverage=[];label_changes=0
    for video in split['dev_video_ids']:
        directory=ROOT/'tracks/raw' if memory==10 else ROOT/f'tracks/development/memo{memory}/raw'
        raw=json.loads((directory/(video+'.json')).read_text())
        first={};labels=defaultdict(set)
        for frame in raw['frames']:
            for det in frame['instances']:
                first.setdefault(det['track_id'],frame['frame_id'])
                if det['confidence']>=.2:labels[det['track_id']].add(det['query_index'])
        label_changes+=sum(len(v)>1 for v in labels.values())
        for q,query in enumerate(raw['queries']):
            doc=query_document(raw,q,.2);track_counts.append(len(doc['tracks']))
            seen={p['frame_id'] for track in doc['tracks'] for p in track['observations']}
            coverage.append(len(seen)/raw['frame_count'])
        for window in windows[video]:
            q=raw['queries'].index(window['query']);matches=[]
            for side in ('before','after'):
                candidates=[d for d in raw['frames'][window[side+'_frame']]['instances'] if d['query_index']==q and d['confidence']>=.2 and iou(d['box_xyxy'],window[side+'_box'])>=.3]
                matches.append(max(candidates,key=lambda d:(iou(d['box_xyxy'],window[side+'_box']),d['confidence'],-d['track_id'])) if candidates else None)
            a,b=matches;judgeable=a is not None and b is not None
            rows.append(dict(**window,judgeable=judgeable,before_id=a['track_id'] if a else None,after_id=b['track_id'] if b else None,
                             different_id=judgeable and a['track_id']!=b['track_id'],
                             fresh_after_id=judgeable and a['track_id']!=b['track_id'] and first[b['track_id']]>=window['after_frame']))
    judged=[r for r in rows if r['judgeable']];fresh=sum(r['fresh_after_id'] for r in rows)
    result=dict(generated_at=now(),scope='dev',memory=memory,fixed_windows=len(rows),judgeable=len(judged),unjudgeable=len(rows)-len(judged),
                fresh_ids=fresh,fresh_id_ratio=fresh/len(judged) if judged else None,
                different_ids=sum(r['different_id'] for r in rows),selection_proxy=(fresh+len(rows)-len(judged))/len(rows) if rows else 1.0,
                mean_tracks_per_query=sum(track_counts)/len(track_counts),mean_query_frame_coverage=sum(coverage)/len(coverage),
                multi_query_label_native_ids_at_0_2=label_changes,physical_occlusion_ground_truth=False,test_videos_read=False,rows=rows)
    write_json(ROOT/f'results/improvement/dev/memo{memory}_proxy.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--register',action='store_true');parser.add_argument('--memory',type=int)
    args=parser.parse_args()
    if args.register:
        data=registry();print(json.dumps(dict(fixed_development_windows=len(data['rows']),scope='dev')))
    else:evaluate(args.memory)
