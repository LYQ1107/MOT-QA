"""One human-feedback-driven candidate revision, with no QA-model inference."""
from collections import Counter
import copy
from datetime import datetime
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

import generate_candidates_round2 as g

R = g.ROOT
D = R / 'results/stage3_readability_v3'
LOCK = D / 'rules_locked.json'
GAP_FAMILIES = {'return_time', 'return_region', 'earlier_return_time', 'earliest_return_person', 'premise_return_time'}
HELD = {'motqa_pilot_r2_0225', 'motqa_pilot_r2_0229', 'motqa_pilot_r2_0777'}
DEFINITION = ('For this question, a visibility gap means being out of clear view '
              'continuously for more than 1 second.')
DEFINITION_ZH = '本题的“可见性间断”指连续超过1秒未处于清晰可见状态。'
PARAMS = {
    'seed': 42,
    'base_gap_definition_s': 1.0,
    'previous_gap_construction_min_s': 1.5,
    'readability_gap_min_s': 2.0,
    'visible_run_before_and_after_gap_min_s': 0.6,
    'sampled_frames_inside_positive_gap_min': 2,
    'visible_sample_before_and_after_positive_gap_min': 1,
    'event_reference_continuous_visible_context_s': 1.0,
    'event_reference_min_width_fraction': 0.02,
    'event_reference_min_width_px': 32,
    'event_reference_search_from_event_max_s': 2.0,
    'event_reference_start_context_min_s': 1.0,
    'numeric_time_sampling_interval_max_s': 1.0,
    'negative_gap_question': 'reject any internal missing run returning in query through the existing2s negative extension, including subthreshold runs',
    'video_input': {
        'frame_count': 32,
        'sampling': 'start + floor(i*N/32), i=0..31, inclusive window length N',
        'window_start': 'earliest displayed reference frame minus1s, clipped to original eligible source window',
        'window_end': 'question end plus2s, clipped to original eligible source window',
        'time_origin': 'original video, not clip-relative',
        'used_to_choose_window': 'question/reference instants only; no answer events or model scores',
        'same_frames_for_all_later_conditions': True,
    },
    'event_facts': 'original GT/visibility convention remains unchanged; stricter candidate eligibility does not redefine source events',
    'non_gap_questions': 'scan references and store actual uniform input; no new duration rule on crossings/point queries',
    'human_feedback': 'held three specific originals are replaced, even if an automatic proxy passes',
    'reference_quota': 'try original225 event references; unclear event references may become box references as authorized; report any shortage',
    'scope': '900 candidate revision and small Chinese supplementary review; stop before filtering or Stage5',
}


def now():
    return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def lock():
    D.mkdir(parents=True, exist_ok=True)
    if LOCK.exists():
        assert json.loads(LOCK.read_text())['parameters'] == PARAMS
        return
    watched = [R/'data/candidates.jsonl', R/'results/generation_config_locked.json',
               R/'results/visibility_convention.json', R/'results/templates_locked.json',
               R/'data/question_review_user_passed_20.jsonl']
    config = {'version': 'stage3_readability_v3', 'status': 'LOCKED_BEFORE_REVISION',
              'locked_at': now(), 'authorization': 'User accepted the proposed full-candidate repair and Chinese supplementary review: 继续吧',
              'parameters': PARAMS, 'preserved_source_files': {str(p): sha(p) for p in watched}}
    g.dump(LOCK, config)
    templates = json.loads((R/'results/templates_locked.json').read_text())
    templates.update(version='readability_v3', locked_at=config['locked_at'],
                     previous_templates_sha256=sha(R/'results/templates_locked.json'))
    for fam in GAP_FAMILIES:
        if fam not in templates['templates']:
            continue
        for t in templates['templates'][fam]:
            t['text'] += ' ' + DEFINITION
            t['semantic_review'] = 'same arguments and output; explicitly state original>1s event definition; construction uses stricter readability gates'
    g.dump(D/'templates_locked.json', templates)
    g.dump(D/'lock_receipt.json', {'recorded_at': now(), 'rules_sha256': sha(LOCK),
                                 'templates_sha256': sha(D/'templates_locked.json')})


@lru_cache(maxsize=1500)
def gaps(key, tid):
    a = g.scene(key)
    fps = g.META[key]['fps']
    vis = a['visible'][a['axis'][tid]]
    edges = np.flatnonzero(np.diff(np.r_[False, vis, False].astype(np.int8)))
    runs = list(zip(edges[::2], edges[1::2]))
    return tuple({'last': int(stop), 'first_missing': int(stop + 1),
                  'return': int(start + 1), 'missing_end': int(start),
                  'duration_s': float((start - stop) / fps),
                  'pre_run_s': float((stop - first) / fps),
                  'post_run_s': float((end - start) / fps)}
                 for (first, stop), (start, end) in zip(runs[:-1], runs[1:]))


def input_window(q):
    key = q['dataset'], q['sequence']
    m = g.META[key]
    lo, hi = m['eligible_source_window_1based']
    start = max(lo, min(p['frame'] for p in q['reference']['persons']) - g.frames(key, 1))
    stop = min(hi, q['evidence']['query_end_frame'] + g.frames(key, 2))
    sampled = start + np.floor(np.arange(32) * (stop - start + 1) / 32).astype(int)
    return {'source_frame_start_1based': int(start), 'source_frame_end_1based': int(stop),
            'sample_frame_indices_1based': sampled.tolist(),
            'sample_timestamps_s': [g.sec(key, f) for f in sampled],
            'start_s': g.sec(key, start), 'end_s': g.sec(key, stop),
            'nominal_interval_s': (stop - start + 1) / m['fps'] / 32,
            'sampling': 'floor(i*N/32)', 'frame_count': 32,
            'timestamps_are_original_video_seconds': True,
            'policy': 'readability_v3; shared by all evaluation conditions'}


def wide_enough(key, tid, frame):
    a = g.scene(key)
    b = a['boxes_xywh'][a['axis'][tid], frame - 1]
    return bool(g.geom(key, tid, frame) and b[2] >= PARAMS['event_reference_min_width_px']
                and b[2] / g.META[key]['width'] >= PARAMS['event_reference_min_width_fraction'])


@lru_cache(maxsize=30000)
def event_anchor(key, tid, frame, typ, last, ret):
    """Return a clearer anchor in the same run, or a stated rejection reason."""
    m = g.META[key]
    a = g.scene(key)
    vis = a['visible'][a['axis'][tid]]
    lo, hi = m['eligible_source_window_1based']
    if frame - lo < g.frames(key, PARAMS['event_reference_start_context_min_s']):
        return None, 'event_reference_insufficient_start_context'
    span = g.frames(key, PARAMS['event_reference_search_from_event_max_s'])
    required = PARAMS['event_reference_continuous_visible_context_s']
    if typ in ['leaves_frame', 'becomes_occluded']:
        if not last:
            return None, 'event_reference_missing_pre_event_view'
        first = last
        while first > lo and vis[first - 2]:
            first -= 1
        if (last - first + 1) / m['fps'] < required:
            return None, 'event_reference_visible_run_too_short'
        candidates = range(last, max(first, frame - span) - 1, -1)
    else:
        first = frame
        end = first
        while end < hi and vis[end]:
            end += 1
        if not vis[first - 1] or (end - first + 1) / m['fps'] < required:
            return None, 'event_reference_visible_run_too_short'
        candidates = range(first, min(end, frame + span) + 1)
    for f in candidates:
        if wide_enough(key, tid, f):
            return int(f), None
    return None, 'event_reference_no_clear_wide_anchor'


def assess(q, repair_reference=False):
    key = q['dataset'], q['sequence']
    m = g.META[key]
    e = q['evidence']
    fam = q['template_id']
    fs, fe = e['query_start_frame'], e['query_end_frame']
    issues, changes = [], []
    for p in q['reference']['persons']:
        if p['type'] != 'event':
            continue
        ev = p['event']
        anchor, issue = event_anchor(key, p['target_id'], ev['frame'], ev['type'],
                                     ev.get('last_visible_frame'), ev.get('next_visible_frame'))
        if issue:
            issues.append(issue)
        elif anchor != p['frame']:
            if repair_reference:
                resource = {'event': ev, 'text': p['text'],
                            'ref_id': p.get('source_reference_id')}
                replacement = g.make_reference(key, p['target_id'], anchor, 'event', resource)
                if fs - max(anchor, ev['frame']) < g.frames(key, 5 if q['operation_name'] == 'O8' else 3):
                    issues.append('reanchored_reference_too_close_to_question')
                else:
                    old_frame = p['frame']
                    p.update(replacement)
                    changes.append({'type': 'clearer_event_reference_frame', 'role': p['role'],
                                    'old_frame': old_frame, 'new_frame': anchor})
            else:
                changes.append({'type': 'clearer_event_reference_frame_available',
                                'role': p['role'], 'old_frame': p['frame'], 'new_frame': anchor})
    window = input_window(q)
    samples = np.array(window['sample_frame_indices_1based'])
    checks = []
    if fam in GAP_FAMILIES:
        negative = q['semantic_answer'] == g.NEVER
        if negative:
            end = min(m['eligible_source_window_1based'][1], fe + g.frames(key, 2))
            for p in q['reference']['persons']:
                if any(fs <= z['return'] <= end for z in gaps(key, p['target_id'])):
                    issues.append('negative_question_has_actual_return_including_short_gap')
        targets = []
        if fam == 'return_time':
            z = next((z for z in gaps(key, q['reference']['primary_target_id'])
                      if z['first_missing'] == e['gt_detail']['gap']['frame']), None)
            if z:
                targets.append((q['reference']['primary_target_id'], z, not negative))
        elif not negative:
            for p in q['reference']['persons']:
                relevant = [z for z in gaps(key, p['target_id']) if fs <= z['return'] <= fe and z['duration_s'] > 1]
                for z in relevant:
                    targets.append((p['target_id'], z, True))
        for tid, z, need_return in targets:
            a = g.scene(key)
            vis = a['visible'][a['axis'][tid]]
            inside = samples[(samples >= z['first_missing']) & (samples <= z['missing_end'])]
            pre = samples[(samples < z['first_missing'])
                          & (samples >= z['first_missing'] - g.frames(key, 2))]
            post = samples[(samples >= z['return'])
                           & (samples <= z['return'] + g.frames(key, 2))]
            npre = int(vis[pre - 1].sum())
            npost = int(vis[post - 1].sum())
            if z['duration_s'] < PARAMS['readability_gap_min_s']:
                issues.append('gap_under_readability_2s')
            if z['pre_run_s'] < .6 or (need_return and z['post_run_s'] < .6):
                issues.append('visible_run_around_gap_under_0_6s')
            if len(inside) < 2 or npre < 1 or (need_return and npost < 1):
                issues.append('32_frames_do_not_resolve_gap_context')
            checks.append({'gt_id': tid, **z, 'return_needed_in_input': need_return,
                           'sampled_missing_times_s': [g.sec(key, f) for f in inside],
                           'sampled_visible_before': npre, 'sampled_visible_after': npost})
        if q['format'] == 'numeric_time' and window['nominal_interval_s'] > 1.0:
            issues.append('numeric_time_sampling_interval_over_1s')
    return {'qa_id': q.get('qa_id'), 'pool_id': q['pool_id'],
            'issues': sorted(set(issues)), 'reference_changes': changes,
            'gap_checks': checks, 'video_input': window,
            'gap_predicate': fam in GAP_FAMILIES}


def prepare(q):
    result = assess(q, repair_reference=True)
    if result['issues']:
        return None, result
    if result['reference_changes']:
        key = q['dataset'], q['sequence']
        first = q['reference']['persons'][0]
        end = q['evidence']['query_end_frame']
        tid = first['target_id']
        nc = sum(first['frame'] <= z['before_frame'] and z['after_frame'] <= end
                 for z in g.events_index(key)[3][tid])
        occ = [z for z in g.events_index(key)[0][tid]
               if z['type'] == 'becomes_occluded' and z['invisible_duration_s'] > 1.5
               and z['last_visible_frame'] >= first['frame']
               and z.get('next_visible_frame') and z['next_visible_frame'] <= end]
        a = g.scene(key)
        vv = a['visible'][a['axis'][tid], first['frame']-1:end]
        edges = np.flatnonzero(np.diff(np.r_[False, ~vv, False].astype(np.int8)))
        q['difficulty'].update(
            n_crossings=int(nc), identity_challenge=bool(nc or occ),
            identity_challenge_evidence={'crossing_count': int(nc), 'internal_gaps_gt1_5s': len(occ)},
            max_gap_s=float(max((edges[1::2]-edges[::2])/g.META[key]['fps'], default=0)),
            density=float(a['visible'][:, first['frame']-1:end].sum(0).mean()))
    q['video_input'] = result['video_input']
    q['readability_v3'] = {'rules': str(LOCK), 'sampling_checked': True,
                           'gap_checks': result['gap_checks'],
                           'reference_changes': result['reference_changes'],
                           'human_readability_approved': False}
    first = q['reference']['persons'][0]
    for f in ['t_ref_s', 'text', 'text_zh']:
        q['reference'][f] = first[f]
    q['evidence']['keyframes_1based'] = sorted(set(
        q['evidence']['keyframes_1based'] + [p['frame'] for p in q['reference']['persons']]))
    if q['template_id'] in GAP_FAMILIES and DEFINITION not in q['question']:
        q['question'] += ' ' + DEFINITION
    return q, result


def chinese_events(q):
    edge_zh = {'left': '左侧', 'right': '右侧', 'top': '上方', 'bottom': '下方'}
    for p in q['reference']['persons']:
        if p['type'] != 'event':
            continue
        ev = p['event']
        kind = ev['type']
        edge = edge_zh.get(ev.get('edge', {}).get('closest_edge'), '')
        action = {'leaves_frame': f'从画面{edge}边缘离开',
                  'enters_frame': f'从画面{edge}边缘进入',
                  'becomes_occluded': '开始可见性间断',
                  'reappears': '重新出现'}[kind]
        p['text_zh'] = f'在 {ev["time_s"]:.3f} 秒附近{action}的人'
    q['reference']['text_zh'] = q['reference']['persons'][0]['text_zh']
    if q['template_id'] in GAP_FAMILIES and DEFINITION_ZH not in q['question_zh']:
        q['question_zh'] += ' ' + DEFINITION_ZH


if __name__ == '__main__':
    lock()
    print(LOCK)
