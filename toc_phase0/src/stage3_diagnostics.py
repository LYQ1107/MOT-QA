"""Offline annotation diagnostics; nothing here is a tracker/model input."""
from collections import Counter, defaultdict
from datetime import datetime
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'upstream/toc_bench'))
from eval_runner import build_prompt


def main():
    items = json.loads((ROOT / 'data/toc_bench/answer_final.json').read_text())['items']
    preds = {p['qa_id']: p for p in map(json.loads, (ROOT / 'results/stage2_predictions.jsonl').read_text().splitlines())}
    system, user = build_prompt({'format': 'numerical', 'question': '{question}'})
    (ROOT / 'results/numerical_official_prompt.txt').write_text('[System]\n' + system + '\n\n[User]\n' + user + '\n')
    repairs = [dict(qa_id=q['qa_id'], dimension=q['metadata']['dim'], change=entry)
               for q in items for entry in q['metadata'].get('repair_log', [])]
    rows = []
    for q in items:
        if q['metadata']['dim'] != 'reappear_identity':
            continue
        def meaning(letter):
            text = q.get('option_' + letter) or q['statement_' + letter]
            return 'different' if 'different one' in text else 'same' if 'same one' in text else 'unknown'
        p = preds[q['qa_id']]
        rows.append(dict(qa_id=q['qa_id'], correct_answer=q['correct_answer'],
                         correct_option_meaning=meaning(q['correct_answer']),
                         semantic_ground_truth=q['metadata']['semantic_ground_truth'],
                         ground_truth_is_real=q['metadata']['ground_truth_is_real'],
                         repair_log=q['metadata'].get('repair_log', []), raw_response=p['raw_response'],
                         prediction_meaning=meaning(p['extracted_answer']),
                         correct=p['extracted_answer'] == q['correct_answer']))
    correspondence = Counter((r['correct_answer'], r['semantic_ground_truth'], r['ground_truth_is_real']) for r in rows)
    hypothetical = {
        'published_labels': {'correct': sum(r['correct'] for r in rows), 'total': 23},
        'all_semantically_same': {'correct': sum(r['prediction_meaning'] == 'same' for r in rows), 'total': 23},
        'all_semantically_different': {'correct': sum(r['prediction_meaning'] == 'different' for r in rows), 'total': 23},
        'metadata_semantic_ground_truth': {'correct': sum(r['prediction_meaning'] == r['semantic_ground_truth'] for r in rows), 'total': 23},
    }
    for real in (True, False):
        selected = [r for r in rows if r['ground_truth_is_real'] == real]
        hypothetical['published_labels_flag_' + str(real).lower()] = {'correct': sum(r['correct'] for r in selected), 'total': len(selected)}
    for v in hypothetical.values():
        v['accuracy_percent'] = 100 * v['correct'] / v['total'] if v['total'] else None
    legal = {'2', '3', '4', '5 or more'}
    numerical = [p for p in preds.values() if p['format'] == 'numerical']
    result = dict(generated_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(), offline_diagnostic_only=True,
                  annotation_files_modified=False, truth_metadata_used_in_prompts=False,
                  numerical_prompt={'system': system, 'user_template': user,
                                    'interpretation': '2, 3, 4 are examples (e.g.), not an exclusive list; 0/1 are not expressly forbidden in the prompt although the official parser rejects them',
                                    'stage2_raw_exact_legal': sum(p['raw_response'].strip() in legal for p in numerical),
                                    'stage2_parser_valid': sum(p['extracted_answer'] is not None for p in numerical), 'total': 300},
                  reid={'qa_count': 23, 'correspondence': [dict(correct_answer=k[0], semantic_ground_truth=k[1], ground_truth_is_real=k[2], count=v) for k,v in sorted(correspondence.items())],
                        'semantic_field_matches_correct_option': sum(r['semantic_ground_truth'] == r['correct_option_meaning'] for r in rows),
                        'repair_items': sum(bool(r['repair_log']) for r in rows),
                        'repair_entries': sum(len(r['repair_log']) for r in rows),
                        'hypothetical_scoring': hypothetical, 'rows': rows,
                        'conclusion': 'All-same counterfactual yields 22/23=95.65%, numerically explaining the paper value, but does not establish which labels the paper actually used. Published labels and main scores remain unchanged.'},
                  all_repairs={'item_count': sum(bool(q['metadata'].get('repair_log')) for q in items),
                               'entry_count': len(repairs), 'by_dimension': dict(Counter(r['dimension'] for r in repairs)),
                               'by_change': dict(Counter(r['change'] for r in repairs)), 'rows': repairs})
    (ROOT / 'results/stage3_diagnostics.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    future = dict(recorded_at=result['generated_at'], stage_four_authorized=False,
                  main_metric='official unconstrained strict accuracy; unchanged',
                  protocols=['official_plus_timestamps_and_evidence', 'brief_reasoning_last_line_Answer_supplement'],
                  numerical_conditions=['A','B','C','D'], legal_choices=['2','3','4','5 or more'],
                  legal_ratio='exact stripped answer-region membership; direct-output main uses entire response, reasoning supplement uses its final Answer region; also report official parser-valid ratio separately',
                  constrained_decoding='separate numerical-only A/B/C/D runs for each protocol; vLLM guided choice / structured_outputs.choice adapter; analysis only, never replace unconstrained main scores',
                  results_separated_by_protocol_and_decoding=True, trackable_subset_reported_alongside_full_scope=True)
    (ROOT / 'results/stage4_numerical_analysis_plan.json').write_text(json.dumps(future, indent=2) + '\n')
    print(json.dumps({**result['numerical_prompt'], 'reid_correspondence': result['reid']['correspondence'],
                      'reid_repairs': result['reid']['repair_entries'], 'hypothetical_scores': hypothetical,
                      'all_repair_entries': len(repairs), 'repair_dimensions': result['all_repairs']['by_dimension'],
                      'repair_change_counts': result['all_repairs']['by_change']}, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
