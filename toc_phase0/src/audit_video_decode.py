"""Run the unchanged official sampler on every verified video, retaining its JPEGs."""
import base64
import concurrent.futures as cf
from collections import Counter
import json
import math
from pathlib import Path
import sys
import time

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'upstream/toc_bench'))
from eval_runner import sample_frames_uniform

cv2.setNumThreads(1)
CACHE = ROOT / 'frames_cache/official32'
MANIFEST = json.loads((ROOT / 'data/toc_bench/video_manifest.json').read_text())


def audit(item):
    path = ROOT / 'data/toc_bench' / item['rfilename']
    video_id = path.stem
    cache_dir = CACHE / video_id
    record_path = cache_dir / 'sampling.json'
    # A completed audit is reusable if this command is resumed after interruption.
    if record_path.exists():
        record = json.loads(record_path.read_text())
        assert all((cache_dir / name).stat().st_size > 0 for name in record['jpeg_files'])
        return record
    record = {'video_id': video_id, 'video_path': str(path), 'anomalies': []}
    try:
        assert path.stat().st_size == item['size']
        cap = cv2.VideoCapture(str(path))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        indices = list(range(total)) if 0 < total <= 32 else [int(i * total / 32) for i in range(32)]
        frames = sample_frames_uniform(path, 32)
        record.update(total_frames=total, fps=fps, width=width, height=height,
                      sampled_count=len(frames), expected_count=min(32, max(0, total)),
                      sample_indices=indices if total > 0 else [],
                      sample_timestamps_s=[i / fps for i in indices] if fps > 0 else [],
                      duration_s=total / fps if fps > 0 else None)
        if total < 32:
            record['anomalies'].append(f'frame_count_below_32: {total}')
        if not math.isfinite(fps) or fps <= 0:
            record['anomalies'].append(f'invalid_fps: {fps}')
        if len(frames) != min(32, max(0, total)) or not frames:
            record['anomalies'].append(f'official_sampler_frame_count: {len(frames)}')
        jpeg_files, dimensions, cache_bytes = [], [], 0
        cache_dir.mkdir(parents=True, exist_ok=True)
        for i, encoded in enumerate(frames):
            data = base64.b64decode(encoded)
            image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
            assert image is not None, (video_id, i)
            h, w = image.shape[:2]
            assert max(h, w) <= 720, (video_id, h, w)
            name = f'{i:02d}.jpg'
            (cache_dir / name).write_bytes(data)
            jpeg_files.append(name)
            dimensions.append([w, h])
            cache_bytes += len(data)
        record.update(jpeg_files=jpeg_files, jpeg_dimensions=dimensions, cache_bytes=cache_bytes)
    except Exception as e:
        record['anomalies'].append(f'{type(e).__name__}: {e}')
        record.setdefault('cache_bytes', 0)
        record.setdefault('jpeg_files', [])
    record['status'] = 'OK' if not record['anomalies'] else 'ANOMALY'
    cache_dir.mkdir(parents=True, exist_ok=True)
    record_path.write_text(json.dumps(record, indent=2) + '\n')
    return record


def audit_when_verified(item):
    # The downloader atomically publishes a video only after size/SHA256 pass.
    # Waiting here pipelines CPU decoding with the remaining network transfer.
    path = ROOT / 'data/toc_bench' / item['rfilename']
    receipt_path = ROOT / 'logs/video_download_receipt.json'
    while not path.exists():
        if receipt_path.exists():
            receipt = json.loads(receipt_path.read_text())
            assert receipt['status'] == 'ALL_VIDEOS_VERIFIED', receipt['failures']
        time.sleep(2)
    return audit(item)


def main():
    start = time.time()
    records = []
    with cf.ThreadPoolExecutor(max_workers=8) as executor:
        for future in cf.as_completed([executor.submit(audit_when_verified, item) for item in MANIFEST]):
            records.append(future.result())
            if len(records) % 25 == 0:
                print(json.dumps({'audited': len(records), 'total': 1951,
                                  'anomalies_so_far': sum(bool(r['anomalies']) for r in records),
                                  'elapsed_s': round(time.time() - start, 1)}), flush=True)
    receipt_path = ROOT / 'logs/video_download_receipt.json'
    while not receipt_path.exists():
        time.sleep(1)
    receipt = json.loads(receipt_path.read_text())
    assert receipt['status'] == 'ALL_VIDEOS_VERIFIED' and receipt['verified_count'] == 1951
    records.sort(key=lambda r: r['video_id'])
    items = json.loads((ROOT / 'data/toc_bench/answer_final.json').read_text())['items']
    assert {r['video_id'] for r in records} == {it['video_id'] for it in items}
    anomalies = [r for r in records if r['anomalies']]
    cache_bytes = sum(r['cache_bytes'] for r in records)
    summary = dict(status='DECODE_AUDIT_CLEAN' if not anomalies else 'DECODE_ANOMALIES_REPORT_BEFORE_INFERENCE',
                   audited_count=len(records), expected_count=1951, anomaly_count=len(anomalies),
                   total_sampled_frames=sum(r.get('sampled_count', 0) for r in records),
                   sampled_count_distribution=dict(Counter(r.get('sampled_count', 0) for r in records)),
                   total_frames_min=min(r.get('total_frames', 0) for r in records),
                   total_frames_max=max(r.get('total_frames', 0) for r in records),
                   fps_distribution=dict(Counter(round(r.get('fps', 0), 6) for r in records)),
                   cache_bytes=cache_bytes, cache_limit_bytes=25 * 1024**3,
                   elapsed_s=round(time.time() - start, 3),
                   overlapped_with_download=True,
                   sampler='unmodified upstream/toc_bench/eval_runner.py:sample_frames_uniform',
                   dataset_revision=receipt['dataset_revision'])
    (ROOT / 'results/video_decode_audit.json').write_text(json.dumps({'summary': summary, 'videos': records}, indent=2) + '\n')
    (ROOT / 'results/video_decode_anomalies.json').write_text(json.dumps(anomalies, indent=2) + '\n')
    print(json.dumps(summary, indent=2), flush=True)
    assert len(records) == 1951 and cache_bytes <= 25 * 1024**3
    # The caller must report this audit before starting inference.


if __name__ == '__main__':
    main()
