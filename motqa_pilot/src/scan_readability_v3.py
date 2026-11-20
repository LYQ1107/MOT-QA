"""Audit all old candidates, then build eligible repairs from the existing pool."""
from collections import Counter, defaultdict
import copy
import json
import shutil
import time

import generate_candidates_round2 as g
import readability_v3 as v
from select_candidates_round2 import hard_eligibility, normalize_confusion


def main():
    v.lock()
    begin = time.monotonic()
    history = v.D / 'before_revision'
    history.mkdir(exist_ok=True)
    source = g.ROOT / 'data/candidates.jsonl'
    archive = history / 'candidates_round2_original.jsonl'
    if not archive.exists():
        shutil.copyfile(source, archive)
    assert v.sha(archive) == json.loads(v.LOCK.read_text())['preserved_source_files'][str(source)]
    original = g.rows(archive)
    review = json.loads((g.RES/'manual_review_diagnosis/review_dispositions.json').read_text())
    passed = {r['qa_id'] for r in review['reviews'] if r['verdict'] == 'pass' and not r['review_hold']}
    reports, direct, pins = [], {}, []
    for q in original:
        old = v.assess(q)
        candidate, repair = v.prepare(copy.deepcopy(q))
        baseline_issue = hard_eligibility(candidate or q)
        if baseline_issue:
            repair['issues'] = sorted(set(repair['issues'] + ['original_hard_rule:' + baseline_issue]))
            candidate = None
        if q['qa_id'] in v.HELD:
            repair['issues'] = sorted(set(repair['issues'] + ['specific_user_concern_requires_replacement']))
            candidate = None
        report = {'qa_id': q['qa_id'], 'pool_id': q['pool_id'], 'dataset': q['dataset'],
                  'operation_name': q['operation_name'], 'old_question_zh': q['question_zh'],
                  'old_reference_type': q['reference']['type'],
                  'initial_assessment': old, 'after_reference_repair': repair,
                  'automatic_disposition': 'eligible_with_recorded_revision' if candidate else 'replace',
                  'previous_user_pass': q['qa_id'] in passed,
                  'human_pass_carried_to_new_question': False}
        if candidate:
            direct[q['pool_id']] = candidate
            # Carry only an unchanged question/reference/options, never a blanket pass.
            if (q['qa_id'] in passed and q['template_id'] not in v.GAP_FAMILIES
                    and not repair['reference_changes']):
                pins.append(q['pool_id'])
                report['preserve_unmodified_reviewed_question'] = True
        reports.append(report)
    g.dump(v.D/'all900_before_revision_audit.json', {
        'recorded_at': v.now(), 'n': len(reports), 'source_sha256': v.sha(archive),
        'rules_sha256': v.sha(v.LOCK),
        'dispositions': dict(Counter(r['automatic_disposition'] for r in reports)),
        'replacement_reasons': dict(Counter(x for r in reports
            for x in r['after_reference_repair']['issues'])),
        'pinned_unchanged_reviewed_pool_ids': pins, 'checks': reports})
    print('OLD900_SCAN', len(direct), 'directly repairable;', len(original)-len(direct),
          'replace;', len(pins), 'unchanged human-reviewed questions preserved', flush=True)
    originals_by_pool = {q['pool_id']: q for q in original}
    forbidden = {q['pool_id'] for q in original if q['qa_id'] in v.HELD}
    reasons = Counter()
    accepted = []
    seen = set()
    # The original normalizer and hard checks remain applicable to every proposal.
    for path in [g.RES/'candidate_pool.jsonl', g.RES/'optional_crop_pool.jsonl']:
        for line in path.open():
            q = json.loads(line)
            pid = q['pool_id']
            if pid in seen or pid in forbidden or q['evidence']['gt_detail'].get('example_only'):
                continue
            seen.add(pid)
            if pid in direct:
                q = copy.deepcopy(direct[pid])
            normalize_confusion(q)
            issue = hard_eligibility(q)
            if issue:
                reasons['original_hard_rule:' + issue] += 1
                continue
            q, result = v.prepare(q)
            if q is None:
                reasons.update(result['issues'])
                continue
            if pid in originals_by_pool:
                q['previous_qa_id'] = originals_by_pool[pid]['qa_id']
            q['preserve_reviewed_question'] = pid in pins
            accepted.append(q)
    missing_pins = set(pins) - {q['pool_id'] for q in accepted}
    assert not missing_pins, missing_pins
    g.putrows(v.D/'eligible_pool.jsonl', accepted)
    counts = Counter((q['operation_name'], q['dataset']) for q in accepted)
    g.dump(v.D/'pool_scan_summary.json', {
        'recorded_at': v.now(), 'old_candidate_n': len(original),
        'directly_repairable_n': len(direct), 'old_questions_needing_replacement_n': len(original)-len(direct),
        'eligible_pool_n': len(accepted), 'rejection_reasons_nonexclusive': dict(reasons),
        'operation_dataset': {op: {ds: counts[op, ds] for ds in ['DanceTrack', 'SportsMOT', 'MOT17']}
                              for op in g.CFG['candidate_operation_targets']},
        'reference_counts': dict(Counter(q['reference']['type'] for q in accepted)),
        'numeric_counts_by_operation': dict(Counter(q['operation_name'] for q in accepted if q['format'].startswith('numeric'))),
        'pinned_pool_ids': pins, 'seconds': time.monotonic()-begin,
        'no_model_inference': True, 'no_source_GT_or_lock_edits': True})
    print('ELIGIBLE_V3', len(accepted), dict(Counter(q['reference']['type'] for q in accepted)),
          'seconds', round(time.monotonic()-begin, 1), flush=True)


if __name__ == '__main__':
    main()
