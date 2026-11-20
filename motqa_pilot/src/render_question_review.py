"""Render local review media and a Chinese-first, exportable complete-QA page."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import hashlib
import json
import math
import subprocess
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from generate_question_review import ROOT, OUT, META, scene, read_jsonl, dump, sha

COLORS = [(230,35,35),(25,105,245),(15,155,55),(155,50,215),(235,125,10),(0,160,165),(205,40,135),(110,90,30)]
FONT = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 24)


def source_path(key, frame):
    m=META[key]
    return Path(m['source_gt_path']).parent.parent/'img1'/f'{frame:0{8 if key[0]=="DanceTrack" else 6}d}.jpg'


def annotate(im, key, frame, roles):
    im=im.copy(); d=ImageDraw.Draw(im);m=META[key];a=scene(key)
    for ti,tid in enumerate(a['gt_ids']):
        if not a['visible'][ti,frame-1]:
            continue
        x,y,w,h=map(float,a['boxes_xywh'][ti,frame-1]);role=roles.get(str(int(tid)))
        color=COLORS[(ord(role)-65)%len(COLORS)] if role else (150,150,150)
        d.rectangle([x,y,x+w,y+h],outline=color,width=4 if role else 1)
        if role:
            xx=max(0,int(x)); yy=max(0,int(y)-32)
            d.rectangle([xx,yy,xx+30,yy+31],fill=color)
            d.text((xx+5,yy+1),role,font=FONT,fill='white')
    text=f'{key[1]}  {(frame-1)/m["fps"]:.3f} s'
    d.rectangle([0,0,min(im.width,len(text)*16+16),36],fill='white')
    d.text((8,2),text,font=FONT,fill='black')
    return im


def render_one(q):
    key=(q['dataset'],q['sequence']);m=META[key];a=scene(key)
    folder=OUT/'media'/q['qa_id'];folder.mkdir(parents=True,exist_ok=True)
    refs=[]
    for r in q['reference']['persons']:
        im=Image.open(source_path(key,r['frame'])).convert('RGB')
        if r['type']=='box':
            d=ImageDraw.Draw(im);b=a['boxes_xywh'][a['axis'][r['target_id']],r['frame']-1]
            x,y,w,h=map(float,b);d.rectangle([x,y,x+w,y+h],outline=(255,0,0),width=3)
            formal=ROOT/'data/ref_frames'/f'{q["qa_id"]}_{r["role"]}.jpg'
            formal.parent.mkdir(parents=True,exist_ok=True);im.save(formal,quality=95)
        path=folder/f'reference_{r["role"]}.jpg';im.save(path,quality=95)
        refs.append({'role':r['role'],'type':r['type'],'text_zh':r['text_zh'],'text':r['text'],
                     'time_s':r['t_ref_s'],'image':str(path.relative_to(OUT)),
                     'image_is_question_input':r['type']=='box'})
    keyframes=sorted(set(q['evidence']['keyframes_1based']+[q['evidence']['query_start_frame']]))
    frames=[]
    roles=q['evidence']['role_mapping']
    for frame in keyframes:
        im=Image.open(source_path(key,frame)).convert('RGB')
        annotated=annotate(im,key,frame,roles)
        path=folder/f'frame_{frame:06d}.jpg';annotated.save(path,quality=92)
        frames.append({'frame':frame,'time_s':(frame-1)/m['fps'],'image':str(path.relative_to(OUT))})
    lo=max(m['eligible_source_window_1based'][0],min(r['frame'] for r in q['reference']['persons'])-int(2*m['fps']))
    hi=min(m['eligible_source_window_1based'][1],q['evidence']['query_end_frame']+int(2*m['fps']))
    if q.get('video_input'):
        lo=q['video_input']['source_frame_start_1based']
        hi=q['video_input']['source_frame_end_1based']
    indices=lo+np.floor(np.arange(math.floor((hi-lo)/m['fps']*10)+1)*m['fps']/10).astype(int)
    indices=np.unique(np.r_[indices,hi])
    scale=min(960/m['width'],540/m['height'],1)
    size=(int(m['width']*scale)//2*2,int(m['height']*scale)//2*2)
    paths=[folder/'clip_original.mp4',folder/'clip_gt_audit.mp4']
    logs=[(folder/f'encode_{i}.log').open('w') for i in range(2)]
    procs=[]
    try:
        for path,log in zip(paths,logs):
            cmd=['/usr/bin/ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24',
                 '-s',f'{size[0]}x{size[1]}','-r','10','-i','pipe:0','-an','-c:v','libx264',
                 '-preset','veryfast','-crf','25','-pix_fmt','yuv420p','-threads','1','-movflags','+faststart',str(path)]
            procs.append(subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=log))
        for frame in indices:
            im=Image.open(source_path(key,int(frame))).convert('RGB')
            procs[0].stdin.write(im.resize(size,Image.Resampling.BILINEAR).tobytes())
            procs[1].stdin.write(annotate(im,key,int(frame),roles).resize(size,Image.Resampling.BILINEAR).tobytes())
        for p in procs:
            p.stdin.close()
        for p in procs:
            assert p.wait()==0,f'ffmpeg failed for {q["qa_id"]}; see {folder}'
    finally:
        for p in procs:
            if p.poll() is None:
                p.terminate();p.wait()
        for log in logs:
            log.close()
    for path in paths:
        info=json.loads(subprocess.check_output(['/usr/bin/ffprobe','-v','error','-show_streams','-of','json',str(path)]))
        stream=info['streams'][0]
        assert int(stream['nb_frames'])==len(indices) and stream['codec_name']=='h264'
    return {'qa_id':q['qa_id'],'references':refs,'frames':frames,'raw_clip':str(paths[0].relative_to(OUT)),
            'gt_clip':str(paths[1].relative_to(OUT)),'clip_start_s':(lo-1)/m['fps'],'clip_end_s':(hi-1)/m['fps'],
            'clip_fps':10,'encoded_frame_count':len(indices),'size':size}


def explanation(q):
    e=q['evidence'];g=e['gt_detail'];fps=q['fps'];op=q['operation_name'];lines=[]
    if g.get('comparison_event')=='first_reappearance_after_long_gap':
        for role,event in g['events_by_role'].items():
            lines.append(f'人物 {role}：最后清晰可见于 {(event["evidence_frames"][0]-1)/fps:.3f} 秒；可见性间断 {event["invisible_duration_s"]:.3f} 秒；首次重新清晰可见于 {event["time_s"]:.3f} 秒。')
        lines.append('只比较题目区间内各人的第一次重现，按源帧时间先后判断，不计算移动距离。')
        if q['dataset']=='MOT17':
            lines.append('MOT17沿用已锁定的可见性比例≥0.25约定。低于该阈值不算清晰可见，本题不把它等同于完全消失；只取同一ID在内部遮挡间断后的恢复，不判断出画后是否返回。')
        return lines
    if op=='O1':
        lines.append(f'查询时刻框中心的归一化横坐标为 {g["center_normalized"][0]:.3f}，对应'+['左侧','中间','右侧'][g['region_index']]+'区域。')
    elif op=='O2':
        lines.append('查询时刻各人物框中心横坐标（越小越靠左）：'+ '；'.join(f'{r} = {x:.3f}' for r,x in zip('AB',g['x_centers_normalized'])))
    elif op in ['O5','composition_motion_relation']:
        lines.append('各人物在查询区间的累计可见移动距离（以画面对角线为单位）：'+ '；'.join(f'{r} = {x:.3f}' for r,x in zip('ABCD',g['path_lengths_diagonals'])))
        lines.append('只累计连续可见帧之间的移动，不跨越不可见间断；这里比较画面内移动。')
        if 'x_difference_fraction_at_end' in g:
            lines.append(f'终点时 A 与 B 横坐标差占画面宽度 {g["x_difference_fraction_at_end"]:.3f}；负数表示 A 更靠左。')
    elif op=='O6':
        lines.append(f'两人在画面中距离最近的源帧为第 {g["closest_frame"]} 帧，即 {(g["closest_frame"]-1)/fps:.3f} 秒。')
        lines.append('四个时间段内的最小距离（以画面对角线为单位）：'+ '；'.join(f'第{i+1}段 {x:.3f}' for i,x in enumerate(g['quarter_min_distances_diagonals'])))
    elif op=='O3':
        gap=g['gap'];n=gap['next_visible_frame']
        lines.append(f'最后可见：{(gap["last_visible_frame"]-1)/fps:.3f} 秒；间断持续 {gap["invisible_duration_s"]:.3f} 秒；再次可见：{(n-1)/fps:.3f} 秒。')
        lines.append('判断只针对题目给定的截止时刻；截止后重新出现不算该区间内的“是”。')
    elif op=='O7':
        lines.append(f'题目指定区间内，“间断超过1秒后重新出现”的事件有 {len(g["reappearance_events_in_interval"])} 次；题目预设的第 {g["requested_ordinal"]} 次不存在。')
    else:
        roles=e['role_mapping'];names=[roles[str(t)] for t in g['counted_gt_ids']]
        lines.append(f'满足条件的不同人物共 {g["count"]} 人；核验标记为 '+('、'.join(names) if names else '无')+'。同一个身份只计一次。')
        lines.append('“交错”沿用既定定义：框重叠达到 IoU 0.1 并持续至少3帧，重叠前后两人左右顺序反转。')
        if op=='composition_cross_exit':
            for event in g['exit_events']:
                lines.append(f'{roles[str(event["gt_id"])]} 消失前最后可见于 {(event["last_visible_frame"]-1)/fps:.3f} 秒，框贴近画面边缘；该事件晚于与 A 的交错。')
    return lines


def main():
    questions=read_jsonl(ROOT/'data/question_review_candidates_20.jsonl')
    media={}
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures={executor.submit(render_one,q):q['qa_id'] for q in questions}
        for future in as_completed(futures):
            r=future.result();media[r['qa_id']]=r
            print(f'MEDIA_DONE {r["qa_id"]} {r["encoded_frame_count"]} frames',flush=True)
    qhash=sha(ROOT/'data/question_review_candidates_20.jsonl')
    packet={'schema_version':'motqa_complete_question_review_v1','packet_id':'motqa_fullquestion20_'+qhash[:16],
            'questions_sha256':qhash,'generated_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
            'questions':questions,'media':media,'explanations':{q['qa_id']:explanation(q) for q in questions}}
    dump(OUT/'media_manifest.json',media)
    template=(ROOT/'src/question_review_template.html').read_text()
    html=template.replace('__PAYLOAD__',json.dumps(packet,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c'))
    page=OUT/'打开完整题审阅.html';page.write_text(html)
    instructions=OUT/'使用说明.txt'
    instructions.write_text('MOT-QA 完整推理题中文预审 · 20题\n\n1. 完整解压 ZIP。\n2. 用 Chrome、Edge 或 Firefox 打开“打开完整题审阅.html”，保留同级media文件夹。\n3. 每页1题。先看人物指代、中文问题与选项，可播放原片和GT核验片段、放大关键帧。\n4. 展开GT答案与依据，检查指代是否清楚、答案是否正确、是否确实需要跨帧身份关联。\n5. 标记通过/不通过/不确定并写备注，可随时导出。导出包含全部20题，未选择不会当作通过。\n6. 上传 question_review_result.json。旧的外观复核JSON用于另一份名单，不要导入本页。\n\n本批是20题设计预审，尚未完成约900题整批构建与过滤。问题正式原文为英文，页面优先显示中文。GT标签和答案只用于人工审阅，框标题的红框参考图是题面的一部分。\n')
    bundle=ROOT/'results/motqa_complete_question_review_20_zh_v1.zip'
    with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED) as z:
        z.write(page,'MOTQA_完整题中文审阅20/打开完整题审阅.html')
        z.write(instructions,'MOTQA_完整题中文审阅20/使用说明.txt')
        for path in sorted((OUT/'media').rglob('*')):
            if path.is_file() and path.suffix in ['.jpg','.mp4']:
                z.write(path,'MOTQA_完整题中文审阅20/'+str(path.relative_to(OUT)))
    with zipfile.ZipFile(bundle) as z:
        assert z.testzip() is None
    receipt={'finished_at':packet['generated_at'],'packet_id':packet['packet_id'],'count':20,'page':str(page),
             'html_bytes':page.stat().st_size,'zip':str(bundle),'zip_bytes':bundle.stat().st_size,'zip_sha256':sha(bundle),
             'video_files':sum(len(list((OUT/'media'/q['qa_id']).glob('*.mp4'))) for q in questions),
             'questions_sha256':qhash,'new_tracker_runs':0,'new_model_calls':0,'full900_completed':False}
    dump(OUT/'delivery_receipt.json',receipt)
    print(json.dumps(receipt,ensure_ascii=False))


if __name__=='__main__':
    main()
