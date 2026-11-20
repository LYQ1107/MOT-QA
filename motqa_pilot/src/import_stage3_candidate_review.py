"""Import the real 20-item review and diagnose the three reported concerns.

This records a review sidecar only. Candidates, GT, locks and human verdicts
are preserved; proposed revisions are not a new generation protocol.
"""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

import generate_candidates_round2 as g
from audit_question_review_gt import raw


OUT = g.RES / 'manual_review_diagnosis'
FEEDBACK = ('检查完了， 其中有几个遮挡的有问题，感觉遮挡的时间很短，人的肉眼都很难判断。'
            '还有就是例如“在 0.440 秒附近消失在画面边缘的人”这种情况比较难，我觉得')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def gaps_in_query(q, person):
    key = q['dataset'], q['sequence']
    _, index, _, visible, _ = raw(key)
    fps = g.META[key]['fps']
    found = np.flatnonzero(visible[index[person['target_id']]])
    lo, hi = q['evidence']['source_window_1based']
    sampled = lo + np.floor(np.arange(32) * (hi - lo + 1) / 32).astype(int)
    start, end = q['evidence']['query_start_frame'], q['evidence']['query_end_frame']
    result = []
    for left, right in zip(found[:-1], found[1:]):
        if right - left <= 1 or right + 1 < start or left + 1 > end:
            continue
        result.append({
            'last_visible_frame': int(left + 1),
            'last_visible_s': float(left / fps),
            'first_missing_s': float((left + 1) / fps),
            'return_frame': int(right + 1),
            'return_s': float(right / fps),
            'missing_duration_s': float((right - left - 1) / fps),
            'sampled_missing_times_s': [float((f - 1) / fps) for f in sampled
                                        if left + 2 <= f <= right],
        })
    return {'role': person['role'], 'gt_id': person['target_id'], 'gaps': result}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('submission', type=Path)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    now = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
    tracked = [g.ROOT / 'data/candidates.jsonl',
               g.ROOT / 'results/generation_config_locked.json',
               g.ROOT / 'results/visibility_convention.json',
               g.ROOT / 'results/templates_locked.json',
               g.ROOT / 'data/question_review_user_passed_20.jsonl']
    before = {str(p): digest(p) for p in tracked}
    receipt = json.loads((g.RES / 'formal_review_receipt.json').read_text())
    sample = g.rows(g.RES / 'formal_sample20.jsonl')
    review = json.loads(args.submission.read_text())
    assert review['packet_id'] == receipt['packet_id']
    ids = [r['qa_id'] for r in review['reviews']]
    assert review['total'] == len(ids) == len(set(ids)) == 20
    assert set(ids) == {q['qa_id'] for q in sample}
    assert all(r['verdict'] in ['pass', 'fail', 'uncertain', None]
               for r in review['reviews'])
    sha = digest(args.submission)
    archived = OUT / 'user_submissions' / (now[:10] + '_' + sha[:12] + '.json')
    archived.parent.mkdir(exist_ok=True)
    archived.write_bytes(args.submission.read_bytes())
    candidates = g.rows(g.ROOT / 'data/candidates.jsonl')
    byid = {q['qa_id']: q for q in candidates}
    concerns = {
        'motqa_pilot_r2_0225': '用户不确定：感觉不是很明显；检查短间断与重现顺序的可辨认性。',
        'motqa_pilot_r2_0229': '用户不确定：遮挡不明显；短间断被事件定义排除，但题面没有说明。',
        'motqa_pilot_r2_0777': '对话额外提出0.440秒边缘消失指代困难；保留JSON中的通过，另列修订疑点。',
    }
    annotated = []
    for r in review['reviews']:
        q = byid[r['qa_id']]
        annotated.append({**r, 'operation_name': q['operation_name'],
                          'dataset': q['dataset'], 'sequence': q['sequence'],
                          'review_hold': r['qa_id'] in concerns,
                          'hold_reason': concerns.get(r['qa_id']),
                          'human_verdict_changed': False})
    g.dump(OUT / 'review_dispositions.json', {
        'recorded_at': now, 'source_sha256': sha,
        'verdicts_are_original_user_choices': True,
        'holds_are_review_sidecar_not_candidate_edits': True, 'reviews': annotated})
    diagnostics = []
    for qid, reason in concerns.items():
        q = byid[qid]
        key = q['dataset'], q['sequence']
        m = g.META[key]
        details = {
            'qa_id': qid, 'reason': reason, 'question_zh': q['question_zh'],
            'semantic_answer': q['semantic_answer'],
            'sampling_scope': 'planned full source window, floor(i*N/32), not review MP4',
            'nominal_sampling_interval_s':
                (q['evidence']['source_window_1based'][1]
                 - q['evidence']['source_window_1based'][0] + 1) / m['fps'] / 32,
            'roles': [gaps_in_query(q, p) for p in q['reference']['persons']],
        }
        if qid.endswith('0777'):
            p = q['reference']['persons'][0]
            _, ix, boxes, vis, _ = raw(key)
            present = np.flatnonzero(vis[ix[p['target_id']]])
            ev = p['event']
            before_event = present[present < ev['frame'] - 1]
            boundary = len(before_event) - 1
            while boundary > 0 and before_event[boundary] - before_event[boundary - 1] == 1:
                boundary -= 1
            details['event_reference'] = {
                'event_time_s': p['event_time_s'], 'anchor_time_s': p['t_ref_s'],
                'continuous_visible_before_event_s': len(before_event[boundary:]) / m['fps'],
                'anchor_width_px': float(boxes[ix[p['target_id']], p['frame'] - 1, 2]),
                'anchor_width_fraction':
                    p['box_xyxy_normalized'][2] - p['box_xyxy_normalized'][0],
                'english_mentions_left_edge': True,
                'chinese_omits_left_direction': True,
                'geometry_gate_does_not_establish_human_identifiability': True,
            }
        diagnostics.append(details)
    g.dump(OUT / 'temporal_reference_diagnostics.json', {
        'recorded_at': now, 'basis': 'Original released GT text; source frames visually inspected.',
        'planned_sampling_not_a_model_run': True, 'cases': diagnostics})
    event_refs = [(q, p) for q in candidates for p in q['reference']['persons']
                  if p['type'] == 'event']
    scan = {
        'event_reference_questions': len({q['qa_id'] for q, _ in event_refs}),
        'event_time_lt_1s_qa_ids': sorted({q['qa_id'] for q, p in event_refs
                                         if p['event_time_s'] < 1}),
        'anchor_width_lt_2percent_qa_ids': sorted({q['qa_id'] for q, p in event_refs
            if p['box_xyxy_normalized'][2] - p['box_xyxy_normalized'][0] < .02}),
        'interpretation': 'Descriptive screening flags only. The 1s/2% cutoffs are not locked eligibility rules; flagged does not mean failed.',
    }
    g.dump(OUT / 'event_reference_descriptive_scan.json', scan)
    counts = dict(Counter(r['verdict'] or 'unreviewed' for r in review['reviews']))
    summary = {
        'recorded_at': now, 'status': 'REVIEW_RECEIVED_3_CONCERNS_PENDING_REVISION',
        'packet_id': review['packet_id'], 'user_exported_at': review['exported_at'],
        'source_file': str(args.submission), 'archived_source': str(archived),
        'source_sha256': sha, 'original_human_counts': counts,
        'review_hold_qa_ids': list(concerns),
        'uncontested_human_passed': sum(r['verdict'] == 'pass' and not r['review_hold']
                                      for r in annotated),
        'other_candidates_not_individually_human_reviewed': len(candidates) - len(sample),
        'candidate_questions_or_answers_changed': False,
        'GT_changed': False, 'generation_or_visibility_locks_changed': False,
        'model_calls': 0, 'tracker_runs': 0, 'filtering_started': False,
        'preserved_files_sha256': before,
    }
    assert all(digest(Path(p)) == h for p, h in before.items())
    g.dump(OUT / 'user_review_import_summary.json', summary)
    report = f'''# 正式候选20题人工审阅：时间事件与指代疑点

记录时间：{now}。这是已授权独立项目`/home/user/motqa_pilot`的审阅导入与事后诊断，不是模型实验。

## 人工结果

上传的20题：18通过、0不通过、2不确定。原始JSON按字节保存，不替用户修改任何勾选。
0225备注“感觉不是很明显”，0229备注“遮挡不明显”。对话另指出0777的“0.440秒附近消失在画面边缘的人”难以指认；
这条在JSON中仍保留通过，另记对话疑点。因此当前17题无额外异议、3题待修订，不能宣称20题全部通过，也不能将这次抽查外推为900题已通过。

## 核对发现

|题号|原始GT与输入事实|问题与处置|
|---|---|---|
|0225 / O5|B在32.750–34.550秒没有GT框，缺失1.800秒；整段50秒采32帧时，间断内只有32.800、34.350秒两张。其他人及B还有多次0.050–1.000秒短间断。|现有1.5秒构造余量通过，并不等于人眼容易辨别；“谁先重新出现”没有写明事件时长口径。保持不确定，暂缓。|
|0229 / O7|A在问题区间内有0.250、0.400、0.050秒GT间断；没有超过1秒的间断，因此脚本给“这件事没有发生”。这些短间断均未落入计划的32帧采样。|无时间限定的自然语言“重新出现”与脚本只数超过1秒间断的口径有歧义。这不是单纯增加正例最短时长能修复的问题。保持不确定，暂缓。|
|0777 / O3，事件指代|用于指代的事件在0.440秒；此前连续可观察仅0.440秒。参考帧为0.320秒，框宽18px，占1280px画面1.406%。|几何门槛通过，但早、窄、贴边，无法据此保证容易确定人物；中文还遗漏英文中的“左侧”。保留原通过勾选，另列指代修订。|

核对使用原始发布GT文本，并查看消失前、间断内、重现后的源帧。标注缺框本身不能证明自然语言所说的完整遮挡在视觉上清楚。
0225的1.800秒不是违反1.5秒硬规则；0229是“短间断不计事件”与题面之间的口径问题。
此前920题GT核验通过仅证明答案按生成规则可重算，不证明全部题目具备人工可辨认性。

## 范围扫描（只用于描述）

900题中225题采用事件指代；其中事件时刻早于1秒的有{len(scan['event_time_lt_1s_qa_ids'])}题，参考框宽小于画面2%的有{len(scan['anchor_width_lt_2percent_qa_ids'])}题，两组可能重叠。
这两个界限仅作本次描述性定位，不是新增硬阈值；未查看其余题原片、未自动认定失败、未批量删除。

## 修订方向（尚未锁定或应用）

1. 保留离开、重现、顺序等推理题型；优先用清楚的红框帧确定人物，再问后续事件。只靠片头瞬间出画或极窄边缘人物作事件指代的题优先替换。
2. 针对事件题检查最终实际32帧输入是否能支持观察事件前、间断中、重现后的状态，并结合原片核查；不足时换题或另立一致的片段方案。不能只凭GT有间断就宣布题目清楚。
3. 统一问句与既定“超过1秒间断”的含义；不要在未限定的“是否重新出现”问法下，把真实短间断后的重现直接写为“没有发生”。优先替换有歧义的样例，而非靠小数秒边界制造否例。
4. 对需要修订的指代保留旧版与改动依据，再检查参考方式比例、答案平衡及每视频/身份上限。

本次仅登记人工结果、3题疑点和诊断，候选900题、答案、原始GT、visibility约定、生成锁定配置、旧20示例均保持原文件。
没有生成替换题、启动过滤、模型推理、跟踪或训练。等待修订方向明确后再推进。
'''
    (OUT / 'review_findings_zh.md').write_text(report)
    marker = f'## 正式候选20题人工结果与时间事件疑点 — {sha[:12]}'
    log = g.ROOT / 'research_log.md'
    if marker not in log.read_text():
        with log.open('a') as f:
            f.write(f'\n{marker}\n\n{now}。用户原JSON18通过/2不确定；原样归档，17题无额外异议，'
                    '0225/0229不确定及对话提及0777单列暂缓。原GT核对：0225关键缺框1.8秒，'
                    '计划32帧中仅2张缺框状态；0229有0.25/0.40秒短间断但被>1秒事件定义排除，'
                    '题面未限定口径却答“没有发生”；0777事件前仅0.44秒可观察，参考框18px。'
                    '源帧已查看；GT可重算不等于人工可辨认。225事件指代中9题事件早于1秒、'
                    '58题参考框宽<2%，仅描述性定位，不当作新增阈值或自动失败。'
                    '保留原人审决定、候选、答案、GT和锁定配置；修订建议另存未应用；无过滤、模型、跟踪或训练。\n')
    print(json.dumps({k: summary[k] for k in ['status', 'original_human_counts',
                     'review_hold_qa_ids', 'uncontested_human_passed']}, ensure_ascii=False))
    print(OUT / 'review_findings_zh.md')


if __name__ == '__main__':
    main()
