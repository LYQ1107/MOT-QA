"""Draw native query boxes on the fixed source-confirmed dev occlusion windows."""
from collections import defaultdict
import json
import cv2
from PIL import Image,ImageDraw,ImageFont
from run_stage3_masa import ROOT,now,write_json


def main():
    selection=json.loads((ROOT/'results/improvement_dev_source_visual_notes.json').read_text())
    output=ROOT/'results/improvement/dev_memory_visuals';output.mkdir(parents=True,exist_ok=True)
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',17)
    rows=[]
    for event in selection['confirmed_full_occlusion_return_events']:
        video=event['video_id'];query=event['query']
        frames=[event['before_frame'],event['fully_hidden_frames'][0],event['after_frame'],event['after_frame']+1]
        crop=(.15,.15,.5,.8) if '10175' in video else (.1,.35,.6,.95)
        cap=cv2.VideoCapture(str(ROOT/'data/toc_bench/videos_5fps'/(video+'.mp4')))
        source={}
        for frame in frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES,frame);ok,image=cap.read();assert ok
            source[frame]=Image.fromarray(cv2.cvtColor(image,cv2.COLOR_BGR2RGB))
        cap.release();w,h=source[frames[0]].size
        crop_pixels=tuple(round(v*(w if i%2==0 else h)) for i,v in enumerate(crop))
        sheet=Image.new('RGB',(1600,65+3*400),'#202020');draw=ImageDraw.Draw(sheet)
        draw.text((8,5),event['event_id']+' | '+query+' | DEV ONLY, native IDs, score>=0.2',font=font,fill='white')
        comparison=[]
        for row,memory in enumerate((10,25,50)):
            directory=ROOT/'tracks/raw' if memory==10 else ROOT/f'tracks/development/memo{memory}/raw'
            raw=json.loads((directory/(video+'.json')).read_text());q=raw['queries'].index(query)
            birth={}
            for fr in raw['frames']:
                for d in fr['instances']:birth.setdefault(d['track_id'],fr['frame_id'])
            frame_records=[]
            for col,frame in enumerate(frames):
                detections=[d for d in raw['frames'][frame]['instances'] if d['query_index']==q and d['confidence']>=.2]
                picture=source[frame].copy();overlay=ImageDraw.Draw(picture)
                for d in detections:
                    tid=d['track_id'];color=((tid*67+61)%190+65,(tid*43+91)%190+65,(tid*19+31)%190+65)
                    box=tuple(d['box_xyxy']);overlay.rectangle(box,outline=color,width=4)
                    text=f'{tid} {d["confidence"]:.2f}';position=(box[0],max(0,box[1]-20))
                    overlay.text(position,text,fill=color,font=font,stroke_width=1,stroke_fill='black')
                picture=picture.crop(crop_pixels);picture.thumbnail((400,350))
                x=col*400;y=65+row*400
                draw.text((x+5,y+4),f'memo{memory} | f{frame} {frame/5:.1f}s',font=font,fill='white')
                sheet.paste(picture,(x+(400-picture.width)//2,y+30))
                frame_records.append(dict(frame=frame,detections=[dict(**d,first_native_frame=birth[d['track_id']]) for d in detections]))
            comparison.append(dict(memory=memory,frames=frame_records))
        path=output/(event['event_id']+'.jpg');sheet.save(path)
        rows.append(dict(event=event,comparison=comparison,image=str(path)))
    write_json(ROOT/'results/improvement_dev_memory_visual_comparison.json',dict(created_at=now(),scope='dev',rows=rows,
               manual_identity_verdicts_pending=True,answers_or_metadata_read=False))
    print(json.dumps(dict(events=len(rows),images=[r['image'] for r in rows])))


if __name__=='__main__':main()
