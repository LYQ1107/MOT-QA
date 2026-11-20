"""Render annotated source frames for the mandated manual tracking review."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import textwrap

import cv2
from PIL import Image, ImageDraw, ImageFont

from run_stage3_masa import ROOT, now, write_json
from track_facts import query_document, visible_segments

FONT_PATH='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
FONT=ImageFont.truetype(FONT_PATH,17)
SMALL=ImageFont.truetype(FONT_PATH,14)
COLORS=['#00ff66','#ffcc00','#00cfff','#ff77ff','#ff7755','#aaff33','#aabaff','#ffffff']


def tile(cap,raw,index,threshold,width=480,height=310):
    cap.set(cv2.CAP_PROP_POS_FRAMES,index)
    ok,frame=cap.read()
    assert ok,(raw['video_id'],index)
    frame=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
    scale=min(width/frame.width,(height-35)/frame.height)
    frame=frame.resize((round(frame.width*scale),round(frame.height*scale)))
    canvas=Image.new('RGB',(width,height),'#151515')
    x0=(width-frame.width)//2;y0=30
    canvas.paste(frame,(x0,y0))
    draw=ImageDraw.Draw(canvas)
    draw.text((5,4),f'{index/5:.1f}s / frame {index}',font=FONT,fill='white')
    # Grey boxes expose the 0.10--threshold band for threshold inspection.
    instances=sorted(raw['frames'][index]['instances'],key=lambda d:d['confidence'])
    for det in instances:
        if det['confidence']<min(.1,threshold):continue
        kept=det['confidence']>=threshold
        color=COLORS[det['track_id']%len(COLORS)] if kept else '#bbbbbb'
        box=[round(v*scale+(x0 if j%2==0 else y0)) for j,v in enumerate(det['box_xyxy'])]
        draw.rectangle(box,outline=color,width=3 if kept else 1)
        label=f'Q{det["query_index"]} ID{det["track_id"]} {det["confidence"]:.2f}'
        left=max(0,min(width-135,box[0]));top=max(y0,min(height-19,box[1]-18))
        draw.rectangle((left,top,left+135,top+18),fill='#111111')
        draw.text((left+1,top),label,font=SMALL,fill=color)
    return canvas


def board(cap,raw,indices,threshold,path,title):
    cols=4;rows=(len(indices)+cols-1)//cols
    header=[title]+[f'Q{i}: {q}' for i,q in enumerate(raw['queries'])]
    header+=['Solid: confidence >= '+str(threshold)+'; grey: 0.10 to threshold; colors follow original MASA ID.']
    wrapped=[part for line in header for part in textwrap.wrap(line,180)]
    offset=12+24*len(wrapped)
    canvas=Image.new('RGB',(cols*480,offset+rows*310),'#242424')
    draw=ImageDraw.Draw(canvas)
    for i,line in enumerate(wrapped):draw.text((10,6+i*24),line,font=FONT,fill='white')
    for i,index in enumerate(indices):canvas.paste(tile(cap,raw,index,threshold),(i%cols*480,offset+i//cols*310))
    canvas.save(path)


def render(raw,threshold,directory):
    video_id=raw['video_id'];cap=cv2.VideoCapture(raw['tracking_video'])
    n=raw['frame_count']
    indices=sorted({round(i*(n-1)/15) for i in range(16)})
    overview=directory/(video_id+'_overview.jpg')
    board(cap,raw,indices,threshold,overview,video_id+' | uniform temporal overview')
    candidates=[]
    track_summary=[]
    for query_index,query in enumerate(raw['queries']):
        doc=query_document(raw,query_index,threshold)
        points={}
        for track in doc['tracks']:
            for point in track['observations']:
                point=dict(point,track_id=track['track_id'])
                if point['frame_id'] not in points or point['confidence']>points[point['frame_id']]['confidence']:
                    points[point['frame_id']]=point
        segments=visible_segments(list(points.values()))
        for before,after in zip(segments,segments[1:]):
            a,b=before[-1],after[0]
            candidates.append(dict(query_index=query_index,query=query,
                                   before_frame=a['frame_id'],after_frame=b['frame_id'],
                                   before_id=a['track_id'],after_id=b['track_id'],
                                   absence_seconds=b['timestamp_seconds']-a['timestamp_seconds'],
                                   same_id=a['track_id']==b['track_id'],
                                   manual_occlusion_confirmation='unreviewed'))
        track_summary.append(dict(query=query,tracks=len(doc['tracks']),observations=len(points),
                                  visibility_fraction=len(points)/n,
                                  ids=[dict(track_id=t['track_id'],observations=len(t['observations']),
                                            first_s=t['observations'][0]['timestamp_seconds'],last_s=t['observations'][-1]['timestamp_seconds']) for t in doc['tracks']]))
    transitions=[]
    for event_index,event in enumerate(candidates):
        a,b=event['before_frame'],event['after_frame']
        selected=sorted({max(0,a-5),max(0,a-2),a,min(n-1,a+1),round((a+b)/2),max(0,b-1),b,min(n-1,b+2),min(n-1,b+5)})
        while len(selected)%4:selected.append(selected[-1])
        path=directory/f'{video_id}_gap_{event_index:02d}.jpg'
        title=f'{video_id} | Q{event["query_index"]} | candidate gap {a/5:.1f}--{b/5:.1f}s | ID {event["before_id"]} -> {event["after_id"]}'
        board(cap,raw,selected,threshold,path,title)
        transitions.append(dict(event,visualization=str(path)))
    cap.release()
    return dict(video_id=video_id,overview=str(overview),threshold=threshold,
                queries=raw['queries'],track_summary=track_summary,candidate_gaps=transitions)


def main(args):
    selection_document=json.loads((ROOT/args.selection).read_text())
    selection=selection_document['video_ids']
    directory=ROOT/'results/stage3_visualizations'/args.mode;directory.mkdir(parents=True,exist_ok=True)
    rows=[]
    for video_id in selection:
        raw=json.loads((ROOT/'tracks/raw'/(video_id+'.json')).read_text())
        rows.append(render(raw,args.threshold,directory))
    receipt=dict(created_at=now(),mode=args.mode,score_threshold=args.threshold,
                 selection=selection_document['method'],
                 candidate_gaps_are_not_confirmed_occlusions=True,rows=rows)
    write_json(ROOT/f'results/stage3_{args.mode}_visualizations.json',receipt)
    print(json.dumps(dict(videos=len(rows),candidate_gaps=sum(len(r['candidate_gaps']) for r in rows),directory=str(directory))))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--mode',default='pilot');parser.add_argument('--threshold',type=float,default=.2)
    parser.add_argument('--selection',default='results/stage3_pilot_selection.json')
    main(parser.parse_args())
