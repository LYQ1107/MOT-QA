"""Finalize the revised pool in separate versioned files; keep original900 intact."""
from collections import Counter, defaultdict
import copy
import json
import random
import time

import numpy as np

import generate_candidates_round2 as g
import readability_v3 as v
import finalize_candidates_round2 as f


def assign_slots(chosen, old):
    bypid = {q['pool_id']: q for q in old}
    kept = [q for q in chosen if q['pool_id'] in bypid]
    novel = [q for q in chosen if q['pool_id'] not in bypid]
    used_slots = {bypid[q['pool_id']]['qa_id'] for q in kept}
    free = [q for q in old if q['qa_id'] not in used_slots]
    assignments = {bypid[q['pool_id']]['qa_id']: q for q in kept}
    free.sort(key=lambda q: (q['qa_id'] not in v.HELD, q['qa_id']))
    for slot in free:
        def score(q):
            return (q['operation_name'] != slot['operation_name'],
                    q['dataset'] != slot['dataset'], q['format'] != slot['format'],
                    q['reference']['type'] != slot['reference']['type'],
                    q['template_id'] != slot['template_id'], q['pool_id'])
        q = min(novel, key=score)
        assignments[slot['qa_id']] = q
        novel.remove(q)
    assert not novel and len(assignments) == 900
    output = []
    for slot in old:
        q = assignments[slot['qa_id']]
        if q.get('preserve_reviewed_question'):
            prior = copy.deepcopy(slot)
            prior.update(video_input=q['video_input'], readability_v3=q['readability_v3'],
                         preserve_reviewed_question=True)
            q = prior
        q.update(qa_id=slot['qa_id']+'_v3', previous_slot_qa_id=slot['qa_id'],
                 previous_qa_id=bypid[q['pool_id']]['qa_id'] if q['pool_id'] in bypid else None,
                 replaces_qa_id=slot['qa_id'] if q['pool_id'] != slot['pool_id'] else None,
                 status='READABILITY_V3_CANDIDATE_PENDING_SUPPLEMENTARY_REVIEW')
        output.append(q)
    return output


def rebalance_option_letters(qs):
    groups = defaultdict(list)
    for q in qs:
        if q['format'] == 'multiple_choice':
            groups[q['operation_name'], q['dataset'], len(q['options']),
                   'image' if q.get('option_modality') == 'image' else 'text'].append(q)
    rng = random.Random(42)
    for _, rows in sorted(groups.items()):
        counts = Counter(q['answer'] for q in rows if q.get('preserve_reviewed_question'))
        letters = sorted(rows[0]['options'])
        for q in rows:
            if q.get('preserve_reviewed_question'):
                continue
            slot = min(letters, key=lambda x: (counts[x], x))
            counts[slot] += 1
            answer = q['answer']
            wrong = [k for k in q['options'] if k != answer]
            rng.shuffle(wrong)
            old_keys = wrong[:]
            old_keys.insert(letters.index(slot), answer)
            for field in ['options', 'options_zh', 'option_provenance', 'option_images']:
                if field in q:
                    values = q[field]
                    q[field] = {k: values[old_k] for k, old_k in zip(letters, old_keys)}
            q['answer'] = slot


def main():
    start = time.monotonic()
    old = g.rows(v.D/'before_revision/candidates_round2_original.jsonl')
    qs = assign_slots(g.rows(v.D/'selected.jsonl'), old)
    changed = [q for q in qs if not q.get('preserve_reviewed_question')]
    # Reuse the official public visual feature cache; no QA model or tracker runs.
    cache = g.RES
    keys = [tuple(x) for x in json.loads((cache/'feature_keys.json').read_text())]
    feats = dict(zip(keys, np.load(cache/'appearance_features.npy')))
    extra_cache = v.D/'features'
    if (extra_cache/'feature_keys.json').exists():
        extra_keys = [tuple(x) for x in json.loads((extra_cache/'feature_keys.json').read_text())]
        feats.update(zip(extra_keys, np.load(extra_cache/'appearance_features.npy')))
    requests = f.request_features(changed)
    missing = {(ds, seq, tid, frame) for (ds, seq, frame), ids in requests.items()
               for tid in ids} - feats.keys()
    work = []
    if missing:
        for q in changed:
            needed = f.request_features([q])
            if any((ds, seq, tid, frame) in missing for (ds, seq, frame), ids in needed.items() for tid in ids):
                work.append(q)
        f.D = v.D/'features'
        f.D.mkdir(exist_ok=True)
        feats.update(f.extract_features(work))
    f.RNG.seed(42)
    f.BOX_COUNTER.clear()
    finalized = f.finalize(changed, feats)
    byid = {q['qa_id']: q for q in finalized}
    for i, q in enumerate(qs):
        if q['qa_id'] in byid:
            qs[i] = byid[q['qa_id']]
        v.chinese_events(qs[i])
        if qs[i].get('preserve_reviewed_question'):
            qs[i]['review_history'] = {
                'previous_user_verdict': 'pass',
                'scope': 'unchanged question, reference, options and source facts; input window now explicit',
                'new_blanket_human_approval': False}
    rebalance_option_letters(qs)
    path = g.ROOT/'data/candidates_readability_v3.jsonl'
    g.putrows(path, qs)
    g.dump(v.D/'finalization_receipt.json', {
        'recorded_at': v.now(), 'candidate_file': str(path), 'candidate_sha256': v.sha(path),
        'n': len(qs), 'retained_original_facts': sum(q['previous_qa_id'] is not None for q in qs),
        'new_factual_candidates': sum(q['previous_qa_id'] is None for q in qs),
        'unchanged_reviewed_questions_preserved': sum(bool(q.get('preserve_reviewed_question')) for q in qs),
        'missing_public_feature_keys': len(missing),
        'public_feature_extraction_device': 'CPU' if missing else 'existing cache only',
        'seconds': time.monotonic()-start,
        'original_candidate_file_unchanged': True, 'QA_model_calls': 0, 'tracker_runs': 0})
    print('FINALIZED_V3', len(qs), path, flush=True)


if __name__ == '__main__':
    main()
