"""Prepare all 5 fps videos on CPU while GPU resources are unavailable."""
import concurrent.futures as cf
import json
from pathlib import Path
import time

from run_stage3_masa import ROOT, resample, write_json, now


def one(task):
    path, frames, width, height, elapsed = resample(task['video_id'])
    return dict(video_id=task['video_id'], path=str(path), fps=5, frame_count=frames,
                width=width, height=height, bytes=path.stat().st_size, elapsed_s=elapsed)


def main():
    start = time.time()
    tasks = json.loads((ROOT/'results/stage3_tracking_tasks.json').read_text())
    rows = []
    with cf.ThreadPoolExecutor(max_workers=4) as executor:
        for future in cf.as_completed([executor.submit(one, task) for task in tasks]):
            rows.append(future.result())
            if len(rows) % 25 == 0:
                print(json.dumps(dict(resampled=len(rows), total=len(tasks), elapsed_s=round(time.time()-start,1))), flush=True)
    assert len(rows) == len({r['video_id'] for r in rows}) == 689
    receipt = dict(status='ALL_STAGE3_VIDEOS_RESAMPLED_5FPS', completed_at=now(),
                   videos=689, frames=sum(r['frame_count'] for r in rows), bytes=sum(r['bytes'] for r in rows),
                   elapsed_s=time.time()-start, ffmpeg='fps=5:start_time=0; libx264 CRF18; original spatial dimensions; no audio',
                   rows=sorted(rows,key=lambda r:r['video_id']))
    write_json(ROOT/'results/stage3_resampling_receipt.json',receipt)
    old_cache=json.loads((ROOT/'results/video_decode_audit.json').read_text())['summary']['cache_bytes']
    assert old_cache+receipt['bytes'] <= 25*1024**3
    print(json.dumps({k:v for k,v in receipt.items() if k!='rows'},indent=2),flush=True)


if __name__ == '__main__':
    main()
