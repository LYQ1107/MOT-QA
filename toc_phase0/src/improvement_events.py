"""Visibility-only proxy events aligned to the public three-fps definitions."""
import math

from rule_prediction import near_edge,representative


def projected_segments(document,points):
    """Two absent samples create a gap; two visible samples confirm a return.

    MASA observations stay at five fps. Rule decisions use a nearest-sample
    three-fps grid, with timestamps on that rule grid. Brief visible blips in
    an already established gap do not confirm reappearance.
    """
    by_frame={p['frame_id']:p for p in points}
    count=math.floor((document['frame_count']-1)*3/5)+1
    indices=[min(document['frame_count']-1,math.floor(j*5/3+0.5)) for j in range(count)]
    samples=[by_frame.get(i) for i in indices]
    runs=[];j=0
    while j<count:
        if samples[j] is None:
            j+=1;continue
        start=j
        while j+1<count and samples[j+1] is not None:j+=1
        runs.append(dict(start=start,end=j,points=samples[start:j+1]))
        j+=1
    if not runs:return dict(segments=[],runs=[],gaps=[],sample_count=count)
    accepted=[dict(runs[0])];gaps=[]
    for run in runs[1:]:
        previous=accepted[-1]
        if run['start']-previous['end']-1<2:
            previous['end']=run['end'];previous['points']+=run['points']
        elif run['end']-run['start']+1>=2:
            gaps.append(dict(before=previous['points'][-1],after=run['points'][0],terminal=False,
                             event_time=(previous['end']+1)/3,return_time=run['start']/3))
            accepted.append(dict(run))
        # A single visible sample after a qualified gap stays unconfirmed.
    last=accepted[-1]
    if count-last['end']-1>=2:
        gaps.append(dict(before=last['points'][-1],after=None,terminal=True,event_time=(last['end']+1)/3))
    return dict(segments=[r['points'] for r in accepted],runs=accepted,gaps=gaps,sample_count=count)


def identity_segments(document,points):
    return projected_segments(document,points)['segments']


def timeline_public(document):
    projected=projected_segments(document,representative(document))
    events={key:[] for key in ('fully_hidden','comes_back_into_view','leaves_frame','disappears',
                               'disappears_for_good','enters_frame','first_shows_up')}
    if projected['runs']:
        first=projected['runs'][0]
        time=first['start']/3
        events['first_shows_up'].append(time)
        if time>0.2 and near_edge(first['points'][0],document):events['enters_frame'].append(time)
    for gap in projected['gaps']:
        events['disappears'].append(gap['event_time'])
        events['leaves_frame' if near_edge(gap['before'],document) else 'fully_hidden'].append(gap['event_time'])
        if gap['terminal']:events['disappears_for_good'].append(gap['event_time'])
        else:
            events['comes_back_into_view'].append(gap['return_time'])
            if near_edge(gap['after'],document):events['enters_frame'].append(gap['return_time'])
    return dict(events=events,segments=projected['segments'],gaps=projected['gaps'])
