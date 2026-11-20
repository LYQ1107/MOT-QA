"""A focused Chinese review of repaired questions, with the real32-frame input."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
import hashlib
import json
import random
import shutil
import zipfile

from PIL import Image, ImageDraw, ImageFont

import generate_candidates_round2 as g
import readability_v3 as v
import render_question_review as renderer

OUT = v.D/'review'
REASONS = {
    'negative_question_has_actual_return_including_short_gap': '旧题有短暂间断，宽泛地回答“没有发生”存在歧义',
    'gap_under_readability_2s': '旧题的关键间断较短',
    'visible_run_around_gap_under_0_6s': '消失前或重现后缺少稳定可见画面',
    '32_frames_do_not_resolve_gap_context': '32帧输入不足以清楚观察间断前后状态',
    'event_reference_no_clear_wide_anchor': '事件指代找不到足够清楚的参考帧',
    'event_reference_visible_run_too_short': '事件指代可观察上下文太短',
    'event_reference_insufficient_start_context': '指代事件紧贴片头',
    'reanchored_reference_too_close_to_question': '清楚的参考帧距提问时刻太近',
    'original_hard_rule:unknown_crossing_cannot_determine_count_or_absence': '旧题涉及不能确定交错状态的片段',
    'numeric_time_sampling_interval_over_1s': '旧题的采样间隔不足以支持时间精度',
    'specific_user_concern_requires_replacement': '用户已指出可辨认性疑点',
}


def pick(qs, audit):
    chosen = []
    byslot = {q['previous_slot_qa_id']: q for q in qs}
    for qid in ['motqa_pilot_r2_0225', 'motqa_pilot_r2_0229', 'motqa_pilot_r2_0777']:
        chosen.append(byslot[qid])
    rng = random.Random(42)
    # Purposeful diagnostic coverage, not a sample used to estimate a pass rate.
    pools = [
        [q for q in qs if q['template_id'] == 'return_region' and q['semantic_answer'] == g.NEVER],
        [q for q in qs if q['template_id'] == 'return_region' and q['semantic_answer'] != g.NEVER],
        [q for q in qs if q['template_id'] == 'return_time' and q['format'] == 'numeric_time'],
        [q for q in qs if q['template_id'] == 'earlier_return_time'],
        [q for q in qs if q['reference']['type'] == 'event' and q['dataset'] == 'SportsMOT'],
        [q for q in qs if q['reference']['type'] == 'event' and q['dataset'] == 'DanceTrack'],
        [q for q in qs if q.get('option_modality') == 'image'],
        [q for q in qs if q['template_id'] in ['cross_time', 'cross_frequency']],
        [q for q in qs if q['operation_name'] == 'O8'],
    ]
    for pool in pools:
        selected_identities = {(q['dataset'], q['sequence'], q['reference']['primary_target_id']) for q in chosen}
        pool = [q for q in pool if q not in chosen and not q.get('preserve_reviewed_question')
                and (q['dataset'], q['sequence'], q['reference']['primary_target_id']) not in selected_identities]
        pool.sort(key=lambda q: (q['replaces_qa_id'] is None,
                                q['previous_qa_id'] is not None, q['qa_id']))
        if pool:
            top = [q for q in pool if (q['replaces_qa_id'] is None, q['previous_qa_id'] is not None)
                   == (pool[0]['replaces_qa_id'] is None, pool[0]['previous_qa_id'] is not None)]
            chosen.append(rng.choice(top))
    assert len(chosen) == len({q['qa_id'] for q in chosen}) == 12
    return copy.deepcopy(chosen)


def render_one(q):
    lo, hi = q['video_input']['source_frame_start_1based'], q['video_input']['source_frame_end_1based']
    extras = []
    for z in q['readability_v3']['gap_checks']:
        extras.extend([z['last'], z['first_missing'],
                       (z['first_missing']+z['missing_end'])//2, z['return']])
    q['evidence']['keyframes_1based'] = sorted({f for f in q['evidence']['keyframes_1based']+extras if lo <= f <= hi})
    roles = q['evidence']['role_mapping']
    d = q['evidence']['gt_detail']
    for tid in d.get('counted_gt_ids', [])+d.get('candidate_gt_ids', []):
        if str(tid) not in roles:
            roles[str(tid)] = chr(65+len(roles))
    if d.get('marked_query_target') is not None and str(d['marked_query_target']) not in roles:
        roles[str(d['marked_query_target'])] = chr(65+len(roles))
    media = renderer.render_one(q)
    folder = OUT/'media'/q['qa_id']
    frames = []
    sheet = Image.new('RGB', (1920, 880), 'white')
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 17)
    for i, (frame, ts) in enumerate(zip(q['video_input']['sample_frame_indices_1based'], q['video_input']['sample_timestamps_s'])):
        im = Image.open(renderer.source_path((q['dataset'], q['sequence']), frame)).convert('RGB')
        im.thumbnail((720, 480))
        path = folder/f'input32_{i+1:02d}.jpg'
        im.save(path, quality=90)
        tile = Image.new('RGB', (240, 220), 'white')
        ImageDraw.Draw(tile).text((7, 3), f'#{i+1:02d}  {ts:.3f}s', font=font, fill='black')
        small = im.copy()
        small.thumbnail((238, 190))
        tile.paste(small, ((240-small.width)//2, 28))
        sheet.paste(tile, ((i%8)*240, (i//8)*220))
        frames.append({'time_s': ts, 'image': str(path.relative_to(OUT))})
    sheet.save(folder/'actual32_overview.jpg', quality=92)
    media['actual32'] = frames
    media['actual32_overview'] = str((folder/'actual32_overview.jpg').relative_to(OUT))
    for p in q['reference']['persons']:
        for field in ['image', 'zoom_crop']:
            src = g.Path(p[field])
            dst = folder/('formal_'+src.name)
            shutil.copyfile(src, dst)
            p[field] = str(dst.relative_to(OUT))
    for field in ['query_image', 'query_zoom_crop']:
        if q.get(field):
            src = g.Path(q[field]); dst = folder/('formal_'+src.name)
            shutil.copyfile(src, dst); q[field] = str(dst.relative_to(OUT))
    if q.get('option_images'):
        for key, src in list(q['option_images'].items()):
            src = g.Path(src); dst = folder/('formal_'+src.name)
            shutil.copyfile(src, dst); q['option_images'][key] = str(dst.relative_to(OUT))
    q['media'] = media
    return q


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    renderer.OUT = OUT
    audit = json.loads((v.D/'raw_gt_and_readability_audit.json').read_text())
    assert audit['status'] == 'PASSED'
    qs = g.rows(g.ROOT/'data/candidates_readability_v3.jsonl')
    old = {q['qa_id']: q for q in g.rows(v.D/'before_revision/candidates_round2_original.jsonl')}
    cases = {r['qa_id']: r for r in json.loads((v.D/'all900_before_revision_audit.json').read_text())['checks']}
    picked = pick(qs, audit)
    g.putrows(v.D/'supplementary_review12.jsonl', picked)
    for q in picked:
        prior = old[q['previous_slot_qa_id']]
        issues = cases[prior['qa_id']]['after_reference_repair']['issues']
        q['change_reasons_zh'] = [REASONS.get(x, x) for x in issues]
        if not q['change_reasons_zh']:
            q['change_reasons_zh'] = ['补充检查本轮修订后的同类题目与清楚的指代']
        q['old_version'] = {'qa_id': prior['qa_id'], 'question_zh': prior['question_zh'],
                            'dataset': prior['dataset'], 'sequence': prior['sequence'],
                            'reference_texts_zh': [p['text_zh'] for p in prior['reference']['persons']]}
    payload = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(render_one, q): q for q in picked}
        for future in as_completed(futures):
            q = future.result(); payload.append(q)
            print('REVIEW_RENDERED', q['qa_id'], flush=True)
    order = {q['qa_id']: i for i, q in enumerate(picked)}
    payload.sort(key=lambda q: order[q['qa_id']])
    packet_id = 'motqa_readability_v3_12_'+hashlib.sha256(json.dumps([q['qa_id'] for q in picked]).encode()).hexdigest()[:16]
    packet = {'packet_id': packet_id, 'count': len(payload), 'questions': payload}
    page = OUT/'打开中文补审12题.html'
    page.write_text(HTML.replace('__PACKET__', json.dumps(packet, ensure_ascii=False).replace('</', '<\\/')))
    (OUT/'使用说明.txt').write_text('完整解压后，用Chrome、Edge或Firefox打开“打开中文补审12题.html”。审核当前修订后的题目；旧版折叠供对照。第1–3题对应此前0225、0229和0777的替换题，其余覆盖相关修订。可查看原片、GT核验片段、实际32帧、参考帧和放大裁剪。请导出stage3_readability_v3_review_result.json。这是有目的的补审，不用于估算全库通过率。\n')
    zip_path = g.ROOT/'results/motqa_readability_v3_review12_zh.zip'
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=3) as z:
        for p in sorted(OUT.rglob('*')):
            if p.is_file() and p.suffix != '.log':
                z.write(p, 'MOTQA_修订补审12题/'+str(p.relative_to(OUT)))
    g.dump(v.D/'review_receipt.json', {'packet_id': packet_id, 'count': len(payload),
        'page': str(page), 'zip': str(zip_path), 'zip_bytes': zip_path.stat().st_size,
        'zip_sha256': v.sha(zip_path), 'export_filename': 'stage3_readability_v3_review_result.json',
        'qa_ids': [q['qa_id'] for q in picked], 'selection': 'purposeful coverage, seed42; not a random estimate of pass rate'})
    print('V3_REVIEW_READY', zip_path, flush=True)


HTML = (g.ROOT/'src/readability_review_template_zh.html').read_text()


if __name__ == '__main__':
    main()
