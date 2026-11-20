"""Quota selection from the pre-screened pool, favoring valid original items."""
from collections import Counter, defaultdict
import copy
import json

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

import generate_candidates_round2 as g
import readability_v3 as v
from select_candidates_round2 import Constraints, classof


def select(pool, exact_events=True):
    old = g.rows(v.D/'before_revision/candidates_round2_original.jsonl')
    old_ids = {q['pool_id'] for q in old}
    groups = defaultdict(list)
    for q in pool:
        groups[(q['dataset'], q['sequence'], q['operation_name'], q['reference']['type'],
                q['format'], q['evidence']['gt_detail'].get('subtype', ''), classof(q))].append(q)
    reduced = []
    for key, rows in sorted(groups.items(), key=lambda x: str(x[0])):
        keep = [q for q in rows if q['pool_id'] in old_ids]
        byid = defaultdict(list)
        for q in rows:
            if q['pool_id'] not in old_ids:
                byid[q['reference']['primary_target_id']].append(q)
        extras = []
        while byid:
            for tid in list(byid):
                extras.append(byid[tid].pop())
                if not byid[tid]:
                    del byid[tid]
        reduced.extend(keep + extras[:30 if key[3] in ['appearance', 'event'] else 18])
    pool = reduced
    n = len(pool)
    c = Constraints(n)
    by = defaultdict(list)
    for i, q in enumerate(pool):
        op, ds = q['operation_name'], q['dataset']
        rr, e = q['reference'], q['evidence']
        d = e['gt_detail']
        for key in [('op', op), ('dataset', ds), ('video', ds, q['sequence']),
                    ('identity', ds, q['sequence'], rr['primary_target_id']), ('ref', rr['type'])]:
            by[key].append(i)
        if q['format'].startswith('numeric'):
            by['numeric', op].append(i)
        if q['difficulty']['identity_challenge']:
            by['hard',].append(i)
        if q['has_confusion_option']:
            by['conf',].append(i)
        if q['format'] == 'multiple_choice':
            by['choice',].append(i)
        if op == 'O7':
            by['O7_exists', bool(d['event_exists'])].append(i)
        if op != 'O7' and q['semantic_answer'] == g.NEVER:
            by['ordinary_never',].append(i)
        if op == 'O8' and d['subtype'] == 'same_person_yes_no':
            by['O8_same',].append(i)
            by['O8_same_answer', q['answer_index']].append(i)
        if q.get('option_modality') == 'image':
            by['image_choice',].append(i)
        key = ('duplicate', ds, q['sequence'], op, rr['primary_target_id'],
               rr['persons'][0]['frame'], e['query_start_frame'], e['query_end_frame'],
               q['template_id'], d.get('ordinal'), d.get('marked_query_target'))
        by[key].append(i)
        if q.get('preserve_reviewed_question'):
            c.add([i], 1, 1, 'preserve unchanged human reviewed ' + str(q['pool_id']))
    for op, target in g.CFG['candidate_operation_targets'].items():
        c.add(by['op', op], target, target, 'operation ' + op)
    for ds, target in g.CFG['realized_dataset_targets'].items():
        c.add(by['dataset', ds], target, target, 'dataset ' + ds)
    for key, indices in by.items():
        if key[0] == 'video':
            c.add(indices, 0, 20, str(key))
        elif key[0] == 'identity':
            c.add(indices, 0, 3, str(key))
        elif key[0] == 'duplicate' and len(indices) > 1:
            c.add(indices, 0, 1, str(key))
    c.add(by['ref', 'event'], 225 if exact_events else 0, 225, 'event reference target or authorized box fallback')
    c.add(by['ref', 'position'], 135, 135, 'position references')
    c.add(by['ref', 'appearance'], 0, 135, 'approved appearance maximum')
    for op, target in [('O3', 40), ('O4', 70), ('O5', 70)]:
        c.add(by['numeric', op], target, target, 'numeric ' + op)
    c.add(by['hard',], 540, np.inf, 'identity challenge >=60%')
    c.add(by['conf',]+by['choice',], 0, np.inf, 'confusion >=70% of choices',
          values=[1.]*len(by['conf',])+[-.7]*len(by['choice',]))
    c.add(by['O7_exists', True], 55, 55, 'O7 true')
    c.add(by['O7_exists', False], 55, 55, 'O7 false')
    c.add(by['ordinary_never',], 40, 40, 'ordinary never about5%')
    c.add(by['O8_same',], 60, 60, 'O8 same person')
    for value in [0, 1]:
        c.add(by['O8_same_answer', value], 30, 30, 'O8 same answer '+str(value))
    image_target = 45 if len(by['image_choice',]) >= 45 else 0
    c.add(by['image_choice',], image_target, image_target, 'optional crop questions')
    bal = defaultdict(list)
    pooled = defaultdict(list)
    for i, q in enumerate(pool):
        cl = classof(q)
        if cl is not None:
            bal[q['template_id'], q['format'], q['dataset']].append((i, cl))
            pooled[q['template_id'], q['format']].append((i, cl))
    for key, vals in bal.items():
        fam, fmt, ds = key
        allii = [i for i, _ in vals]
        classes = sorted({cl for _, cl in vals})
        if fam in ['return_region', 'premise_return_time']:
            none = [i for i, cl in vals if cl == '3']
            c.add(none+allii, -1, 1, 'O7 half false '+ds,
                  values=[1.]*len(none)+[-.5]*len(allii))
            positive = [i for i, cl in vals if cl != '3']
            for cl in ['0', '1', '2']:
                ii = [i for i, a in vals if a == cl]
                c.add(ii+positive, -1, 1, 'O7 region '+ds+cl,
                      values=[1.]*len(ii)+[-1/3]*len(positive))
        elif fam in ['region', 'left_pair', 'cross_region', 'identity_same']:
            fraction = .5 if fam in ['left_pair', 'identity_same'] else 1/3
            for cl in classes:
                ii = [i for i, a in vals if a == cl]
                c.add(ii+allii, -1, 1, 'balanced '+str(key)+cl,
                      values=[1.]*len(ii)+[-fraction]*len(allii))
        else:
            for cl in classes:
                ii = [i for i, a in vals if a == cl]
                c.add(ii+allii, -np.inf, 1, 'majority cap '+str(key)+cl,
                      values=[1.]*len(ii)+[-.35]*len(allii))
        if fam in ['return_time', 'earliest_return_person', 'cross_count']:
            mode = '2' if fam == 'cross_count' else '3'
            modal = [i for i, cl in vals if cl == mode]
            for cl in classes:
                if cl == mode:
                    continue
                ii = [i for i, a in vals if a == cl]
                c.add(ii+modal, -np.inf, 0, 'shared semantic mode '+str(key)+cl,
                      values=[1.]*len(ii)+[-1.]*len(modal))
    for (fam, fmt), vals in pooled.items():
        if fam not in ['return_time', 'earliest_return_person', 'cross_count']:
            continue
        allii = [i for i, _ in vals]
        for cl in sorted({a for _, a in vals}):
            ii = [i for i, a in vals if a == cl]
            c.add(ii+allii, -np.inf, 0, 'strict pooled semantic cap '+fam+fmt+cl,
                  values=[1.]*len(ii)+[-.35]*len(allii))
    # O6 mixes portrait choices, time bins and integer counts. Keep subtype/source
    # concentration from making the parent-operation source-only baseline exceed5pp.
    for ds in ['DanceTrack', 'SportsMOT', 'MOT17']:
        image = [i for i, q in enumerate(pool) if q['operation_name'] == 'O6'
                 and q['dataset'] == ds and q.get('option_modality') == 'image']
        semantic_groups = defaultdict(list)
        for i, q in enumerate(pool):
            if q['operation_name'] != 'O6' or q['dataset'] != ds or q.get('option_modality') == 'image':
                continue
            label = ('time_bin', q['answer_index']) if q['template_id'] in ['cross_time', 'closest_time'] else ('count', q['semantic_answer'])
            semantic_groups[label].append(i)
        for label, indices in semantic_groups.items():
            c.add(indices+image, -np.inf, 1, 'O6 parent semantic source cap '+ds+str(label),
                  values=[1.]*len(indices)+[-.25]*len(image))
    rng = np.random.default_rng(42)
    objective = rng.uniform(0, .001, n) + np.array([
        -20.*(q['pool_id'] in old_ids) - 2.*(q['reference']['type'] == 'appearance')
        - (.1 if not exact_events else 0.)*(q['reference']['type'] == 'event')
        + .15*(not q['has_confusion_option']) + .03*(not q['difficulty']['identity_challenge'])
        for q in pool])
    a = c.matrix()
    suffix = 'events225' if exact_events else 'event_box_fallback'
    g.dump(v.D/f'selection_constraints_{suffix}.json', {
        'n_variables': n, 'n_constraints': len(c.lb), 'constraint_names': c.names,
        'prioritize_retaining_eligible_original_questions': True,
        'preserve_unchanged_user_passed_questions': True,
        'event_reference_exact_target': exact_events})
    print('V3_MILP_START', suffix, n, len(c.lb), flush=True)
    solution = milp(objective, integrality=np.ones(n), bounds=Bounds(0, 1),
                    constraints=LinearConstraint(a, c.lb, c.ub),
                    options={'time_limit': 240, 'mip_rel_gap': .01})
    g.dump(v.D/f'selection_solver_{suffix}.json', {
        'status': int(solution.status), 'message': solution.message,
        'fun': solution.fun, 'mip_gap': getattr(solution, 'mip_gap', None)})
    if solution.x is None:
        return None
    ix = np.flatnonzero(solution.x > .5)
    residual = a @ np.round(solution.x)
    assert np.all(residual >= np.array(c.lb)-1e-6) and np.all(residual <= np.array(c.ub)+1e-6)
    return [copy.deepcopy(pool[i]) for i in ix]


def main():
    enriched = v.D/'eligible_pool_enriched.jsonl'
    pool = g.rows(enriched if enriched.exists() else v.D/'eligible_pool.jsonl')
    language_revisions = []
    for q in pool:
        if q.get('preserve_reviewed_question'):
            translated = copy.deepcopy(q)
            v.chinese_events(translated)
            if [p['text_zh'] for p in q['reference']['persons']] != [p['text_zh'] for p in translated['reference']['persons']]:
                q['preserve_reviewed_question'] = False
                language_revisions.append(q['previous_qa_id'])
    g.dump(v.D/'reviewed_reference_translation_revisions.json', {
        'qa_ids': language_revisions,
        'reason': 'Preserve original user decisions, but a changed event-reference translation requires revision rather than claiming unchanged.'})
    chosen = select(pool)
    if chosen is None:
        # This fallback was declared in the lock and explicitly authorized by the user.
        chosen = select(pool, exact_events=False)
    if chosen is None:
        raise RuntimeError('No900 selection satisfies the locked quality and balance gates; report shortage, do not weaken criteria.')
    chosen.sort(key=lambda q: (q['dataset'], q['sequence'], q['pool_id']))
    g.putrows(v.D/'selected.jsonl', chosen)
    g.dump(v.D/'selection_summary.json', {
        'n': len(chosen), 'operations': dict(Counter(q['operation_name'] for q in chosen)),
        'datasets': dict(Counter(q['dataset'] for q in chosen)),
        'references': dict(Counter(q['reference']['type'] for q in chosen)),
        'retained_original_pool_ids': sum('previous_qa_id' in q for q in chosen),
        'preserved_reviewed': sum(q.get('preserve_reviewed_question', False) for q in chosen)})
    print('V3_SELECTED', len(chosen), flush=True)


if __name__ == '__main__':
    main()
