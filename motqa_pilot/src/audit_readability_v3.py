"""Original-GT answer re-derivation and meaningful whole-candidate checks."""
from collections import Counter, defaultdict
import json
import time

import numpy as np

import generate_candidates_round2 as g
import readability_v3 as v
from audit_candidates_round2 import recompute
from select_candidates_round2 import hard_eligibility
from report_candidates_round2 import semantic as original_semantic, majority


def semantic(q):
    if q['template_id'] == 'premise_return_time':
        return 'time_bin:'+str(q['answer_index']) if q['semantic_answer'] != g.NEVER else g.NEVER
    return original_semantic(q)


def summarize(qs):
    opgroups = defaultdict(list)
    for q in qs:
        opgroups[q['operation_name']].append(q)
    blind, warnings = {}, []
    for op, rows in sorted(opgroups.items()):
        choice = [q for q in rows if q['format'] == 'multiple_choice']
        def source_majority(fn):
            sources = defaultdict(list)
            for q in choice:
                sources[q['dataset']].append(q)
            return sum(len(rows)*majority(rows, fn) for rows in sources.values())/max(1, len(choice))
        letter = majority(choice, lambda q: q['answer'])
        sem = majority(choice, semantic)
        chance = float(np.mean([1/len(q['options']) for q in choice])) if choice else None
        x = {'n': len(rows), 'multiple_choice_n': len(choice), 'majority_letter': letter,
             'dataset_only_letter': source_majority(lambda q: q['answer']),
             'uniform_choice_chance': chance, 'semantic_majority': sem,
             'semantic_dataset_only': source_majority(semantic)}
        blind[op] = x
        for name, delta, limit in [
            ('source_minus_global_letter', x['dataset_only_letter']-letter, .05),
            ('source_minus_global_semantic', x['semantic_dataset_only']-sem, .05),
            ('letter_majority_minus_chance', letter-(chance or 0), .1),
            ('semantic_majority_minus_chance', sem-(chance or 0), .1)]:
            if choice and delta > limit+1e-7 and not(op == 'O7' and name.endswith('minus_chance')):
                warnings.append({'operation': op, 'metric': name, 'delta': delta, 'limit': limit})
    videos = Counter((q['dataset'], q['sequence']) for q in qs)
    ids = Counter((q['dataset'], q['sequence'], q['reference']['primary_target_id']) for q in qs)
    choice = [q for q in qs if q['format'] == 'multiple_choice']
    old = {q['qa_id']: q for q in g.rows(v.D/'before_revision/candidates_round2_original.jsonl')}
    counts = {
        'n': len(qs), 'operations': dict(Counter(q['operation_name'] for q in qs)),
        'datasets': dict(Counter(q['dataset'] for q in qs)),
        'references': dict(Counter(q['reference']['type'] for q in qs)),
        'formats': dict(Counter(q['format'] for q in qs)),
        'operation_dataset': {op: dict(Counter(q['dataset'] for q in rows)) for op, rows in opgroups.items()},
        'retained_original_facts': sum(q['previous_qa_id'] is not None for q in qs),
        'replaced_original_questions': sum(q['replaces_qa_id'] is not None for q in qs),
        'wording_changed_vs_old_slot': sum(q['question'] != old[q['previous_slot_qa_id']]['question'] for q in qs),
        'original_gap_definition_made_explicit': sum(q['template_id'] in v.GAP_FAMILIES for q in qs),
        'event_reference_reanchored': sum(bool(q['readability_v3']['reference_changes']) for q in qs),
        'unchanged_reviewed_preserved': sum(bool(q.get('preserve_reviewed_question')) for q in qs),
        'videos': len(videos), 'max_per_video': max(videos.values()),
        'primary_identities': len(ids), 'max_primary_reuse': max(ids.values()),
        'identity_challenge': sum(q['difficulty']['identity_challenge'] for q in qs),
        'binary': sum(len(q['options']) == 2 for q in choice),
        'image_options': sum(q.get('option_modality') == 'image' for q in qs),
        'confusion_options': sum(q['has_confusion_option'] for q in choice),
        'choice_n': len(choice),
        'O7_premise_counts': dict(Counter(str(q['evidence']['gt_detail']['event_exists']) for q in qs if q['operation_name'] == 'O7')),
        'ordinary_never_correct': sum(q['semantic_answer'] == g.NEVER for q in qs if q['operation_name'] != 'O7'),
        'held_out_wordings': sum(q['paraphrase_split'] == 'held_out' for q in qs),
        'blind_baselines': blind, 'balance_warnings': warnings,
    }
    durations = [q['video_input']['end_s']-q['video_input']['start_s'] for q in qs]
    spacing = [q['video_input']['nominal_interval_s'] for q in qs]
    counts['input_window_duration_s'] = dict(zip(['min', 'p50', 'p95', 'max'], np.quantile(durations, [0, .5, .95, 1]).tolist()))
    counts['input_sampling_interval_s'] = dict(zip(['min', 'p50', 'p95', 'max'], np.quantile(spacing, [0, .5, .95, 1]).tolist()))
    return counts


def main():
    start = time.monotonic()
    path = g.ROOT/'data/candidates_readability_v3.jsonl'
    qs = g.rows(path)
    old = {q['qa_id']: q for q in g.rows(v.D/'before_revision/candidates_round2_original.jsonl')}
    failures = []
    checks = []
    for q in qs:
        try:
            checks.append(recompute(q))
            assert not hard_eligibility(q), hard_eligibility(q)
            screen = v.assess(q)
            assert not screen['issues'], screen['issues']
            assert q['video_input'] == screen['video_input']
            assert len(set(q['video_input']['sample_frame_indices_1based'])) == 32
            if q.get('preserve_reviewed_question'):
                prior = old[q['previous_qa_id']]
                for field in ['question', 'question_zh', 'reference', 'options', 'options_zh', 'answer']:
                    assert q[field] == prior[field], ('changed prior human-reviewed question', field)
        except Exception as ex:
            failures.append({'qa_id': q['qa_id'], 'pool_id': q['pool_id'], 'template': q['template_id'], 'error': repr(ex)})
    summary = summarize(qs)
    assert len(qs) == len({q['qa_id'] for q in qs}) == 900
    assert summary['operations'] == g.CFG['candidate_operation_targets']
    assert summary['datasets'] == g.CFG['realized_dataset_targets']
    assert summary['max_per_video'] <= 20 and summary['max_primary_reuse'] <= 3
    assert summary['identity_challenge'] >= 540 and summary['binary'] <= 225
    assert sum(q['format'].startswith('numeric') for q in qs) == 180
    assert summary['confusion_options'] >= .7*summary['choice_n']
    assert summary['O7_premise_counts'] == {'True': 55, 'False': 55}
    assert summary['ordinary_never_correct'] == 40
    for p, digest in json.loads(v.LOCK.read_text())['preserved_source_files'].items():
        assert v.sha(p) == digest, p
    g.dump(v.D/'summary.json', summary)
    g.dump(v.D/'raw_gt_and_readability_audit.json', {
        'recorded_at': v.now(), 'status': 'FAILED' if failures or summary['balance_warnings'] else 'PASSED',
        'verified_original_GT_answers': len(checks), 'n': len(qs), 'failures': failures,
        'balance_warnings': summary['balance_warnings'], 'candidate_sha256': v.sha(path),
        'seconds': time.monotonic()-start, 'checks': checks,
        'human_readability_is_not_claimed_by_this_automated_audit': True})
    if failures or summary['balance_warnings']:
        raise RuntimeError(json.dumps({'failures': failures, 'balance': summary['balance_warnings']}, ensure_ascii=False))
    print('PASSED_V3_ORIGINAL_GT_AND_QUOTAS', len(qs), flush=True)
    print(json.dumps({k: summary[k] for k in ['retained_original_facts', 'replaced_original_questions',
                     'references', 'identity_challenge', 'confusion_options', 'image_options']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
