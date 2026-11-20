"""Add time-bin false-premise questions without relaxing any readability gate."""
import copy
import json
import math

import generate_candidates_round2 as g
import readability_v3 as v
from select_candidates_round2 import hard_eligibility


TEMPLATES = [
    'During {start}–{end} s, in which time interval does A make the {ordinal} return to clear view after a visibility gap?',
    'Which listed interval contains A’s {ordinal} post-gap reappearance within {start}–{end} s?',
    'Locate the time interval of A’s {ordinal} clear reappearance following a gap during {start}–{end} s.',
    'For {start}–{end} s, choose when A first returns to clear view after a gap, or indicate that the event does not occur.',
    'When in {start}–{end} s does A have the {ordinal} return after a visibility interruption? Choose an interval or the no-event option.',
]


def main():
    lock = v.D/'o7_time_template_addendum_locked.json'
    if not lock.exists():
        g.dump(lock, {
            'recorded_at': v.now(), 'status': 'LOCKED_BEFORE_GENERATION',
            'base_rules_sha256': v.sha(v.LOCK),
            'reason': 'Strict readability removes most short Dance occlusions; Sports has no center-region return among>=2s stable-gap facts. Add a when-question within the already authorized O7 false-premise operation, retaining conditional positive-class balance rather than weakening it.',
            'no_event_definition_or_visibility_changes': True,
            'operation': 'O7', 'family': 'premise_return_time', 'format': 'multiple_choice',
            'time_bins': 3, 'time_bin_event_margin_s': .5, 'held_out_ids': [3, 4],
            'premise': 'first return after a visibility gap; original>1s definition; construction>=2s',
            'templates': [{'paraphrase_id': i, 'paraphrase_split': 'held_out' if i >= 3 else 'shared',
                           'text': t+' '+v.DEFINITION,
                           'semantic_review': 'first ordinal only; identical question scope and no-event alternative'}
                          for i, t in enumerate(TEMPLATES)]})
    rows = g.rows(v.D/'eligible_pool.jsonl')
    extras = []
    for q in rows:
        if q['template_id'] != 'return_region' or q['evidence']['gt_detail']['ordinal'] != 1:
            continue
        key = q['dataset'], q['sequence']
        e = q['evidence']
        fs, fe = e['query_start_frame'], e['query_end_frame']
        bins = g.numbered_bins(key, fs, fe, n=3)
        if bins is None:
            continue
        exists = e['gt_detail']['event_exists']
        returned = e['gt_detail']['reappearance_frames'][0] if exists else None
        if returned is not None:
            # The event cannot sit just across an internal time-bin boundary.
            if any(abs(returned-start) < g.frames(key, .5) for start, stop in bins[1:]):
                continue
        values = g.time_values(key, bins, True)
        answer = next((i for i, (a, b) in enumerate(bins) if returned is not None and a <= returned <= b), 3)
        new = copy.deepcopy(q)
        new['pool_id'] = 9_000_000 + len(extras)
        new['template_id'] = 'premise_return_time'
        new['paraphrase_id'] = len(extras) % 5
        new['paraphrase_split'] = 'held_out' if new['paraphrase_id'] >= 3 else 'shared'
        new['question'] = TEMPLATES[new['paraphrase_id']].format(start=g.fmt(key, fs), end=g.fmt(key, fe), ordinal='first')+' '+v.DEFINITION
        new['raw_options'] = values
        new['answer_index'] = answer
        new['semantic_answer'] = values[answer]
        new['preserve_reviewed_question'] = False
        new.pop('previous_qa_id', None)
        new.pop('qa_id', None)
        new['evidence']['gt_detail']['time_bin_frames'] = bins
        new['evidence']['confusion'] = None
        for other, _ in g.conf_partners(key, q['reference']['primary_target_id'],
                                       q['reference']['persons'][0]['frame'], fe).most_common():
            returns = g.relevant_returns(key, other, fs, fe)
            frame = returns[0][0]['frame'] if returns else None
            alt = next((i for i, (a, b) in enumerate(bins) if frame is not None and a <= frame <= b), 3)
            if alt != answer:
                new['evidence']['confusion'] = {'gt_id': other, 'semantic_answer': values[alt],
                                               'method': 'follow_overlapping_person_first_return_time_bin'}
                break
        new['has_confusion_option'] = new['evidence']['confusion'] is not None
        if hard_eligibility(new):
            continue
        new, result = v.prepare(new)
        if new is not None:
            extras.append(new)
    g.putrows(v.D/'o7_time_extra_pool.jsonl', extras)
    g.putrows(v.D/'eligible_pool_enriched.jsonl', rows+extras)
    g.dump(v.D/'o7_time_enrichment_receipt.json', {
        'recorded_at': v.now(), 'source_pool_n': len(rows), 'additional_candidates': len(extras),
        'new_formal_questions_not_generated_yet': True, 'formal_total_target_unchanged': 900,
        'thresholds_changed': False, 'addendum_sha256': v.sha(lock)})
    print('O7_TIME_CANDIDATES_ADDED', len(extras), flush=True)


if __name__ == '__main__':
    main()
