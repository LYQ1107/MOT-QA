"""Durable two-server Stage 5 official main + separate guided count runs.

All prompt/D/hypothesis artifacts must already be locked. Successful requests
commit atomically; invalid parses are retained. Failures stop the job, and a
restart resumes only missing units without reassigning prompts or conditions.
"""
import argparse
import base64
import concurrent.futures as cf
from functools import lru_cache
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import threading
import time
import traceback
import urllib.request

from stage5_common import (ROOT, CONDITIONS, LEGAL, now, read, rows, write, write_rows,
                           sha, verify_stage5, sampling, extract)

PORTS = (18012, 18013)
MODEL = 'Qwen/Qwen2.5-VL-7B-Instruct'
STOP = threading.Event()
MUTEX = threading.Lock()
JOB = {}


def journal(**update):
    JOB.update(update, updated_at=now())
    write(ROOT / 'logs/stage5_job.json', JOB)


def allocation(attempt):
    snapshot = subprocess.check_output(['nvidia-smi', '--query-gpu=index,uuid,name,memory.total,memory.used,utilization.gpu', '--format=csv,noheader,nounits'], text=True)
    processes = subprocess.check_output(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid,used_memory', '--format=csv,noheader,nounits'], text=True)
    counts = {}
    for line in processes.splitlines():
        uid = line.split(',')[0].strip()
        counts[uid] = counts.get(uid, 0) + 1
    available = []
    for line in snapshot.splitlines():
        index, uid, name, total, used, utilization = [v.strip() for v in line.split(',')]
        total, used = int(total), int(used)
        reserve = int(total * .65)
        # vLLM reserves a fraction of total physical memory, not free memory.
        if 'A800' in name and total - used >= reserve + 5632:
            available.append(dict(physical_index=int(index), uuid=uid, name=name,
                initial_used_MiB=used, initial_free_MiB=total-used, reserved_budget_MiB=reserve,
                existing_process_count=counts.get(uid, 0), initial_utilization=int(utilization)))
    available.sort(key=lambda d: (d['existing_process_count'], d['initial_utilization'], -d['initial_free_MiB'], d['physical_index']))
    assert len(available) >= 2, f'Two A800 need 65% total + 5.5GiB headroom each; foreign jobs untouched.\n{snapshot}'
    selected = available[:2]
    write(ROOT / f'logs/stage5_allocation_attempt{attempt}.json', dict(checked_at=now(), selected=selected,
        full_snapshot=snapshot, compute_processes=processes, sharing_user_authorized=True,
        selection='memory fits, then fewer processes, lower utilization, more free memory', gpu_count=2))
    return selected


def environment(device):
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(device['physical_index']), CUDA_DEVICE_ORDER='PCI_BUS_ID',
        HF_HOME=str(ROOT / 'cache/huggingface'), HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
        OMP_NUM_THREADS='4', TOKENIZERS_PARALLELISM='false')
    for key in ('http_proxy','https_proxy','HTTP_PROXY','HTTPS_PROXY','all_proxy','ALL_PROXY'):
        env.pop(key, None)
    return env


def stop_servers(servers):
    for process, _, _ in servers:
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    for process, stream, _ in servers:
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        stream.close()


def start_servers(devices, attempt):
    servers = []
    runtimes = []
    try:
        for slot, device in enumerate(devices):
            with socket.socket() as probe:
                assert probe.connect_ex(('127.0.0.1', PORTS[slot])) != 0, f'Port {PORTS[slot]} busy'
            env = environment(device)
            probe_code = ('import ctypes,uuid; d=ctypes.CDLL("libcuda.so.1"); assert d.cuInit(0)==0; '
                          'b=(ctypes.c_ubyte*16)(); assert d.cuDeviceGetUuid(ctypes.byref(b),0)==0; '
                          'print("GPU-"+str(uuid.UUID(bytes=bytes(b))))')
            actual = subprocess.check_output([str(ROOT/'env/bin/python'), '-c', probe_code], env=env, text=True).strip()
            assert actual.lower() == device['uuid'].lower(), (actual, device)
            args = [str(ROOT/'env/bin/python'), '-m', 'vllm.entrypoints.openai.api_server',
                '--model', str(ROOT/'models/Qwen2.5-VL-7B-Instruct'), '--served-model-name', MODEL,
                '--host','127.0.0.1','--port',str(PORTS[slot]), '--tensor-parallel-size','1','--dtype','bfloat16',
                '--max-model-len','65536','--max-num-seqs','8','--max-num-batched-tokens','32768',
                '--gpu-memory-utilization','0.65','--seed','42','--enforce-eager',
                '--limit-mm-per-prompt','{"image":{"count":32,"width":720,"height":720},"video":0}',
                '--disable-log-requests']
            log_path = ROOT/f'logs/stage5_vllm_slot{slot}_attempt{attempt}.log'
            stream = log_path.open('w')
            process = subprocess.Popen(args, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            servers.append((process, stream, log_path))
            runtimes.append(dict(slot=slot, pid=process.pid, physical_gpu=device, actual_cuda_uuid=actual,
                args=args, log=str(log_path), cuda_visible_devices=env['CUDA_VISIBLE_DEVICES']))
        write(ROOT/f'logs/stage5_runtime_attempt{attempt}.json', dict(started_at=now(), servers=runtimes,
            all_conditions_identical_config=True, per_endpoint_concurrency=4,
            model_generation_defaults='auto; repetition_penalty1.05; no per-condition overrides'))
        journal(stage='server_startup', devices=devices, server_pids=[p.pid for p,_,_ in servers], server_ready=0)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        deadline, ready, last = time.monotonic()+1800, set(), 0
        while len(ready) < len(servers):
            for slot, (process, _, log_path) in enumerate(servers):
                assert process.poll() is None, f'Server exited: {log_path}'
                if slot in ready:
                    continue
                try:
                    with opener.open(f'http://127.0.0.1:{PORTS[slot]}/health', timeout=2) as response:
                        if response.status == 200:
                            ready.add(slot)
                except OSError:
                    pass
            assert time.monotonic() < deadline, 'Server startup exceeded 30 minutes'
            if time.monotonic()-last >= 30:
                journal(server_ready=len(ready))
                print(json.dumps(dict(stage='startup', ready=len(ready), at=now())), flush=True)
                last = time.monotonic()
            if len(ready)<len(servers):
                time.sleep(3)
        journal(server_ready=2)
        return servers
    except BaseException:
        stop_servers(servers)
        raise


def gpu_monitor(devices, servers, done, result):
    import pynvml
    pynvml.nvmlInit()
    groups = {p.pid for p,_,_ in servers}
    result.update(started_at=now(), interval_s=5, devices={d['uuid']:dict(own_peak_MiB=0, total_peak_MiB=0) for d in devices})
    try:
        while not done.is_set():
            for device in devices:
                handle = pynvml.nvmlDeviceGetHandleByUUID(device['uuid'])
                total = pynvml.nvmlDeviceGetMemoryInfo(handle).used/1024**2
                owned = 0
                for p in pynvml.nvmlDeviceGetComputeRunningProcesses(handle):
                    try:
                        if os.getpgid(p.pid) in groups:
                            owned += p.usedGpuMemory/1024**2
                    except ProcessLookupError:
                        pass
                record = result['devices'][device['uuid']]
                record['own_peak_MiB'] = max(record['own_peak_MiB'], owned)
                record['total_peak_MiB'] = max(record['total_peak_MiB'], total)
            done.wait(5)
    finally:
        pynvml.nvmlShutdown()
        result['completed_at'] = now()


@lru_cache(maxsize=16)
def frames(video):
    directory, sample = sampling(video)
    return tuple(base64.b64encode((directory/name).read_bytes()).decode('ascii') for name in sample['jpeg_files'])
