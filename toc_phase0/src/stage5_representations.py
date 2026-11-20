"""Deterministic facts from the unchanged representative/timeline rule functions."""
from copy import deepcopy

from rule_prediction import representative,timeline,near_edge,PARAMETERS
from track_facts import center
from improvement_facts import serialize_compressed


def select(document):
    points=representative(document)
    if not points:return dict(points=[],base_id=None,native_ids=[],omitted=document['unfiltered_track_count'])
    base=max(document['tracks'],key=lambda t:(sum(p['confidence'] for p in t['observations']),-t['track_id']))
    owners={id(p):track['track_id'] for track in document['tracks'] for p in track['observations']}
    selected=set(owners[id(point)] for point in points)
    native_ids=[track['track_id'] for track in document['tracks'] if track['track_id'] in selected]
    return dict(points=points,base_id=base['track_id'],native_ids=native_ids,omitted=document['unfiltered_track_count']-len(selected))


def b_main(document,selection):
    transformed={k:v for k,v in document.items() if k!='tracks'}
    transformed['tracks']=([dict(track_id=selection['base_id'],observations=selection['points'])] if selection['points'] else [])
    transformed['total_omitted']=selection['omitted']
    text=serialize_compressed(transformed)
    if selection['points']:
        # Geometric stitching is explicit; raw native IDs are never called one identity.
        text+='Note: Representative native track IDs: '+', '.join(map(str,selection['native_ids']))+'; stitched using the frozen geometric rule.\n'
    return text


def b_events(document,selection):
    line=timeline(document)
    segments=line['segments']
    assert [p for segment in segments for p in segment]==selection['points']
    header=f'[Tracking events] query="{document["query"]}"  video_length={document["video_length_seconds"]:.1f}s  tracker_fps=5\n'
    if not segments:
        return header+'No retained observations.\n'+(f'Note: {selection["omitted"]} additional short, low-confidence, or lower-ranked tracks were omitted.\n' if selection['omitted'] else ''),[]
    def pos(point):
        x,y=center(point,document['width'],document['height'])
        return f'({x:.2f}, {y:.2f})'
    events=[]
    first,last=selection['points'][0],selection['points'][-1]
    events.append(dict(type='first_appears',time=first['timestamp_seconds'],text=f'first appears at {first["timestamp_seconds"]:.1f}s at {pos(first)}'))
    for gap in line['gaps']:
        before=gap['before'];x,y=center(before,document['width'],document['height'])
        sides=[label for label,value in [('left',x),('top',y),('right',1-x),('bottom',1-y)] if value<=PARAMETERS['edge_center_margin']]
        assert bool(sides)==near_edge(before,document)
        edge='yes ('+', '.join(sides)+')' if sides else 'no'
        at=before['timestamp_seconds']+.2
        events.append(dict(type='disappears',time=at,last_observation_time=before['timestamp_seconds'],
            edge_sides=sides,terminal=gap['terminal'],text=f'disappears at {at:.1f}s; last position {pos(before)}; within 0.05 of frame edge: {edge}'))
        if gap['after'] is not None:
            after=gap['after']
            events.append(dict(type='reappears',time=after['timestamp_seconds'],text=f'reappears at {after["timestamp_seconds"]:.1f}s at {pos(after)}'))
    events.append(dict(type='last_seen',time=last['timestamp_seconds'],text=f'last seen at {last["timestamp_seconds"]:.1f}s at {pos(last)}'))
    events.sort(key=lambda e:e['time'])
    text=header+'\n'.join(e['text'] for e in events)+'\n'
    text+='Note: Representative native track IDs: '+', '.join(map(str,selection['native_ids']))+'; stitched using the frozen geometric rule.\n'
    if selection['omitted']:text+=f'Note: {selection["omitted"]} additional short, low-confidence, or lower-ranked tracks were omitted.\n'
    assert not any(word in text.lower() for word in ['fully hidden','fully blocked','left the frame','leaves the frame','event count'])
    return text,events


def suspicious_track(track,document):
    flagged=0
    for point in track['observations']:
        x,y=center(point,document['width'],document['height'])
        x1,y1,x2,y2=point['box_xyxy']
        fraction=max(0,x2-x1)*max(0,y2-y1)/(document['width']*document['height'])
        flagged+=abs(x-.5)<=.05 and abs(y-.5)<=.05 and fraction>=.8
    n=len(track['observations'])
    return dict(observations=n,suspicious_observations=flagged,any_suspicious=flagged>0,majority_suspicious=flagged/n>=.5)
