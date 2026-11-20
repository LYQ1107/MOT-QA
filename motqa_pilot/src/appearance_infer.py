"""Owned TP2 server lifecycle and resumable caption / blind matching requests.

One blocking job manages startup, progress, memory measurement and cleanup.
No benchmark questions/answers, evaluated-model runs, tracking or training.
"""
import base64
import concurrent.futures as cf
from functools import lru_cache
import importlib.metadata
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import threading
import time
import traceback
import urllib.request
import httpx
from appearance_common import ROOT, RES, DATA, MODEL, PYTHON, MODEL_NAME, now, sha, write, read, rows

PORT = 18031
JOB = {}
LOCK = threading.Lock()

POLICY = {
    'generation_image_note': 'The target person is also included once among the comparison gallery tiles. Identify that repeated target visually; do not treat the repeated target tile as a different rival. Look for truthful stable appearance that distinguishes the target from OTHER people.',
    'parse': 'JSON object, optionally surrounded by one markdown JSON fence. No partial-JSON recovery, content resampling, forced unique choice, or guessed identities.',
    'phrase': {'prefix': 'the person', 'max_words': 30,
               'reject_regex': r'\b(?:P\d{2}|GT|ID\s*\d+|leftmost|rightmost)\b|\b(?:in|on) the (?:left|right|front|back) (?:side|row|corner)\b'},
    'matching': 'unique valid labels, no intersection between matches/uncertain; unknown label = parse failure; exactly intended target, zero uncertain = pass',
    'request': {'temperature':0,'seed':42,'top_p':1,'repetition_penalty':1.0,
                'generation_max_tokens':512,'match_max_tokens':768},
    'checkpoint': 'one JSON file per ID and phase; successful HTTP outputs, including parse failures, are immutable on resume',
    'transport_failure': 'save error and stop job; resume only missing units after root-cause fix',
    'pilot': 'first deterministic ID, all three applicable stages, solely to check API and estimate runtime, retained in final data',
    'estimated_hours_stop_threshold': 6,
    'note_before_inference': 'The locked initial prompt did not clarify that the target is repeated once in the comparison gallery; the explicit image note resolves that known layout fact before any model inference. No acceptance rules or source images change.'
}


def journal(**kwargs):
    with LOCK:
        JOB.update(kwargs,updated_at=now())
        write(ROOT/'logs/appearance_job.json',JOB)


def parse_json(text):
    t = text.strip()
    if t.startswith('```'):
        t = re.sub(r'^```(?:json)?\s*', '', t)
        t = re.sub(r'\s*```$', '', t)
    result = json.loads(t)
    assert isinstance(result,dict), 'JSON must be an object'
    return result


def phrase_check(raw):
    try:
        obj = parse_json(raw)
        phrase = obj['phrase']
        assert isinstance(phrase,str)
        assert isinstance(obj['supported_attributes'],list)
        assert isinstance(obj['visually_distinct'],bool)
        assert phrase.strip(), 'empty/unreliable phrase'
        assert phrase.casefold().startswith('the person'), 'wrong phrase prefix'
        assert len(phrase.split()) <= 30, 'phrase exceeds locked length'
        assert not re.search(POLICY['phrase']['reject_regex'],phrase,re.I), 'label/location phrase'
        return dict(valid=True,parsed=obj,phrase=phrase.strip(),error=None)
    except (ValueError,KeyError,AssertionError,TypeError) as exc:
        return dict(valid=False,parsed=None,phrase=None,error=str(exc))


def match_check(raw, gallery, target):
    try:
        obj = parse_json(raw)
        matches,uncertain = obj['matches'],obj['uncertain']
        assert isinstance(matches,list) and isinstance(uncertain,list)
        assert all(isinstance(x,str) for x in matches+uncertain)
        assert len(set(matches))==len(matches) and len(set(uncertain))==len(uncertain)
        assert not set(matches)&set(uncertain)
        assert set(matches+uncertain) <= set(gallery['label_to_gt_id'])
        mids = [gallery['label_to_gt_id'][x] for x in matches]
        uids = [gallery['label_to_gt_id'][x] for x in uncertain]
        return dict(valid=True,parsed=obj,matched_gt_ids=mids,uncertain_gt_ids=uids,
                    passed=mids==[target] and not uids,error=None)
    except (ValueError,KeyError,AssertionError,TypeError) as exc:
        return dict(valid=False,parsed=None,matched_gt_ids=[],uncertain_gt_ids=[],passed=False,error=str(exc))


def allocate():
    snapshot = subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid,name,memory.total,memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True)
    processes = subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_memory','--format=csv,noheader,nounits'],text=True)
    counts = {}
    for line in processes.splitlines():
        uid = line.split(',')[0].strip()
        counts[uid] = counts.get(uid,0)+1
    candidates = []
    for line in snapshot.splitlines():
        idx,uid,name,total,used,util = [v.strip() for v in line.split(',')]
        if 'A800' in name and int(total)-int(used) > .80*int(total)+4096:
            candidates.append(dict(physical_index=int(idx),uuid=uid,name=name,total_MiB=int(total),
                    initial_used_MiB=int(used),initial_utilization=int(util),existing_processes=counts.get(uid,0)))
    candidates.sort(key=lambda d:(d['existing_processes'],d['initial_utilization'],d['initial_used_MiB'],d['physical_index']))
    assert len(candidates)>=2, 'Need two cards with enough free memory; foreign processes untouched. '+snapshot
    selected = candidates[:2]
    write(ROOT/'logs/appearance_gpu_allocation.json',dict(at=now(),selected=selected,
        selection='fewer processes first, then lower utilization and more free memory',full_snapshot=snapshot,processes=processes))
    return selected


def server_env(devices):
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=','.join(str(d['physical_index']) for d in devices),CUDA_DEVICE_ORDER='PCI_BUS_ID',
        HF_HOME=str(ROOT/'cache/huggingface'),HF_ENDPOINT='https://hf-mirror.com',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
        TOKENIZERS_PARALLELISM='false',OMP_NUM_THREADS='4',VLLM_CACHE_ROOT=str(ROOT/'cache/vllm'))
    for k in ('http_proxy','https_proxy','HTTP_PROXY','HTTPS_PROXY','all_proxy','ALL_PROXY'):
        env.pop(k,None)
    return env


def memory_monitor(devices,done,result):
    import pynvml
    pynvml.nvmlInit()
    result.update(started_at=now(),interval_s=5,devices={d['uuid']:{'own_peak_MiB':0,'total_peak_MiB':0} for d in devices})
    try:
        while not done.is_set():
            for d in devices:
                h = pynvml.nvmlDeviceGetHandleByUUID(d['uuid'])
                total = pynvml.nvmlDeviceGetMemoryInfo(h).used/1024**2
                owned = 0
                for p in pynvml.nvmlDeviceGetComputeRunningProcesses(h):
                    try:
                        if os.getpgid(p.pid)==JOB.get('server_pid'):
                            owned += p.usedGpuMemory/1024**2
                    except ProcessLookupError:
                        pass
                row = result['devices'][d['uuid']]
                row['own_peak_MiB'] = max(row['own_peak_MiB'],owned)
                row['total_peak_MiB'] = max(row['total_peak_MiB'],total)
            done.wait(5)
    finally:
        result['completed_at'] = now()
        pynvml.nvmlShutdown()


def start_server(devices):
    env = server_env(devices)
    probe = ('import ctypes,uuid;d=ctypes.CDLL("libcuda.so.1");assert d.cuInit(0)==0;'
             'b=(ctypes.c_ubyte*16)();'
             '[(d.cuDeviceGetUuid(ctypes.byref(b),i)==0 and print("GPU-"+str(uuid.UUID(bytes=bytes(b))))) for i in range(2)]')
    actual = subprocess.check_output([PYTHON,'-c',probe],env=env,text=True).strip().splitlines()
    assert [v.lower() for v in actual]==[d['uuid'].lower() for d in devices],(actual,devices)
    with socket.socket() as s:
        assert s.connect_ex(('127.0.0.1',PORT))!=0,'Port occupied'
    args = [PYTHON,'-m','vllm.entrypoints.openai.api_server','--model',str(MODEL),'--served-model-name',MODEL_NAME,
        '--host','127.0.0.1','--port',str(PORT),'--tensor-parallel-size','2','--dtype','bfloat16',
        '--max-model-len','32768','--max-num-seqs','4','--max-num-batched-tokens','16384',
        '--gpu-memory-utilization','0.80','--seed','42','--enforce-eager',
        '--limit-mm-per-prompt','{"image":4,"video":0}',
        '--mm-processor-kwargs','{"max_pixels":2097152,"min_pixels":65536}',
        '--generation-config','vllm','--disable-log-requests']
    path = ROOT/'logs/appearance_vllm.log'
    stream = path.open('a')
    process = subprocess.Popen(args,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
    journal(server_pid=process.pid,stage='server_startup')
    write(ROOT/'logs/appearance_runtime.json',dict(started_at=now(),server_pid=process.pid,args=args,
        devices=devices,actual_cuda_uuids=actual,environment_python=PYTHON,
        software={p:importlib.metadata.version(p) for p in ['torch','vllm','transformers','numpy','Pillow','httpx']},
        cuda_visible_devices=env['CUDA_VISIBLE_DEVICES'],proxy=False))
    return process,stream


def wait_ready(process):
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline,last = time.monotonic()+1800,0
    while True:
        assert process.poll() is None,'vLLM server exited; inspect logs/appearance_vllm.log'
        try:
            with op.open(f'http://127.0.0.1:{PORT}/health',timeout=2) as r:
                if r.status==200:
                    return
        except OSError:
            pass
        assert time.monotonic()<deadline,'Startup exceeded 30min'
        if time.monotonic()-last>30:
            print(json.dumps({'stage':'server_startup','at':now()}),flush=True)
            last = time.monotonic()
        time.sleep(3)


@lru_cache(maxsize=128)
def image_url(path):
    return 'data:image/jpeg;base64,'+base64.b64encode(Path(path).read_bytes()).decode('ascii')


def request(unit,phase,prompts,client):
    out = RES/'raw'/phase/(unit['unit_key']+'.json')
    if out.exists():
        return read(out)
    promptset = read(RES/'prompts_locked.json')
    if phase=='generate':
        imgs = [unit['target_image']]+unit['generation_gallery']['images']
        prompt = promptset['generate']+'\n'+POLICY['generation_image_note']
        limit = 512
        gallery = None
    else:
        gallery = unit['global_gallery'] if phase=='blind_match' else unit['local_gallery']
        imgs = gallery['images']
        phrase = prompts['check']['phrase']
        pattern = promptset['blind_match' if phase=='blind_match' else 'reference_instant_match']
        prompt = pattern.format(phrase_json=json.dumps(phrase),labels_json=json.dumps(list(gallery['label_to_gt_id'])))
        limit = 768
    assert len(imgs)<=4
    content = [{'type':'text','text':prompt}]+[{'type':'image_url','image_url':{'url':image_url(p)}} for p in imgs]
    body = {'model':MODEL_NAME,'messages':[{'role':'system','content':promptset['system']},{'role':'user','content':content}],
            'temperature':0,'top_p':1,'seed':42,'max_tokens':limit,'repetition_penalty':1.0}
    started,at = time.monotonic(),now()
    response = client.post(f'http://127.0.0.1:{PORT}/v1/chat/completions',json=body,timeout=900)
    if response.status_code!=200:
        write(RES/'errors'/f'{phase}_{unit["unit_key"]}.json',{'at':now(),'status':response.status_code,'body':response.text})
    response.raise_for_status()
    data = response.json()
    raw = data['choices'][0]['message']['content']
    check = phrase_check(raw) if phase=='generate' else match_check(raw,gallery,unit['gt_id'])
    result = {'unit_key':unit['unit_key'],'sequence':unit['sequence'],'gt_id':unit['gt_id'],'phase':phase,
              'started_at':at,'completed_at':now(),'seconds':time.monotonic()-started,
              'prompt_text':prompt,'image_paths':imgs,'image_sha256':[sha(p) for p in imgs],
              'response':data,'check':check,
              'inference_policy_sha256':sha(RES/'inference_policy_locked.json')}
    write(out,result)
    return result


def run_phase(units,phase,generations,client):
    results = {}
    journal(stage=phase,total_units=len(units))
    with cf.ThreadPoolExecutor(max_workers=3) as pool:
        tasks = {pool.submit(request,u,phase,generations.get(u['unit_key']),client):u for u in units}
        for future in cf.as_completed(tasks):
            u = tasks[future]
            result = future.result()
            results[u['unit_key']] = result
            n = len(results)
            if n%20==0 or n==len(units):
                print(json.dumps({'stage':phase,'completed':n,'total':len(units),'at':now()}),flush=True)
                journal(completed_units=n)
    return results


def main():
    start = time.monotonic()
    policy_path = RES/'inference_policy_locked.json'
    if policy_path.exists():
        assert {k:v for k,v in read(policy_path).items() if k!='locked_at'}==POLICY
    else:
        write(policy_path,dict(POLICY,locked_at=now()))
        write(RES/'inference_code_receipt.json',{'at':now(),'policy_sha256':sha(policy_path),'runner_sha256':sha(Path(__file__)),
              'model_manifest_sha256':sha(ROOT/'sources/appearance/modelscope_manifest_pinned.json')})
    assert read(ROOT/'sources/appearance/download_complete.json')['revision']==read(RES/'protocol_locked.json')['model']['modelscope_revision']
    subprocess.run(['sha256sum','-c','--status',str(RES/'preinference_snapshot.sha256')],check=True,cwd=ROOT)
    units = rows(RES/'crop_manifest.jsonl')
    assert len(units)==273
    devices = allocate()
    process = stream = None
    done = threading.Event()
    memory = {}
    monitor = threading.Thread(target=memory_monitor,args=(devices,done,memory),daemon=True)
    status = 'FAILED'
    try:
        process,stream = start_server(devices)
        monitor.start()
        wait_ready(process)
        print(json.dumps({'stage':'server_ready','at':now()}),flush=True)
        with httpx.Client(trust_env=False,limits=httpx.Limits(max_connections=4,max_keepalive_connections=4)) as client:
            pilot = units[0]
            pstart = time.monotonic()
            g = request(pilot,'generate',None,client)
            pilot_results = [g]
            if g['check']['valid']:
                v = request(pilot,'blind_match',g,client)
                pilot_results.append(v)
                if v['check']['passed'] and pilot['anchor'] and pilot['anchor']['geometric_quality_pass']:
                    pilot_results.append(request(pilot,'reference_instant_match',g,client))
            elapsed = time.monotonic()-pstart
            # Deliberately pessimistic: up to three calls for every ID; no concurrency allowance.
            estimate = max(r['seconds'] for r in pilot_results)*3*273/3600
            write(RES/'inference_runtime_estimate.json',{'at':now(),'pilot_seconds':elapsed,'upper_scenario_hours':estimate,
                'method':'slowest observed pilot request x3 stages x273 IDs, ignoring endpoint concurrency; pilot retained, not used to tune captions or acceptance'})
            assert estimate<6,'Pilot estimates >6h; report before continuing'
            print(json.dumps({'stage':'pilot_complete','seconds':elapsed,'conservative_hours':estimate,'at':now()}),flush=True)
            gen = run_phase(units,'generate',{},client)
            valid = [u for u in units if gen[u['unit_key']]['check']['valid'] and u['crop_complete']]
            blind = run_phase(valid,'blind_match',gen,client)
            local_units = [u for u in valid if blind[u['unit_key']]['check']['passed'] and u['anchor'] and u['anchor']['geometric_quality_pass']]
            local = run_phase(local_units,'reference_instant_match',gen,client)
            write(RES/'inference_completeness.json',{'at':now(),'IDs':len(units),'generation_outputs':len(gen),
                'valid_phrases':len(valid),'blind_outputs':len(blind),'global_unique_pass':sum(x['check']['passed'] for x in blind.values()),
                'local_eligible':len(local_units),'local_outputs':len(local),'local_unique_pass':sum(x['check']['passed'] for x in local.values()),
                'conditional_skips': 'invalid/empty phrase -> no match request; blind not unique, no eligible anchor or poor geometry -> no local request; every ID retained in final ledger'})
        status = 'INFERENCE_COMPLETE_STOPPED_BEFORE_STAGE3'
    except BaseException as exc:
        journal(error=repr(exc),traceback=traceback.format_exc())
        raise
    finally:
        if process is not None:
            if process.poll() is None:
                os.killpg(process.pid,signal.SIGTERM)
            try:
                process.wait(timeout=45)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL)
                process.wait()
        if stream:
            stream.close()
        done.set()
        if monitor.is_alive():
            monitor.join(timeout=15)
        write(ROOT/'logs/appearance_gpu_memory.json',memory)
        journal(status=status,seconds=time.monotonic()-start,server_terminated=(process is None or process.poll() is not None),completed_at=now())
        print(json.dumps({'stage':status,'seconds':time.monotonic()-start,'at':now()}),flush=True)


if __name__=='__main__':
    main()
