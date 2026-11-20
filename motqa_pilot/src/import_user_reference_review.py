"""Import human decisions and apply the user's explicit bulk follow-up."""
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import copy
import hashlib
import json
import re
import shutil

ROOT = Path('/home/user/motqa_pilot')
OUT = ROOT / 'results/review'
SOURCE = Path('/home/user/.codex/attachments/38bf204f-87c6-4c66-988f-5960cfbcc011/reference_review_result.json')
FOLLOWUP = '剩下的我没有写的也都是同样的问题'
REASON = '描述过于笼统，多人符合，无法唯一指认'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def counts(rows):
    c = Counter(r['verdict'] or 'pending' for r in rows)
    return {'total': len(rows), **{k: c[k] for k in ['pass', 'fail', 'uncertain', 'pending']},
            'completed': len(rows) - c['pending']}


def sports_gate(rows):
    c = counts([r for r in rows if r['group'] == 'sports_lamot_stratified'])
    assert c['total'] == 40
    return {'sample_n': 40, 'completed': c['completed'], 'passed': c['pass'],
            'pass_rate': c['pass'] / 40,
            'status': 'PENDING' if c['pending'] else 'ALLOW_INDIVIDUALLY_PASSED_ONLY'
            if c['pass'] >= 28 else 'DISABLE_ALL_SPORTSMOT_APPEARANCE'}


def main():
    now = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
    selection_path = OUT / 'reference_review_selection_locked.json'
    config_path = ROOT / 'results/generation_config_locked.json'
    visibility_path = ROOT / 'results/visibility_convention.json'
    locked = {str(p): sha(p) for p in [selection_path, config_path, visibility_path]}
    selection = json.loads(selection_path.read_text())
    uploaded = json.loads(SOURCE.read_text())
    legacy = OUT / 'history/compact_delivery_revision/reference_review_embedded_v1.html'
    packet = json.loads(re.search(
        r'<script id="review-payload" type="application/json">([\s\S]*?)</script>',
        legacy.read_text()).group(1))
    assert uploaded['packet_id'] == selection['packet_id']
    assert uploaded['selection_sha256'] == sha(selection_path)
    assert uploaded['generation_config_sha256'] == sha(config_path)
    assert uploaded['seed'] == selection['seed'] == 42
    assert len(uploaded['reviews']) == len(selection['cases']) == 154
    originals = {c['review_id']: c for c in packet['cases']}
    assert len({r['review_id'] for r in uploaded['reviews']}) == 154
    for r in uploaded['reviews']:
        assert {k: v for k, v in r.items() if k not in {'verdict', 'note'}} == originals[r['review_id']]
        assert r['verdict'] in {None, 'pass', 'fail', 'uncertain'}
    raw_counts = {scope: counts([r for r in uploaded['reviews'] if r['review_scope'] == scope])
                  for scope in ['main', 'additional']}
    assert uploaded['counts'] == raw_counts
    assert uploaded['sports_appearance_gate'] == sports_gate(uploaded['reviews'])
    submission_dir = OUT / 'user_submissions'
    submission_dir.mkdir(exist_ok=True)
    archived = submission_dir / f'20261105_reference_review_result_{sha(SOURCE)[:12]}.json'
    if not archived.exists():
        shutil.copyfile(SOURCE, archived)
    assert sha(archived) == sha(SOURCE)

    final = copy.deepcopy(uploaded)
    changes, conflicts = [], []
    for row in final['reviews']:
        before = {'verdict': row['verdict'], 'note': row['note']}
        rule = None
        if row['verdict'] is None:
            row['verdict'] = 'fail'
            row['note'] = row['note'] or REASON
            rule = 'user_bulk_followup_for_unselected_rows'
        elif row['verdict'] == 'pass' and any(s in row['note'] for s in ['多人', '不唯一', '歧义']):
            conflicts.append({'index': row['index'], 'review_id': row['review_id'],
                              'original_verdict': 'pass', 'original_note': row['note']})
            row['verdict'] = 'fail'
            rule = 'user_explicit_ambiguity_note_and_single_person_criterion'
        elif row['verdict'] == 'fail' and not row['note']:
            row['note'] = REASON
            rule = 'user_bulk_followup_supplies_missing_failure_reason'
        if rule:
            changes.append({'index': row['index'], 'review_id': row['review_id'], 'rule': rule,
                            'before': before, 'after': {'verdict': row['verdict'], 'note': row['note']}})
    final['exported_at'] = now
    final['counts'] = {scope: counts([r for r in final['reviews'] if r['review_scope'] == scope])
                       for scope in ['main', 'additional']}
    final['main_complete'] = final['counts']['main']['pending'] == 0
    final['sports_appearance_gate'] = sports_gate(final['reviews'])
    final['adjudication'] = {
        'processed_at': now, 'original_exported_at': uploaded['exported_at'],
        'original_file': str(archived), 'original_sha256': sha(SOURCE),
        'user_followup_verbatim': FOLLOWUP,
        'interpretation': 'Apply the user follow-up to all unselected rows and missing reasons on existing failures; retain unambiguous explicit passes and existing uncertain decisions. Resolve pass/ambiguity-note conflicts as failed single-person references.',
        'changes_file': str(OUT / 'reference_review_adjudication_changes.json'),
        'new_independent_visual_review': False,
    }
    final_path = OUT / 'reference_review_result_final.json'
    write(final_path, final)
    shutil.copyfile(final_path, OUT / 'reference_review_result.json')
    write(OUT / 'reference_review_adjudication_changes.json', {
        'processed_at': now, 'source_sha256': sha(SOURCE),
        'user_followup_verbatim': FOLLOWUP, 'changes': changes})

    manifest = {c['review_id']: c for c in selection['cases']}
    translations = json.loads((ROOT / 'src/reference_review_translations_zh.json').read_text())['translations']
    approved, eligible, held = [], [], []
    for r in final['reviews']:
        if r['verdict'] != 'pass':
            continue
        c = manifest[r['review_id']]
        entry = {**c, 'text_zh': translations[c['text']], 'user_verdict': 'pass', 'user_note': r['note'],
                 'review_result_sha256': sha(final_path), 'human_decision_source': str(final_path)}
        approved.append(entry)
        reasons = []
        if c['dataset'] == 'SportsMOT' and final['sports_appearance_gate']['status'] != 'ALLOW_INDIVIDUALLY_PASSED_ONLY':
            reasons.append('sports_dataset_gate_not_passed')
        if not c['review_frame_quality']['future_3s']:
            reasons.append('less_than_3s_after_locked_review_instant')
        if reasons:
            held.append({**entry, 'generation_hold_reasons': reasons})
        else:
            eligible.append(entry)
    for name, rows in [('appearance_reference_user_passed.jsonl', approved),
                       ('appearance_reference_pool_user_verified.jsonl', eligible),
                       ('appearance_reference_generation_holds.jsonl', held)]:
        (OUT / name).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))
    summary = {
        'processed_at': now, 'original_file': str(archived), 'original_sha256': sha(SOURCE),
        'result': str(final_path), 'result_sha256': sha(final_path), 'input': counts(uploaded['reviews']),
        'final': counts(final['reviews']),
        'by_dataset': {ds: counts([r for r in final['reviews'] if r['dataset'] == ds])
                       for ds in sorted({r['dataset'] for r in final['reviews']})},
        'raw_explicit_ambiguity_notes': dict(Counter(r['dataset'] for r in uploaded['reviews']
                                                  if any(s in r['note'] for s in ['多人', '不唯一', '歧义']))),
        'pass_note_conflicts_resolved': conflicts, 'changed_decisions': sum(c['before']['verdict'] != c['after']['verdict'] for c in changes),
        'bulk_pending_to_fail': sum(c['before']['verdict'] is None for c in changes),
        'sports_appearance_gate': final['sports_appearance_gate'],
        'human_passed_descriptions': len(approved),
        'generation_eligible_descriptions': len(eligible),
        'generation_eligible_by_dataset': dict(Counter(c['dataset'] for c in eligible)),
        'generation_holds': [{'index': r['index'], 'dataset': r['dataset'],
                              'reasons': r['generation_hold_reasons']} for r in held],
        'MOT20_in_this_packet': False,
        'phrase_policy': 'Non-unique descriptions are excluded from single-person appearance references. Do not convert one bound GT ID to a semantic group. Appearance shortfall transfers to box references under the locked configuration.',
        'locked_files_sha256': locked, 'qa_generated': 0, 'new_model_calls': 0, 'new_tracker_runs': 0,
    }
    write(OUT / 'user_review_import_summary.json', summary)
    assert all(sha(Path(p)) == digest for p, digest in locked.items())
    assert summary['final'] == {'total': 154, 'pass': 51, 'fail': 101, 'uncertain': 2, 'pending': 0, 'completed': 154}
    assert summary['sports_appearance_gate']['passed'] == 29
    assert len(approved) == 51 and len(eligible) == 47 and len(held) == 4

    handoff_path = OUT / 'handoff_receipt.json'
    handoff = json.loads(handoff_path.read_text())
    write(submission_dir / 'handoff_before_user_import.json', handoff)
    handoff.update({'status': 'USER_REFERENCE_REVIEW_RECONCILED', 'actual_user_review_received': True,
                    'user_review_result': str(final_path), 'user_review_summary': str(OUT / 'user_review_import_summary.json'),
                    'user_review_processed_at': now, 'user_review_counts': summary['final'],
                    'sports_appearance_gate': final['sports_appearance_gate'], 'qa_generated': 0})
    write(handoff_path, handoff)
    with (ROOT / 'research_log.md').open('a') as f:
        f.write(f'\n## 人工复核导入与用户批量补充 — {now}\n\n'
                f'原始上传JSON完整留存：{archived.name}，SHA256 {sha(SOURCE)}。名单、原文、时刻与锁定包一致。'
                '原文件54通过/40不通过/2不确定/58未选择。用户补充“剩下的我没有写的也都是同样的问题”，据此将58未选择项记为多人歧义不通过；'
                'Sports第62/64/68条原勾通过但备注明确多人符合，按用户备注和单人唯一性标准整理为不通过；原勾选未被抹去，所有更改另存逐条依据。'
                '最终51通过/101不通过/2不确定。MOT17的68条均不通过，本包无MOT20。Sports29/40=72.5%，达到70%门槛，只允许逐条通过项。'
                '51条人工通过中4条Sports固定时刻后不足3秒，保留通过决定但不能用于正式出题；当前可用外观指代47条（Dance22/Sports25）。'
                '不唯一描述不从单个绑定ID外推成多人集合，外观缺口按既定规则转框标指代。锁定配置、名单、源数据不变；本轮仅整理人工反馈，尚未生成QA或调用模型/跟踪器。\n')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
