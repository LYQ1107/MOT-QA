"""Answer-free tool execution over frozen v1 tracks. No benchmark labels."""
from copy import deepcopy
from functools import lru_cache
import math
import re
import unicodedata
from pathlib import Path

from stage5_common import ROOT, read, sha
from stage5_representations import select, b_main, b_events


def normalized(value):
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().strip().split())


class Tools:
    def __init__(self):
        self.index={(r['video_id'],r['query']):r for r in read(ROOT/'results/v1_track_index.json')}
        self.reps={(r['video_id'],r['query']):r for r in read(ROOT/'results/stage5_representations_locked.json')['files']}
        self.assignments={(r['video_id'],r['query']):r for r in read(ROOT/'results/stage4_D_assignments_locked.json')['assignments']}
        self.names={v:sorted(q for vv,q in self.index if vv==v) for v,q in self.index}

    @lru_cache(maxsize=32)
    def document(self, video, query, shuffled=False):
        row=self.index[video,query]
        doc=read(row['json_path'])
        if not shuffled:return doc
        assignment=self.assignments[video,query]
        if assignment['method']=='different_video_same_exact_phrase':
            return read(self.index[assignment['donor_video_id'],query]['json_path'])
        doc=deepcopy(doc)
        mappings={r['track_id']:r for r in assignment['per_track_permutation']}
        for track in doc['tracks']:
            mapping=mappings[track['track_id']];old=deepcopy(track['observations']);points=[];cursor=0
            for tile_index in mapping['tile_order']:
                tile=mapping['tiles'][tile_index]
                if tile['visible']:
                    for point in old:
                        if tile['start']<=point['frame_id']<tile['start']+tile['length']:
                            point=deepcopy(point);point['frame_id']=cursor+point['frame_id']-tile['start']
                            point['timestamp_seconds']=point['frame_id']/doc['fps'];points.append(point)
                cursor+=tile['length']
            assert cursor==doc['frame_count'] and len(points)==len(old)
            track['observations']=sorted(points,key=lambda p:p['frame_id'])
        return doc

    def execute(self, video, name, arguments, mode='real'):
        record=dict(name=name,arguments=arguments,legal=False,matched=False,images=[],mode=mode)
        if name not in ('track','events','look') or not isinstance(arguments,dict):
            record['text']='invalid tool call: expected track, events, or look and an arguments object'
            return self.finish(record,mode)
        allowed={'track':{'object','t_start','t_end'},'events':{'object'},'look':{'object','time'}}[name]
        required={'object','time'} if name=='look' else {'object'}
        if set(arguments)-allowed or not required<=set(arguments) or not isinstance(arguments.get('object'),str):
            record['text']='invalid tool arguments; use only the documented arguments'
            return self.finish(record,mode)
        for key in ('time','t_start','t_end'):
            x=arguments.get(key)
            if x is not None and (isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x)):
                record['text']='invalid time: expected a finite number in seconds'
                return self.finish(record,mode)
        if name=='look' and arguments.get('time') is None:
            record['text']='invalid time: expected a finite number in seconds';return self.finish(record,mode)
        if arguments.get('t_start') is not None and arguments.get('t_end') is not None and arguments['t_start']>arguments['t_end']:
            record['text']='invalid time range: t_start is later than t_end';return self.finish(record,mode)
        record['legal']=True
        matches=[q for q in self.names[video] if normalized(q)==normalized(arguments['object'])]
        assert len(matches)<=1
        if not matches:
            import json
            record['text']=f'no tracks for {arguments["object"]}; tracked objects in this video: '+json.dumps(self.names[video])
            return self.finish(record,mode)
        query=matches[0];record.update(matched=True,resolved_object=query)
        shuffled=mode=='shuffled';doc=self.document(video,query,shuffled)
        selection=select(doc)
        if name in ('track','events') and not shuffled and all(arguments.get(k) is None for k in ('t_start','t_end')):
            record['text']=Path(self.reps[video,query]['main_path' if name=='track' else 'events_path']).read_text()
        elif name=='events':
            record['text']=b_events(doc,selection)[0]
        elif name=='track':
            start=arguments.get('t_start');end=arguments.get('t_end')
            if start is not None or end is not None:
                selection=dict(selection,points=[p for p in selection['points'] if
                    (start is None or p['timestamp_seconds']>=start) and (end is None or p['timestamp_seconds']<=end)])
            record['text']=b_main(doc,selection)
            if start is not None or end is not None:record['text']+=f'Requested closed time window: {start} to {end} seconds.\n'
        elif mode=='placeholder':
            record['text']='[tool output omitted]'
        else:
            record.update(self.look(video,query,arguments['time'],doc,selection))
        return self.finish(record,mode)

    @staticmethod
    def finish(record,mode):
        if mode=='placeholder':
            record['original_text_sha256']=__import__('hashlib').sha256(record['text'].encode()).hexdigest()
            record['text']='[tool output omitted]';record['images']=[]
        return record

    def look(self,video,query,time,doc,selection):
        import cv2
        from stage4_common import digest
        source=ROOT/'data/toc_bench/videos_5fps'/f'{video}.mp4'
        target=read(self.index[video,query]['json_path'])
        index=min(max(0,int(math.ceil(time*5-.5))),target['frame_count']-1)
        capture=cv2.VideoCapture(str(source));capture.set(cv2.CAP_PROP_POS_FRAMES,index)
        ok,frame=capture.read();capture.release()
        assert ok,f'look decode failed: {source} frame{index}'
        h,w=frame.shape[:2];assert (w,h)==(target['width'],target['height'])
        point=next((p for p in selection['points'] if p['frame_id']==index),None)
        key=digest(dict(video=video,query=query,index=index,document_source=doc['video_id'],point=point))[:24]
        directory=ROOT/'results/stage6/look_images';directory.mkdir(parents=True,exist_ok=True)
        def save(im,kind,limit):
            hh,ww=im.shape[:2]
            if max(hh,ww)>limit:im=cv2.resize(im,(max(1,round(ww*limit/max(hh,ww))),max(1,round(hh*limit/max(hh,ww)))))
            path=directory/f'{key}.{kind}.jpg'
            if not path.exists():assert cv2.imwrite(str(path),im,[cv2.IMWRITE_JPEG_QUALITY,85])
            return dict(path=str(path),sha256=sha(path),kind=kind)
        thumbnail=save(frame,'full_frame',360)
        text=f'look query="{query}"; requested time={time:g}s; nearest 5fps frame={index}; timestamp={index/5:.1f}s.\n'
        images=[]
        if point is None:text+='not detected at this time\n'
        else:
            x1,y1,x2,y2=point['box_xyxy'];x1*=w/doc['width'];x2*=w/doc['width'];y1*=h/doc['height'];y2*=h/doc['height']
            pad_x=.3*(x2-x1);pad_y=.3*(y2-y1)
            left=max(0,math.floor(x1-pad_x));right=min(w,math.ceil(x2+pad_x))
            top=max(0,math.floor(y1-pad_y));bottom=min(h,math.ceil(y2+pad_y))
            assert right>left and bottom>top
            images.append(save(frame[top:bottom,left:right],'subject_crop',720))
            text+=f'subject box=({x1/w:.3f},{y1/h:.3f},{x2/w:.3f},{y2/h:.3f}); crop expands each side by 30% of box width/height.\n'
        images.append(thumbnail)
        text+='Images: '+', '.join(im['kind'] for im in images)+'.'
        return dict(text=text,images=images,frame_index=index,actual_time_seconds=index/5,detected=point is not None)
