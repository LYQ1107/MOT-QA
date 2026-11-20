"""Run only repaired T1 and gated controls using the unchanged Stage 6 loop."""
import concurrent.futures as cf
from datetime import datetime
import json
import os
import subprocess
import threading
import time
import traceback
import run_stage6 as base
from stage6_common import *
from stage6_runtime import start_server,stop
from stage6_tools import Tools
from stage7_parser import parse_call_pair,parse_fixed_call

STATE={};LOCK=threading.Lock();ATTEMPT=0;PROTOCOL={}


def target(mode,condition,qid):return ROOT/'results/stage7/predictions'/mode/condition/f'{qid}.json'


def journal(**update):
    with LOCK:
        STATE.update(update,updated_at=now());write(ROOT/'logs/stage7_job.json',STATE)
        print(json.dumps({k:STATE.get(k) for k in ['updated_at','status','stage','condition','mode','committed','expected','eta_min','error']},ensure_ascii=False),flush=True)


def allocate_one():
    snapshot=subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid,name,memory.total,memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True)
    apps=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_memory','--format=csv,noheader,nounits'],text=True)
    candidates=[]
    for line in snapshot.splitlines():
        index,uid,name,total,used,util=[x.strip() for x in line.split(',')];total=int(total);used=int(used)
        if 'A800' in name and total-used>=int(.65*total)+5632:
            candidates.append(dict(physical_index=int(index),uuid=uid,name=name,initial_used_MiB=used,initial_free_MiB=total-used,
                existing_process_count=sum(l.split(',')[0].strip()==uid for l in apps.splitlines()),initial_utilization=int(util)))
    candidates.sort(key=lambda d:(d['existing_process_count'],d['initial_utilization'],-d['initial_free_MiB'],d['physical_index']))
    assert candidates,('No GPU fits unchanged service memory; foreign jobs untouched',snapshot)
    result=dict(checked_at=now(),selected=candidates[0],gpu_count=1,sharing_user_authorized=True,snapshot=snapshot,compute_processes=apps)
    write(ROOT/f'logs/stage7_allocation_attempt{ATTEMPT}.json',result)
    return result


def run_condition(client,condition,mode):
    prompts=rows(PROTOCOL['T1_prompt_path'])
    if mode=='guided':prompts=[p for p in prompts if p['format']=='numerical']
    assert len(prompts)==(242 if mode=='guided' else 602)
    pending=[]
    for p in prompts:
        path=target(mode,condition,p['qa_id'])
        if path.exists():
            saved=read(path)
            assert saved['protocol_sha256']==sha(ROOT/'results/stage7_protocol_locked.json')
            assert saved['hypotheses_sha256']==PROTOCOL['hypotheses']['sha256']
            assert saved['initial_messages_sha256']==p['initial_messages_sha256'] and saved['error'] is None
        else:pending.append(p)
    started=time.monotonic();committed=len(prompts)-len(pending)
    journal(stage='inference',condition=condition,mode=mode,committed=committed,expected=len(prompts),eta_min=None)
    def work(p):
        try:
            out=base.infer_tools(p,client,mode,condition)
            if out is None:return None
            out.update(interface_version='stage7_complete_JSON_to_EOS',
                recovered_turn_indices=[t['turn'] for t in out['turns'] if parse_fixed_call(t['raw_response'])[2]],
                original_stage6_protocol_sha256=PROTOCOL['stage6_protocol_sha256'])
            write(target(mode,condition,p['qa_id']),out)
            return out
        except BaseException as error:
            base.STOP.set()
            with LOCK,(ROOT/'logs/stage7_request_errors.jsonl').open('a') as stream:
                stream.write(json.dumps(dict(at=now(),condition=condition,mode=mode,qa_id=p['qa_id'],error=repr(error),traceback=traceback.format_exc()),ensure_ascii=False)+'\n')
            raise
    with cf.ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(work,p) for p in pending]
        for future in cf.as_completed(futures):
            out=future.result()
            if out is None:continue
            committed+=1
            if committed%20==0 or committed==len(prompts):
                nnew=committed-(len(prompts)-len(pending))
                journal(condition=condition,mode=mode,committed=committed,expected=len(prompts),
                    eta_min=round((len(prompts)-committed)*(time.monotonic()-started)/max(nnew,1)/60,1))
    assert not base.STOP.is_set(),'Request failed; valid records preserved'
    values=[read(target(mode,condition,p['qa_id'])) for p in prompts]
    assert len(values)==len({p['qa_id'] for p in values})==len(prompts)
    path=ROOT/'results/stage7'/f'{mode}_{condition}_predictions.jsonl';write_rows(path,values)
    receipt=ROOT/'logs'/f'stage7_{mode}_{condition}_receipt.json'
    if pending or not receipt.exists():write(receipt,dict(completed_at=now(),condition=condition,mode=mode,predictions=len(values),
        new_predictions=len(pending),elapsed_s=time.monotonic()-started,output=str(path),sha256=sha(path)))


def controls_gate():
    path=ROOT/'results/stage7_controls_decision_locked.json'
    if path.exists():return read(path)
    from stage4_scores import inputs
    from compute_metrics import is_correct
    scopes,trackable=inputs();qs=[q for q in scopes['test'] if q['qa_id'] in trackable]
    predictions={p['qa_id']:p for p in rows(ROOT/'results/stage7/main_T1_predictions.jsonl')}
    reference={p['qa_id']:p for p in rows(PROTOCOL['primary_T_none_path'])}
    correct=sum(is_correct(predictions[q['qa_id']]['extracted_answer'],q) for q in qs)
    ref=sum(is_correct(reference[q['qa_id']]['extracted_answer'],q) for q in qs);assert ref==73
    value=dict(decided_at=now(),scope='test trackable251',T1_correct=correct,T_none_correct=ref,run_controls=correct>ref,
        gate='strictly more correct; significance not required',T1_sha256=sha(ROOT/'results/stage7/main_T1_predictions.jsonl'),
        T_none_sha256=PROTOCOL['primary_T_none_sha256'])
    immutable(path,value);return value


def main():
    global ATTEMPT,PROTOCOL
    verify_stage5();path=ROOT/'results/stage7_protocol_locked.json';PROTOCOL=read(path)
    for name,expected in PROTOCOL['source_sha256'].items():assert sha(ROOT/'src'/name)==expected,name
    assert sha(PROTOCOL['T1_prompt_path'])==PROTOCOL['T1_prompt_sha256']
    assert sha(PROTOCOL['primary_T_none_path'])==PROTOCOL['primary_T_none_sha256']
    assert sha(ROOT/'results/stage7_hypotheses_preregistered.json')==PROTOCOL['hypotheses']['sha256']
    assert sha(ROOT/'results/stage6_demonstrations_locked.json')==PROTOCOL['demonstrations_sha256']
    ATTEMPT=1+len(list((ROOT/'logs').glob('stage7_job_attempt*.json')))
    allocation=allocate_one();device=allocation['selected']
    # Use the exact previous loop: only parse_call and output destination differ.
    base.parse_call=parse_call_pair;base.target=target;base.ATTEMPT=ATTEMPT;base.TOOL_STORE=Tools()
    base.PROTOCOL=dict(sha256=sha(path),hypotheses_sha256=PROTOCOL['hypotheses']['sha256'],
        final_field_guidance_v2=True,guidance_fix_sha256=PROTOCOL['final_field_guidance_sha256'])
    STATE.update(status='RUNNING',started_at=now(),controller_pid=os.getpid(),attempt=ATTEMPT,
                 protocol_sha256=sha(path),hypotheses_sha256=PROTOCOL['hypotheses']['sha256'],allocation=allocation)
    journal(stage='starting_server')
    server=None;done=threading.Event();monitor_thread=None;memory=dict(own_peak_MiB=0,total_peak_MiB=0,gpu_uuid=device['uuid'])
    started=time.monotonic()
    try:
        server=start_server(device,f'stage7_{ATTEMPT}',progress=journal)
        write(ROOT/f'logs/stage7_runtime_attempt{ATTEMPT}.json',server[2])
        def monitor():
            import pynvml
            pynvml.nvmlInit();handle=pynvml.nvmlDeviceGetHandleByUUID(device['uuid'])
            try:
                while not done.is_set():
                    own=0
                    for p in pynvml.nvmlDeviceGetComputeRunningProcesses(handle):
                        try:
                            if os.getpgid(p.pid)==server[0].pid:own+=p.usedGpuMemory/1024**2
                        except ProcessLookupError:pass
                    memory['own_peak_MiB']=max(memory['own_peak_MiB'],own)
                    memory['total_peak_MiB']=max(memory['total_peak_MiB'],pynvml.nvmlDeviceGetMemoryInfo(handle).used/1024**2)
                    done.wait(5)
            finally:pynvml.nvmlShutdown()
        monitor_thread=threading.Thread(target=monitor,daemon=True);monitor_thread.start()
        from openai import OpenAI,DefaultHttpxClient
        client=OpenAI(api_key='local',base_url='http://127.0.0.1:18022/v1',
            http_client=DefaultHttpxClient(trust_env=False,timeout=900),timeout=900,max_retries=0)
        try:
            run_condition(client,'T1','main')
            decision=controls_gate();journal(controls_decision=decision)
            run_condition(client,'T1','guided')
            if decision['run_controls']:
                for condition in ('T-ph','T-sh'):
                    for mode in ('main','guided'):run_condition(client,condition,mode)
        finally:client.close()
        journal(status='COMPLETE',stage='all_requested_conditions_complete',elapsed_s=time.monotonic()-started)
    except BaseException as error:
        base.STOP.set();journal(status='FAILED',stage='failed',error=repr(error),traceback=traceback.format_exc(),elapsed_s=time.monotonic()-started)
        raise
    finally:
        done.set()
        if monitor_thread:monitor_thread.join(timeout=10)
        if server:stop(server[0],server[1])
        write(ROOT/f'logs/stage7_gpu_memory_attempt{ATTEMPT}.json',memory)
        write(ROOT/f'logs/stage7_job_attempt{ATTEMPT}.json',STATE)


if __name__=='__main__':main()
