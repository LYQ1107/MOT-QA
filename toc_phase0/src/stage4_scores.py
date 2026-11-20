"""Offline scoring only. Labels are never imported by the inference runner."""
from collections import Counter
from stage4_common import ROOT, LEGAL, read, rows, write, write_rows, now
from compute_metrics import is_correct, compute_one_model

DIMENSIONS = ('event_count', 'reappear_or_disappear', 'cross_object_order',
              'event_ordering', 'reappear_identity')


def inputs():
    visible = rows(ROOT / 'results/stage3_visible_inputs.jsonl')
    ids = {q['qa_id'] for q in visible}
    items = sorted([q for q in read(ROOT / 'data/toc_bench/answer_final.json')['items']
                    if q['qa_id'] in ids], key=lambda q: q['qa_id'])
    split = read(ROOT / 'results/dev_test_split_locked.json')
    trackable = set(read(ROOT / 'results/trackable_subset_preregistered.json')['trackable_qa_ids'])
    scopes = dict(full=items,
                  dev=[q for q in items if q['qa_id'] in set(split['dev_qa_ids'])],
                  test=[q for q in items if q['qa_id'] in set(split['test_qa_ids'])])
    assert len(items) == 749 and len(scopes['test']) == 602
    return scopes, trackable


def groups(items, trackable):
    result = dict(all=items,
                  main=[q for q in items if q['metadata']['dim'] != 'reappear_identity'],
                  trackable=[q for q in items if q['qa_id'] in trackable],
                  main_trackable=[q for q in items if q['qa_id'] in trackable and q['metadata']['dim'] != 'reappear_identity'])
    for dimension in DIMENSIONS:
        result['dimension:' + dimension] = [q for q in items if q['metadata']['dim'] == dimension]
        result['trackable_dimension:' + dimension] = [q for q in result['dimension:' + dimension] if q['qa_id'] in trackable]
    return result


def summarize(items, predictions):
    assert all(q['qa_id'] in predictions for q in items)
    n = len(items)
    correct = sum(is_correct(predictions[q['qa_id']]['extracted_answer'], q) for q in items)
    failures = sum(predictions[q['qa_id']]['extracted_answer'] is None for q in items)
    covered = sum(predictions[q['qa_id']].get('covered', True) for q in items)
    numerical = [q for q in items if q['format'] == 'numerical']
    legal = sum((predictions[q['qa_id']].get('raw_response') or '').strip() in LEGAL for q in numerical)
    return dict(total=n, correct=correct, accuracy=correct / n if n else None,
                covered=covered, coverage=covered / n if n else None,
                accuracy_covered=correct / covered if covered else None,
                parse_failures=failures, parse_failure_rate=failures / n if n else None,
                numerical_total=len(numerical), numerical_legal=legal,
                numerical_legal_ratio=legal / len(numerical) if numerical else None)


def score_all(predictions):
    scopes, trackable = inputs()
    return {scope: {name: summarize(items, predictions) for name, items in groups(qa, trackable).items()}
            for scope, qa in scopes.items()}


def route(fallback_path, name):
    rules = {p['qa_id']: p for p in rows(ROOT / 'results/v1_rule_predictions.jsonl')}
    fallback = {p['qa_id']: p for p in rows(fallback_path)}
    scopes, _ = inputs()
    result = []
    for item in scopes['full']:
        qid = item['qa_id']
        source = rules[qid] if rules[qid]['covered'] else fallback[qid]
        result.append(dict(qa_id=qid, format=item['format'], raw_response=source['raw_response'],
                           extracted_answer=source['extracted_answer'], error=None,
                           routing_source='frozen_rule' if rules[qid]['covered'] else name,
                           rule_covered=rules[qid]['covered']))
    path = ROOT / f'results/stage4/routing_{name}_predictions.jsonl'
    write_rows(path, result)
    write(ROOT / f'results/stage4/routing_{name}_metrics.json', dict(
        generated_at=now(), policy='Use frozen rule whenever covered, including illegal or unparsable rule answers; otherwise use fallback.',
        fallback_source=str(fallback_path), metrics=score_all({p['qa_id']: p for p in result})))
    return result


def development_count_confusion():
    scopes, _ = inputs()
    items = [q for q in scopes['dev'] if q['format'] == 'numerical']
    rules = {p['qa_id']: p for p in rows(ROOT / 'results/v1_rule_predictions.jsonl')}
    labels = ('0', '1', *LEGAL, 'abstain', 'other')
    matrix = {gt: {prediction: 0 for prediction in labels} for gt in LEGAL}
    directions = Counter()
    records = []
    for item in items:
        p = rules[item['qa_id']]
        raw = p['raw_response']
        bucket = 'abstain' if not p['covered'] else raw if raw in labels else 'other'
        gt = str(item['correct_answer'])
        matrix[gt][bucket] += 1
        if bucket == 'abstain':
            direction = 'uncovered'
        elif bucket in ('other',):
            direction = 'unclassifiable'
        else:
            pred_n = 5 if bucket == '5 or more' else int(bucket)
            gt_n = 5 if gt == '5 or more' else int(gt)
            direction = 'same_bucket' if pred_n == gt_n else 'undercount' if pred_n < gt_n else 'overcount'
        directions[direction] += 1
        records.append(dict(qa_id=item['qa_id'], truth=gt, prediction=raw, covered=p['covered'],
                            raw_rule_count=p.get('raw_rule_count'), direction=direction))
    result = dict(generated_at=now(), scope='dev only; diagnostic, no further tuning',
                  total=len(items), truth_rows=list(LEGAL), prediction_columns=list(labels),
                  confusion_matrix=matrix, error_direction=dict(directions), records=records,
                  top_coding='5 or more is one bucket; same_bucket does not imply exact unbounded count.')
    write(ROOT / 'results/stage4/dev_count_rule_confusion.json', result)
    return result
