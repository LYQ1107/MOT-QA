"""Prepare metadata-free tracker inputs and pre-register trackable questions."""
from collections import Counter, defaultdict
from datetime import datetime
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

from stage3_text import EVENT_RULES, EXPRESSIBLE, VISIBLE_FIELDS, classify, extract_targets, normalize_for_evaluation

ROOT = Path(__file__).resolve().parents[1]
DIMS = ['event_count', 'reappear_or_disappear', 'cross_object_order', 'event_ordering', 'reappear_identity']


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


def main():
    items = json.loads((ROOT / 'data/toc_bench/answer_final.json').read_text())['items']
    scope = [q for q in items if q['metadata']['dim'] in DIMS]
    assert len(scope) == 749
    inputs = [{k: q[k] for k in ('qa_id', 'video_id', 'format', *VISIBLE_FIELDS, 'events') if k in q} for q in scope]
    (ROOT / 'results/stage3_visible_inputs.jsonl').write_text(''.join(json.dumps(q, ensure_ascii=False) + '\n' for q in inputs))
    extracted = {q['qa_id']: dict(qa_id=q['qa_id'], video_id=q['video_id'], **extract_targets(q)) for q in inputs}
    # Persist predictions before opening any subject_label for evaluation.
    write_json(ROOT / 'results/stage3_extracted_queries.json', list(extracted.values()))
    rows, per_type, tasks = [], defaultdict(Counter), defaultdict(set)
    for q, visible in zip(scope, inputs):
        result = classify(visible)
        rows.append(dict(qa_id=q['qa_id'], video_id=q['video_id'], dimension=q['metadata']['dim'], **result))
        for kind in result['event_types']:
            per_type[kind][q['metadata']['dim']] += 1
        tasks[q['video_id']].update(extracted[q['qa_id']]['queries'])
    evaluation = []
    for q in scope:
        predicted = extracted[q['qa_id']]['queries']
        label = q['metadata']['subject_label']
        labels = label if isinstance(label, list) else [label]
        norm_predicted = {normalize_for_evaluation(p) for p in predicted}
        matches = [normalize_for_evaluation(label) in norm_predicted for label in labels]
        evaluation.append(dict(qa_id=q['qa_id'], dimension=q['metadata']['dim'], hallucination=q['metadata'].get('hallucination'),
                               subject_label=label, predicted=predicted, all_metadata_subjects_matched=all(matches),
                               matched_subjects=sum(matches), metadata_subjects=len(labels),
                               cross_object_two_targets=len(predicted) >= 2 if q['metadata']['dim'] == 'cross_object_order' else None))
    summary = dict(qa_count=749, main_qa_count=726, video_count=len(tasks),
                   main_video_count=len({q['video_id'] for q in scope if q['metadata']['dim'] != 'reappear_identity'}),
                   unique_video_query_pairs=sum(len(v) for v in tasks.values()),
                   queries_per_video=dict(Counter(len(v) for v in tasks.values())),
                   empty_extractions=[r['qa_id'] for r in extracted.values() if not r['queries']],
                   event_type_dimension_counts={k: dict(v) for k, v in per_type.items()},
                   trackable_count=sum(r['trackable'] for r in rows),
                   trackable_main_count=sum(r['trackable'] and r['dimension'] != 'reappear_identity' for r in rows),
                   trackable_per_dimension=dict(Counter(r['dimension'] for r in rows if r['trackable'])),
                   extraction_matched=sum(r['all_metadata_subjects_matched'] for r in evaluation),
                   extraction_evaluated=749,
                   extraction_mismatches=[r for r in evaluation if not r['all_metadata_subjects_matched']],
                   hallucination_evaluation={str(tag): {'matched': sum(r['all_metadata_subjects_matched'] for r in evaluation if r['hallucination'] == tag),
                                                       'total': sum(r['hallucination'] == tag for r in evaluation)}
                                            for tag in {r['hallucination'] for r in evaluation}},
                   cross_object_evaluation_note='subject_label names one anchor in this release; anchor recall is evaluable, complete two-object precision is not an independent ground-truth metric')
    write_json(ROOT / 'results/stage3_query_evaluation.json', {'summary': summary, 'rows': evaluation})
    write_json(ROOT / 'results/stage3_tracking_tasks.json', [dict(video_id=v, queries=sorted(q)) for v, q in sorted(tasks.items())])
    registration = dict(created_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
                        dataset_revision='da3065053d958c38151304e33a42e138b1899eaf',
                        input_fields=list(VISIBLE_FIELDS) + ['events.event_text'], metadata_used_for_classification=False,
                        classification='multi-label predicates from every visible text field; each type counted once per QA',
                        event_type_patterns=EVENT_RULES, expressible_types=sorted(EXPRESSIBLE),
                        inclusion_rule='all mentioned event types must be expressible; any partly hidden/state change/other excludes the QA',
                        caveat='expressible means box/visibility/position proxies are available; it does not guarantee detector coverage, correct identity or physically verified occlusion',
                        freeze_before_stage_four=True, summary={k: summary[k] for k in ('qa_count','main_qa_count','video_count','trackable_count','trackable_main_count','trackable_per_dimension','event_type_dimension_counts')},
                        trackable_qa_ids=sorted(r['qa_id'] for r in rows if r['trackable']), rows=rows)
    draft = ROOT / 'results/trackable_subset_draft.json'
    write_json(draft, registration)
    if '--freeze' in sys.argv:
        assert not summary['empty_extractions']
        assert not any('other' in r['event_types'] for r in rows)
        path = ROOT / 'results/trackable_subset_preregistered.json'
        with path.open('x') as f:
            f.write(json.dumps(registration, indent=2, ensure_ascii=False) + '\n')
        path.chmod(0o444)
    write_json(ROOT / 'results/stage3_scope_summary.json', summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
