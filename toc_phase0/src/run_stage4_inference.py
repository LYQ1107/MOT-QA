"""Durable two-server Stage 4 official main + separate guided count runs.

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

from stage4_common import (ROOT, CONDITIONS, LEGAL, now, read, rows, write, write_rows,
                           sha, verify_stage4, sampling, extract)

PORTS = (18012, 18013)
MODEL = 'Qwen/Qwen2.5-VL-7B-Instruct'
STOP = threading.Event()
MUTEX = threading.Lock()
JOB = {}


def journal(**update):
    JOB.update(update, updated_at=now())
    write(ROOT / 'logs/stage4_job.json', JOB)


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
        if 'A800' in name and total - used >= reserve + 6144:
            available.append(dict(physical_index=int(index), uuid=uid, name=name,
                initial_used_MiB=used, initial_free_MiB=total-used, reserved_budget_MiB=reserve,
                existing_process_count=counts.get(uid, 0), initial_utilization=int(utilization)))
    available.sort(key=lambda d: (d['existing_process_count'], d['initial_utilization'], -d['initial_free_MiB'], d['physical_index']))
    assert len(available) >= 2, f'Two A800 need 65% total + 6GiB headroom each; foreign jobs untouched.\n{snapshot}'
    selected = available[:2]
    write(ROOT / f'logs/stage4_allocation_attempt{attempt}.json', dict(checked_at=now(), selected=selected,
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
            log_path = ROOT/f'logs/stage4_vllm_slot{slot}_attempt{attempt}.log'
            stream = log_path.open('w')
            process = subprocess.Popen(args, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            servers.append((process, stream, log_path))
            runtimes.append(dict(slot=slot, pid=process.pid, physical_gpu=device, actual_cuda_uuid=actual,
                args=args, log=str(log_path), cuda_visible_devices=env['CUDA_VISIBLE_DEVICES']))
        write(ROOT/f'logs/stage4_runtime_attempt{attempt}.json', dict(started_at=now(), servers=runtimes,
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


def prediction_path(mode, condition, qa_id):
    return ROOT/'results/stage4/predictions'/mode/condition/f'{qa_id}.json'


def infer(record, slot, mode, attempt, client):
    if STOP.is_set():
        return None
    start = time.monotonic()
    try:
        content = [dict(type='image_url', image_url=dict(url='data:image/jpeg;base64,'+b64)) for b64 in frames(record['video_id'])]
        content.append(dict(type='text',text=record['user']))
        kwargs = dict(model=MODEL, messages=[dict(role='system', content=record['system']),dict(role='user',content=content)],
            temperature=0.0, max_tokens=record['max_tokens'], seed=42)
        if mode == 'guided':
            assert record['format']=='numerical'
            kwargs['extra_body'] = dict(structured_outputs=dict(choice=list(LEGAL)))
        response = client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        raw = choice.message.content
        assert isinstance(raw,str), 'Missing assistant text'
        actual_tokens = response.usage.prompt_tokens
        assert actual_tokens == record['expected_prompt_tokens'], (record['qa_id'],actual_tokens,record['expected_prompt_tokens'])
        if mode == 'guided':
            assert raw.strip() in LEGAL, ('Guided decoding violated its choice set',raw)
        result = dict(qa_id=record['qa_id'], video_id=record['video_id'], format=record['format'],
            condition=record['condition'], decoding=mode, protocol='official_plus_timestamps_and_evidence',
            raw_response=raw, extracted_answer=extract(raw,record['format']), error=None,
            endpoint_slot=slot, attempt=attempt, started_at=now(), latency_s=round(time.monotonic()-start,3),
            prompt_sha256=record['prompt_sha256'], sampled_frames=len(content)-1,
            expected_prompt_tokens=record['expected_prompt_tokens'], usage=response.usage.model_dump(),
            max_tokens=record['max_tokens'], finish_reason=choice.finish_reason, model=response.model,
            frozen_config_sha256=JOB['frozen_config_sha256'], hypotheses_sha256=JOB['hypotheses_sha256'],
            d_assignment_sha256=JOB['d_assignment_sha256'])
        write(prediction_path(mode,record['condition'],record['qa_id']), result)
        return result
    except Exception as error:
        STOP.set()
        record_error = dict(at=now(),qa_id=record['qa_id'],condition=record['condition'],decoding=mode,
            endpoint_slot=slot,attempt=attempt,latency_s=round(time.monotonic()-start,3),error=repr(error),
            traceback=traceback.format_exc())
        with MUTEX, (ROOT/'logs/stage4_request_errors.jsonl').open('a') as stream:
            stream.write(json.dumps(record_error,ensure_ascii=False)+'\n')
        raise RuntimeError(json.dumps(record_error,ensure_ascii=False)) from error


def run_condition(condition, mode, attempt, clients, slots):
    records = rows(ROOT/'results/stage4/prompts'/f'{condition}.jsonl')
    if mode=='guided':
        records = [r for r in records if r['format']=='numerical']
    assert len(records)==(300 if mode=='guided' else 749)
    existing = {}
    for record in records:
        path = prediction_path(mode,condition,record['qa_id'])
        if path.exists():
            p = read(path)
            assert p['prompt_sha256']==record['prompt_sha256'] and p['error'] is None
            assert p['decoding']==mode and p['condition']==condition
            assert p['hypotheses_sha256']==JOB['hypotheses_sha256'] and p['d_assignment_sha256']==JOB['d_assignment_sha256']
            existing[record['qa_id']] = p
    unfinished = [r for r in records if r['qa_id'] not in existing]
    start = time.monotonic()
    journal(stage='inference',condition=condition,decoding=mode,expected=len(records),committed=len(existing),new_committed=0)
    pools = [cf.ThreadPoolExecutor(max_workers=4) for _ in clients]
    try:
        pending = [pools[slots[r['qa_id']]].submit(infer,r,slots[r['qa_id']],mode,attempt,clients[slots[r['qa_id']]]) for r in unfinished]
        completed = 0
        for future in cf.as_completed(pending):
            result = future.result()
            if result is None:
                continue
            completed += 1
            if completed % 25==0 or completed==len(unfinished):
                elapsed=time.monotonic()-start
                update=dict(committed=len(existing)+completed,new_committed=completed,phase_elapsed_s=round(elapsed,1),
                    eta_minutes=round((len(unfinished)-completed)*elapsed/max(1,completed)/60,1))
                journal(**update)
                print(json.dumps(dict(condition=condition,decoding=mode,**update)),flush=True)
    finally:
        for pool in pools:
            pool.shutdown(wait=True,cancel_futures=STOP.is_set())
    committed = [read(prediction_path(mode,condition,r['qa_id'])) for r in records]
    assert len(committed)==len({p['qa_id'] for p in committed})==len(records)
    assert all(p['error'] is None for p in committed)
    output=ROOT/'results/stage4'/f'{mode}_{condition}_predictions.jsonl'
    write_rows(output,committed)
    receipt=dict(condition=condition,decoding=mode,completed_at=now(),predictions=len(committed),unique=len(committed),
        new_predictions=len(unfinished),elapsed_this_attempt_s=round(time.monotonic()-start,3),output=str(output),sha256=sha(output),
        parse_failures=sum(p['extracted_answer'] is None for p in committed))
    write(ROOT/'logs'/f'stage4_{mode}_{condition}_receipt.json',receipt)
    print(json.dumps(receipt),flush=True)
    if mode=='main' and condition=='A':
        # Keep label-bearing offline scoring out of the server/request process.
        subprocess.run([str(ROOT/'env/bin/python'),'-c',
            'from stage4_scores import route; from stage4_common import ROOT; route(ROOT/"results/stage4/main_A_predictions.jsonl", "A")'],
            cwd=ROOT,env=dict(os.environ,PYTHONPATH=str(ROOT/'src')),check=True)


def main(args):
    started=time.monotonic()
    lock=verify_stage4()
    for row in read(ROOT/'results/stage4_image_manifest_locked.json')['videos']:
        directory,_=sampling(row['video_id'])
        assert sha(directory/'sampling.json')==row['sampling_sha256']
        for file in row['files']:
            assert sha(file['path'])==file['sha256'],file['path']
    for file in read(ROOT/'results/stage4_D_text_manifest_locked.json')['files']:
        assert sha(file['path'])==file['sha256']
    attempt=len(list((ROOT/'logs').glob('stage4_runtime_attempt*.json')))+1
    JOB.update(status='RUNNING',started_at=now(),controller_pid=os.getpid(),attempt=attempt,phase=args.phase,
        frozen_config_sha256=lock['frozen_config_sha256'],
        hypotheses_sha256=sha(ROOT/'results/stage4_hypotheses_preregistered.json'),
        d_assignment_sha256=sha(ROOT/'results/stage4_D_assignments_locked.json'))
    journal(stage='preflight')
    all_records=rows(ROOT/'results/stage4/prompts/A.jsonl')
    slots={r['qa_id']:i%2 for i,r in enumerate(all_records)}
    shard_path=ROOT/'results/stage4_endpoint_shards_locked.json'
    if not shard_path.exists():
        from stage4_common import immutable
        immutable(shard_path,dict(created_at=now(),rule='sorted qa_id alternating, identical in all conditions/modes',assignments=slots))
    else:
        assert read(shard_path)['assignments']==slots
    servers=[]
    monitor_done=threading.Event(); monitor_result={}; monitor=None
    try:
        devices=allocation(attempt)
        servers=start_servers(devices,attempt)
        monitor=threading.Thread(target=gpu_monitor,args=(devices,servers,monitor_done,monitor_result),daemon=True)
        monitor.start()
        import httpx
        from openai import OpenAI
        clients=[OpenAI(api_key='EMPTY',base_url=f'http://127.0.0.1:{port}/v1',timeout=600,max_retries=0,
                        http_client=httpx.Client(trust_env=False,timeout=600)) for port in PORTS]
        modes=('main','guided') if args.phase=='all' else (args.phase,)
        for mode in modes:
            for condition in CONDITIONS:
                run_condition(condition,mode,attempt,clients,slots)
            write(ROOT/'logs'/f'stage4_{mode}_complete.json',dict(completed_at=now(),conditions=list(CONDITIONS),
                predictions_per_condition=749 if mode=='main' else 300,protocol='official main format',
                hypotheses_sha256=JOB['hypotheses_sha256'],d_assignment_sha256=JOB['d_assignment_sha256']))
        for client in clients:
            client.close()
        journal(status='INFERENCE_COMPLETE',stage='shutdown',elapsed_s=round(time.monotonic()-started,3))
    except BaseException as error:
        journal(status='FAILED',error=repr(error),traceback=traceback.format_exc(),elapsed_s=round(time.monotonic()-started,3))
        raise
    finally:
        STOP.set()
        stop_servers(servers)
        monitor_done.set()
        if monitor is not None:
            monitor.join(timeout=10)
        write(ROOT/f'logs/stage4_gpu_memory_attempt{attempt}.json',monitor_result)
        if JOB.get('status')=='INFERENCE_COMPLETE':
            journal(status='COMPLETE',stage='finished',gpu_memory=monitor_result,elapsed_s=round(time.monotonic()-started,3))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--phase',choices=['main','guided','all'],default='all')
    main(parser.parse_args())
