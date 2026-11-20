"""Human-review design exclusions for provisional MOT-QA questions."""


def camera_motion_exclusion_reason(question):
    uses_cumulative_image_path = 'path_lengths_diagonals' in question['evidence']['gt_detail']
    if uses_cumulative_image_path and question['difficulty']['camera_motion'] != 'static':
        return 'camera_motion_confounds_cumulative_image_path_comparison'
    return None
