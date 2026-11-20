"""Run unified MASA at 5 fps on up to two GPUs; no vLLM or SAM inference."""
import argparse
import concurrent.futures as cf
import ctypes
from datetime import datetime
import json
import os
from pathlib import Path
import random
import signal
import subprocess
import sys
import threading
import time
import uuid
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + '.incomplete')
    partial.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n')
    partial.replace(path)


def now():
    return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()


def pilot_selection(tasks):
    existing = ROOT / 'results/stage3_pilot_selection.json'
    if existing.exists():
        selected = set(json.loads(existing.read_text())['video_ids'])
        return [t for t in tasks if t['video_id'] in selected]
    rng = random.Random(42)
    rows = json.loads((ROOT / 'results/trackable_subset_preregistered.json').read_text())['rows']
    groups = {}
    for t in tasks:
        groups.setdefault('source:' + t['video_id'].split('_')[0], set()).add(t['video_id'])
    for row in rows:
        groups.setdefault('dimension:' + row['dimension'], set()).add(row['video_id'])
        for kind in row['event_types']:
            groups.setdefault('event:' + kind, set()).add(row['video_id'])
    selected = set()
    for key in sorted(groups):
        selected.add(rng.choice(sorted(groups[key])))
    remaining = sorted(t['video_id'] for t in tasks if t['video_id'] not in selected)
    selected.update(rng.sample(remaining, 20 - len(selected)))
    assert len(selected) == 20
    write_json(existing, dict(created_at=now(), seed=42, method='one seeded choice per source, dimension and event type; fill without replacement to 20; no answers used', video_ids=sorted(selected)))
    return [t for t in tasks if t['video_id'] in selected]


def pick_devices(phase, attempt):
    snapshot = subprocess.check_output(['nvidia-smi', '--query-gpu=index,uuid,name,memory.used,memory.total,utilization.gpu', '--format=csv,noheader,nounits'], text=True)
    processes = subprocess.check_output(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid,process_name', '--format=csv,noheader'], text=True)
    process_counts = {}
    for line in processes.splitlines():
        uid = line.split(',')[0].strip()
        process_counts[uid] = process_counts.get(uid, 0) + 1
    minimum_free_mib = 20 * 1024
    available = []
    for line in snapshot.splitlines():
        index, uid, name, memory, total, utilization = [v.strip() for v in line.split(',')]
        free = int(total) - int(memory)
        if 'A800' in name and free >= minimum_free_mib:
            available.append(dict(physical_index=int(index), uuid=uid, name=name,
                                  existing_process_count=process_counts.get(uid, 0),
                                  initial_used_MiB=int(memory), initial_free_MiB=free,
                                  initial_utilization_percent=int(utilization)))
    preference_path = ROOT / 'results/stage3_resource_preference.json'
    if preference_path.exists():
        preference=json.loads(preference_path.read_text())
        available=[d for d in available if d['physical_index'] in preference['allowed_gpu_ids']]
    assert available, f'No allowed A800 has {minimum_free_mib} MiB free; existing processes untouched.\n{snapshot}'
    recent_rates={}
    if phase=='full':
        measured={}
        for vid in json.loads((ROOT/'results/stage3_pilot_selection.json').read_text())['video_ids']:
            row=json.loads((ROOT/'tracks/raw'/(vid+'.json')).read_text())
            uid=row['physical_gpu']['uuid'];frames,seconds=measured.get(uid,(0,0))
            measured[uid]=(frames+row['frame_count'],seconds+row['inference_s'])
        recent_rates={uid:frames/seconds for uid,(frames,seconds) in measured.items()}
    selected = sorted(available, key=lambda d: (d['existing_process_count'], d['initial_utilization_percent'], -recent_rates.get(d['uuid'],0), -d['initial_free_MiB'], d['physical_index']))[:2]
    print('PROGRESS ' + json.dumps(dict(phase=phase, selected_devices=selected, worker_count=len(selected), sharing_authorized=True)), flush=True)
    write_json(ROOT / f'logs/stage3_{phase}_allocation_attempt{attempt}.json', dict(checked_at=now(), selected=selected, snapshot=snapshot, compute_processes=processes,
               sharing_authorized_by_user=True, selection='at least 20 GiB free, then fewer processes, lower utilization, measured MASA speed when available, more free memory', minimum_free_MiB=minimum_free_mib,recent_pilot_fps=recent_rates))
    return selected


def resample(video_id):
    import cv2
    source = ROOT / 'data/toc_bench/videos' / (video_id + '.mp4')
    target = ROOT / 'data/toc_bench/videos_5fps' / (video_id + '.mp4')
    target.parent.mkdir(parents=True, exist_ok=True)
    start = time.time()
    if not target.exists():
        partial = target.with_suffix(f'.mp4.{os.getpid()}.incomplete')
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-threads', '2',
                        '-i', str(source), '-map', '0:v:0', '-an', '-vf', 'fps=5:start_time=0',
                        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-threads', '2',
                        '-f', 'mp4', str(partial)], check=True)
        partial.replace(target)
    cap = cv2.VideoCapture(str(target))
    fps, frames = cap.get(cv2.CAP_PROP_FPS), int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    assert abs(fps - 5) < 1e-6 and frames > 0, (video_id, fps, frames)
    return target, frames, width, height, time.time() - start


def cuda_uuid():
    driver = ctypes.CDLL('libcuda.so.1')
    assert driver.cuInit(0) == 0
    buffer = (ctypes.c_ubyte * 16)()
    assert driver.cuDeviceGetUuid(ctypes.byref(buffer), 0) == 0
    return 'GPU-' + str(uuid.UUID(bytes=bytes(buffer)))


def reset_video_text_cache(model):
    # MASA's demo reuses one prompt per process. Its detector does not replace
    # track_text_dict on a subsequent video with a different prompt.
    for name in ('track_text_prompt','track_text_dict','token_positive_maps','track_entities'):
        setattr(model.detector,name,None)


def worker(args):
    start = time.time()
    expected_device = json.loads(args.device_json)
    actual_uid = cuda_uuid()
    assert actual_uid.lower() == expected_device['uuid'].lower(), (actual_uid, expected_device)
    sys.path.insert(0, str(ROOT / 'upstream/masa'))
    import cv2
    import numpy as np
    import torch
    import masa
    from masa.apis import init_masa, inference_masa, build_test_pipeline
    from mmengine.config import Config

    cv2.setNumThreads(1)
    random.seed(42); np.random.seed(42); torch.manual_seed(42)
    assert torch.cuda.device_count() == 1
    config = Config.fromfile(ROOT / 'upstream/masa/configs/masa-gdino/masa_gdino_swinb_inference.py')
    config.model.detector.language_model.name = str(ROOT / 'models/MASA/bert-base-uncased')
    config.model.tracker.fps = 5
    config.dump(ROOT / f'logs/stage3_{args.phase}_fresh_config_worker{args.slot}.py')
    assert config.model.unified_backbone and config.model.tracker.fps == 5
    model = init_masa(config, str(ROOT / 'models/MASA/gdino_masa.pth'), device='cuda:0')
    pipeline = build_test_pipeline(model.cfg, with_text=True)
    tasks = json.loads(Path(args.tasks).read_text())
    records = []
    print('PROGRESS ' + json.dumps(dict(worker=args.slot, device=expected_device, actual_cuda_uuid=actual_uid, model_loaded=True, tasks=len(tasks))), flush=True)
    for task in tasks:
        video_id, queries = task['video_id'], task['queries']
        out = ROOT / 'tracks/raw' / (video_id + '.json')
        if out.exists():
            old = json.loads(out.read_text())
            assert old['complete'] and old['queries'] == queries and old['fps'] == 5 and old['fp16'] is True and old['text_cache_reset_per_video']
            records.append(dict(video_id=video_id, status='reused_complete', frames=old['frame_count'], inference_s=old['inference_s']))
            continue
        video, total, width, height, resample_s = resample(video_id)
        prompt = ' . '.join(queries)
        cap = cv2.VideoCapture(str(video))
        reset_video_text_cache(model)
        torch.manual_seed(42)
        torch.cuda.synchronize(); torch.cuda.reset_peak_memory_stats()
        frames, begin = [], time.time()
        for index in range(total):
            ok, image = cap.read()
            assert ok, f'Unexpected 5fps decode failure: {video_id}, frame {index}/{total}'
            result = inference_masa(model, image, frame_id=index, video_len=total,
                                    test_pipeline=pipeline, text_prompt=prompt, custom_entities=True,
                                    fp16=True, detector_type='mmdet', show_fps=False)
            pred = result[0].pred_track_instances
            boxes = pred.bboxes.float().cpu().tolist()
            scores, labels = pred.scores.float().cpu().tolist(), pred.labels.cpu().tolist()
            ids = pred.instances_id.cpu().tolist()
            instances = []
            for box, score, label, track_id in zip(boxes, scores, labels, ids):
                assert 0 <= label < len(queries) and track_id >= 0
                instances.append(dict(track_id=int(track_id), query_index=int(label), box_xyxy=box, confidence=float(score)))
            frames.append(dict(frame_id=index, timestamp_seconds=index / 5, instances=instances))
            if (index + 1) % 100 == 0:
                print('PROGRESS ' + json.dumps(dict(worker=args.slot, video_id=video_id, frame=index+1, frames=total)), flush=True)
        cap.release(); torch.cuda.synchronize()
        elapsed = time.time() - begin
        data = dict(complete=True, video_id=video_id, source_video=str(ROOT / 'data/toc_bench/videos' / (video_id+'.mp4')),
                    tracking_video=str(video), queries=queries, text_prompt=prompt, unified=True, custom_entities=True,
                    fps=5, frame_count=total, width=width, height=height, video_length_seconds=total / 5,
                    fp16=True, seed=42, sam_mask=False, sam2_or_sam3_used=False, demo_postprocessing=False,
                    native_scores_preserved=True, inference_s=elapsed, resample_s=resample_s,
                    text_cache_reset_per_video=True,
                    tracker_parameters=dict(config.model.tracker),
                    peak_gpu_allocated_bytes=torch.cuda.max_memory_allocated(),
                    peak_gpu_reserved_bytes=torch.cuda.max_memory_reserved(), physical_gpu=expected_device,
                    completed_at=now(), frames=frames)
        write_json(out, data)
        record = {k: data[k] for k in ('video_id','frame_count','inference_s','resample_s','peak_gpu_allocated_bytes','peak_gpu_reserved_bytes')}
        records.append(dict(record, status='computed'))
        print('PROGRESS ' + json.dumps(dict(worker=args.slot, completed=len(records), assigned=len(tasks), **record)), flush=True)
    summary = dict(worker=args.slot, phase=args.phase, device=expected_device, elapsed_s=time.time()-start,
                   peak_gpu_reserved_bytes=torch.cuda.max_memory_reserved(), records=records)
    write_json(Path(args.summary), summary)
    print('WORKER_SUMMARY ' + json.dumps({k:v for k,v in summary.items() if k!='records'}), flush=True)


def terminate_owned(processes):
    for p in processes:
        try:
            os.killpg(p.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    for p in processes:
        try:
            p.wait(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL); p.wait()


def main(args):
    start = time.time()
    tasks = json.loads((ROOT / 'results/stage3_tracking_tasks.json').read_text())
    if args.phase == 'pilot':
        tasks = pilot_selection(tasks)
    else:
        frozen = json.loads((ROOT / 'results/stage3_tracker_frozen.json').read_text())
        assert frozen['pilot_videos_reviewed'] == 20 and frozen['fp16'] is True
    attempt = len(list((ROOT / 'logs').glob(f'stage3_{args.phase}_allocation_attempt*.json'))) + 1
    deadline=time.time()+args.wait_for_idle_minutes*60
    while True:
        try:
            devices=pick_devices(args.phase,attempt)
            break
        except AssertionError:
            if time.time()>=deadline:raise
            print('WAIT_GPU '+json.dumps(dict(phase=args.phase,message='No allowed GPU has enough free VRAM; existing jobs untouched',remaining_wait_minutes=round((deadline-time.time())/60,1))),flush=True)
            time.sleep(min(30,max(0,deadline-time.time())))
    idle_wait_s=time.time()-start
    device_rates=[1.0 for _ in devices]
    sizes={}
    if args.phase=='full':
        pilot=json.loads((ROOT/'results/stage3_pilot_receipt.json').read_text())
        sizes={r['video_id']:r['frame_count'] for r in json.loads((ROOT/'results/stage3_resampling_receipt.json').read_text())['rows']}
        remaining_frames=sum(sizes[t['video_id']] for t in tasks if not (ROOT/'tracks/raw'/(t['video_id']+'.json')).exists())
        measured={}
        for video_id in json.loads((ROOT/'results/stage3_pilot_selection.json').read_text())['video_ids']:
            row=json.loads((ROOT/'tracks/raw'/(video_id+'.json')).read_text())
            uid=row['physical_gpu']['uuid']
            frames,seconds=measured.get(uid,(0,0))
            measured[uid]=(frames+row['frame_count'],seconds+row['inference_s'])
        fallback=pilot['frames']/pilot['summed_video_inference_s']
        device_rates=[measured[d['uuid']][0]/measured[d['uuid']][1] if d['uuid'] in measured else fallback for d in devices]
        estimate_s=remaining_frames/sum(device_rates)
        assert estimate_s<=6*3600, f'Estimated remaining tracking {estimate_s/3600:.2f}h exceeds user 6h step limit; stop and report'
        print('PROGRESS '+json.dumps(dict(estimated_remaining_tracking_hours=round(estimate_s/3600,2),remaining_frames=remaining_frames,per_device_measured_fps=device_rates)),flush=True)
    audit = {v['video_id']:v for v in json.loads((ROOT / 'results/video_decode_audit.json').read_text())['videos']}
    shards, loads = [[] for _ in devices], [0 for _ in devices]
    for task in sorted(tasks, key=lambda t: (-sizes.get(t['video_id'],audit[t['video_id']]['duration_s']*5), t['video_id'])):
        slot = min(range(len(devices)), key=lambda i: loads[i])
        shards[slot].append(task)
        if not (ROOT/'tracks/raw'/(task['video_id']+'.json')).exists():
            loads[slot] += sizes.get(task['video_id'],audit[task['video_id']]['duration_s']*5)/device_rates[slot]
    if args.phase=='full':
        assert max(loads)<=6*3600,f'Longest shard estimate {max(loads)/3600:.2f}h exceeds user step limit; stop and report'
    monitor_stop = threading.Event()
    memory_rows = []
    processes, streams = [], []
    owned_memory_rows = []
    def monitor():
        with (ROOT / f'logs/stage3_{args.phase}_gpu_memory_attempt{attempt}.csv').open('w') as log:
            log.write('elapsed_s,index,shared_card_memory_used_MiB,utilization_percent,owned_process_memory_MiB\n')
            while not monitor_stop.is_set():
                text = subprocess.check_output(['nvidia-smi', '--query-gpu=index,memory.used,utilization.gpu', '--format=csv,noheader,nounits'], text=True)
                app_text = subprocess.check_output(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid,used_gpu_memory', '--format=csv,noheader,nounits'], text=True)
                owned_pids = {p.pid for p in processes}
                owned_memory = {}
                for line in app_text.splitlines():
                    uid, pid, used = [s.strip() for s in line.split(',')]
                    if int(pid) in owned_pids:
                        owned_memory[uid] = owned_memory.get(uid, 0) + int(used)
                for line in text.splitlines():
                    index, memory, utilization = [int(s.strip()) for s in line.split(',')]
                    if index in [d['physical_index'] for d in devices]:
                        uid = next(d['uuid'] for d in devices if d['physical_index'] == index)
                        own = owned_memory.get(uid, 0)
                        owned_memory_rows.append(own)
                        row = [round(time.time()-start, 2), index, memory, utilization, own]
                        memory_rows.append(row); log.write(','.join(map(str,row))+'\n'); log.flush()
                monitor_stop.wait(5)
    monitor_thread = threading.Thread(target=monitor, daemon=True); monitor_thread.start()
    try:
        for slot, device in enumerate(devices):
            shard_path = ROOT / f'logs/stage3_{args.phase}_shard{slot}_attempt{attempt}.json'
            summary_path = ROOT / f'logs/stage3_{args.phase}_worker{slot}_attempt{attempt}.json'
            write_json(shard_path, shards[slot])
            env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(device['physical_index']), CUDA_DEVICE_ORDER='PCI_BUS_ID',
                       HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HOME=str(ROOT/'cache/masa_huggingface'),
                       MASA_SKIP_NLTK_DOWNLOAD='1',
                       OMP_NUM_THREADS='4', MKL_NUM_THREADS='4', TOKENIZERS_PARALLELISM='false')
            for key in ('http_proxy','https_proxy','HTTP_PROXY','HTTPS_PROXY','all_proxy','ALL_PROXY'):
                env.pop(key, None)
            command = [str(ROOT/'env_masa/bin/python'), '-u', str(Path(__file__).resolve()), '--phase', args.phase,
                       '--worker', '--slot', str(slot), '--tasks', str(shard_path), '--summary', str(summary_path),
                       '--device-json', json.dumps(device)]
            p = subprocess.Popen(command, cwd=ROOT/'upstream/masa', env=env, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True, bufsize=1, start_new_session=True)
            processes.append(p)
            def stream(process, path):
                with path.open('w') as log:
                    for line in process.stdout:
                        log.write(line); log.flush()
                        if line.startswith(('PROGRESS ', 'WORKER_SUMMARY ', 'Traceback', 'ERROR')):
                            print(line.rstrip(), flush=True)
            t = threading.Thread(target=stream, args=(p,ROOT/f'logs/stage3_{args.phase}_worker{slot}_attempt{attempt}.log'), daemon=True)
            t.start(); streams.append(t)
        # One blocking controller waits; progress and GPU monitoring stay inside it.
        with cf.ThreadPoolExecutor(max_workers=len(devices)) as executor:
            for future in cf.as_completed([executor.submit(p.wait) for p in processes]):
                code = future.result()
                assert code == 0, f'MASA worker failed with exit {code}; inspect phase worker logs'
    finally:
        terminate_owned(processes)
        for t in streams: t.join(timeout=5)
        monitor_stop.set(); monitor_thread.join(timeout=10)
    records = [json.loads((ROOT/'tracks/raw'/(t['video_id']+'.json')).read_text()) for t in tasks]
    assert len(records) == len(tasks) and all(r['complete'] for r in records)
    receipt = dict(status='MASA_PHASE_COMPLETE', phase=args.phase, attempt=attempt, completed_at=now(),
                   videos=len(records), query_pairs=sum(len(r['queries']) for r in records),
                   idle_wait_s=idle_wait_s,
                   frames=sum(r['frame_count'] for r in records), elapsed_wall_s=time.time()-start,
                   summed_video_inference_s=sum(r['inference_s'] for r in records),
                   max_gpu_allocated_bytes=max(r['peak_gpu_allocated_bytes'] for r in records),
                   max_gpu_reserved_bytes=max(r['peak_gpu_reserved_bytes'] for r in records),
                   physical_memory_peak_MiB=max(r[2] for r in memory_rows), devices=devices,
                   shared_gpu_memory_includes_other_jobs=True,
                   owned_process_memory_peak_MiB=max(owned_memory_rows, default=0),
                   shard_projected_seconds=loads,per_device_measured_fps=device_rates,
                   fp16=True, fps=5, unified=True, sam_mask=False, vllm_run=False)
    write_json(ROOT/f'results/stage3_{args.phase}_receipt.json',receipt)
    print(json.dumps(receipt,indent=2),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=['pilot','full'], required=True)
    parser.add_argument('--wait-for-idle-minutes',type=float,default=0)
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--slot', type=int); parser.add_argument('--tasks'); parser.add_argument('--summary'); parser.add_argument('--device-json')
    args = parser.parse_args()
    if args.worker: worker(args)
    else: main(args)
