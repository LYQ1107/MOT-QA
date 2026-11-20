"""Custom multi-turn tools plus concurrent synthetic LoRA and frozen B-events evaluation."""
import concurrent.futures as cf
import json
import os
import re
import threading
import time
import traceback
from pathlib import Path

from stage6_common import *
from stage6_tools import Tools
from stage6_runtime import MODEL,allocation,launch_training,start_server,stop

STOP=threading.Event();JOURNAL_LOCK=threading.Lock();LOOK_LOCK=threading.Lock()
STATE={};ATTEMPT=0;PROTOCOL={};TOOL_STORE=None


def journal(**update):
    with JOURNAL_LOCK:
        STATE.update(update,updated_at=now());write(ROOT/'logs/stage6_job.json',STATE)
        view={k:STATE.get(k) for k in ['updated_at','status','stage','tools_stage','tools_committed','tools_expected','tools_eta_min','lora_stage','lora_committed','lora_expected','lora_eta_min','error']}
        training=ROOT/'logs/stage6_training_job.json'
        if training.exists():
            tr=read(training);view['training']={k:tr.get(k) for k in ['status','stage','global_step','max_steps','epoch','error']}
        print(json.dumps(view,ensure_ascii=False),flush=True)


def target(mode,condition,qid):return ROOT/'results/stage6/predictions'/mode/condition/f'{qid}.json'


def call_model(client,messages,remaining,guided,allow_tools,model=MODEL):
    if guided and PROTOCOL.get('final_field_guidance_v2'):
        from stage6_final_field_guidance import generate
        return generate(client,materialize(messages),remaining,model)
    kwargs=dict(model=model,messages=materialize(messages),temperature=0.,seed=42,max_tokens=remaining)
    if guided:kwargs['extra_body']=dict(structured_outputs=dict(regex=TOOL_OR_FINAL_REGEX if allow_tools else FINAL_REGEX),bad_words=['<|endoftext|>'])
    response=client.chat.completions.create(**kwargs);choice=response.choices[0]
    assert isinstance(choice.message.content,str)
    assert response.usage.prompt_tokens+remaining<=65536
    assert 0<=response.usage.completion_tokens<=remaining
    if guided and choice.finish_reason!='length':
        assert re.fullmatch(TOOL_OR_FINAL_REGEX if allow_tools else FINAL_REGEX,choice.message.content),('Constrained output violated grammar',choice.message.content)
    return response,choice


def infer_tools(p,client,mode,condition):
    if STOP.is_set():return None
    qid=p['qa_id'];start=time.monotonic();messages=__import__('copy').deepcopy(p['messages'])
    output=dict(qa_id=qid,video_id=p['video_id'],format=p['format'],condition=condition,decoding=mode,
                template='stage6_tools',started_at=now(),error=None,tool_calls=[],turns=[],
                protocol_sha256=PROTOCOL['sha256'],hypotheses_sha256=PROTOCOL['hypotheses_sha256'],
                initial_messages_sha256=p['initial_messages_sha256'],attempt=ATTEMPT,
                guidance_fix_sha256=PROTOCOL.get('guidance_fix_sha256') if mode=='guided' else None)
    consumed=0;calls=0;raw='';finish=None
    for turn in range(5):
        if consumed>=2048:break
        remaining=2048-consumed;allowed=condition!='T-none' and calls<4
        response,choice=call_model(client,messages,remaining,mode=='guided',allowed)
        actual_initial=(response.physical_requests[0]['usage']['prompt_tokens'] if hasattr(response,'physical_requests') else response.usage.prompt_tokens)
        if turn==0:assert actual_initial==p['expected_initial_prompt_tokens'],(qid,actual_initial,p['expected_initial_prompt_tokens'])
        raw=choice.message.content;finish=choice.finish_reason;consumed+=response.usage.completion_tokens
        output['turns'].append(dict(turn=turn,raw_response=raw,usage=response.usage.model_dump(),finish_reason=finish,response_id=response.id,
                                    max_tokens=remaining,stop_reason=getattr(choice,'stop_reason',None),
                                    physical_requests=getattr(response,'physical_requests',None)))
        messages.append(dict(role='assistant',content=raw))
        call,parse_error=parse_call(raw)
        if call is None and parse_error is None:break
        if calls>=4:
            output['rejected_after_call_budget']=dict(parsed_call=call,parse_error=parse_error,reason='Final turn requested a fifth call; not executed')
            break
        calls+=1
        if call is None:result=dict(legal=False,matched=False,name=None,arguments=None,text=parse_error,images=[])
        elif not allowed:result=dict(legal=False,matched=False,**call,text='No tools are available now. Give your final answer directly.',images=[])
        else:
            kind='placeholder' if condition=='T-ph' else 'shuffled' if condition=='T-sh' else 'real'
            if call['name']=='look':
                with LOOK_LOCK:result=TOOL_STORE.execute(p['video_id'],**call,mode=kind)
            else:result=TOOL_STORE.execute(p['video_id'],**call,mode=kind)
        output['tool_calls'].append(dict(call_index=calls,parsed_call=call,parse_error=parse_error,result=result))
        if calls>=4:
            result=dict(result,text=result['text']+'\nTool-call budget exhausted. Do not call any tool again. Give a brief explanation and your final Answer: line now.')
        messages.append(tool_message(result))
        assert sum(b['type']=='image_path' for m in messages if isinstance(m['content'],list) for b in m['content'])<=40
        if calls>=4 and turn>=4:break
    answer,region=final_answer(raw,p['format'])
    # A response still issuing a call is not a final answer, even if it also prints a label.
    if '<tool_call' in raw:answer=None
    output.update(completed_at=now(),latency_s=round(time.monotonic()-start,3),raw_response=raw,extracted_answer=answer,
        final_answer_region=region,total_generated_tokens=consumed,max_total_generation_tokens=2048,
        finish_reason=finish,call_attempts=calls,messages=messages,parse_failed=answer is None,
        budget_exhausted=consumed>=2048,original_frame_count=32)
    assert consumed<=2048 and calls<=4
    write(target(mode,condition,qid),output)
    return output


def infer_lora(p,client):
    if STOP.is_set():return None
    directory,sample=sampling(p['video_id'])
    messages=[dict(role='system',content=p['system']),dict(role='user',content=[dict(type='image_path',path=str(directory/name)) for name in sample['jpeg_files']]+[dict(type='text',text=p['user'])])]
    start=time.monotonic();started=now()
    response,choice=call_model(client,messages,1024,False,False,'stage6_lora')
    assert response.usage.prompt_tokens==p['expected_prompt_tokens']
    raw=choice.message.content;answer,region=final_answer(raw,p['format'])
    out=dict(qa_id=p['qa_id'],video_id=p['video_id'],format=p['format'],condition='LoRA-B-events',template='stage5_reasoning',
        decoding='main',started_at=started,completed_at=now(),latency_s=round(time.monotonic()-start,3),
        raw_response=raw,extracted_answer=answer,final_answer_region=region,error=None,
        messages=messages+[dict(role='assistant',content=raw)],usage=response.usage.model_dump(),finish_reason=choice.finish_reason,
        max_tokens=1024,attempt=ATTEMPT,hypotheses_sha256=PROTOCOL['hypotheses_sha256'],
        adapter_sha256=read(ROOT/'results/stage6_training_receipt.json')['adapter_sha256'],
        reused_stage5_prompt_sha256=p['prompt_sha256'])
    write(target('main','LoRA-B-events',p['qa_id']),out);return out


def run_condition(condition,mode,client,base_condition=None,lora=False):
    if lora:
        test=set(read(ROOT/'results/dev_test_split_locked.json')['test_qa_ids'])
        trackable=set(read(ROOT/'results/trackable_subset_preregistered.json')['trackable_qa_ids'])
        prompts=[p for p in rows(ROOT/'results/stage5/prompts/reasoning/B-events.jsonl') if p['qa_id'] in test&trackable]
    else:prompts=rows(ROOT/'results/stage6/prompts'/f'{base_condition or condition}.jsonl')
    if mode=='guided':prompts=[p for p in prompts if p['format']=='numerical']
    expected=251 if lora else 242 if mode=='guided' else 602
    assert len(prompts)==expected
    unfinished=[]
    for p in prompts:
        path=target(mode,condition,p['qa_id'])
        if path.exists():
            old=read(path);assert old['hypotheses_sha256']==PROTOCOL['hypotheses_sha256'] and old['error'] is None
            if not lora:assert old['initial_messages_sha256']==p['initial_messages_sha256'] and old['protocol_sha256']==PROTOCOL['sha256']
        else:unfinished.append(p)
    start=time.monotonic();committed=len(prompts)-len(unfinished)
    prefix='lora' if lora else 'tools'
    journal(**{prefix+'_stage':condition+'/'+mode,prefix+'_committed':committed,prefix+'_expected':expected})
    def work(p):
        try:return infer_lora(p,client) if lora else infer_tools(p,client,mode,condition)
        except BaseException as error:
            STOP.set()
            failure=dict(at=now(),qa_id=p['qa_id'],condition=condition,mode=mode,error=repr(error),traceback=traceback.format_exc())
            with JOURNAL_LOCK,(ROOT/'logs/stage6_request_errors.jsonl').open('a') as stream:stream.write(json.dumps(failure,ensure_ascii=False)+'\n')
            raise
    with cf.ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(work,p) for p in unfinished]
        for future in cf.as_completed(futures):
            result=future.result()
            if result is None:continue
            committed+=1
            if committed%20==0 or committed==expected:
                elapsed=time.monotonic()-start;nnew=committed-(len(prompts)-len(unfinished))
                journal(**{prefix+'_stage':condition+'/'+mode,prefix+'_committed':committed,prefix+'_expected':expected,
                           prefix+'_eta_min':round((expected-committed)*elapsed/max(nnew,1)/60,1)})
    assert not STOP.is_set(),'Another worker failed; valid individual records preserved'
    values=[read(target(mode,condition,p['qa_id'])) for p in prompts]
    assert len({v['qa_id'] for v in values})==expected
    out=ROOT/'results/stage6'/f'{mode}_{condition}_predictions.jsonl';write_rows(out,values)
    receipt=ROOT/'logs'/f'stage6_{mode}_{condition}_receipt.json'
    if unfinished or not receipt.exists():write(receipt,dict(completed_at=now(),condition=condition,mode=mode,predictions=expected,
        new_predictions=len(unfinished),elapsed_s=round(time.monotonic()-start,3),output=str(out),sha256=sha(out)))


def decide_controls():
    path=ROOT/'results/stage6_controls_decision_locked.json'
    if path.exists():return read(path)
    # Offline scoring is confined to this prespecified gate, never passed to a model or a tool.
    from stage4_scores import inputs
    from compute_metrics import is_correct
    scopes,trackable=inputs();items=[q for q in scopes['test'] if q['qa_id'] in trackable]
    scores={};hashes={}
    for c in ['T-none','T0','T1']:
        file=ROOT/'results/stage6'/f'main_{c}_predictions.jsonl';ps={p['qa_id']:p for p in rows(file)}
        scores[c]=sum(is_correct(ps[q['qa_id']]['extracted_answer'],q) for q in items);hashes[c]=sha(file)
    best='T0' if scores['T0']>=scores['T1'] else 'T1'
    value=dict(decided_at=now(),primary_n=251,correct=scores,best=best,run_controls=scores[best]>scores['T-none'],
               rule='Observed strictly higher correct count; T0 wins ties; fixed before control inference',prediction_sha256=hashes)
    immutable(path,value);return value


def main():
    global ATTEMPT,PROTOCOL,TOOL_STORE,TOOL_OR_FINAL_REGEX
    verify_stage5();protocol_path=ROOT/'results/stage6_protocol_locked.json';protocol=read(protocol_path)
    for source,expected in protocol['source_sha256'].items():assert sha(ROOT/'src'/source)==expected
    for artifact in protocol['prompts']:assert sha(artifact['path'])==artifact['sha256']
    PROTOCOL=dict(sha256=sha(protocol_path),hypotheses_sha256=sha(ROOT/'results/stage6_hypotheses_preregistered.json'))
    fix_path=ROOT/'results/stage6_guided_tool_turn_fix_locked.json'
    if fix_path.exists():
        fix=read(fix_path)
        assert fix['final_answer_regex_unchanged']==FINAL_REGEX
        TOOL_OR_FINAL_REGEX=fix['corrected_tool_or_final_regex']
        PROTOCOL['guidance_fix_sha256']=sha(fix_path)
    final_field_fix=ROOT/'results/stage6_final_field_guidance_v2_locked.json'
    if final_field_fix.exists():
        fix=read(final_field_fix)
        assert sha(ROOT/'src/stage6_final_field_guidance.py')==fix['implementation_sha256']
        PROTOCOL.update(final_field_guidance_v2=True,guidance_fix_sha256=sha(final_field_fix))
    ATTEMPT=1+len(list((ROOT/'logs').glob('stage6_job_attempt*.json')))
    allocation_path=ROOT/'logs/stage6_allocation_locked.json'
    if allocation_path.exists():devices=read(allocation_path)
    else:
        devices=allocation();immutable(allocation_path,devices)
    STATE.update(status='RUNNING',controller_pid=os.getpid(),started_at=now(),attempt=ATTEMPT,
                 protocol_sha256=PROTOCOL['sha256'],hypotheses_sha256=PROTOCOL['hypotheses_sha256'],allocation=devices,
                 source_sha256={s:sha(ROOT/'src'/s) for s in ['run_stage6.py','stage6_runtime.py','train_stage6.py']})
    journal(stage='initializing')
    TOOL_STORE=Tools();servers=[];train=None;errors=[];memory={};monitor_done=threading.Event();groups=set();groups_lock=threading.Lock()
    def monitor():
        import pynvml
        pynvml.nvmlInit()
        for device in (devices['vllm'],devices['training_and_lora_eval']):memory[device['uuid']]=dict(own_peak_MiB=0,total_peak_MiB=0)
        while not monitor_done.is_set():
            with groups_lock:owned_groups=set(groups)
            for uid,stats in memory.items():
                handle=pynvml.nvmlDeviceGetHandleByUUID(uid);own=0
                for p in pynvml.nvmlDeviceGetComputeRunningProcesses(handle):
                    try:
                        if os.getpgid(p.pid) in owned_groups:own+=p.usedGpuMemory/1024**2
                    except ProcessLookupError:pass
                stats['own_peak_MiB']=max(stats['own_peak_MiB'],own)
                stats['total_peak_MiB']=max(stats['total_peak_MiB'],pynvml.nvmlDeviceGetMemoryInfo(handle).used/1024**2)
            monitor_done.wait(5)
        pynvml.nvmlShutdown()
    monitor_thread=threading.Thread(target=monitor,daemon=True);monitor_thread.start()
    from openai import OpenAI,DefaultHttpxClient
    lora_thread=None;started=time.monotonic()
    try:
        if not (ROOT/'results/stage6_training_receipt.json').exists():
            train=launch_training(devices['training_and_lora_eval'],ATTEMPT)
            with groups_lock:groups.add(train[0].pid)
            write(ROOT/f'logs/stage6_runtime_training_attempt{ATTEMPT}.json',train[2]);journal(training_pid=train[0].pid)
        def train_eval():
            try:
                if train:
                    code=train[0].wait();train[1].close()
                    assert code==0,('LlamaFactory training failed',train[2]['log'])
                assert read(ROOT/'results/stage6_training_receipt.json')['epochs']>=2.-1e-6
                completed_lora=ROOT/'logs/stage6_main_LoRA-B-events_receipt.json'
                if completed_lora.exists():
                    receipt=read(completed_lora)
                    assert receipt['predictions']==251 and sha(receipt['output'])==receipt['sha256']
                    run_condition('LoRA-B-events','main',None,lora=True)
                    journal(lora_stage='complete_reused_no_model_launch')
                    return
                server=start_server(devices['training_and_lora_eval'],ATTEMPT,lora=True,progress=lambda **x:journal(lora_stage=x['stage']))
                servers.append(server)
                with groups_lock:groups.add(server[0].pid)
                client=OpenAI(api_key='local',base_url='http://127.0.0.1:18023/v1',http_client=DefaultHttpxClient(trust_env=False,timeout=900),timeout=900,max_retries=0)
                try:run_condition('LoRA-B-events','main',client,lora=True)
                finally:client.close();stop(server[0],server[1]);servers.remove(server)
                journal(lora_stage='complete')
            except BaseException as error:errors.append(dict(branch='training_lora',error=repr(error),traceback=traceback.format_exc()));STOP.set()
        lora_thread=threading.Thread(target=train_eval);lora_thread.start()
        server=start_server(devices['vllm'],ATTEMPT,progress=journal);servers.append(server)
        with groups_lock:groups.add(server[0].pid)
        client=OpenAI(api_key='local',base_url='http://127.0.0.1:18022/v1',http_client=DefaultHttpxClient(trust_env=False,timeout=900),timeout=900,max_retries=0)
        try:
            for mode in ['main','guided']:
                for condition in ['T-none','T0','T1']:run_condition(condition,mode,client)
            decision=decide_controls();journal(controls_decision=decision)
            if decision['run_controls']:
                for mode in ['main','guided']:
                    for condition in ['T-ph','T-sh']:run_condition(condition,mode,client,base_condition=decision['best'])
            journal(tools_stage='complete')
        finally:client.close();stop(server[0],server[1]);servers.remove(server)
        if lora_thread:lora_thread.join()
        assert not errors,errors
        assert not STOP.is_set()
        journal(status='COMPLETE',stage='inference_and_training_complete',elapsed_s=round(time.monotonic()-started,3))
    except BaseException as error:
        STOP.set();journal(status='FAILED',stage='failed',error=repr(error),traceback=traceback.format_exc(),branch_errors=errors,elapsed_s=round(time.monotonic()-started,3));raise
    finally:
        for process,stream,record in list(servers):stop(process,stream)
        if train and train[0].poll() is None:stop(train[0],train[1])
        if lora_thread and lora_thread.is_alive():lora_thread.join(timeout=40)
        monitor_done.set();monitor_thread.join(timeout=10)
        write(ROOT/f'logs/stage6_gpu_memory_attempt{ATTEMPT}.json',memory)
        write(ROOT/f'logs/stage6_job_attempt{ATTEMPT}.json',STATE)


if __name__=='__main__':main()
