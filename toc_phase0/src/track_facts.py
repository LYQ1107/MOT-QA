"""Raw trajectory observations, user-specified visibility intervals and text."""
from collections import defaultdict


def center(point, width, height):
    x1,y1,x2,y2=point['box_xyxy']
    return ((x1+x2)/2/width,(y1+y2)/2/height)


def visible_segments(observations, gap_seconds=0.5):
    segments=[]
    for point in sorted(observations,key=lambda p:p['frame_id']):
        if not segments or point['timestamp_seconds']-segments[-1][-1]['timestamp_seconds']>gap_seconds+1e-8:
            segments.append([point])
        else:
            segments[-1].append(point)
    return segments


def query_document(raw, index, threshold):
    tracks=defaultdict(list)
    for frame in raw['frames']:
        for detection in frame['instances']:
            if detection['query_index']==index and detection['confidence']>=threshold:
                tracks[detection['track_id']].append(dict(frame_id=frame['frame_id'],timestamp_seconds=frame['timestamp_seconds'],
                                                        box_xyxy=detection['box_xyxy'],confidence=detection['confidence']))
    return dict(video_id=raw['video_id'],query=raw['queries'][index],fps=5,
                frame_count=raw['frame_count'],video_length_seconds=raw['video_length_seconds'],
                width=raw['width'],height=raw['height'],score_threshold=threshold,
                tracks=[dict(track_id=key,observations=points) for key,points in sorted(tracks.items())])


def serialize(document):
    query=document['query']
    if not document['tracks']:
        return f'[Tracking results] query="{query}" : no detections in the video.\n'
    width,height=document['width'],document['height']
    lines=[f'[Tracking results] query="{query}"  video_length={document["video_length_seconds"]:.1f}s  tracker_fps=5']
    def position(point):
        x,y=center(point,width,height)
        return f'({x:.2f}, {y:.2f})'
    for track in document['tracks']:
        points=track['observations']; segments=visible_segments(points)
        mean=sum(p['confidence'] for p in points)/len(points)
        lines += [f'Track {track["track_id"]} (mean_conf={mean:.2f})',
                  '  visible: '+' | '.join(f'{s[0]["timestamp_seconds"]:.1f}-{s[-1]["timestamp_seconds"]:.1f}s' for s in segments),
                  f'  first_seen: {points[0]["timestamp_seconds"]:.1f}s at {position(points[0])}   last_seen: {points[-1]["timestamp_seconds"]:.1f}s at {position(points[-1])}']
        gaps=[f'{a[-1]["timestamp_seconds"]:.1f}-{b[0]["timestamp_seconds"]:.1f}s (last pos {position(a[-1])})' for a,b in zip(segments,segments[1:])]
        lines.append('  gaps: '+(' | '.join(gaps) if gaps else 'none'))
    lines += ['Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,',
              'and a short low-confidence track may be a false detection or a split of another track.']
    return '\n'.join(lines)+'\n'
