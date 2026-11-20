"""Answer-free filtering and raw-fact compression for the development round."""
from copy import deepcopy

from track_facts import serialize


def filter_document(document,parameters):
    result={k:v for k,v in document.items() if k!='tracks'}
    ranked=[];short_weak=0
    for track in document['tracks']:
        points=track['observations']
        duration=len(points)/document['fps']
        confidence=sum(p['confidence'] for p in points)/len(points)
        if duration<parameters['short_seconds'] and confidence<parameters['low_confidence']:
            short_weak+=1
        else:
            ranked.append((confidence*duration,track))
    ranked.sort(key=lambda item:(-item[0],item[1]['track_id']))
    top_k=parameters['top_k'];kept=ranked if top_k is None else ranked[:top_k]
    result.update(tracks=[track for _,track in kept],filter_parameters=parameters,
                  unfiltered_track_count=len(document['tracks']),short_weak_removed=short_weak,
                  rank_omitted=len(ranked)-len(kept),total_omitted=len(document['tracks'])-len(kept))
    return result


def serialize_compressed(document):
    omitted=document.get('total_omitted',0)
    if not document['tracks'] and document.get('unfiltered_track_count',0)>0:
        text=f'[Tracking results] query="{document["query"]}" : no retained detections after the registered filter.\n'
    else:
        text=serialize(document)
    if omitted:
        text+=f'Note: {omitted} additional short, low-confidence, or lower-ranked tracks were omitted.\n'
    return text
