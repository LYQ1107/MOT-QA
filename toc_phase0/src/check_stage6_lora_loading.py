"""One managed two-GPU diagnostic; no new benchmark evaluation or training."""
import concurrent.futures as cf
import os
import subprocess
import time
from stage6_common import *
from stage6_runtime import env_for,verify_uuid,start_server,stop


def main():
    protocol_path=ROOT/'results/stage6_lora_sanity_protocol_locked.json'
    if not protocol_path.exists():
        training=read(ROOT/'data/stage6_synthetic/train.json')
        cases=[]
        for synthetic_id in ['synthetic_0000','synthetic_1400']:
            row=next(r for r in training if r['id']==synthetic_id)
            cases.append(dict(id=synthetic_id,system=row['system'],user=row['instruction'],images=[],
                              expected_final=row['output'].strip().splitlines()[-1],split='synthetic training example for loading check only'))
        qid='13a41b8c6b50';assert qid in set(read(ROOT/'results/dev_test_split_locked.json')['dev_qa_ids'])
        p=next(r for r in rows(ROOT/'results/stage5/prompts/reasoning/B-events.jsonl') if r['qa_id']==qid)
        directory,sample=sampling(p['video_id'])
        cases.append(dict(id='dev_'+qid,system=p['system'],user=p['user'],images=[str(directory/name) for name in sample['jpeg_files']],
                          split='development, no label passed to model'))
        immutable(protocol_path,dict(locked_at=now(),purpose='Verify trained adapter loading after repetition/truncation observed; no test examples and no parameter selection.',
            adapter_sha256=read(ROOT/'results/stage6_training_receipt.json')['adapter_sha256'],cases=cases,max_tokens=1024,seed=42,
            temperature=0,repetition_penalty=1.05,main_predictions_changed=False,training_repeated=False))
    protocol=read(protocol_path);devices=read(ROOT/'logs/stage6_allocation_locked.json')
    hf_device=devices['vllm'];vllm_device=devices['training_and_lora_eval']
    env=env_for(hf_device);verify_uuid(hf_device,env)
    stream=(ROOT/'logs/stage6_lora_sanity_hf.log').open('w')
    args=[str(ROOT/'env_stage6_train/bin/python'),'-u',str(ROOT/'src/stage6_lora_sanity_hf.py')]
    process=subprocess.Popen(args,env=env,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
    write(ROOT/'logs/stage6_lora_sanity_hf_runtime.json',dict(pid=process.pid,device=hf_device,args=args))
    server=None;started=time.monotonic()
    try:
        server=start_server(vllm_device,'sanity',lora=True,progress=lambda **x:print(x,flush=True))
        from openai import OpenAI,DefaultHttpxClient
        client=OpenAI(api_key='local',base_url='http://127.0.0.1:18023/v1',http_client=DefaultHttpxClient(trust_env=False,timeout=900),timeout=900,max_retries=0)
        try:
            for case in protocol['cases']:
                messages=[dict(role='system',content=case['system']),dict(role='user',content=
                    [dict(type='image_path',path=path) for path in case['images']]+[dict(type='text',text=case['user'])])]
                start=time.monotonic();response=client.chat.completions.create(model='stage6_lora',messages=materialize(messages),
                                    temperature=0.,seed=42,max_tokens=1024)
                result=dict(case=case['id'],backend='vllm0.16.0',raw_response=response.choices[0].message.content,
                            usage=response.usage.model_dump(),finish_reason=response.choices[0].finish_reason,elapsed_s=time.monotonic()-start)
                write(ROOT/'results/stage6_loading_sanity'/f'{case["id"]}.vllm.json',result)
                print(dict(case=case['id'],backend='vLLM',tokens=response.usage.completion_tokens),flush=True)
        finally:client.close();stop(server[0],server[1]);server=None
        assert process.wait()==0,'HF loading sanity failed; see logs/stage6_lora_sanity_hf.log'
        summary=[]
        for case in protocol['cases']:
            hf=read(ROOT/'results/stage6_loading_sanity'/f'{case["id"]}.hf.json');vl=read(ROOT/'results/stage6_loading_sanity'/f'{case["id"]}.vllm.json')
            fmt='numerical' if case['id']=='synthetic_1400' else 'sp'
            hanswer=final_answer(hf['raw_response'],fmt)[0];vanswer=final_answer(vl['raw_response'],fmt)[0]
            summary.append(dict(case=case['id'],hf_answer=hanswer,vllm_answer=vanswer,
                full_text_identical=hf['raw_response']==vl['raw_response'],hf_tokens=hf['generated_tokens'],vllm_tokens=vl['usage']['completion_tokens']))
        write(ROOT/'results/stage6_lora_loading_sanity.json',dict(completed_at=now(),protocol_sha256=sha(protocol_path),
              cases=summary,elapsed_s=time.monotonic()-started,main_predictions_changed=False,training_repeated=False))
        print(__import__('json').dumps(summary,ensure_ascii=False),flush=True)
    finally:
        if server:stop(server[0],server[1])
        if process.poll() is None:stop(process,stream)
        else:stream.close()


if __name__=='__main__':main()
