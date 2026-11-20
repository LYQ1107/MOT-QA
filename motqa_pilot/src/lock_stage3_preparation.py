"""Record the user's Stage 2 decisions and Stage 3 amendment; no QA generation."""
from pathlib import Path
import hashlib
import json
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path('/home/user/motqa_pilot')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    now = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
    visibility = ROOT / 'results/visibility_convention.json'
    config_path = ROOT / 'results/generation_config_locked.json'
    assert not config_path.exists(), 'Already locked; do not overwrite.'
    previous = visibility.read_bytes()
    old = json.loads(previous)
    assert old['threshold'] == 0.25
    history = ROOT / 'results/review/history'
    history.mkdir(parents=True, exist_ok=True)
    (history / 'visibility_convention_before_lock.json').write_bytes(previous)
    old_sidecar = visibility.with_suffix('.sha256')
    if old_sidecar.exists():
        (history / 'visibility_convention_before_lock.sha256').write_bytes(old_sidecar.read_bytes())
    old['status'] = 'LOCKED'
    old['locked_at'] = now
    old['lock_reason'] = '沿用任务预设，未依据 QA 结果调参'
    old['threshold_recommendation'] = 'User confirmed 0.25; now locked.'
    old['previous_sha256'] = hashlib.sha256(previous).hexdigest()
    write(visibility, old)
    old_sidecar.write_text(sha(visibility) + '  visibility_convention.json\n')

    config = {
        'version': 'stage3_user_amendment_v1', 'status': 'LOCKED', 'locked_at': now,
        'project_root': str(ROOT), 'seed': 42,
        'authorization': 'Latest user supplement overrides conflicting original MOT-QA task requirements.',
        'current_action': 'Prepare human appearance review and audit tracker documentation; stop before any QA generation.',
        'visibility_convention': {'path': str(visibility), 'sha256': sha(visibility), 'status': 'LOCKED'},
        'time_display_decimals': 3,
        'source_scope': {'DanceTrack': 'val only', 'SportsMOT': 'val only',
                         'MOT17': 'each train sequence frames floor(N/2)+1..N; original timestamps retained',
                         'manifest': str(ROOT/'results/provisional_source_eligibility.json'),
                         'tracker_train_tune_overlap': 'requires selected complete detector/association/ReID pipeline audit'},
        'candidate_target_n': 900,
        'dataset_target_fraction': {'DanceTrack': 0.40, 'SportsMOT': 0.40, 'MOT17': 0.20},
        'mot17_shortage': {'minimum_fraction': 0.15, 'transfer_shortfall_to': 'SportsMOT',
                          'report_actual_counts_and_reason': True},
        'reference_target_fraction': {'box': 0.45, 'event': 0.25, 'appearance': 0.15, 'position': 0.15},
        'appearance_shortage_fallback': 'transfer all shortage to box; no additional model-generated descriptions',
        'reference_box': {
            'in_frame_area_fraction_min': 0.95, 'max_other_box_cover_fraction': 0.35,
            'cover_definition': 'maximum intersection / target-box area over another GT person, matching Stage 2 appearance supplement',
            'min_width_px': 16, 'min_height_px': 48, 'min_future_video_s': 3.0,
            'other_people_iou_strictly_greater_than': 0.3, 'max_other_people_above_iou': 1,
            'native_resolution': True, 'red_rgb': [255, 0, 0], 'line_width_px': 3,
            'draw_ids': False, 'draw_other_boxes': False,
            'image_template': 'data/ref_frames/{qa_id}.jpg', 'jpeg_quality': 95,
            'coordinate_field': 'reference.box_xyxy_normalized',
            'coordinate_definition': 'clipped continuous xyxy pixel edges divided by frame width,height; retain raw GT box in evidence',
            'reference_type': 'box', 'needs_visual_grounding': True,
            'image_insert': 'after_frames',
            'text_template': 'the person marked with the red box at {t_ref_s:.3f} s',
            'evaluation_implementation': 'later stage; add one labeled reference image after video frames and state its timestamp',
        },
        'target_identity_reuse': {'max_questions_per_identity': 3,
                                  'key': ['dataset', 'sequence', 'gt_id'],
                                  'scope': 'all reference types and operations combined; count every explicitly targeted person'},
        'appearance_review': {
            'page': 'results/review/reference_review.html', 'result_filename': 'reference_review_result.json',
            'all_formal_appearance_requires_user_pass': True,
            'main_groups': {'dance_flagged_vlm': 8, 'dance_original_refer': 21,
                            'sports_lamot_stratified': 40, 'mot17_lamot': 68},
            'additional_group': {'dance_agent_cleared_vlm': 17,
                                'reason': 'Include in collapsed section to apply final user-pass-only instruction also to the 17 previously agent-cleared phrases.'},
            'accepted_values': ['pass', 'fail', 'uncertain'], 'default': None,
            'phrase_policy': 'review exact original text; notes do not automatically rewrite or approve another phrase',
            'sports_dataset_gate': {'sample_n': 40, 'all_40_decisions_required': True,
                                   'pass_rate_min': 0.70,
                                   'denominator': 'all 40 selected rows, including fail and uncertain',
                                   'below_threshold': 'disable ALL SportsMOT appearance references; use box instead',
                                   'above_threshold': 'only individually user-passed reviewed descriptions; no extrapolation to unreviewed rows'},
            'scope_of_pass': 'specific phrase + sequence + target + verified reference frame; no interval-wide extrapolation',
            'start_generation_gate': 'wait for user-uploaded exported result; unresolved or unreviewed phrases never count as passed',
        },
        'operation_dataset_limits': {
            'MOT17': {
                'O3_allowed': 'only same-ID internal gaps classified as occlusion followed by reappearance; no frame-exit return questions',
                'O3_forbidden': 'questions whether a person returns after leaving the frame',
                'O4_allowed': 'window-local count of ID first appearances/entries, without same-person second entry within the window',
                'O4_identity_scope': 'within_id',
                'O4_no_cross_exit_reentry_dedup': True,
                'O4_conservative_window_policy': 'exclude a counting window with observed exits/re-entry ambiguity; do not label different IDs as different natural persons across exit/re-entry',
            },
            'SportsMOT': {
                'forbidden': 'occluded versus left-the-frame disappearance-cause questions',
                'reason': 'GT retains occluded people; disappearance cause strongly predicts dataset source',
            },
            'DanceTrack': {
                'same_id_after_full_occlusion': 'guaranteed by publisher',
                'O3_exit_return_precheck': 'inspect all same-sequence exit and new-ID first-appearance events for spatial/time ambiguity before generating each out-of-view-return item; retain evidence',
                'identity_risk_if_unresolved': True,
                'conservative_policy': 'without an independent natural-person re-entry guarantee, keep exit/return items identity_risk=true even if no obvious conflicting new ID is found',
                'max_identity_risk_fraction_of_O3': 0.20,
            },
        },
        'answer_balance': {
            'strata': ['question_type', 'question_type x dataset'],
            'report_global_majority_baseline': True, 'report_dataset_only_majority_baseline_within_type': True,
            'rebalance_when_dataset_only_exceeds_global_pp': 5,
            'rebalance_when_type_majority_exceeds_uniform_random_pp': 10,
            'scope': 'class letter, semantic yes/no, count/time bins and ordering as appropriate; do not hide semantic skew by only permuting letters',
        },
        'unchanged_stage3_requirements': {
            'language': 'English, no GT ID in questions', 'ref_to_question_min_s': 3.0,
            'O1_max_fraction': 0.15, 'held_out_composition_target_n': 100,
            'composition_split_role': 'held_out_composition',
            'false_premise_fraction': [0.10, 0.15],
            'identity_confusion_option_required_unless_unavailable': True,
            'no_confusion_option_max_fraction': 0.30,
            'difficulty_fields': ['n_crossings', 'max_gap_s', 'density', 'appearance_similarity',
                                  'needs_visual_grounding', 'camera_motion'],
            'appearance_similarity_model': 'select and document public feature model before eventual generation; not needed or run for this review preparation',
            'templates_and_additional_implementation_thresholds': 'lock separately before generating any QA; this file freezes the user-specified constraints now',
        },
        'stage3_manual_question_review': {'n': 20, 'stratified_reference_counts': {'box': 8, 'event': 5, 'appearance': 4, 'position': 3},
                                          'export_style': 'same local HTML radio choices, notes and JSON export as reference review'},
        'current_prohibitions': ['no QA generation until user review upload', 'no tracker execution',
                                 'no tracker weight download', 'no model inference/training',
                                 'no new appearance phrase generation', 'no raw data edits', 'no proxy'],
    }
    write(config_path, config)
    config_path.with_suffix('.sha256').write_text(sha(config_path) + '  generation_config_locked.json\n')
    receipt = {'at': now, 'visibility_old_sha256': hashlib.sha256(previous).hexdigest(),
               'visibility_locked_sha256': sha(visibility), 'config_sha256': sha(config_path),
               'source_original_task_sha256': sha(ROOT/'task_request.txt'),
               'authorization': 'User Stage 2 decisions and Stage 3 adjustment, received in this turn.',
               'history': str(history), 'qa_generated': 0}
    write(ROOT/'results/review/preparation_decisions.json', receipt)
    with (ROOT/'research_log.md').open('a') as f:
        f.write(f'\n## Stage 2 decisions and pre-Stage 3 review preparation — {now}\n\n'
                'Hypothesis: box references can reduce appearance ambiguity without inventing person descriptions. '
                'User locked MOT17 visibility>=0.25, source windows and 3-decimal timestamps; old visibility file archived. '
                'Plan: lock revised generation constraints, prepare 137 requested phrase review rows plus a collapsed 17-row prior-agent-clear section; '
                'use existing GT and deterministic CPU image descriptors only for review-frame selection and nearest distractor display. '
                'Audit official tracker training splits without weights or execution. Stop once the offline review page is delivered; '
                'wait for user-uploaded reference_review_result.json before QA generation. No benchmark labels/results used for tuning.\n')
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == '__main__':
    main()
