"""Complete the locked two-template matrix; preserve every raw response and failure."""
import argparse
import concurrent.futures as cf
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time
import traceback

from stage5_common import *
from stage5_guided_v2_server import (PORTS,MODEL,STOP,MUTEX,JOB,journal,allocation,start_servers,
                          stop_servers,gpu_monitor,frames)


FINAL_NUMBER_REGEX='(?:(?:[^A\\n][^\\n]*|A|A[^n\\n][^\\n]*|An|An[^s\\n][^\\n]*|Ans|Ans[^w\\n][^\\n]*|Answ|Answ[^e\\n][^\\n]*|Answe|Answe[^r\\n][^\\n]*|Answer|Answer[^:\\n][^\\n]*)?\\n)*Answer: (2|3|4|5 or more)'
GUIDANCE_PROTOCOL_SHA256='a850b394a5ece1a115ddd8a59e4e35c4519d9c8c3f70c924cf726d862ab55efe'

def path_for(template,mode,condition,qid):
    return ROOT/'results/stage5_guided_v2/predictions'/template/mode/condition/f'{qid}.json'


def infer(p,slot,mode,attempt,client):
    if STOP.is_set():return None
    start=time.monotonic();started_at=now()
    try:
        content=[dict(type='image_url',image_url=dict(url='data:image/jpeg;base64,'+b64)) for b64 in frames(p['video_id'])]
        content.append(dict(type='text',text=p['user']))
        kwargs=dict(model=MODEL,messages=[dict(role='system',content=p['system']),dict(role='user',content=content)],
                    temperature=0.,max_tokens=p['max_tokens'],seed=42)
        if mode=='guided':
            assert p['format']=='numerical'
            constraint=dict(regex=FINAL_NUMBER_REGEX) if p['template']=='reasoning' else dict(choice=list(LEGAL))
            kwargs['extra_body']=dict(structured_outputs=constraint)
            if p['template']=='reasoning':
                # The HF generation config also stops on151643, but xgrammar
                # recognizes only tokenizer EOS151645. Prevent early stopping
                # through that extra token in the arbitrary reasoning prefix.
                kwargs['extra_body']['bad_words']=['<|endoftext|>']
        response=client.chat.completions.create(**kwargs)
        choice=response.choices[0];raw=choice.message.content
        assert isinstance(raw,str)
        assert response.usage.prompt_tokens==p['expected_prompt_tokens'],(p['qa_id'],response.usage.prompt_tokens,p['expected_prompt_tokens'])
        if p['template']=='reasoning':answer,region=final_answer(raw,p['format'])
        else:answer,region=extract(raw,p['format']),raw.strip()
        violation=bool(mode=='guided' and choice.finish_reason!='length' and
                       (region not in LEGAL or (p['template']=='reasoning' and not re.fullmatch(FINAL_NUMBER_REGEX,raw))))
        record=dict(qa_id=p['qa_id'],video_id=p['video_id'],format=p['format'],template=p['template'],condition=p['condition'],
            decoding=mode,raw_response=raw,extracted_answer=answer,final_answer_region=region,error=None,
            started_at=started_at,completed_at=now(),latency_s=round(time.monotonic()-start,3),
            usage=response.usage.model_dump(),finish_reason=choice.finish_reason,max_tokens=p['max_tokens'],
            prompt_sha256=p['prompt_sha256'],expected_prompt_tokens=p['expected_prompt_tokens'],sampled_frames=len(content)-1,
            endpoint_slot=slot,attempt=attempt,response_id=response.id,stop_reason=getattr(choice,'stop_reason',None),
            constraint_violation=violation,guidance_version='v2_committed_final_answer_field',guidance_protocol_sha256=GUIDANCE_PROTOCOL_SHA256,
            guided_eos_fix_sha256=JOB.get('guided_eos_fix_sha256') if mode=='guided' and p['template']=='reasoning' else None,
            hypotheses_sha256=JOB['hypotheses_sha256'],representation_manifest_sha256=JOB['representation_manifest_sha256'],
            frozen_config_sha256=JOB['frozen_config_sha256'],d_assignment_sha256=JOB['d_assignment_sha256'])
        write(path_for(p['template'],mode,p['condition'],p['qa_id']),record)
        assert not violation,('Completed constrained response violated final-answer grammar; raw record saved',raw)
        return record
    except Exception as error:
        STOP.set()
        failure=dict(at=now(),qa_id=p['qa_id'],condition=p['condition'],template=p['template'],decoding=mode,
            endpoint_slot=slot,attempt=attempt,error=repr(error),traceback=traceback.format_exc())
        with MUTEX,(ROOT/'logs/stage5_guided_v2_request_errors.jsonl').open('a') as stream:stream.write(json.dumps(failure,ensure_ascii=False)+'\n')
        raise RuntimeError(json.dumps(failure,ensure_ascii=False)) from error


def run_condition(template,mode,condition,attempt,clients,slots):
    records=rows(ROOT/'results/stage5/prompts'/template/f'{condition}.jsonl')
    if mode=='guided':records=[p for p in records if p['format']=='numerical']
    assert len(records)==(300 if mode=='guided' else 749)
    existing={}
    for p in records:
        path=path_for(template,mode,condition,p['qa_id'])
        if path.exists():
            rec=read(path)
            assert rec['prompt_sha256']==p['prompt_sha256'] and rec['error'] is None
            assert rec['hypotheses_sha256']==JOB['hypotheses_sha256']
            assert rec['representation_manifest_sha256']==JOB['representation_manifest_sha256']
            assert rec['template']==template and rec['condition']==condition and rec['decoding']==mode
            existing[p['qa_id']]=rec
    unfinished=[p for p in records if p['qa_id'] not in existing]
    receipt_path=ROOT/'logs'/f'stage5_guided_v2_{template}_{mode}_{condition}_receipt.json'
    if not unfinished and receipt_path.exists():
        prior=read(receipt_path)
        assert prior['predictions']==len(records) and sha(prior['output'])==prior['sha256']
        print(json.dumps(dict(resume='already complete; original timing and raw predictions preserved',template=template,mode=mode,condition=condition)),flush=True)
        return
    started=time.monotonic()
    journal(stage='inference',template=template,decoding=mode,condition=condition,expected=len(records),
            committed=len(existing),new_committed=0,eta_minutes=None,phase_elapsed_s=0)
    pools=[cf.ThreadPoolExecutor(max_workers=4) for _ in clients]
    try:
        pending=[pools[slots[p['qa_id']]].submit(infer,p,slots[p['qa_id']],mode,attempt,clients[slots[p['qa_id']]]) for p in unfinished]
        completed=0
        for future in cf.as_completed(pending):
            result=future.result()
            if result is None:continue
            completed+=1
            if completed%25==0 or completed==len(unfinished):
                elapsed=time.monotonic()-started
                eta=(len(unfinished)-completed)*elapsed/completed/60
                journal(committed=len(existing)+completed,new_committed=completed,phase_elapsed_s=round(elapsed,1),eta_minutes=round(eta,1))
                print(json.dumps(dict(template=template,decoding=mode,condition=condition,committed=len(existing)+completed,expected=len(records),eta_minutes=round(eta,1))),flush=True)
    finally:
        for pool in pools:pool.shutdown(wait=True,cancel_futures=STOP.is_set())
    saved=[read(path_for(template,mode,condition,p['qa_id'])) for p in records]
    assert len(saved)==len({p['qa_id'] for p in saved})==len(records)
    output=ROOT/'results/stage5_guided_v2'/f'{template}_{mode}_{condition}_predictions.jsonl'
    write_rows(output,saved)
    receipt=dict(completed_at=now(),template=template,decoding=mode,condition=condition,predictions=len(saved),
        new_predictions=len(unfinished),elapsed_this_attempt_s=round(time.monotonic()-started,3),
        parse_failures=sum(p['extracted_answer'] is None for p in saved),
        truncated=sum(p['finish_reason']=='length' for p in saved),sha256=sha(output),output=str(output))
    write(receipt_path,receipt)
    print(json.dumps(receipt),flush=True)
    if template=='reasoning' and mode=='main' and condition=='A':
        subprocess.run([str(ROOT/'env/bin/python'),'-c','from stage5_scores import routing; routing("reasoning")'],
            cwd=ROOT,env=dict(os.environ,PYTHONPATH=str(ROOT/'src')),check=True)


def main(args):
    started=time.monotonic();lock=verify_stage5()
    assert sha(ROOT/'results/stage5_guided_v2_commit_protocol_locked.json')==GUIDANCE_PROTOCOL_SHA256
    for name,expected in lock['source_sha256'].items():assert sha(ROOT/'src'/name)==expected
    for video in read(ROOT/'results/stage4_image_manifest_locked.json')['videos']:
        directory,_=sampling(video['video_id'])
        assert sha(directory/'sampling.json')==video['sampling_sha256']
        for file in video['files']:assert sha(file['path'])==file['sha256']
    for row in read(ROOT/'results/stage5_representations_locked.json')['files']:
        for kind in ('main','events','facts'):assert sha(row[kind+'_path'])==row[kind+'_sha256']
    for file in read(ROOT/'results/stage5_stage4_reuse_locked.json')['files']:assert sha(file['path'])==file['sha256']
    attempt=max(len(list((ROOT/'logs').glob('stage5_guided_v2_runtime_attempt*.json'))),
                len(list((ROOT/'logs').glob('stage5_guided_v2_job_attempt*.json'))))+1
    previous=ROOT/'logs/stage5_guided_v2_job.json'
    if previous.exists():write(ROOT/'logs'/f'stage5_guided_v2_previous_job_before_attempt{attempt}.json',read(previous))
    JOB.update(status='RUNNING',started_at=now(),controller_pid=os.getpid(),attempt=attempt,phase=args.phase,
        frozen_config_sha256=lock['frozen_config_sha256'],hypotheses_sha256=sha(ROOT/'results/stage5_hypotheses_preregistered.json'),
        representation_manifest_sha256=sha(ROOT/'results/stage5_representations_locked.json'),
        d_assignment_sha256=sha(ROOT/'results/stage4_D_assignments_locked.json'))
    eos_fix=ROOT/'results/stage5_guided_eos_fix_locked.json'
    assert eos_fix.exists() and eos_fix.stat().st_mode&0o222==0
    JOB['guided_eos_fix_sha256']=sha(eos_fix)
    journal(stage='preflight')
    slots=read(ROOT/'results/stage4_endpoint_shards_locked.json')['assignments']
    servers=[];monitor_done=threading.Event();memory={};monitor=None
    try:
        resource_started=time.monotonic()
        while True:
            try:
                devices=allocation(attempt)
                break
            except AssertionError as resource_error:
                if not str(resource_error).startswith('Two A800 need'):
                    raise
                journal(stage='waiting_gpus',resource_wait_s=round(time.monotonic()-resource_started),
                        resource_wait_reason=str(resource_error),server_ready=0)
                assert time.monotonic()-resource_started<4*3600, 'GPU capacity unchanged for4h; existing jobs remain untouched.'
                print('Waiting internally for two GPUs with unchanged Stage4 memory/configuration requirements.',flush=True)
                time.sleep(60)
        servers=start_servers(devices,attempt)
        monitor=threading.Thread(target=gpu_monitor,args=(devices,servers,monitor_done,memory),daemon=True);monitor.start()
        import httpx
        from openai import OpenAI
        clients=[OpenAI(api_key='EMPTY',base_url=f'http://127.0.0.1:{port}/v1',timeout=1200,max_retries=0,
            http_client=httpx.Client(trust_env=False,timeout=1200)) for port in PORTS]
        phases=[('reasoning','guided',CONDITIONS)]
        for template,mode,conditions in phases:
            if args.phase!='all' and args.phase!=template+'_'+mode:continue
            for condition in conditions:run_condition(template,mode,condition,attempt,clients,slots)
            write(ROOT/'logs'/f'stage5_guided_v2_{template}_{mode}_complete.json',dict(completed_at=now(),template=template,decoding=mode,
                conditions=list(conditions),predictions_per_condition=300 if mode=='guided' else 749))
        for client in clients:client.close()
        journal(status='INFERENCE_COMPLETE',stage='shutdown',elapsed_s=round(time.monotonic()-started,3))
    except BaseException as error:
        journal(status='FAILED',error=repr(error),traceback=traceback.format_exc(),elapsed_s=round(time.monotonic()-started,3))
        raise
    finally:
        STOP.set();stop_servers(servers);monitor_done.set()
        if monitor:monitor.join(timeout=10)
        write(ROOT/'logs'/f'stage5_guided_v2_gpu_memory_attempt{attempt}.json',memory)
        if JOB.get('status')=='INFERENCE_COMPLETE':journal(status='COMPLETE',stage='finished',elapsed_s=round(time.monotonic()-started,3),gpu_memory=memory)
        write(ROOT/'logs'/f'stage5_guided_v2_job_attempt{attempt}.json',JOB)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--phase',default='all',choices=['all','official_main','official_guided','reasoning_main','reasoning_guided'])
    main(parser.parse_args())
