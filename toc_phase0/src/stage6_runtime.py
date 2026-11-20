"""Registered two-GPU allocation and task-owned server lifecycle."""
import os
import signal
import socket
import subprocess
import time
import urllib.request
from stage6_common import ROOT,read,write,now
from stage5_server import environment

MODEL='Qwen/Qwen2.5-VL-7B-Instruct'


def allocation():
    snapshot=subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid,name,memory.total,memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True)
    procs=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_memory','--format=csv,noheader,nounits'],text=True)
    candidates=[]
    for line in snapshot.splitlines():
        ix,uid,name,total,used,util=[v.strip() for v in line.split(',')];total=int(total);used=int(used)
        if 'A800' in name and total-used>=int(.65*total)+5632:
            candidates.append(dict(physical_index=int(ix),uuid=uid,name=name,initial_used_MiB=used,
                initial_free_MiB=total-used,existing_process_count=sum(l.split(',')[0].strip()==uid for l in procs.splitlines()),initial_utilization=int(util)))
    candidates.sort(key=lambda d:(d['existing_process_count'],d['initial_utilization'],-d['initial_free_MiB'],d['physical_index']))
    assert len(candidates)>=2,('Two GPUs need enough memory; other jobs untouched',snapshot)
    result=dict(checked_at=now(),vllm=candidates[0],training_and_lora_eval=candidates[1],
                registered_physical_gpus=[candidates[0]['physical_index'],candidates[1]['physical_index']],
                sharing_user_authorized=True,full_snapshot=snapshot,processes=procs)
    return result


def env_for(device,training=False):
    env=environment(device);env.update(STAGE6_GPU_UUID=device['uuid'],WANDB_DISABLED='true',HF_DATASETS_OFFLINE='1',
        MPLCONFIGDIR=str(ROOT/'cache/stage6_matplotlib'),HF_DATASETS_CACHE=str(ROOT/'cache/stage6_datasets'))
    return env


def verify_uuid(device,env):
    code=('import ctypes,uuid; d=ctypes.CDLL("libcuda.so.1"); assert d.cuInit(0)==0; '
          'b=(ctypes.c_ubyte*16)(); assert d.cuDeviceGetUuid(ctypes.byref(b),0)==0; '
          'print("GPU-"+str(uuid.UUID(bytes=bytes(b))))')
    actual=subprocess.check_output([str(ROOT/'env/bin/python'),'-c',code],env=env,text=True).strip()
    assert actual.lower()==device['uuid'].lower(),(actual,device)
    return actual


def launch_training(device,attempt):
    env=env_for(device,True);verify_uuid(device,env)
    path=ROOT/f'logs/stage6_training_attempt{attempt}.log';stream=path.open('w')
    args=[str(ROOT/'env_stage6_train/bin/python'),'-u',str(ROOT/'src/train_stage6.py')]
    process=subprocess.Popen(args,env=env,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
    return process,stream,dict(pid=process.pid,args=args,device=device,log=str(path))


def start_server(device,attempt,lora=False,progress=lambda **x:None):
    port=18023 if lora else 18022
    with socket.socket() as sock:assert sock.connect_ex(('127.0.0.1',port))!=0,f'Port{port} occupied'
    env=env_for(device);actual=verify_uuid(device,env)
    args=[str(ROOT/'env/bin/python'),'-m','vllm.entrypoints.openai.api_server',
        '--model',str(ROOT/'models/Qwen2.5-VL-7B-Instruct'),'--served-model-name',MODEL,
        '--host','127.0.0.1','--port',str(port),'--tensor-parallel-size','1','--dtype','bfloat16',
        '--max-model-len','65536','--max-num-seqs','8','--max-num-batched-tokens','32768',
        '--gpu-memory-utilization','0.65','--seed','42','--enforce-eager',
        '--limit-mm-per-prompt','{"image":{"count":40,"width":720,"height":720},"video":0}',
        '--disable-log-requests']
    if lora:args+=['--enable-lora','--max-lora-rank','8','--lora-modules',f'stage6_lora={ROOT/"models/stage6_lora_r8"}']
    kind='lora' if lora else 'base';path=ROOT/f'logs/stage6_vllm_{kind}_attempt{attempt}.log';stream=path.open('w')
    process=subprocess.Popen(args,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
    record=dict(kind=kind,pid=process.pid,port=port,device=device,args=args,actual_cuda_uuid=actual,log=str(path))
    write(ROOT/f'logs/stage6_runtime_{kind}_attempt{attempt}.json',record)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}));deadline=time.monotonic()+1800;last=0
    try:
        while True:
            assert process.poll() is None,f'Server exited; see{path}'
            try:
                with opener.open(f'http://127.0.0.1:{port}/health',timeout=2) as response:
                    if response.status==200:break
            except OSError:pass
            assert time.monotonic()<deadline,f'Server startup exceeded30min; see{path}'
            if time.monotonic()-last>30:progress(stage=f'{kind}_server_startup',server_pid=process.pid);last=time.monotonic()
            time.sleep(3)
    except BaseException:
        stop(process,stream);raise
    return process,stream,record


def stop(process,stream):
    if process.poll() is None:
        try:os.killpg(process.pid,signal.SIGTERM)
        except ProcessLookupError:pass
    try:process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid,signal.SIGKILL);process.wait()
    stream.close()
