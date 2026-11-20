"""Source-only sheets for the fixed development visual sample."""
import json
import math
from pathlib import Path

import cv2
from PIL import Image,ImageDraw,ImageFont

from run_stage3_masa import ROOT,now,write_json


def main():
    selection=json.loads((ROOT/'results/improvement_dev_visual_selection.json').read_text())
    split=json.loads((ROOT/'results/dev_test_split_locked.json').read_text())
    assert set(selection['video_ids'])<=set(split['dev_video_ids'])
    tasks={r['video_id']:r for r in json.loads((ROOT/'results/stage3_tracking_tasks.json').read_text())}
    directory=ROOT/'results/improvement/dev_source';directory.mkdir(parents=True,exist_ok=True)
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',18)
    rows=[]
    for video in selection['video_ids']:
        cap=cv2.VideoCapture(str(ROOT/'data/toc_bench/videos_5fps'/(video+'.mp4')))
        n=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));indices=list(range(0,n,5))
        if indices[-1]!=n-1:indices.append(n-1)
        pages=[]
        for page,start in enumerate(range(0,len(indices),16)):
            chosen=indices[start:start+16];sheet=Image.new('RGB',(1920,100+math.ceil(len(chosen)/4)*330),'#202020')
            draw=ImageDraw.Draw(sheet)
            draw.text((8,8),video+' | DEVELOPMENT SOURCE ONLY | '+', '.join(tasks[video]['queries']),font=font,fill='white')
            draw.text((8,38),'1fps overview; no tracker IDs, answers or metadata read',font=font,fill='white')
            for k,index in enumerate(chosen):
                cap.set(cv2.CAP_PROP_POS_FRAMES,index);ok,frame=cap.read();assert ok
                img=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB));img.thumbnail((480,300))
                x=k%4*480;y=100+k//4*330
                draw.text((x+5,y+3),f'{index/5:.1f}s / frame {index}',font=font,fill='white')
                sheet.paste(img,(x+(480-img.width)//2,y+28))
            path=directory/f'{video}_page{page:02d}.jpg';sheet.save(path);pages.append(str(path))
        cap.release();rows.append(dict(video_id=video,queries=tasks[video]['queries'],frames=n,pages=pages))
    write_json(ROOT/'results/improvement_dev_source_index.json',dict(created_at=now(),scope='dev',answers_or_metadata_read=False,tracker_outputs_read=False,rows=rows))
    print(json.dumps(dict(videos=len(rows),pages=sum(len(r['pages']) for r in rows))))


if __name__=='__main__':main()
