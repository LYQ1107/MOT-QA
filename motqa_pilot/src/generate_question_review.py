"""Generate 20 complete GT-based questions for design review, before the full batch."""
from collections import Counter, defaultdict
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo
import hashlib
import json
import math
import random

import numpy as np

ROOT = Path('/home/user/motqa_pilot')
OUT = ROOT / 'results/question_review'
RNG = random.Random(42)
REGIONS = ['left', 'center', 'right']
REGIONS_ZH = ['左侧', '中间', '右侧']
SPECS = [
    ('DanceTrack', 'box', 'O2'), ('SportsMOT', 'box', 'O2'), ('MOT17', 'box', 'O2'),
    ('DanceTrack', 'box', 'O5'), ('MOT17', 'box', 'O5'), ('SportsMOT', 'box', 'O6'),
    ('DanceTrack', 'box', 'O4'), ('MOT17', 'box', 'composition_motion_relation'),
    ('DanceTrack', 'event', 'O3'), ('DanceTrack', 'event', 'O3'),
    ('SportsMOT', 'event', 'O4'), ('SportsMOT', 'event', 'O7'), ('MOT17', 'event', 'O6'),
    ('DanceTrack', 'appearance', 'O1'), ('SportsMOT', 'appearance', 'O1'),
    ('DanceTrack', 'appearance', 'O6'), ('SportsMOT', 'appearance', 'O5'),
    ('DanceTrack', 'position', 'O7'), ('SportsMOT', 'position', 'O4'),
    ('SportsMOT', 'position', 'composition_cross_exit'),
]


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


META = {(m['dataset'], m['sequence']): m for m in json.loads((ROOT/'results/stage2/sequence_metadata.json').read_text())}
EVENTS, OVERLAPS = defaultdict(list), defaultdict(list)
for e in read_jsonl(ROOT/'results/stage2/point_events.jsonl'):
    if e['eligible_source']:
        EVENTS[(e['dataset'], e['sequence'])].append(e)
for e in read_jsonl(ROOT/'results/stage2/overlap_events.jsonl'):
    if e['eligible_source']:
        OVERLAPS[(e['dataset'], e['sequence'])].append(e)


@lru_cache(maxsize=10)
def scene(key):
    m = META[key]
    with np.load(m['unified_path']) as a:
        a = {k: a[k] for k in ['gt_ids', 'boxes_xywh', 'visible', 'present', 'region', 'visibility']}
    a['centers'] = a['boxes_xywh'][..., :2] + a['boxes_xywh'][..., 2:]/2
    a['axis'] = {int(t): i for i, t in enumerate(a['gt_ids'])}
    return a


def good_box(key, tid, frame):
    m, a = META[key], scene(key)
    i, f = a['axis'][tid], frame-1
    if not a['visible'][i, f]:
        return False
    b = a['boxes_xywh'][i, f].astype(float)
    x, y, w, h = b
    if w < 16 or h < 48:
        return False
    inside = max(0, min(x+w, m['width'])-max(x, 0))*max(0, min(y+h, m['height'])-max(y, 0))/(w*h)
    if inside < .95:
        return False
    ob = a['boxes_xywh'][:, f].astype(float)
    inter = np.maximum(0, np.minimum(b[:2]+b[2:], ob[:, :2]+ob[:, 2:])-np.maximum(b[:2], ob[:, :2])).prod(axis=1)
    inter[~a['present'][:, f]] = 0
    inter[i] = 0
    if np.nanmax(np.nan_to_num(inter/(w*h))) > .35:
        return False
    ious = inter/(w*h+ob[:, 2]*ob[:, 3]-inter)
    return int(np.nansum(ious > .3)) <= 1


def make_ref(key, tid, frame, kind, resource=None):
    m = META[key]
    r = dict(type=kind, target_id=int(tid), frame=int(frame), t_ref_s=(frame-1)/m['fps'])
    if kind == 'box':
        if not good_box(key, tid, frame):
            return None
        r.update(text=f'the person marked with the red box at {r["t_ref_s"]:.3f} s',
                 text_zh=f'{r["t_ref_s"]:.3f} 秒参考帧中红框标出的人', image_insert='after_frames')
    elif kind == 'appearance':
        r.update(text=resource['text'], text_zh=resource['text_zh'], review_id=resource['review_id'])
    elif kind == 'position':
        rank = resource['rank']
        r.update(text=resource['text'], text_zh=f'{r["t_ref_s"]:.3f} 秒时画面中最靠'+('左' if rank=='leftmost' else '右')+'的人')
    else:
        e = resource['event']
        phrase = {'enters_frame': '进入画面', 'leaves_frame': '消失在画面边缘',
                  'becomes_occluded': '从视野中消失', 'reappears': '重新出现'}[e['type']]
        r.update(text=resource['text'], text_zh=f'在 {e["time_s"]:.3f} 秒附近{phrase}的人', event=e)
    if resource:
        r['source_reference_id'] = resource.get('ref_id', resource.get('review_id'))
    b = scene(key)['boxes_xywh'][scene(key)['axis'][tid], frame-1]
    r['box_xyxy_normalized'] = [max(0, float(b[0]))/m['width'], max(0, float(b[1]))/m['height'],
                               min(m['width'], float(b[0]+b[2]))/m['width'], min(m['height'], float(b[1]+b[3]))/m['height']]
    return r


def options(values_en, values_zh, answer, confusion=None):
    order = list(range(len(values_en)))
    RNG.shuffle(order)
    letters = 'ABCDEF'
    return ({letters[j]: values_en[i] for j, i in enumerate(order)},
            {letters[j]: values_zh[i] for j, i in enumerate(order)},
            letters[order.index(answer)],
            {letters[j]: 'correct' if i==answer else 'identity_confusion' if confusion and i==confusion['answer_index'] else 'other'
             for j, i in enumerate(order)})


def partners(key, tid, start, end, crossed=False):
    d = Counter()
    for e in OVERLAPS[key]:
        if tid not in e['gt_ids'] or e['frame_start'] < start or e['frame_end'] > end:
            continue
        if crossed and not (e['crossing_status']=='crossed' and e['crossing_eligible_source'] and e['before_frame']>=start and e['after_frame']<=end):
            continue
        other = next(t for t in e['gt_ids'] if t!=tid)
        d[other] += e['frames']
    return d


def crossing_people(key, tid, start, end):
    return set(partners(key, tid, start, end, True))


def path_length(a, tid, start, end, diag):
    i = a['axis'][tid]
    v = a['visible'][i, start-1:end]
    c = a['centers'][i, start-1:end]
    return float(np.linalg.norm(np.diff(c, axis=0), axis=1)[v[:-1] & v[1:]].sum()/diag)


def facts(key, ref, op, desired_o3=None, require_confusion=False):
    m, a = META[key], scene(key)
    tid, rf, fps = ref['target_id'], ref['frame'], m['fps']
    i = a['axis'][tid]
    high = m['eligible_source_window_1based'][1]
    start = rf + math.ceil(3*fps)
    if start+fps > high:
        return None
    candidates = list(range(start, min(high, rf+int(17*fps))+1, max(1, int(fps))))
    RNG.shuffle(candidates)
    for end in candidates:
        visible_end = [int(t) for t in a['gt_ids'] if a['visible'][a['axis'][int(t)], end-1]]
        overlap_partners = partners(key, tid, rf, end)
        base = dict(query_start_frame=start, query_end_frame=end, target_ids=[tid], refs=[ref],
                    confusion=None, selected_events=[], evidence_frames=[rf, end], identity_risk=False)
        if op == 'O1':
            region = int(a['region'][i, end-1])
            if region < 0:
                continue
            conf = next((t for t, _ in overlap_partners.most_common() if int(a['region'][a['axis'][t], end-1])>=0 and int(a['region'][a['axis'][t], end-1])!=region), None)
            base.update(question=f'Which region of the frame is person A in at {(end-1)/fps:.3f} s?',
                        question_zh=f'在 {(end-1)/fps:.3f} 秒时，人物 A 位于画面的哪个区域？',
                        values_en=REGIONS, values_zh=REGIONS_ZH, answer_index=region,
                        gt_detail={'region_index': region, 'center_normalized': (a['centers'][i,end-1]/[m['width'],m['height']]).tolist()})
            if conf is not None:
                base['confusion']={'gt_id': conf, 'answer_index': int(a['region'][a['axis'][conf],end-1]), 'method':'follow_overlapping_other_identity'}
        elif op in ['O2', 'O5', 'O6', 'composition_motion_relation']:
            others = [t for t in visible_end if t!=tid and a['visible'][a['axis'][t],rf-1] and good_box(key,t,rf)]
            RNG.shuffle(others)
            if op in ['O2', 'composition_motion_relation']:
                others.sort(key=lambda t: -partners(key,tid,rf,end)[t])
            found = None
            for t in others:
                j = a['axis'][t]
                dx = float(a['centers'][i,end-1,0]-a['centers'][j,end-1,0])/m['width']
                if op=='O2':
                    if abs(dx)<.05 or not overlap_partners[t]:
                        continue
                    found = ([tid,t], ['Person A','Person B'], ['人物 A','人物 B'], 0 if dx<0 else 1,
                             {'gt_id':t,'answer_index':1 if dx<0 else 0,'method':'swap_two_overlapping_identities'},
                             {'x_centers_normalized':[float(a['centers'][k,end-1,0]/m['width']) for k in [i,j]]})
                elif op=='O6':
                    blocks=np.array_split(np.arange(start-1,end),4)
                    if any(not np.any(a['visible'][i,b]&a['visible'][j,b]) for b in blocks):
                        continue
                    mins=[float(np.linalg.norm(a['centers'][i,b][a['visible'][i,b]&a['visible'][j,b]]-a['centers'][j,b][a['visible'][i,b]&a['visible'][j,b]],axis=1).min()/math.hypot(m['width'],m['height'])) for b in blocks]
                    answer=int(np.argmin(mins))
                    if sorted(mins)[1]-min(mins)<.005:
                        continue
                    bounds=[[(int(b[0]))/fps,(int(b[-1]))/fps] for b in blocks]
                    en=[f'{lo:.3f}–{hi:.3f} s' for lo,hi in bounds]
                    zh=[f'{lo:.3f}–{hi:.3f} 秒' for lo,hi in bounds]
                    conf=None
                    for other,_ in overlap_partners.most_common():
                        if other==t:
                            continue
                        oi=a['axis'][other]
                        if any(not np.any(a['visible'][oi,b]&a['visible'][j,b]) for b in blocks):
                            continue
                        om=[np.linalg.norm(a['centers'][oi,b][a['visible'][oi,b]&a['visible'][j,b]]-a['centers'][j,b][a['visible'][oi,b]&a['visible'][j,b]],axis=1).min() for b in blocks]
                        if int(np.argmin(om))!=answer:
                            conf={'gt_id':other,'answer_index':int(np.argmin(om)),'method':'replace_person_A_with_overlapping_identity'};break
                    allf=np.concatenate(blocks);v=a['visible'][i,allf]&a['visible'][j,allf];f=allf[v]
                    closest=int(f[np.argmin(np.linalg.norm(a['centers'][i,f]-a['centers'][j,f],axis=1))])+1
                    found=([tid,t],en,zh,answer,conf,{'quarter_min_distances_diagonals':mins,'closest_frame':closest,'time_bin_frames':[[int(b[0])+1,int(b[-1])+1] for b in blocks]})
                elif op=='composition_motion_relation':
                    lengths=[path_length(a,x,start,end,math.hypot(m['width'],m['height'])) for x in [tid,t]]
                    if abs(lengths[0]-lengths[1])<.03 or abs(dx)<.05:
                        continue
                    winner=int(np.argmax(lengths)); left=(dx<0) if winner==0 else (dx>0)
                    answer=winner*2+(0 if left else 1)
                    found=([tid,t],['A travels farther; A is left of B','A travels farther; A is right of B','B travels farther; B is left of A','B travels farther; B is right of A'],
                           ['A 移动更远，且 A 在 B 左侧','A 移动更远，且 A 在 B 右侧','B 移动更远，且 B 在 A 左侧','B 移动更远，且 B 在 A 右侧'],answer,
                           {'gt_id':t,'answer_index':(1-winner)*2+(0 if left else 1),'method':'swap_two_identities'} if overlap_partners[t] else None,
                           {'path_lengths_diagonals':lengths,'x_difference_fraction_at_end':dx})
                else:
                    group=[tid]+others[:3]
                    if len(group)<4:
                        continue
                    lengths=[path_length(a,x,start,end,math.hypot(m['width'],m['height'])) for x in group]
                    winner=int(np.argmax(lengths))
                    if sorted(lengths)[-1]-sorted(lengths)[-2]<.03:
                        continue
                    conf=None
                    for oi, other in enumerate(group):
                        if oi!=winner and partners(key,group[winner],rf,end)[other]:
                            conf={'gt_id':other,'answer_index':oi,'method':'swap_winner_with_overlapping_listed_person','swapped_gt_ids':[group[winner],other]};break
                    found=(group,[f'Person {x}' for x in 'ABCD'],[f'人物 {x}' for x in 'ABCD'],winner,conf,{'path_lengths_diagonals':lengths})
                if found:
                    break
            if not found:
                continue
            group,en,zh,answer,conf,detail=found
            refs=[ref]+[make_ref(key,t,rf,'box') for t in group[1:]]
            if any(r is None for r in refs):
                continue
            if op=='O2':
                q=f'Which person is farther left in the frame at {(end-1)/fps:.3f} s: A or B?'
                qzh=f'在 {(end-1)/fps:.3f} 秒时，人物 A 和 B 中谁更靠画面左侧？'
            elif op=='O5':
                q=f'Between {(start-1)/fps:.3f} and {(end-1)/fps:.3f} s, which person travels the greatest distance within the image?'
                qzh=f'在 {(start-1)/fps:.3f}–{(end-1)/fps:.3f} 秒内，A、B、C、D 中谁在画面内累计移动的距离最大？'
            elif op=='O6':
                q=f'Between {(start-1)/fps:.3f} and {(end-1)/fps:.3f} s, in which time segment are A and B closest in the image?'
                qzh=f'在 {(start-1)/fps:.3f}–{(end-1)/fps:.3f} 秒内，人物 A 和 B 在画面中距离最近的时刻落在哪个时间段？'
            else:
                q=f'Between {(start-1)/fps:.3f} and {(end-1)/fps:.3f} s, which person travels farther in the image, and is that person left or right of the other at the end?'
                qzh=f'在 {(start-1)/fps:.3f}–{(end-1)/fps:.3f} 秒内，A、B 中谁在画面内累计移动更远？在区间终点，这个人位于另一人的左侧还是右侧？'
            base.update(target_ids=group,refs=refs,question=q,question_zh=qzh,values_en=en,values_zh=zh,answer_index=answer,confusion=conf,gt_detail=detail)
            if 'closest_frame' in detail:
                base['evidence_frames'].append(detail['closest_frame'])
        elif op in ['O4','composition_cross_exit']:
            def count_for(t):
                ids=crossing_people(key,t,start,end)
                if op=='composition_cross_exit':
                    ids={x for x in ids if any(e['type']=='leaves_frame' and e['gt_id']==x and start<=e['last_visible_frame']<=end
                         and any(o['crossing_status']=='crossed' and o['crossing_eligible_source'] and set(o['gt_ids'])=={t,x} and start<=o['before_frame']<o['after_frame']<e['last_visible_frame'] for o in OVERLAPS[key]) for e in EVENTS[key])}
                return ids
            ids=count_for(tid);value=min(len(ids),3)
            if not ids:
                continue
            conf=None
            for other,_ in overlap_partners.most_common():
                v=min(len(count_for(other)),3)
                if v!=value:
                    conf={'gt_id':other,'answer_index':v,'method':'count_after_following_overlapping_other_identity'};break
            if op=='O4':
                q=f'How many different people cross paths with A between {(start-1)/fps:.3f} and {(end-1)/fps:.3f} s? Count each person only once.'
                qzh=f'在 {(start-1)/fps:.3f}–{(end-1)/fps:.3f} 秒内，有多少个不同的人与人物 A 发生过交错？同一个人只计一次。'
            else:
                q=f'Among the people who cross paths with A between {(start-1)/fps:.3f} and {(end-1)/fps:.3f} s, how many subsequently leave the frame before the end of that interval? Count each person once.'
                qzh=f'在 {(start-1)/fps:.3f}–{(end-1)/fps:.3f} 秒内，与人物 A 交错过的人中，有多少人在交错之后、该区间结束之前离开画面？每人只计一次。'
            evidence=[e for e in OVERLAPS[key] if e['crossing_status']=='crossed' and e['crossing_eligible_source'] and tid in e['gt_ids'] and e['before_frame']>=start and e['after_frame']<=end]
            base.update(question=q,question_zh=qzh,values_en=['0','1','2','3 or more'],values_zh=['0 人','1 人','2 人','3 人或以上'],
                        answer_index=value,confusion=conf,gt_detail={'count':len(ids),'counted_gt_ids':sorted(ids),'crossing_evidence':evidence},
                        evidence_frames=[rf,end]+[e['after_frame'] for e in evidence[:4]])
            if op=='composition_cross_exit':
                base['gt_detail']['exit_events']=[e for e in EVENTS[key] if e['type']=='leaves_frame' and e['gt_id'] in ids and start<=e['last_visible_frame']<=end]
        elif op=='O3':
            gaps=[e for e in EVENTS[key] if e['gt_id']==tid and e['type']=='becomes_occluded' and e.get('next_visible_frame')
                  and e['last_visible_frame']>=rf and e['frame']<=end and e['next_visible_frame']<=min(high,rf+int(24*fps))]
            selected=None
            for e in gaps:
                answer=e['next_visible_frame']<=end
                if desired_o3 is not None and answer!=desired_o3:
                    continue
                if e['last_visible_frame']>=end:
                    continue
                selected=e;break
            if not selected:
                continue
            answer=int(bool(selected['next_visible_frame']<=end))
            base.update(question=f'A disappears from view around {selected["time_s"]:.3f} s. Does the same person become visible again by {(end-1)/fps:.3f} s?',
                        question_zh=f'人物 A 在 {selected["time_s"]:.3f} 秒附近从视野中消失。到 {(end-1)/fps:.3f} 秒为止，同一个人是否再次清晰可见？',
                        values_en=['No','Yes'],values_zh=['否','是'],answer_index=answer,
                        selected_events=[selected],gt_detail={'gap':selected,'returns_within_question_interval':bool(answer)},
                        evidence_frames=[rf,selected['last_visible_frame'],selected['frame'],end]+([selected['next_visible_frame']] if answer else []))
            for other,_ in overlap_partners.most_common():
                o=[e for e in EVENTS[key] if e['gt_id']==other and e['type']=='becomes_occluded' and abs(e['frame']-selected['frame'])<=fps]
                if o and int(bool(o[0].get('next_visible_frame') and o[0]['next_visible_frame']<=end))!=answer:
                    base['confusion']={'gt_id':other,'answer_index':1-answer,'method':'follow_overlapping_identity_with_other_return_status'};break
        else:
            reappears=[e for e in EVENTS[key] if e['gt_id']==tid and e['type']=='reappears' and start<=e['frame']<=end]
            ordinal=len(reappears)+1
            if ordinal>2:
                continue
            en_ord=['','first','second'][ordinal];zh_ord=['','一','二'][ordinal]
            base.update(question=f'Between {(start-1)/fps:.3f} and {(end-1)/fps:.3f} s, in which region is A when A reappears for the {en_ord} time after an absence of more than one second?',
                        question_zh=f'在 {(start-1)/fps:.3f}–{(end-1)/fps:.3f} 秒内，人物 A 第{zh_ord}次在消失超过 1 秒后重新出现时，位于画面哪个区域？',
                        values_en=REGIONS+['This never happens.'],values_zh=REGIONS_ZH+['这件事没有发生'],answer_index=3,
                        gt_detail={'reappearance_events_in_interval':reappears,'requested_ordinal':ordinal,'event_exists':False})
            for other,_ in overlap_partners.most_common():
                oe=[e for e in EVENTS[key] if e['gt_id']==other and e['type']=='reappears' and start<=e['frame']<=end]
                if len(oe)>=ordinal:
                    rr=int(a['region'][a['axis'][other],oe[ordinal-1]['frame']-1])
                    if rr>=0:
                        base['confusion']={'gt_id':other,'answer_index':rr,'method':'follow_overlapping_identity_with_existing_presupposed_event'};break
        if base.get('question'):
            if require_confusion and base['confusion'] is None:
                continue
            return base
    return None


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    config=ROOT/'results/generation_config_locked.json'
    final_review=ROOT/'results/review/reference_review_result_final.json'
    protocol={'generated_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'status':'LOCKED_FOR_20_QUESTION_DESIGN_REVIEW',
              'scope':'20 newly generated complete questions for user design review; not a random sample from a completed900-question batch.',
              'seed':42,'source_config_sha256':sha(config),'human_review_sha256':sha(final_review),'generator_sha256':sha(Path(__file__)),
              'specs':[{'dataset':d,'reference_type':r,'operation':o} for d,r,o in SPECS],
              'ref_to_question_min_s':3,'query_max_after_reference_s':17,'return_evidence_search_max_s':24,
              'box_geometry':'unchanged frozen box gates','count_bins':[0,1,2,'3 or more'],
              'box_reference_candidates':'existing event/position anchors plus frames3.5seconds before eligible GT crossing episodes or MOT17 overlap episodes; require all frozen box gates',
              'O2_identity_interaction':'require a real overlap between reference and query, as permitted by the original overlap-or-crossing distractor rule; literal question asks left/right at query',
              'time_bins':'four consecutive frame-index quarters of the stated question interval; no overlapping frames',
              'O2_min_x_difference_width_fraction':.05,'O5_min_path_length_winner_margin_diagonals':.03,
              'O6_min_quarter_minimum_distance_margin_diagonals':.005,
              'crossing_definition':'frozen Stage2 IoU>=.1 for>=3frames plus reversed left-right order, with both evidence frames inside interval',
              'path_length':'sum consecutive-visible-frame center displacements; never bridge missing frames',
              'appearance_similarity':'not computed in this design-review batch; public visual feature model still required before full Stage3 release',
              'annotation_video':'10fps review derivative; exact source keyframes also provided; no tracking inference',
              'full_batch_status':'not generated; global answer/dataset balance and confusion coverage acceptance are not claimed for this small design review'}
    protocol['selection_policy']='Prefer candidates with a different GT-derived answer under an overlapping-identity substitution; retain original>=70% confusion coverage requirement.'
    dump(OUT/'protocol.json',protocol)
    resources=read_jsonl(ROOT/'results/stage2/reference_resources.jsonl')
    approved=read_jsonl(ROOT/'results/review/appearance_reference_pool_user_verified.jsonl')
    pools=defaultdict(list)
    for x in resources:
        if x['ref_type']=='appearance' or not x.get('with_future_3s_frames'):
            continue
        key=(x['dataset'],x['sequence']);tid=int(x['target_ids'][0]);frame=x['reference_frame']
        r=make_ref(key,tid,frame,x['ref_type'],x)
        pools[(x['dataset'],x['ref_type'])].append((key,r))
        b=make_ref(key,tid,frame,'box',x)
        if b:
            pools[(x['dataset'],'box')].append((key,b))
    for x in approved:
        key=(x['dataset'],x['sequence'])
        pools[(x['dataset'],'appearance')].append((key,make_ref(key,x['gt_id'],x['reference_frame'],'appearance',x)))
    for key, episodes in OVERLAPS.items():
        m=META[key]
        if not m['eligible_source_window_1based']:
            continue
        for e in episodes:
            if e['before_frame'] is None:
                continue
            if key[0]!='MOT17' and (e['crossing_status']!='crossed' or not e['crossing_eligible_source']):
                continue
            frame=e['before_frame']-math.ceil(3.5*m['fps'])
            if frame<m['eligible_source_window_1based'][0]:
                continue
            for tid in e['gt_ids']:
                b=make_ref(key,tid,frame,'box')
                if b:
                    pools[(key[0],'box')].append((key,b))
    for rows in pools.values():
        RNG.shuffle(rows)
    reuse=Counter();used_refs=set();result=[];attempts=[]
    for number,(dataset,kind,op) in enumerate(SPECS,1):
        found=None;tried=0
        desired=False if number==10 else True if number==9 else None
        for require_confusion in [True,False]:
            for key,ref in pools[(dataset,kind)]:
                identity=(*key,ref['target_id'])
                if reuse[identity]>=3 or (key,ref['target_id'],ref['frame'],kind,op) in used_refs:
                    continue
                tried+=1
                candidate=facts(key,ref,op,desired,require_confusion)
                if not candidate or any(reuse[(*key,t)]>=3 for t in candidate['target_ids']):
                    continue
                found=(key,ref,candidate);break
            if found:
                break
        attempts.append({'index':number,'dataset':dataset,'reference_type':kind,'operation':op,'tried':tried,'found':bool(found)})
        dump(OUT/'generation_progress.json',attempts)
        if found is None:
            raise RuntimeError(f'No valid GT question for specification {number}: {dataset}/{kind}/{op}')
        key,ref,f=found;m=META[key];a=scene(key)
        qid=f'motqa_precheck_{number:02d}'
        for t in f['target_ids']:
            reuse[(*key,t)]+=1
        used_refs.add((key,ref['target_id'],ref['frame'],kind,op))
        oe,oz,answer,provenance=options(f.pop('values_en'),f.pop('values_zh'),f.pop('answer_index'),f['confusion'])
        refs=f.pop('refs')
        for letter,r in zip('ABCD',refs):
            r['role']=letter
        mapping={t:letter for t,letter in zip(f['target_ids'],'ABCD')}
        if op in ['O4','composition_cross_exit']:
            for t in sorted(f['gt_detail']['counted_gt_ids']):
                if t not in mapping:
                    mapping[t]=chr(65+len(mapping))
        fs,fe=f['query_start_frame'],f['query_end_frame'];i=a['axis'][ref['target_id']]
        vv=a['visible'][i,ref['frame']-1:fe];missing=np.flatnonzero(np.diff(np.r_[False,~vv,False].astype(int)))
        gaps=(missing[1::2]-missing[::2])/m['fps']
        question={'qa_id':qid,'review_index':number,'status':'DESIGN_REVIEW_CANDIDATE',
                  'dataset':dataset,'sequence':key[1],'source_split':m['source_split'],'fps':m['fps'],
                  'video_duration_s':m['frames']/m['fps'],'question':f.pop('question'),'question_zh':f.pop('question_zh'),
                  'format':'multiple_choice','options':oe,'options_zh':oz,'answer':answer,'option_provenance':provenance,
                  'reference':{'type':kind,'persons':refs,'target_ids':f['target_ids'],'t_ref_s':ref['t_ref_s']},
                  'operations':{'composition_motion_relation':['O5','O2'],'composition_cross_exit':['O6','O4']}.get(op,[op]),
                  'operation_name':op,'split_role':'held_out_composition' if op.startswith('composition') else 'regular',
                  'has_confusion_option':f['confusion'] is not None,
                  'evidence':{'gt_ids':f['target_ids'],'role_mapping':{str(t):role for t,role in mapping.items()},
                              'source_window_1based':m['eligible_source_window_1based'],'time_spans_s':[[(fs-1)/m['fps'],(fe-1)/m['fps']]],
                              'keyframes_1based':sorted(set(f['evidence_frames'])),**f},
                  'difficulty':{'n_crossings':len([e for e in OVERLAPS[key] if ref['target_id'] in e['gt_ids'] and e['crossing_status']=='crossed' and e['crossing_eligible_source'] and e['before_frame']>=ref['frame'] and e['after_frame']<=fe]),
                                'max_gap_s':float(max(gaps,default=0)),'density':float(a['visible'][:,ref['frame']-1:fe].sum(axis=0).mean()),
                                'appearance_similarity':None,'appearance_similarity_status':'pending_public_feature_model_before_full_batch',
                                'needs_visual_grounding':kind!='position','camera_motion':m['camera_motion']},
                  'template_id':'review_v1_'+op,'identity_risk':False,
                  'license_registry':'logs/licenses.md','source_gt_sha256':m['source_gt_sha256'],'unified_gt_sha256':m['npz_sha256']}
        result.append(question)
        print(f'CREATED {number:02d} {dataset} {kind} {op} {key[1]}',flush=True)
    assert len(result)==20 and max(reuse.values())<=3
    assert Counter(q['reference']['type'] for q in result)==dict(box=8,event=5,appearance=4,position=3)
    assert Counter(q['dataset'] for q in result)==dict(DanceTrack=8,SportsMOT=8,MOT17=4)
    assert all(q['evidence']['query_end_frame']-max(r['frame'] for r in q['reference']['persons'])>=3*q['fps'] for q in result)
    assert all(q['dataset']!='MOT17' or not any(o in ['O3','O4'] for o in q['operations']) for q in result)
    assert sum(q['has_confusion_option'] for q in result)>=14
    path=ROOT/'data/question_review_candidates_20.jsonl'
    path.write_text(''.join(json.dumps(q,ensure_ascii=False)+'\n' for q in result))
    summary={'generated_at':protocol['generated_at'],'scope':protocol['scope'],'count':20,'reference_counts':dict(Counter(q['reference']['type'] for q in result)),
             'dataset_counts':dict(Counter(q['dataset'] for q in result)),'operation_counts':dict(Counter(q['operation_name'] for q in result)),
             'confusion_coverage':sum(q['has_confusion_option'] for q in result)/20,'max_target_identity_reuse':max(reuse.values()),
             'questions':str(path),'questions_sha256':sha(path),'protocol_sha256':sha(OUT/'protocol.json'),
             'full_900_candidate_batch_generated':False,'new_model_calls':0,'new_tracker_runs':0}
    dump(OUT/'summary.json',summary)
    assert sha(config)==protocol['source_config_sha256']
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':
    main()
