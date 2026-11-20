"""Render before/hidden/after native boxes for the source-selected audit cases."""
import json
from pathlib import Path

import cv2
from PIL import Image,ImageDraw,ImageFont

from run_stage3_masa import ROOT,now,write_json
from render_stage3_review import COLORS

FONT=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',16)
CROPS={'perception_test_video_10599':(.06,.25,.37,.85),
       'charades_E184J':(.20,.20,.95,.9),'charades_YJV7W':(0,0,.65,1)}


def panel(cap,raw,index,query_index):
    cap.set(cv2.CAP_PROP_POS_FRAMES,index);ok,frame=cap.read();assert ok
    h,w=frame.shape[:2];roi=CROPS[raw['video_id']]
    x1,y1,x2,y2=[round(v*(w if i%2==0 else h)) for i,v in enumerate(roi)]
    frame=Image.fromarray(cv2.cvtColor(frame[y1:y2,x1:x2],cv2.COLOR_BGR2RGB))
    frame.thumbnail((480,285))
    canvas=Image.new('RGB',(480,325),'#181818');dx=(480-frame.width)//2;dy=32
    canvas.paste(frame,(dx,dy));draw=ImageDraw.Draw(canvas)
    draw.text((5,5),f't={index/5:.1f}s frame {index}',font=FONT,fill='white')
    sx=frame.width/(x2-x1);sy=frame.height/(y2-y1)
    shown=[]
    for det in raw['frames'][index]['instances']:
        if det['query_index']!=query_index or det['confidence']<.2:continue
        a,b,c,d=det['box_xyxy']
        if c<x1 or a>x2 or d<y1 or b>y2:continue
        color=COLORS[det['track_id']%len(COLORS)]
        box=(dx+(a-x1)*sx,dy+(b-y1)*sy,dx+(c-x1)*sx,dy+(d-y1)*sy)
        draw.rectangle(box,outline=color,width=3)
        label=f'ID{det["track_id"]} {det["confidence"]:.2f}'
        xx=max(0,min(350,box[0]));yy=max(32,min(300,box[1]-21))
        draw.rectangle((xx,yy,xx+128,yy+21),fill='#111111');draw.text((xx+1,yy+1),label,font=FONT,fill=color)
        shown.append(dict(track_id=det['track_id'],confidence=det['confidence'],box_xyxy=det['box_xyxy']))
    return canvas,shown


def main():
    cases=json.loads((ROOT/'results/stage3_source_confirmed_occlusion_candidates.json').read_text())['rows']
    directory=ROOT/'results/stage3_visualizations/occlusion_cases';directory.mkdir(parents=True,exist_ok=True)
    data=[];caps={};raws={}
    for page,start in enumerate(range(0,len(cases),4)):
        selected=cases[start:start+4];sheet=Image.new('RGB',(1440,60+len(selected)*365),'#242424');draw=ImageDraw.Draw(sheet)
        draw.text((8,6),'Source-selected occlusions | before / hidden witness / after | native MASA confidence >= 0.2',font=FONT,fill='white')
        for row,event in enumerate(selected):
            vid=event['video_id']
            if vid not in raws:
                raws[vid]=json.loads((ROOT/'tracks/raw'/(vid+'.json')).read_text())
                caps[vid]=cv2.VideoCapture(raws[vid]['tracking_video'])
            raw=raws[vid];query_index=raw['queries'].index(event['query']);top=60+row*365
            draw.text((8,top),f'{event["event_id"]}: {vid}; query={event["query"]}',font=FONT,fill='white')
            frames=[event['before_frame'],(event['verified_hidden_first_frame']+event['verified_hidden_last_frame'])//2,event['after_frame']]
            points=[]
            for col,index in enumerate(frames):
                img,shown=panel(caps[vid],raw,index,query_index);sheet.paste(img,(col*480,top+30))
                points.append(dict(frame_id=index,timestamp_seconds=index/5,detections_intersecting_source_crop=shown))
            data.append(dict(**event,displayed_native_frames=points,visualization=str(directory/f'occlusion_page{page:02d}.jpg')))
        sheet.save(directory/f'occlusion_page{page:02d}.jpg')
    for cap in caps.values():cap.release()
    write_json(ROOT/'results/stage3_occlusion_track_comparison_draft.json',dict(created_at=now(),rows=data,
               warning='boxes are candidates for visual review; intersecting the crop is not sufficient to establish a correct target match'))
    print(json.dumps(dict(cases=len(data),pages=(len(cases)+3)//4,directory=str(directory))))


if __name__=='__main__':main()
