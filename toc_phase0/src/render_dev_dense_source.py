"""Dense source-only crops for a bounded set of development visual windows."""
import json
import math
import cv2
from PIL import Image,ImageDraw,ImageFont
from run_stage3_masa import ROOT,now,write_json


def main():
    specifications=[dict(video_id='perception_test_video_7116',query='eggs',crop=[.1,.35,.6,.95],ranges=[[3,5.4],[9,11.4],[13,15.6]]),
                    dict(video_id='perception_test_video_10175',query='blue cup',crop=[.15,.15,.5,.8],ranges=[[2,4.4],[7,10],[11,13.4]])]
    dev=set(json.loads((ROOT/'results/dev_test_split_locked.json').read_text())['dev_video_ids'])
    directory=ROOT/'results/improvement/dev_dense_source';directory.mkdir(parents=True,exist_ok=True)
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',17);rows=[]
    for spec in specifications:
        video=spec['video_id'];assert video in dev
        cap=cv2.VideoCapture(str(ROOT/'data/toc_bench/videos_5fps'/(video+'.mp4')))
        n=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH));height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        x1,y1,x2,y2=[round(v*(width if i%2==0 else height)) for i,v in enumerate(spec['crop'])]
        for window,(start,end) in enumerate(spec['ranges']):
            indices=list(range(round(start*5),min(n-1,round(end*5))+1));pages=[]
            for page,offset in enumerate(range(0,len(indices),12)):
                selected=indices[offset:offset+12];sheet=Image.new('RGB',(1440,65+math.ceil(len(selected)/4)*350),'#202020');draw=ImageDraw.Draw(sheet)
                draw.text((8,6),video+' | DEVELOPMENT SOURCE ONLY | '+spec['query'],font=font,fill='white')
                draw.text((8,30),'5fps; no tracker outputs, answers or metadata read',font=font,fill='white')
                for k,index in enumerate(selected):
                    cap.set(cv2.CAP_PROP_POS_FRAMES,index);ok,frame=cap.read();assert ok
                    img=Image.fromarray(cv2.cvtColor(frame[y1:y2,x1:x2],cv2.COLOR_BGR2RGB));img.thumbnail((360,315))
                    x=k%4*360;y=65+k//4*350
                    draw.text((x+5,y+3),f'{index/5:.1f}s f{index}',font=font,fill='white');sheet.paste(img,(x+(360-img.width)//2,y+28))
                output=directory/f'{video}_window{window:02d}_page{page:02d}.jpg';sheet.save(output);pages.append(str(output))
            rows.append(dict(**spec,window=window,frames=indices,pages=pages))
        cap.release()
    write_json(ROOT/'results/improvement_dev_dense_source_index.json',dict(created_at=now(),scope='dev',tracker_outputs_or_answers_read=False,rows=rows))
    print(json.dumps(dict(windows=len(rows),pages=sum(len(r['pages']) for r in rows))))


if __name__=='__main__':main()
