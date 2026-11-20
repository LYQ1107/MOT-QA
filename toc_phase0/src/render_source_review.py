"""Source-only 1 fps sheets for judging physical occlusion before viewing IDs."""
import json
import math
from pathlib import Path
import textwrap

import cv2
from PIL import Image,ImageDraw,ImageFont

from run_stage3_masa import ROOT,now,write_json
from stage3_text import question_subject


def main():
    selection=json.loads((ROOT/'results/stage3_occlusion_audit_selection.json').read_text())
    directory=ROOT/'results/stage3_visualizations/occlusion_source';directory.mkdir(parents=True,exist_ok=True)
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',18)
    rows=[]
    for item in selection['rows']:
        video_id=item['video_id'];query=question_subject(item['question'])
        path=ROOT/'data/toc_bench/videos_5fps'/(video_id+'.mp4')
        cap=cv2.VideoCapture(str(path));n=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        indices=list(range(0,n,5))
        if indices[-1]!=n-1:indices.append(n-1)
        pages=[]
        for page,start in enumerate(range(0,len(indices),16)):
            selected=indices[start:start+16];nrows=math.ceil(len(selected)/4)
            canvas=Image.new('RGB',(1920,90+nrows*330),'#202020');draw=ImageDraw.Draw(canvas)
            draw.text((10,8),f'{video_id} | source-only review | query: {query}',font=font,fill='white')
            draw.text((10,36),'1 fps overview; no tracker boxes, IDs, metadata or answers',font=font,fill='white')
            for k,index in enumerate(selected):
                cap.set(cv2.CAP_PROP_POS_FRAMES,index);ok,frame=cap.read();assert ok
                img=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
                img.thumbnail((480,300))
                x=k%4*480;y=90+k//4*330
                draw.text((x+5,y+3),f'{index/5:.1f}s / frame {index}',font=font,fill='white')
                canvas.paste(img,(x+(480-img.width)//2,y+28))
            output=directory/f'{video_id}_page{page:02d}.jpg';canvas.save(output);pages.append(str(output))
        cap.release();rows.append(dict(**item,query=query,frame_count=n,source_pages=pages))
        print('SOURCE_REVIEW '+video_id,flush=True)
    write_json(ROOT/'results/stage3_source_visualizations.json',dict(created_at=now(),rows=rows,tracker_results_read=False,metadata_or_answers_read=False))


if __name__=='__main__':main()
