"""Import the 20-question human review and record the camera-motion design decision."""
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import copy
import hashlib
import json
import shutil

from question_design_eligibility import camera_motion_exclusion_reason

ROOT = Path('/home/user/motqa_pilot')
OUT = ROOT / 'results/question_review'
SOURCE = Path('/home/user/.codex/attachments/4b441354-4af7-48cf-a8e7-3e85e71432b3/question_review_result.json')
FEEDBACK = '这里面有三个不确定。原因都是因为相机会运动，也就是相机本身的摄像是移动的，没法判断里面的目标的具体移动距离'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def main():
    now = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
    data_path = ROOT / 'data/question_review_candidates_20.jsonl'
    config_path = ROOT / 'results/generation_config_locked.json'
    questions = [json.loads(x) for x in data_path.read_text().splitlines()]
    by_id = {q['qa_id']: q for q in questions}
    uploaded = json.loads(SOURCE.read_text())
    receipt_path = OUT / 'delivery_receipt.json'
    receipt = json.loads(receipt_path.read_text())
    original_hashes = {str(p): sha(p) for p in [data_path, config_path, ROOT/'results/review/reference_review_result_final.json']}
    assert uploaded['packet_id'] == receipt['packet_id']
    assert uploaded['questions_sha256'] == receipt['questions_sha256'] == sha(data_path)
    assert len(uploaded['reviews']) == len(by_id) == 20
    assert {r['qa_id'] for r in uploaded['reviews']} == set(by_id)
    counts = Counter(r['verdict'] or 'pending' for r in uploaded['reviews'])
    assert uploaded['counts'] == {'total': 20, **{k: counts[k] for k in ['pass', 'fail', 'uncertain', 'pending']}}
    for r in uploaded['reviews']:
        q = by_id[r['qa_id']]
        assert (r['dataset'], r['sequence'], r['question_zh'], r['operations'], r['reference_type']) == (
            q['dataset'], q['sequence'], q['question_zh'], q['operations'], q['reference']['type'])
    submissions = OUT / 'user_submissions'
    submissions.mkdir(exist_ok=True)
    original = submissions / f'20261105_question_review_result_{sha(SOURCE)[:12]}.json'
    if not original.exists():
        shutil.copyfile(SOURCE, original)
    assert sha(original) == sha(SOURCE)
    annotations = copy.deepcopy(uploaded)
    changes = []
    for r in annotations['reviews']:
        if r['verdict'] == 'uncertain':
            assert camera_motion_exclusion_reason(by_id[r['qa_id']]) is not None
            if not r['note']:
                r['note'] = '移动镜头下无法可靠判断人物自身移动距离；保留不确定，需替换或改题。'
                changes.append({'qa_id': r['qa_id'], 'field': 'note', 'before': '', 'after': r['note'],
                                'source': 'user_followup_verbatim'})
    annotations['followup_annotation'] = {
        'processed_at': now, 'original_file': str(original), 'original_sha256': sha(original),
        'user_followup_verbatim': FEEDBACK, 'changed_fields': changes,
        'verdicts_unchanged': True,
    }
    annotated = OUT / 'question_review_result_with_camera_notes.json'
    write(annotated, annotations)
    accepted, held = [], []
    for r in annotations['reviews']:
        q = copy.deepcopy(by_id[r['qa_id']])
        reason = camera_motion_exclusion_reason(q)
        q['human_design_review'] = {'verdict': r['verdict'], 'note': r['note'],
                                    'source_file': str(annotated), 'original_sha256': sha(original)}
        if r['verdict'] == 'pass' and reason is None:
            q['status'] = 'USER_PASSED_DESIGN_REVIEW_NOT_RELEASED'
            accepted.append(q)
        else:
            q['status'] = 'DESIGN_REVISION_REQUIRED'
            q['revision_reason'] = reason or 'human_review_not_passed'
            held.append(q)
    assert [q['review_index'] for q in held] == [4, 5, 17]
    assert len(accepted) == 17 and counts['pass'] == 17 and counts['uncertain'] == 3
    accepted_path = ROOT/'data/question_review_user_passed_17.jsonl'
    held_path = ROOT/'data/question_review_camera_revision_3.jsonl'
    for path, rows in [(accepted_path, accepted), (held_path, held)]:
        path.write_text(''.join(json.dumps(q, ensure_ascii=False) + '\n' for q in rows))
    policy = {
        'version': 'camera_motion_design_addendum_v1', 'status': 'APPLIED_TO_PRE_RELEASE_DESIGN_ELIGIBILITY',
        'recorded_at': now, 'source_config_sha256': sha(config_path), 'source_user_review_sha256': sha(original),
        'user_feedback_verbatim': FEEDBACK,
        'finding': 'Raw bbox-center path length is an image-coordinate measurement. Camera motion contributes to it; it does not identify a person’s physical distance travelled.',
        'main_pool_rule': 'Exclude cumulative image-path comparison questions, including compositions using that quantity, unless camera_motion is static. Non-static or unknown camera tags are held.',
        'O5_replacement_priority': 'Prefer temporal comparisons such as first-appearance/reappearance order on moving-camera videos, retaining the comparison/sorting operation.',
        'static_camera_wording': 'If retained, explicitly ask about cumulative movement of the box center in image coordinates, never physical/world distance.',
        'other_operations': 'Keep the 17 human-passed questions under their original image-plane/event meanings. Do not discard all moving-camera videos.',
        'numeric_GT_values_changed': False, 'human_verdicts_changed': False,
        'base_locked_config_changed': False, 'no_camera_compensated_or_world_distances_estimated': True,
        'replacement_questions_generated': 0,
    }
    write(OUT/'camera_motion_design_addendum_v1.json', policy)
    summary = {
        'processed_at': now, 'source_file': str(original), 'source_sha256': sha(original),
        'counts': uploaded['counts'], 'accepted_design_count': len(accepted), 'held_for_revision': len(held),
        'uncertain_indices': [q['review_index'] for q in held],
        'held_details': [{'qa_id': q['qa_id'], 'index': q['review_index'], 'dataset': q['dataset'],
                          'sequence': q['sequence'], 'operation': q['operation_name'],
                          'camera_motion': q['difficulty']['camera_motion'], 'reason': q['revision_reason']} for q in held],
        'accepted_design_file': str(accepted_path), 'held_file': str(held_path),
        'annotated_review_file': str(annotated), 'policy': str(OUT/'camera_motion_design_addendum_v1.json'),
        'original_questions_and_GT_unchanged': True, 'replacement_questions_generated': 0,
        'full_900_batch_completed': False, 'new_model_calls': 0, 'new_tracker_runs': 0,
    }
    write(OUT/'user_question_review_import_summary.json', summary)
    backup = submissions/'delivery_receipt_before_user_review.json'
    if not backup.exists():
        shutil.copyfile(receipt_path, backup)
    receipt.update({'status': 'USER_REVIEW_RECEIVED_17_PASS_3_REVISION_REQUIRED',
                    'actual_user_question_review_received': True, 'user_review_received_at': now,
                    'user_review_original': str(original), 'user_review_summary': str(OUT/'user_question_review_import_summary.json'),
                    'user_review_counts': uploaded['counts'], 'camera_motion_revision_required_indices': [4, 5, 17]})
    write(receipt_path, receipt)
    assert all(sha(Path(path)) == digest for path, digest in original_hashes.items())
    with (ROOT/'research_log.md').open('a') as f:
        f.write(f'\n## 完整题人工复核：移动镜头位移歧义 — {now}\n\n'
                '用户上传20题复核：17通过、0不通过、3不确定、0未选择。原始JSON按字节留存，名单/问题/哈希核对通过。'
                '用户明确三条不确定均因相机运动，核对为第4(Dance0019)、5(MOT17-11)、17(SportsG-v...)，全部O5累计位移比较且camera_motion=moving。'
                '原题虽限定画面内，GT计算仍是框中心的图像路径，不能代表人物实际走过的路程；数值重算通过不足以证明题面适合人工/模型推理。'
                '保留17条通过和3条不确定，不把不确定改成失败或通过。补充原因另存；17条进入已通过设计池，3条暂缓。'
                '记录生成前补充规则：主池累计图像路径比较只允许明确固定机位，移动/未知机位不纳入；O5优先换成首次出现/重现先后比较。'
                '其他移动机位题仍按原画面位置/事件含义保留，不移除整类视频，不修改锁定基础配置、原题、GT或答案。尚未生成替换3题与900题整批，无模型/跟踪器运行。\n')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
