"""Two isolated vLLM servers; unchanged official Qwen prompt/call/parser.

The official sampler's audited JPEG bytes are reused without re-encoding.
Only successful HTTP calls are committed; invalid parses remain final wrong
predictions. Interrupted runs resume committed qa_ids and preserve errors.
"""
import base64
import concurrent.futures as cf
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'upstream/toc_bench'))
from eval_runner import MODEL_REGISTRY, build_prompt, call_openai_video, extract, get_max_tokens

MODEL_NAME = 'qwen2.5-vl-7b'
PORTS = [18002, 18003]
PRED_DIR = ROOT / 'results/stage2_predictions'
STOP = threading.Event()
LOCK = threading.Lock()
INPUT_FIELDS = ('qa_id', 'video_id', 'format', 'question', 'option_A', 'option_B',
                'option_C', 'option_D', 'statement_A', 'statement_B', 'events')


def now():
    return datetime.now(timezone.utc).isoformat()


def assert_official_sample_complete(sampling):
    # The official short-video branch takes every available frame (N <= 32).
    total = sampling['total_frames']
    assert total > 0 and sampling['fps'] > 0
    assert sampling['sampled_count'] == sampling['expected_count'] == min(32, total)
    allowed = [f'frame_count_below_32: {total}'] if total < 32 else []
    assert sampling['anomalies'] == allowed, sampling


def choose_gpus(attempt):
    command = ['nvidia-smi', '--query-gpu=index,uuid,name,memory.used,utilization.gpu', '--format=csv,noheader,nounits']
    snapshot = subprocess.check_output(command, text=True)
    processes = subprocess.check_output(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid,process_name', '--format=csv,noheader'], text=True)
    devices = []
    for line in snapshot.strip().splitlines():
        index, uuid, name, memory, util = [v.strip() for v in line.split(',')]
        if 'A800' in name and int(memory) == 0 and int(util) == 0 and uuid not in processes:
            devices.append(dict(physical_index=int(index), uuid=uuid, name=name))
    assert len(devices) >= 2, f'Two idle A800 GPUs required; no process will be stopped.\n{snapshot}'
    chosen = devices[:2]
    receipt = dict(checked_at=now(), full_gpu_snapshot=snapshot, compute_process_snapshot=processes,
                   selected=chosen, physical_gpu_count=2, masa_run=False)
    (ROOT / 'logs/stage2_gpu_allocation.json').write_text(json.dumps(receipt, indent=2) + '\n')
    (ROOT / f'logs/stage2_gpu_allocation_attempt{attempt}.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return chosen


def start_servers(devices, attempt):
    servers = []
    try:
        for slot, device in enumerate(devices):
            with socket.socket() as probe:
                assert probe.connect_ex(('127.0.0.1', PORTS[slot])) != 0, f'Port {PORTS[slot]} already in use'
            log_path = ROOT / f'logs/stage2_vllm_slot{slot}_attempt{attempt}.log'
            args = [str(ROOT / 'env/bin/python'), '-m', 'vllm.entrypoints.openai.api_server',
                    '--model', str(ROOT / 'models/Qwen2.5-VL-7B-Instruct'),
                    '--served-model-name', 'Qwen/Qwen2.5-VL-7B-Instruct',
                    '--host', '127.0.0.1', '--port', str(PORTS[slot]),
                    '--tensor-parallel-size', '1', '--dtype', 'bfloat16',
                    '--max-model-len', '32768', '--max-num-seqs', '8',
                    '--max-num-batched-tokens', '32768', '--gpu-memory-utilization', '0.75',
                    '--seed', '42', '--enforce-eager',
                    '--limit-mm-per-prompt', '{"image":{"count":32,"width":720,"height":720},"video":0}',
                    '--disable-log-requests']
            # vLLM 0.16's NVML device-id helper requires a numeric mask.
            env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(device['physical_index']),
                       CUDA_DEVICE_ORDER='PCI_BUS_ID', HF_HOME=str(ROOT / 'cache/huggingface'),
                       HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                       OMP_NUM_THREADS='4', TOKENIZERS_PARALLELISM='false')
            for key in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY'):
                env.pop(key, None)
            logfile = log_path.open('w')
            process = subprocess.Popen(args, cwd=ROOT, env=env, stdout=logfile, stderr=subprocess.STDOUT,
                                       start_new_session=True)
            servers.append((process, logfile, log_path))
            print(json.dumps({'server_started': slot, 'pid': process.pid, 'device': device,
                              'log': str(log_path)}), flush=True)
        runtime = dict(attempt=attempt, started_at=now(), devices=devices, ports=PORTS,
                       server_pids=[process.pid for process, _, _ in servers],
                       cuda_visible_devices=[str(d['physical_index']) for d in devices],
                       server_arguments=args[2:], generation_config='auto (original model defaults)',
                       model_repetition_penalty=1.05, mm_processor_overrides=None,
                       profiling_only_image_dimensions=[720, 720],
                       per_endpoint_concurrency=4, split_rule='sorted qa_id alternating endpoints',
                       parser='official answer_extractor.extract', guided_choice=False)
        (ROOT / f'logs/stage2_runtime_attempt{attempt}.json').write_text(json.dumps(runtime, indent=2) + '\n')
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        deadline, ready, last_progress = time.time() + 1800, set(), 0
        while len(ready) < 2:
            for slot, (process, _, log_path) in enumerate(servers):
                assert process.poll() is None, f'vLLM exited: {log_path}'
                if slot in ready:
                    continue
                try:
                    with opener.open(f'http://127.0.0.1:{PORTS[slot]}/health', timeout=2) as response:
                        if response.status == 200:
                            ready.add(slot)
                            print(f'vLLM slot {slot} ready', flush=True)
                except OSError:
                    pass
            assert time.time() < deadline, 'vLLM startup exceeded 30 minutes'
            if time.time() - last_progress >= 30:
                print(f'Waiting within launcher for vLLM startup: {len(ready)}/2 ready', flush=True)
                last_progress = time.time()
            if len(ready) < 2:
                time.sleep(3)
        return servers
    except BaseException:
        stop_servers(servers)
        raise


def stop_servers(servers):
    for process, _, _ in servers:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    for process, logfile, _ in servers:
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        logfile.close()


def infer(item, slot, attempt):
    if STOP.is_set():
        return None
    start = time.time()
    safe_item = {key: item[key] for key in INPUT_FIELDS if key in item}
    cache = ROOT / 'frames_cache/official32' / item['video_id']
    sampling = json.loads((cache / 'sampling.json').read_text())
    assert_official_sample_complete(sampling)
    frames = [base64.b64encode((cache / name).read_bytes()).decode('ascii') for name in sampling['jpeg_files']]
    cfg = dict(MODEL_REGISTRY[MODEL_NAME], _name=MODEL_NAME, base_url=f'http://127.0.0.1:{PORTS[slot]}/v1')
    assert not cfg.get('strict_numerical')
    try:
        raw = call_openai_video(cfg, safe_item, frames, get_max_tokens(item['format'], cfg))
        record = dict(qa_id=item['qa_id'], model=MODEL_NAME, format=item['format'],
                      raw_response=raw, extracted_answer=extract(raw, item['format']),
                      latency_s=round(time.time() - start, 3), error=None,
                      endpoint_slot=slot, attempt=attempt, sampled_frames=len(frames),
                      max_tokens=get_max_tokens(item['format'], cfg))
        path = PRED_DIR / f'{item["qa_id"]}.json'
        partial = path.with_suffix('.json.incomplete')
        partial.write_text(json.dumps(record, ensure_ascii=False) + '\n')
        partial.replace(path)
        return record
    except Exception as e:
        STOP.set()
        error = dict(qa_id=item['qa_id'], endpoint_slot=slot, attempt=attempt,
                     error=f'{type(e).__name__}: {e}', latency_s=round(time.time() - start, 3), at=now())
        with LOCK, (ROOT / 'logs/stage2_inference_errors.jsonl').open('a') as f:
            f.write(json.dumps(error) + '\n')
        raise RuntimeError(json.dumps(error)) from e


def main():
    started = time.time()
    audit = json.loads((ROOT / 'results/video_decode_audit.json').read_text())
    assert audit['summary']['audited_count'] == 1951
    for sampling in audit['videos']:
        assert_official_sample_complete(sampling)
    gate = json.loads((ROOT / 'logs/stage2_decode_gate_reported.json').read_text())
    assert gate['reported_to_user'] and gate['anomaly_count'] == audit['summary']['anomaly_count']
    assert set(gate['short_video_ids']) == {r['video_id'] for r in audit['videos'] if r['total_frames'] < 32}
    items = sorted(json.loads((ROOT / 'data/toc_bench/answer_final.json').read_text())['items'], key=lambda x: x['qa_id'])
    assert len(items) == len({it['qa_id'] for it in items}) == 2323
    PRED_DIR.mkdir(parents=True, exist_ok=True)
    assignment = [{'qa_id': item['qa_id'], 'endpoint_slot': i % 2} for i, item in enumerate(items)]
    (ROOT / 'results/stage2_shards.json').write_text(json.dumps(assignment, indent=2) + '\n')
    existing = {}
    for path in PRED_DIR.glob('*.json'):
        record = json.loads(path.read_text())
        assert record['qa_id'] not in existing and record['error'] is None
        existing[record['qa_id']] = record
    assert set(existing).issubset({it['qa_id'] for it in items})
    tasks = [(item, i % 2) for i, item in enumerate(items) if item['qa_id'] not in existing]
    attempt = len(list((ROOT / 'logs').glob('stage2_runtime_attempt*.json'))) + 1
    servers, pools = [], []
    infer_start = time.time()
    try:
        if tasks:
            devices = choose_gpus(attempt)
            servers = start_servers(devices, attempt)
            infer_start = time.time()
            # Keep an inspectable text-only representation; no construction metadata is passed.
            example = tasks[0][0]
            safe_example = {k: example[k] for k in INPUT_FIELDS if k in example}
            system, user = build_prompt(safe_example)
            (ROOT / 'logs/stage2_request_example.json').write_text(json.dumps({
                'qa_id': example['qa_id'], 'system': system, 'user': user,
                'content_order': ['32 official JPEG image_url parts', 'official user prompt'],
                'temperature': 0.0, 'seed': 42, 'max_tokens': get_max_tokens(example['format']),
                'metadata_passed': False, 'extra_body': None}, indent=2) + '\n')
            pools = [cf.ThreadPoolExecutor(max_workers=4) for _ in range(2)]
            pending = {pools[slot].submit(infer, item, slot, attempt) for item, slot in tasks}
            completed = 0
            for future in cf.as_completed(pending):
                record = future.result()
                if record is None:
                    continue
                completed += 1
                if completed % 25 == 0 or completed == len(tasks):
                    elapsed = time.time() - infer_start
                    print(json.dumps({'new_predictions': completed, 'committed_total': len(existing) + completed,
                                      'expected_total': 2323, 'elapsed_inference_s': round(elapsed, 1),
                                      'eta_minutes': round((len(tasks) - completed) * elapsed / max(1, completed) / 60, 1)}), flush=True)
    finally:
        STOP.set()
        for pool in pools:
            pool.shutdown(wait=True, cancel_futures=True)
        stop_servers(servers)
    merged = [json.loads((PRED_DIR / f'{item["qa_id"]}.json').read_text()) for item in items]
    assert len(merged) == len({r['qa_id'] for r in merged}) == 2323
    expected_frames = {r['video_id']: min(32, r['total_frames']) for r in audit['videos']}
    item_by_id = {it['qa_id']: it for it in items}
    assert all(r['error'] is None and r['sampled_frames'] == expected_frames[item_by_id[r['qa_id']]['video_id']] for r in merged)
    assert all(r['extracted_answer'] == extract(r['raw_response'], r['format']) for r in merged)
    merged_path = ROOT / 'results/stage2_predictions.jsonl'
    merged_path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in merged))
    timing = dict(status='ALL_2323_UNIQUE_PREDICTIONS_COMPLETE', attempt=attempt, ended_at=now(),
                  unique_predictions=2323, parse_failures=sum(r['extracted_answer'] is None for r in merged),
                  resumed_predictions=len(existing), new_predictions=len(tasks),
                  invocation_total_s=round(time.time() - started, 3),
                  inference_s=round(time.time() - infer_start, 3),
                  raw_outputs_preserved=True, prediction_path=str(merged_path))
    (ROOT / f'logs/stage2_inference_receipt_attempt{attempt}.json').write_text(json.dumps(timing, indent=2) + '\n')
    print(json.dumps(timing, indent=2), flush=True)


if __name__ == '__main__':
    main()
