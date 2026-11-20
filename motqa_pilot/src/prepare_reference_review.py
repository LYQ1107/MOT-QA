"""Build a portable, human-only appearance review packet from existing GT resources."""
from __future__ import annotations

import argparse
import base64
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib
import html
import io
import json
import math
from pathlib import Path
import random
import time
from zoneinfo import ZoneInfo

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps, ImageFont

ROOT = Path('/home/user/motqa_pilot')
OUT = ROOT/'results/review'
SELECTION = OUT/'reference_review_selection_locked.json'
cv2.setNumThreads(1)

GROUP_NAMES = {
    'dance_flagged_vlm': 'DanceTrack：8条标疑模型描述',
    'dance_original_refer': 'DanceTrack：21个原Refer-Dance身份',
    'sports_lamot_stratified': 'SportsMOT：40条视频分层LaMOT抽样',
    'mot17_lamot': 'MOT17：全部68个LaMOT身份',
    'dance_agent_cleared_vlm': '补充：此前17条未见明显疑点的模型描述',
}


def now():
    return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def key(row):
    return row['dataset'], row['sequence'], int(row['target_ids'][0])


def crop(frame, box):
    x, y, w, h = map(float, box)
    # Padding matches the previous appearance supplement; preserve source pixels.
    return frame.crop((max(0, math.floor(x-.05*w)), max(0, math.floor(y-.05*h)),
                       min(frame.width, math.ceil(x+1.05*w)), min(frame.height, math.ceil(y+1.05*h))))


def descriptor(image):
    a = np.asarray(image.resize((64,128), Image.Resampling.LANCZOS))
    hsv = cv2.cvtColor(a, cv2.COLOR_RGB2HSV)
    hist = []
    for strip in np.array_split(hsv, 3, axis=0):
        hs = cv2.calcHist([strip], [0,1], None, [8,4], [0,180,0,256]).ravel()
        val = cv2.calcHist([strip], [2], None, [8], [0,256]).ravel()
        hist.extend(np.sqrt(hs/max(hs.sum(),1)))
        hist.extend(np.sqrt(val/max(val.sum(),1)))
    hist = np.array(hist)
    hist /= max(np.linalg.norm(hist), 1e-12)
    gray = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)
    # This OpenCV 5 build omits objdetect/HOGDescriptor. Compute the declared
    # unsigned gradient-cell histogram directly; no additional model/package.
    gy,gx=np.gradient(gray.astype(np.float64))
    magnitude=np.hypot(gx,gy)
    bins=((np.degrees(np.arctan2(gy,gx))%180)/20).astype(int)
    cells=np.zeros((16,8,9),dtype=np.float64)
    for cy in range(16):
        for cx in range(8):
            ys,xs=slice(cy*8,(cy+1)*8),slice(cx*8,(cx+1)*8)
            cells[cy,cx]=np.bincount(bins[ys,xs].ravel(),weights=magnitude[ys,xs].ravel(),minlength=9)
    blocks=[]
    for cy in range(15):
        for cx in range(7):
            block=cells[cy:cy+2,cx:cx+2].ravel()
            blocks.extend(block/max(np.linalg.norm(block),1e-12))
    hog=np.asarray(blocks)
    hog /= max(np.linalg.norm(hog),1e-12)
    return hist, hog


def quality_arrays(a, ti, meta):
    frames = np.flatnonzero(a['visible'][ti])
    b = a['boxes_xywh'][ti,frames].astype(np.float64)
    area = b[:,2]*b[:,3]
    inside = ((np.minimum(b[:,0]+b[:,2],meta['width'])-np.maximum(b[:,0],0)).clip(0)*
              (np.minimum(b[:,1]+b[:,3],meta['height'])-np.maximum(b[:,1],0)).clip(0))/area
    cover = np.zeros(len(frames))
    count_iou = np.zeros(len(frames), dtype=int)
    for oi in range(len(a['gt_ids'])):
        if oi == ti:
            continue
        ob = a['boxes_xywh'][oi,frames].astype(np.float64)
        intersect = ((np.minimum(b[:,0]+b[:,2],ob[:,0]+ob[:,2])-np.maximum(b[:,0],ob[:,0])).clip(0)*
                     (np.minimum(b[:,1]+b[:,3],ob[:,1]+ob[:,3])-np.maximum(b[:,1],ob[:,1])).clip(0))
        other_present = a['present'][oi,frames]
        frac = np.where(other_present, np.nan_to_num(intersect/area, nan=0), 0)
        cover = np.maximum(cover, frac)
        union = area + ob[:,2]*ob[:,3]-intersect
        iou = np.where(other_present, np.nan_to_num(intersect/union, nan=0), 0)
        count_iou += iou > .3
    q = np.sqrt(area/area.max()) * inside * (1-cover)
    geometric = (inside >= .95) & (cover <= .35) & (b[:,2]>=16) & (b[:,3]>=48)
    future = frames/meta['fps'] <= (meta['frames']-1)/meta['fps']-3
    other_visible = a['visible'][:,frames].sum(axis=0)-1
    return dict(frames=frames, quality=q, inside=inside, cover=cover, iou_count=count_iou,
                geometric=geometric, future=future, other_visible=other_visible)


def select_units():
    refs = [r for r in rows(ROOT/'results/stage2/reference_resources.jsonl') if r['ref_type']=='appearance']
    by_id = defaultdict(list)
    for r in refs:
        by_id[key(r)].append(r)
    rng = random.Random(42)
    units = []

    def original(group, identity):
        rr = sorted(by_id[identity], key=lambda r: (-r['with_future_3s_frames'], -r['reference_frames'], r['ref_id']))
        r = rr[0]
        units.append(dict(group=group, dataset=r['dataset'], sequence=r['sequence'], gt_id=r['target_ids'][0],
                          source_split=r['source_split'], text=r['text'], source_reference_id=r['ref_id'],
                          source_kind='Refer-Dance' if r['dataset']=='DanceTrack' else 'LaMOT',
                          source_paths=r['source_paths'], source_hashes=r['source_hashes'],
                          interval_1based=[r['frame_start'],r['frame_end']],
                          prior_observation='', review_scope='main'))

    dance = sorted(k for k in by_id if k[0]=='DanceTrack')
    mot = sorted(k for k in by_id if k[0]=='MOT17')
    assert len(dance)==21 and len(mot)==68
    # Equal-video stratification: shuffled video order, one shuffled identity per
    # round, no repeated identity. All 29 eligible videos occur before a second draw.
    sports = defaultdict(list)
    for k in sorted(by_id):
        if k[0]=='SportsMOT':
            sports[k[1]].append(k)
    videos = sorted(sports)
    rng.shuffle(videos)
    for seq in videos:
        rng.shuffle(sports[seq])
    sport_selected = []
    while len(sport_selected)<40:
        for seq in videos:
            if sports[seq] and len(sport_selected)<40:
                sport_selected.append(sports[seq].pop())
    assert len(set(sport_selected))==40

    flagged = json.loads((ROOT/'results/stage2_appearance/review_flags.json').read_text())['auto_pass_cases_flagged']
    flag_map = {x['unit_key']:x['observation'] for x in flagged}
    supplement = rows(ROOT/'results/stage2_appearance/reference_resources_supplement.jsonl')
    cleared = rows(ROOT/'results/stage2_appearance/reference_resources_agent_cleared.jsonl')

    def vlm(group, r):
        k = f'{r["sequence"]}__id{r["target_ids"][0]:03d}'
        units.append(dict(group=group, dataset=r['dataset'], sequence=r['sequence'], gt_id=r['target_ids'][0],
                          source_split=r['source_split'], text=r['text'], source_reference_id=r['reference_id'],
                          source_kind='Qwen3-VL-32B generated, same-model validated',
                          source_paths=list(r['raw_paths'].values()),
                          source_hashes=[sha(Path(x)) for x in r['raw_paths'].values()],
                          fixed_frame_1based=r['reference_frame'],
                          prior_observation=flag_map.get(k,r.get('agent_review',{}).get('observation','')),
                          review_scope='additional' if group=='dance_agent_cleared_vlm' else 'main'))

    selected_flags = [r for r in supplement if f'{r["sequence"]}__id{r["target_ids"][0]:03d}' in flag_map]
    assert len(selected_flags)==8
    for r in sorted(selected_flags,key=key):
        vlm('dance_flagged_vlm',r)
    for identity in dance:
        original('dance_original_refer',identity)
    for identity in sport_selected:
        original('sports_lamot_stratified',identity)
    for identity in mot:
        original('mot17_lamot',identity)
    for r in sorted(cleared,key=key):
        vlm('dance_agent_cleared_vlm',r)
    assert len(units)==154
    for i,u in enumerate(units,1):
        ident = f'{u["group"]}|{u["dataset"]}|{u["sequence"]}|{u["gt_id"]}|{u["source_reference_id"]}'
        u['review_id']='refreview_'+hashlib.sha256(ident.encode()).hexdigest()[:16]
        u['index']=i
    return units


def process_sequence(pair):
    meta, units = pair
    with np.load(meta['unified_path']) as data:
        a = {k:data[k] for k in ['gt_ids','boxes_xywh','present','visible']}
    paths = sorted(p for p in (Path(meta['source_gt_path']).parent.parent/'img1').glob('*.jpg')
                   if not p.name.startswith('._'))
    assert len(paths)==meta['frames']
    assert [int(p.stem) for p in paths]==list(range(1,meta['frames']+1))
    win = meta['eligible_source_window_1based']
    results = []
    for u in units:
        ti = int(np.flatnonzero(a['gt_ids']==u['gt_id'])[0])
        q = quality_arrays(a,ti,meta)
        frames = q['frames']
        if 'fixed_frame_1based' in u:
            f = u['fixed_frame_1based']-1
            qi = int(np.flatnonzero(frames==f)[0])
        else:
            lo,hi=u['interval_1based']
            pool=np.flatnonzero((frames>=lo-1)&(frames<=hi-1))
            # Keep every requested identity, including end-of-video references;
            # visibly flag inadequate horizon rather than silently dropping it.
            qi=min(map(int,pool),key=lambda j:(not q['future'][j],not q['geometric'][j],
                  q['other_visible'][j]<2,-q['quality'][j],int(frames[j])))
            f=int(frames[qi])
        assert win[0]-1<=f<=win[1]-1 and a['visible'][ti,f]
        box=a['boxes_xywh'][ti,f]
        folder=OUT/'images'/u['review_id']
        folder.mkdir(parents=True,exist_ok=True)
        with Image.open(paths[f]) as src:
            frame=src.convert('RGB')
        assert frame.size==(meta['width'],meta['height'])
        marked=frame.copy()
        draw=ImageDraw.Draw(marked)
        for oi in np.flatnonzero(a['present'][:,f]):
            if oi==ti:
                continue
            x,y,w,h=map(float,a['boxes_xywh'][oi,f])
            draw.rectangle((x,y,x+w,y+h),outline=(175,175,175),width=1)
        x,y,w,h=map(float,box)
        draw.rectangle((x,y,x+w,y+h),outline=(255,0,0),width=3)
        full=folder/'reference_full.jpg'
        marked.save(full,quality=90)

        # Two other times of this same ID, confined to the provisional source.
        source_pool=[j for j,ff in enumerate(frames) if win[0]-1<=ff<=win[1]-1 and ff!=f]
        chosen=[]
        relaxations=[]
        for fraction in (.20,.80):
            spaced=[j for j in source_pool if abs(int(frames[j])-f)>=.5*meta['fps'] and
                    all(abs(int(frames[j])-int(frames[k]))>=.5*meta['fps'] for k in chosen)]
            pool=spaced or [j for j in source_pool if j not in chosen]
            if not pool:
                break
            if not spaced:
                relaxations.append('0.5s spacing relaxed; distinct frames preserved')
            desired=frames[source_pool[0]]+fraction*(frames[source_pool[-1]]-frames[source_pool[0]])
            chosen.append(min(pool,key=lambda j:(not q['geometric'][j],
                -(q['quality'][j]-.15*abs(int(frames[j])-desired)/max(meta['frames']-1,1)),int(frames[j]))))
        others=[]
        for j in chosen:
            ff=int(frames[j]);path=folder/f'target_other_{len(others)+1}.jpg'
            with Image.open(paths[ff]) as image:
                crop(image.convert('RGB'),a['boxes_xywh'][ti,ff]).save(path,quality=95)
            others.append(dict(frame=ff+1,time_s=ff/meta['fps'],path=str(path),
                               source_frame_path=str(paths[ff]),source_frame_sha256=sha(paths[ff])))
        target_feat=descriptor(crop(frame,box))
        neighbors=[]
        for oi in np.flatnonzero(a['visible'][:,f]):
            if oi==ti:
                continue
            ob=a['boxes_xywh'][oi,f]
            if ob[2]<=0 or ob[3]<=0:
                continue
            tile=crop(frame,ob)
            if not tile.width or not tile.height:
                continue
            feat=descriptor(tile)
            score=.7*float(target_feat[0]@feat[0])+.3*float(target_feat[1]@feat[1])
            neighbors.append((score,int(a['gt_ids'][oi]),oi,tile))
        neighbors.sort(key=lambda x:(-x[0],x[1]))
        near=[]
        for score,tid,oi,tile in neighbors[:2]:
            path=folder/f'similar_person_{len(near)+1}.jpg'
            tile.save(path,quality=95)
            near.append(dict(gt_id=tid,similarity=score,path=str(path),box_xywh=a['boxes_xywh'][oi,f].tolist()))
        unit=dict(u)
        unit.update(dict(t_ref_s=f/meta['fps'],t_ref_display=f'{f/meta["fps"]:.3f}',reference_frame=f+1,
                         fps=meta['fps'],video_frames=meta['frames'],width=meta['width'],height=meta['height'],
                         target_box_xywh=box.tolist(),
                         target_box_xyxy_normalized=[max(0,x)/meta['width'],max(0,y)/meta['height'],
                             min(meta['width'],x+w)/meta['width'],min(meta['height'],y+h)/meta['height']],
                         full_frame=str(full),source_frame_path=str(paths[f]),source_frame_sha256=sha(paths[f]),
                         unified_gt_path=meta['unified_path'],unified_gt_sha256=meta['npz_sha256'],
                         other_target_views=others,similar_people=near,
                         review_frame_quality=dict(in_frame_fraction=float(q['inside'][qi]),
                             max_other_cover_fraction=float(q['cover'][qi]),
                             others_above_iou_point3=int(q['iou_count'][qi]),
                             geometric_gate_pass=bool(q['geometric'][qi]),
                             future_3s=bool(q['future'][qi]),visible_people=int(q['other_visible'][qi])+1),
                         view_spacing_relaxations=relaxations,
                         user_verdict=None,user_note=''))
        assert len({v['frame'] for v in others} | {f+1})==len(others)+1
        unit['available_other_target_views']=len(others)
        unit['total_visible_frames_in_source_window']=len(source_pool)+1
        results.append(unit)
    return results


def render_page(packet):
    template=(ROOT/'src/reference_review_template.html').read_text()
    manifest_sha=sha(SELECTION)
    export_meta=dict(schema_version='motqa_reference_review_v1',packet_id=packet['packet_id'],
                     selection_sha256=manifest_sha,generation_config_sha256=packet['generation_config_sha256'],
                     seed=42,main_count=137,additional_count=17)
    export_cases=[]
    sections=[]
    for group,title in GROUP_NAMES.items():
        cases=[r for r in packet['cases'] if r['group']==group]
        contents=[]
        for r in cases:
            def image_tag(path, caption, klass=''):
                data=base64.b64encode(Path(path).read_bytes()).decode()
                return '<figure class="'+klass+'"><img loading="lazy" src="data:image/jpeg;base64,'+data+'" alt="'+html.escape(caption,quote=True)+'"><figcaption>'+html.escape(caption)+'</figcaption></figure>'
            warning=[]
            if not r['review_frame_quality']['future_3s']:
                warning.append('本时刻之后不足3秒，仅作描述复核，不能直接出题')
            if not r['review_frame_quality']['geometric_gate_pass']:
                warning.append('未达到框标几何门槛，请仔细检查可见细节')
            if len(r['similar_people'])<2:
                warning.append('该帧不足两名其他可见人物；已展示全部可见比较者')
            if len(r['other_target_views'])<2:
                warning.append(f'原始GT在允许窗口内仅{r["total_visible_frames_in_source_window"]}个可见帧，只能提供{len(r["other_target_views"])}张其他时刻图；不复用图片、不换抽样对象')
            snippets=[image_tag(r['full_frame'],'指代整帧：红框为目标，灰框为其他GT人物；无ID文字','full')]
            for i,v in enumerate(r['other_target_views'],1):
                snippets.append(image_tag(v['path'],f'同一目标其他时刻 {i}：{v["time_s"]:.3f} s'))
            for missing in range(len(r['other_target_views']),2):
                snippets.append('<figure><div class="missing-view">原始GT没有更多不同的可见帧</div><figcaption>目标其他时刻 '+str(missing+1)+'：无可用图片</figcaption></figure>')
            for i,v in enumerate(r['similar_people'],1):
                snippets.append(image_tag(v['path'],f'同帧相似人物 {i}（颜色/纹理代理排序）'))
            rid=r['review_id']
            controls=''.join(f'<label class="choice {code}"><input type="radio" name="{rid}" value="{code}">{label}</label>'
                             for code,label in [('pass','通过'),('fail','不通过'),('uncertain','不确定')])
            contents.append('<article class="review-row" id="'+rid+'" data-id="'+rid+'" data-dataset="'+r['dataset']+'" data-scope="'+r['review_scope']+'">'
                '<header><strong>#'+str(r['index'])+' · '+html.escape(r['dataset']+' / '+r['sequence'])+'</strong>'
                '<span class="stamp">t_ref = '+r['t_ref_display']+' s</span></header>'
                '<p class="phrase" lang="en">'+html.escape(r['text'])+'</p>'
                '<p class="source">来源：'+html.escape(r['source_kind'])+'</p>'+
                (''.join('<p class="warning">'+html.escape(w)+'</p>' for w in warning))+
                '<div class="images">'+''.join(snippets)+'</div>'+
                ('<details class="prior"><summary>此前智能体观察（可选查看）</summary><p>'+html.escape(r['prior_observation'])+'</p></details>' if r['prior_observation'] else '')+
                '<div class="verdict">'+controls+'<button class="clear" type="button" data-id="'+rid+'">清除选择</button><span class="row-status">未选择</span></div>'
                '<label class="note-label">备注<textarea rows="2" placeholder="描述是否准确、是否唯一；不通过或不确定的具体原因"></textarea></label></article>')
            export_cases.append({k:r[k] for k in ['review_id','index','group','review_scope','dataset','sequence','source_split',
                                                  'gt_id','text','source_reference_id','source_kind','reference_frame',
                                                  't_ref_s','t_ref_display','review_frame_quality']})
        block='<h2>'+html.escape(title)+' <span class="group-progress" data-group="'+group+'"></span></h2>'+''.join(contents)
        if group=='dance_agent_cleared_vlm':
            block='<details id="additional"><summary>补充区：17条先前智能体未见明显疑点的描述（如需使用，也请逐条复核）</summary>'+block+'</details>'
        sections.append(block)
    js_payload=json.dumps(dict(meta=export_meta,cases=export_cases),ensure_ascii=False).replace('<','\\u003c')
    document=(template.replace('__GENERATED_AT__',html.escape(packet['generated_at']))
              .replace('__SELECTION_SHA__',manifest_sha)
              .replace('__REVIEW_ROWS__',''.join(sections)).replace('__REVIEW_PAYLOAD__',js_payload))
    (OUT/'reference_review.html').write_text(document)
    return manifest_sha


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--render-only',action='store_true')
    args=parser.parse_args()
    started=time.monotonic()
    if args.render_only:
        packet=json.loads(SELECTION.read_text())
    else:
        assert not SELECTION.exists(), 'Selection already locked; use --render-only for presentation fixes.'
        protocol={
            'generated_at':now(),'seed':42,'scope':'appearance human review only, no QA, tracker, learned-model inference or training',
            'main_counts':{'dance_flagged_vlm':8,'dance_original_refer':21,'sports_lamot_stratified':40,'mot17_lamot':68},
            'additional_counts':{'dance_agent_cleared_vlm':17},
            'sports_selection':'all60 original appearance-unique video/ID units grouped across29 videos; seed42 shuffle videos and IDs, round-robin until40; no repeated identity',
            'original_phrase_selection':'per identity choose interval with most future3s frames, then longest unique interval, then stable ref_id',
            'original_tref_selection':'within that exact annotation-unique interval; prefer >=3s remaining, previous geometric thresholds, >=2 others visible, then fixed quality, earliest tie',
            'vlm_tref_selection':'retain the exact previously validated single instant, do not change identity or phrase',
            'quality':'sqrt(area/max-ID-area) * in-frame fraction * (1 - max other-box cover / target area)',
            'geometric_thresholds':{'in_frame_min':.95,'max_cover':.35,'min_width':16,'min_height':48},
            'other_target_views':'two distinct visible frames in the eligible source window, excluding t_ref; quality with mild preference for20%/80% temporal span; prefer0.5s separation, record relaxation',
            'similarity':{'kind':'deterministic CPU color/gradient proxy, not a learned ReID feature or semantic guarantee',
                          'crop_padding_each_side':.05,'resize':[64,128],
                          'HSV':'three horizontal strips, HxS histogram8x4 plus V8; square-root probability then L2 normalize',
                          'HOG':'NumPy central gradients, unsigned hard9-bin orientation, magnitude-weighted8x8 cells,16x16 blocks stride8, per-block then global L2 normalize; 64x128 image',
                          'score':'.7*cos(HSV)+.3*cos(HOG)','pool':'all other GT-visible people in the same original frame; descending score, GT-ID tie break'},
            'render':'full native-resolution frame; target red3px, other GT-present people gray1px; no ID labels; JPEG90; crops JPEG95',
            'source_image_enumeration':'same as Stage1: exclude AppleDouble ._ sidecars; require numeric frames1..N',
            'review_only':'marked gray/red images are for user review, never an appearance-evaluation input',
            'missing_horizon':'keep requested identities and explicitly flag horizon<3s; no silent drop or eligibility claim',
            'insufficient_other_views':'retain selected ID, show available distinct frames plus explicit missing-image placeholder; never duplicate a frame or resample away a difficult identity',
            'no_description_rewrite':True,'default_verdict':None,
            'future_generation_gate':'only explicit user pass for exact reviewed phrase+instant; Sports>=28/40 pass, otherwise globally disable Sports appearance',
            'all_new_outputs_under':str(OUT),
            'generation_config_sha256':sha(ROOT/'results/generation_config_locked.json'),
        }
        write(OUT/'reference_review_protocol_locked.json',protocol)
        units=select_units()
        meta={(r['dataset'],r['sequence']):r for r in json.loads((ROOT/'results/stage2/sequence_metadata.json').read_text())}
        by_seq=defaultdict(list)
        for r in units:
            by_seq[(r['dataset'],r['sequence'])].append(r)
        selected=[]
        with ThreadPoolExecutor(max_workers=4) as pool:
            for output in pool.map(process_sequence,[(meta[k],v) for k,v in sorted(by_seq.items())]):
                selected.extend(output)
        selected.sort(key=lambda x:x['index'])
        assert len(selected)==154 and len({r['review_id'] for r in selected})==154
        identity=hashlib.sha256(json.dumps([(r['review_id'],r['reference_frame'],r['text']) for r in selected],ensure_ascii=False).encode()).hexdigest()
        packet=dict(generated_at=now(),packet_id='motqa_reference_review_'+identity[:20],
                    seed=42,main_count=137,additional_count=17,
                    generation_config_sha256=protocol['generation_config_sha256'],
                    protocol_sha256=sha(OUT/'reference_review_protocol_locked.json'),cases=selected)
        write(SELECTION,packet)
        SELECTION.with_suffix('.sha256').write_text(sha(SELECTION)+'  '+SELECTION.name+'\n')
    selection_sha=render_page(packet)
    cases=packet['cases']
    report={
        'at':now(),'elapsed_s':time.monotonic()-started,'packet_id':packet['packet_id'],
        'main_count':137,'additional_count':17,'total_rows':len(cases),
        'by_group':dict(Counter(r['group'] for r in cases)),
        'sports_videos':len({r['sequence'] for r in cases if r['dataset']=='SportsMOT'}),
        'no_future_3s':[r['review_id'] for r in cases if not r['review_frame_quality']['future_3s']],
        'less_than_two_same_frame_comparators':[r['review_id'] for r in cases if len(r['similar_people'])<2],
        'less_than_two_other_target_views':[r['review_id'] for r in cases if len(r['other_target_views'])<2],
        'geometric_gate_not_met':[r['review_id'] for r in cases if not r['review_frame_quality']['geometric_gate_pass']],
        'selection_sha256':selection_sha,'html_sha256':sha(OUT/'reference_review.html'),
        'html_bytes':(OUT/'reference_review.html').stat().st_size,
        'all_user_verdicts_pending':all(r['user_verdict'] is None for r in cases),
        'qa_generated':0,'model_calls':0,'tracker_runs':0,
    }
    write(OUT/'reference_review_receipt.json',report)
    print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
