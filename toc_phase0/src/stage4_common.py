"""Shared, answer-free Stage 4 prompt construction and artifact checks."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'upstream/toc_bench'))
from eval_runner import build_prompt, get_max_tokens
from answer_extractor import extract

CONDITIONS = ('A', 'B', 'C', 'D')
LEGAL = ('2', '3', '4', '5 or more')
TRACKER_PREFACE = (
    'An object tracker was run on the full video at 5 fps. Its output is below.\n'
    'The tracker sees every frame, while you only see 32 sampled frames, so use\n'
    'the tracks as evidence about when objects appear, disappear and reappear.\n'
    'The tracker can make mistakes (fragmented tracks, identity switches, false\n'
    'detections); check the tracks against the frames when they conflict.\n\n')
PLACEHOLDER = 'An object tracker was run on the full video at 5 fps.\n[Tracking output omitted]\n'


def now():
    return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s]


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.incomplete')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def write_rows(path, values):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.incomplete')
    temporary.write_text(''.join(json.dumps(v, ensure_ascii=False) + '\n' for v in values))
    temporary.replace(path)


def immutable(path, value):
    path = Path(path)
    assert not path.exists(), f'Already locked: {path}'
    write(path, value)
    path.chmod(0o444)
    return dict(path=str(path), sha256=sha(path), locked_at=now())


def verify_prior():
    frozen_path = ROOT / 'results/frozen_config_v1.json'
    frozen = read(frozen_path)
    lock = read(ROOT / 'logs/frozen_config_v1_lock.json')
    assert sha(frozen_path) == lock['sha256']
    assert sha(ROOT / 'results/dev_test_split_locked.json') == frozen['split_sha256']
    assert sha(ROOT / 'results/trackable_subset_preregistered.json') == frozen['preregistration_sha256']
    for path, expected in frozen['source_sha256'].items():
        path = Path(path)
        if not path.is_absolute():
            path = ROOT / 'src' / path
        assert sha(path) == expected, path
    return frozen, lock['sha256']


def verify_stage4():
    frozen, frozen_sha = verify_prior()
    lock = read(ROOT / 'logs/stage4_preinference_lock.json')
    for artifact in lock['artifacts']:
        path = Path(artifact['path'])
        assert sha(path) == artifact['sha256'], path
        assert path.stat().st_mode & 0o222 == 0, path
    assert lock['frozen_config_sha256'] == frozen_sha
    assert lock['no_stage4_inference_at_lock']
    return lock


def sampling(video):
    directory = ROOT / 'frames_cache/official32' / video
    sample = read(directory / 'sampling.json')
    n = sample['total_frames']
    assert sample['fps'] > 0 and n > 0
    assert sample['sampled_count'] == sample['expected_count'] == min(32, n)
    expected_indices = list(range(n)) if n <= 32 else [int(i * n / 32) for i in range(32)]
    assert sample['sample_indices'] == expected_indices
    allowed = [f'frame_count_below_32: {n}'] if n < 32 else []
    assert sample['anomalies'] == allowed
    return directory, sample


def prompt(item, sample, evidence):
    # item must be from the metadata-stripped visible-input artifact.
    assert not any(k in item for k in ('metadata', 'correct_answer', 'correct_order'))
    system, user = build_prompt(item)
    if evidence:
        user = user.replace('Question:', evidence + '\nQuestion:', 1)
    stamp = 'The frames above were sampled at these times (seconds): ' + ', '.join(
        f'{i / sample["fps"]:.3f}' for i in sample['sample_indices']) + '.'
    return system, stamp + '\n' + user
