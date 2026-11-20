"""Geometry/visibility rules. Inputs are visible text and trajectories only."""
import math
import re

from stage3_text import classify,event_types,question_subject,required_events
from track_facts import center,visible_segments

PARAMETERS=dict(gap_seconds=0.5,edge_center_margin=0.05,fragment_max_gap_seconds=10.0,
                fragment_max_center_distance=0.25,fragment_max_area_ratio=3.0,event_tie_tolerance_seconds=0.2,
                representative='largest sum of confidence; greedily attach non-overlapping adjacent fragments by geometry',
                unsupported=['partly_hidden','changes_abruptly','other'],
                reid='compare original MASA IDs before/after first observed query-visibility gap; no ID merging for identity decision')


def area(point,width,height):
    x1,y1,x2,y2=point['box_xyxy']
    return max(1e-12,(x2-x1)*(y2-y1)/width/height)


def representative(document):
    tracks=document['tracks'];w,h=document['width'],document['height']
    if not tracks:return []
    base=max(tracks,key=lambda t:(sum(p['confidence'] for p in t['observations']),-t['track_id']))
    chain=list(base['observations']);used={base['track_id']}
    while True:
        candidates=[]
        for t in tracks:
            if t['track_id'] in used:continue
            points=t['observations']
            if points[-1]['frame_id']<chain[0]['frame_id']:left,right=points[-1],chain[0]
            elif points[0]['frame_id']>chain[-1]['frame_id']:left,right=chain[-1],points[0]
            else:continue
            gap=right['timestamp_seconds']-left['timestamp_seconds']
            dist=math.dist(center(left,w,h),center(right,w,h))
            ratio=max(area(left,w,h),area(right,w,h))/min(area(left,w,h),area(right,w,h))
            if gap<=PARAMETERS['fragment_max_gap_seconds'] and dist<=PARAMETERS['fragment_max_center_distance'] and ratio<=PARAMETERS['fragment_max_area_ratio']:
                candidates.append((dist+gap/100,t))
        if not candidates:break
        chosen=min(candidates,key=lambda x:(x[0],x[1]['track_id']))[1];used.add(chosen['track_id'])
        chain=sorted(chain+chosen['observations'],key=lambda p:p['frame_id'])
    return chain


def near_edge(point,document):
    x,y=center(point,document['width'],document['height'])
    return min(x,y,1-x,1-y)<=PARAMETERS['edge_center_margin']


def timeline(document):
    points=representative(document); events={k:[] for k in ('fully_hidden','comes_back_into_view','leaves_frame','disappears','disappears_for_good','enters_frame','first_shows_up')}
    if not points:return dict(events=events,segments=[],gaps=[])
    segments=visible_segments(points,PARAMETERS['gap_seconds']);gaps=[]
    events['first_shows_up'].append(points[0]['timestamp_seconds'])
    if points[0]['timestamp_seconds']>0.2 and near_edge(points[0],document):events['enters_frame'].append(points[0]['timestamp_seconds'])
    for left,right in zip(segments,segments[1:]):
        gaps.append(dict(before=left[-1],after=right[0],terminal=False))
        events['comes_back_into_view'].append(right[0]['timestamp_seconds'])
        if near_edge(right[0],document):events['enters_frame'].append(right[0]['timestamp_seconds'])
    if document['video_length_seconds']-segments[-1][-1]['timestamp_seconds']>PARAMETERS['gap_seconds']:
        gaps.append(dict(before=segments[-1][-1],after=None,terminal=True))
    for gap in gaps:
        time=gap['before']['timestamp_seconds']+0.2
        events['disappears'].append(time)
        events['leaves_frame' if near_edge(gap['before'],document) else 'fully_hidden'].append(time)
        if gap['terminal']:events['disappears_for_good'].append(time)
    return dict(events=events,segments=segments,gaps=gaps)


def predict(item,documents,*,timeline_fn=None,identity_segments_fn=None):
    classification=classify(item)
    if not classification['trackable']:
        return dict(answer=None,covered=False,reason='unsupported event type: '+', '.join(classification['exclusion_reasons']))
    timelines={q:(timeline_fn or timeline)(d) for q,d in documents.items()}
    primary=question_subject(item['question'])
    def abstain(reason):return dict(answer=None,covered=False,reason=reason)
    def result(answer,**extra):return dict(answer=answer,covered=True,reason='rule computed',**extra)
    def first_time(query,kind,text=''):
        if kind=='disappears' and 'for good' in text:kind='disappears_for_good'
        times=timelines.get(query,{}).get('events',{}).get(kind,[])
        return times[0] if times else None
    if item['format']=='numerical':
        kinds=event_types(item['question'])
        if len(kinds)!=1 or primary not in timelines:return abstain('no unique supported subject-predicate')
        count=len(timelines[primary]['events'][kinds[0]])
        return result('5 or more' if count>=5 else str(count),raw_rule_count=count)
    if item['format'].startswith('ordering'):
        times=[]
        for event in item['events']:
            kinds=event_types(event['event_text'])
            t=first_time(primary,kinds[0],event['event_text']) if len(kinds)==1 else None
            if t is None:return abstain('at least one requested event was not observed')
            times.append((t,event['label']))
        times.sort()
        if any(b[0]-a[0]<=PARAMETERS['event_tie_tolerance_seconds']+1e-8 for a,b in zip(times,times[1:])):return abstain('event timestamps tied at 5 fps')
        return result([label for _,label in times],event_times=times)
    statements={letter:item.get('option_'+letter) or item.get('statement_'+letter) for letter in ('A','B')}
    if item['question'].startswith('Which event happens first'):
        by_field={}
        for event in required_events(item):
            if event['field'].endswith('_A') or event['field'].endswith('_B'):
                by_field.setdefault(event['field'][-1],[]).append(event)
        judgments={}
        for letter,events in by_field.items():
            values=[first_time(e['query'],e['event_type'],e['text']) for e in events]
            if any(t is None for t in values):return abstain('a cross-object event was not observed')
            if len(values)==2:
                if abs(values[0]-values[1])<=PARAMETERS['event_tie_tolerance_seconds']+1e-8:return abstain('cross-object event timestamps tied')
                judgments[letter]=values[0]<values[1]
            elif len(values)==1:judgments[letter]=values[0]
            else:return abstain('unsupported cross-object statement structure')
        if all(isinstance(v,bool) for v in judgments.values()):
            true=[k for k,v in judgments.items() if v]
            return result(true[0]) if len(true)==1 else abstain('statements do not have one true temporal relation')
        if set(judgments)=={'A','B'} and abs(judgments['A']-judgments['B'])>PARAMETERS['event_tie_tolerance_seconds']+1e-8:return result(min(judgments,key=judgments.get))
        return abstain('cross-object timing unresolved')
    if primary not in documents:return abstain('target trajectory unavailable')
    if 'same ' in item['question'] or 'same one' in item['question']:
        # Select the highest-confidence query instance per frame. Keep raw IDs.
        points={}
        for track in documents[primary]['tracks']:
            for point in track['observations']:
                p=dict(point,track_id=track['track_id'])
                if p['frame_id'] not in points or p['confidence']>points[p['frame_id']]['confidence']:points[p['frame_id']]=p
        segments=(identity_segments_fn(documents[primary],list(points.values())) if identity_segments_fn
                  else visible_segments(list(points.values()),PARAMETERS['gap_seconds']))
        if len(segments)<2:return abstain('no observed disappearance/reappearance gap')
        same=segments[0][-1]['track_id']==segments[1][0]['track_id']
        match=[l for l,t in statements.items() if ('same one' in t)==same]
        return result(match[0]) if len(match)==1 else abstain('identity statement not recognized')
    if item['question'].startswith(('When ','Before ')):
        gaps=timelines[primary]['gaps']
        if item['question'].startswith('Before '):gaps=[g for g in gaps if not g['terminal']]
        if not gaps:return abstain('no disappearance event observed')
        leaves=near_edge(gaps[0]['before'],documents[primary])
        match=[l for l,t in statements.items() if ('left the frame' in t)==leaves]
        return result(match[0]) if len(match)==1 else abstain('disappearance statement not recognized')
    return abstain('unsupported question structure')
