"""Development memo ablation or fresh frozen-v1 tracking in isolated output paths."""
import argparse
import concurrent.futures as cf
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import threading
import time

from run_stage3_masa import ROOT, cuda_uuid, now, pick_devices, reset_video_text_cache, resample, terminate_owned, write_json


def output_path(mode, memory, video_id):
    directory=ROOT/'tracks'/('development/memo'+str(memory) if mode=='dev' else 'v1')/'raw'
    return directory/(video_id+'.json')


def worker(args):
    device=json.loads(args.device_json)
    assert cuda_uuid().lower()==device['uuid'].lower()
    sys.path.insert(0,str(ROOT/'upstream/masa'))
    import cv2
    import numpy as np
    import torch
    import masa
    from masa.apis import build_test_pipeline, inference_masa, init_masa
    from mmengine.config import Config
    cv2.setNumThreads(1)
    random.seed(42);np.random.seed(42);torch.manual_seed(42)
    assert torch.cuda.device_count()==1
    tasks=json.loads(Path(args.tasks).read_text())
    memories=[int(v) for v in args.memories.split(',')]
    cfg=Config.fromfile(ROOT/'upstream/masa/configs/masa-gdino/masa_gdino_swinb_inference.py')
    cfg.model.detector.language_model.name=str(ROOT/'models/MASA/bert-base-uncased')
    cfg.model.tracker.fps=5
    cfg.model.tracker.memo_tracklet_frames=memories[0]
    cfg.dump(ROOT/f'logs/improvement_{args.mode}_config_worker{args.slot}_attempt{args.attempt}.py')
    model=init_masa(cfg,str(ROOT/'models/MASA/gdino_masa.pth'),device='cuda:0')
    pipeline=build_test_pipeline(model.cfg,with_text=True)
    records=[]
    print('PROGRESS '+json.dumps(dict(kind='loaded',slot=args.slot,videos=len(tasks),memories=memories,device=device)),flush=True)
    for task in tasks:
        video_id,queries=task['video_id'],task['queries']
        video,n,width,height,resample_s=resample(video_id)
        for memory in memories:
            target=output_path(args.mode,memory,video_id)
            if target.exists():
                previous=json.loads(target.read_text())
                assert previous['complete'] and previous['queries']==queries and previous['memo_tracklet_frames']==memory
                assert previous.get('frozen_config_sha256')==args.frozen_sha and previous['frame_count']==n
                print('PROGRESS '+json.dumps(dict(kind='complete',video_id=video_id,memory=memory,frames=n,reused=True,slot=args.slot)),flush=True)
                continue
            model.cfg.model.tracker.memo_tracklet_frames=memory
            model.tracker.memo_tracklet_frames=memory
            model.tracker.reset()
            reset_video_text_cache(model)
            torch.manual_seed(42)
            torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats()
            cap=cv2.VideoCapture(str(video));frames=[];started=time.time()
            for i in range(n):
                ok,frame=cap.read();assert ok,(video_id,i,n)
                result=inference_masa(model,frame,frame_id=i,video_len=n,test_pipeline=pipeline,
                                      text_prompt=' . '.join(queries),custom_entities=True,fp16=True,
                                      detector_type='mmdet',show_fps=False)
                pred=result[0].pred_track_instances
                boxes=pred.bboxes.float().cpu().tolist();scores=pred.scores.float().cpu().tolist()
                labels=pred.labels.cpu().tolist();ids=pred.instances_id.cpu().tolist()
                instances=[]
                for box,score,label,tid in zip(boxes,scores,labels,ids):
                    assert 0<=label<len(queries) and tid>=0
                    instances.append(dict(track_id=int(tid),query_index=int(label),box_xyxy=box,confidence=float(score)))
                frames.append(dict(frame_id=i,timestamp_seconds=i/5,instances=instances))
                if (i+1)%100==0:
                    print('PROGRESS '+json.dumps(dict(kind='frame',video_id=video_id,memory=memory,frame=i+1,frames=n,slot=args.slot)),flush=True)
            cap.release();torch.cuda.synchronize()
            record=dict(complete=True,video_id=video_id,queries=queries,text_prompt=' . '.join(queries),
                        source_video=str(ROOT/'data/toc_bench/videos'/(video_id+'.mp4')),tracking_video=str(video),
                        fps=5,frame_count=n,width=width,height=height,video_length_seconds=n/5,
                        fp16=True,seed=42,unified=True,custom_entities=True,sam_mask=False,sam2_or_sam3_used=False,
                        demo_postprocessing=False,native_scores_preserved=True,text_cache_reset_per_video=True,
                        memo_tracklet_frames=memory,tracker_parameters=dict(model.cfg.model.tracker),
                        frozen_config_sha256=args.frozen_sha,study_mode=args.mode,inference_s=time.time()-started,
                        resample_s=resample_s,physical_gpu=device,completed_at=now(),
                        peak_gpu_allocated_bytes=torch.cuda.max_memory_allocated(),
                        peak_gpu_reserved_bytes=torch.cuda.max_memory_reserved(),frames=frames)
            write_json(target,record)
            summary={k:record[k] for k in ('video_id','memo_tracklet_frames','frame_count','inference_s','peak_gpu_allocated_bytes','peak_gpu_reserved_bytes')}
            records.append(summary)
            print('PROGRESS '+json.dumps(dict(kind='complete',video_id=video_id,memory=memory,frames=n,slot=args.slot,**{'inference_s':record['inference_s']})),flush=True)
    write_json(Path(args.summary),dict(status='COMPLETE',slot=args.slot,device=device,records=records,completed_at=now()))


def main(args):
    started=time.time();split_path=ROOT/'results/dev_test_split_locked.json'
    lock=json.loads((ROOT/'logs/dev_test_split_lock.json').read_text())
    assert hashlib.sha256(split_path.read_bytes()).hexdigest()==lock['sha256']
    split=json.loads(split_path.read_text())
    tasks=json.loads((ROOT/'results/stage3_tracking_tasks.json').read_text())
    frozen_sha=None
    if args.mode=='dev':
        tasks=[t for t in tasks if t['video_id'] in set(split['dev_video_ids'])]
        memories=[25,50]
        assert len(tasks)==138
    else:
        frozen_path=ROOT/'results/frozen_config_v1.json'
        frozen=json.loads(frozen_path.read_text())
        frozen_sha=hashlib.sha256(frozen_path.read_bytes()).hexdigest()
        freeze_lock=json.loads((ROOT/'logs/frozen_config_v1_lock.json').read_text())
        assert frozen_path.stat().st_mode&0o222==0 and freeze_lock['sha256']==frozen_sha
        memories=[frozen['tracking']['memo_tracklet_frames']]
        assert len(tasks)==689
    attempt=len(list((ROOT/'logs').glob(f'stage3_improvement_{args.mode}_allocation_attempt*.json')))+1
    devices=pick_devices('improvement_'+args.mode,attempt)
    sizes={r['video_id']:r['frame_count'] for r in json.loads((ROOT/'results/stage3_resampling_receipt.json').read_text())['rows']}
    historical=json.loads((ROOT/'results/stage3_full_receipt.json').read_text())
    rate=historical['frames']/historical['summed_video_inference_s']*.8
    rate_source='accepted full run, with 20 percent throughput margin'
    observed_device_rates={}
    if args.mode=='final':
        development=json.loads((ROOT/'logs/improvement_dev_job.json').read_text())
        assert development['status']=='COMPLETE'
        measured=[r for r in development['records'] if r['memo_tracklet_frames']==memories[0]]
        if not measured:
            # Memo10 has no new GPU ablation; longer-memory timings provide
            # the current shared-device planning sample without new inference.
            measured=development['records']
        if measured:
            measured_rate=sum(r['frame_count'] for r in measured)/sum(r['inference_s'] for r in measured)*.8
            rate=min(rate,measured_rate)
            rate_source='accepted full and available development shared-device throughput, with 20 percent margin; matched devices use their own measured rates'
            for uid in {r['physical_gpu']['uuid'] for r in measured}:
                rows=[r for r in measured if r['physical_gpu']['uuid']==uid]
                observed_device_rates[uid]=sum(r['frame_count'] for r in rows)/sum(r['inference_s'] for r in rows)*.8
    shard_rates=[observed_device_rates.get(d['uuid'],rate) for d in devices]
    shards=[[] for _ in devices];loads=[0.0 for _ in devices]
    for task in sorted(tasks,key=lambda t:(-sizes[t['video_id']],t['video_id'])):
        pending=sum(not output_path(args.mode,m,task['video_id']).exists() for m in memories)
        work=pending*sizes[task['video_id']]
        slot=min(range(len(devices)),key=lambda j:loads[j]+work/shard_rates[j])
        shards[slot].append(task);loads[slot]+=work/shard_rates[slot]
    assert max(loads)<=6*3600,f'Projected longest tracking shard {max(loads)/3600:.2f}h exceeds user six-hour step limit'
    journal_path=ROOT/f'logs/improvement_{args.mode}_job.json'
    journal=dict(status='RUNNING',mode=args.mode,pid=os.getpid(),started_at=now(),attempt=attempt,
                 selected_devices=devices,memories=memories,videos=len(tasks),expected_units=len(tasks)*len(memories),
                 completed_units=0,completed_frames=0,projected_shard_s=loads,split_sha256=lock['sha256'],
                 frozen_config_sha256=frozen_sha,process_ids=[],vllm_run=False,
                 planning_frames_per_second=rate,planning_rate_source=rate_source,
                 planning_per_device_frames_per_second=shard_rates,
                 planning_observed_uuid_rates=observed_device_rates)
    write_json(journal_path,journal)
    print('PROJECTED '+json.dumps(dict(mode=args.mode,hours=max(loads)/3600,units=journal['expected_units'])),flush=True)
    process_list=[];stream_threads=[];guard=threading.Lock();stop=threading.Event();memory_rows=[]
    def monitor():
        with (ROOT/f'logs/improvement_{args.mode}_gpu_memory_attempt{attempt}.csv').open('w') as stream:
            stream.write('elapsed_s,index,shared_card_MiB,owned_process_MiB\n')
            while not stop.is_set():
                cards=subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid,memory.used','--format=csv,noheader,nounits'],text=True)
                apps=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_gpu_memory','--format=csv,noheader,nounits'],text=True)
                owned={p.pid for p in process_list};usage={}
                for line in apps.splitlines():
                    uid,pid,memory=[v.strip() for v in line.split(',')]
                    if int(pid) in owned:usage[uid]=usage.get(uid,0)+int(memory)
                for line in cards.splitlines():
                    idx,uid,memory=[v.strip() for v in line.split(',')]
                    if int(idx) in {d['physical_index'] for d in devices}:
                        row=[round(time.time()-started,2),int(idx),int(memory),usage.get(uid,0)]
                        memory_rows.append(row);stream.write(','.join(map(str,row))+'\n');stream.flush()
                stop.wait(5)
    monitor_thread=threading.Thread(target=monitor,daemon=True);monitor_thread.start()
    try:
        for slot,(device,shard) in enumerate(zip(devices,shards)):
            task_path=ROOT/f'logs/improvement_{args.mode}_tasks{slot}_attempt{attempt}.json';write_json(task_path,shard)
            summary=ROOT/f'logs/improvement_{args.mode}_worker{slot}_attempt{attempt}.json'
            env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(device['physical_index']),CUDA_DEVICE_ORDER='PCI_BUS_ID',
                     MASA_SKIP_NLTK_DOWNLOAD='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
                     OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',TOKENIZERS_PARALLELISM='false')
            for key in ('http_proxy','https_proxy','HTTP_PROXY','HTTPS_PROXY','all_proxy','ALL_PROXY'):env.pop(key,None)
            command=[str(ROOT/'env_masa/bin/python'),'-u',str(Path(__file__).resolve()),'--worker','--mode',args.mode,
                     '--slot',str(slot),'--attempt',str(attempt),'--tasks',str(task_path),'--summary',str(summary),
                     '--device-json',json.dumps(device),'--memories',','.join(map(str,memories))]
            if frozen_sha:command+=['--frozen-sha',frozen_sha]
            process=subprocess.Popen(command,cwd=ROOT/'upstream/masa',env=env,stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT,text=True,bufsize=1,start_new_session=True)
            process_list.append(process)
            def stream_output(proc,path,worker_slot):
                with path.open('w') as log:
                    for line in proc.stdout:
                        log.write(line);log.flush()
                        if line.startswith('PROGRESS '):
                            payload=json.loads(line[len('PROGRESS '):])
                            with guard:
                                journal.setdefault('workers',{})[str(worker_slot)]=payload
                                if payload['kind']=='complete':
                                    journal['completed_units']+=1;journal['completed_frames']+=payload['frames']
                                journal['updated_at']=now();write_json(journal_path,journal)
                            print(line.rstrip(),flush=True)
                        elif line.startswith(('Traceback','ERROR')):print(line.rstrip(),flush=True)
            thread=threading.Thread(target=stream_output,args=(process,ROOT/f'logs/improvement_{args.mode}_worker{slot}_attempt{attempt}.log',slot),daemon=True)
            thread.start();stream_threads.append(thread)
        journal['process_ids']=[p.pid for p in process_list]
        with cf.ThreadPoolExecutor(max_workers=len(process_list)) as executor:
            for future in cf.as_completed([executor.submit(p.wait) for p in process_list]):
                code=future.result()
                if code!=0:
                    terminate_owned(process_list)
                    raise RuntimeError(f'MASA worker exited {code}; inspect improvement_{args.mode} worker logs')
        for thread in stream_threads:thread.join()
        summaries=[]
        for task in tasks:
            for memory in memories:
                raw=json.loads(output_path(args.mode,memory,task['video_id']).read_text())
                assert raw['complete'] and raw['frame_count']==sizes[task['video_id']] and raw['queries']==task['queries']
                assert raw['memo_tracklet_frames']==memory and raw.get('frozen_config_sha256')==frozen_sha
                summaries.append({k:raw[k] for k in ('video_id','memo_tracklet_frames','frame_count','inference_s','peak_gpu_allocated_bytes','peak_gpu_reserved_bytes','physical_gpu')})
        journal.update(status='COMPLETE',finished_at=now(),elapsed_s=time.time()-started,exit_code=0,
                       records=summaries,owned_process_peak_MiB=max((r[3] for r in memory_rows),default=0),
                       shared_card_peak_MiB=max((r[2] for r in memory_rows),default=0))
        write_json(journal_path,journal)
        print('COMPLETE '+json.dumps({k:v for k,v in journal.items() if k not in ('records','workers')}),flush=True)
    except BaseException as error:
        journal.update(status='FAILED',failed_at=now(),elapsed_s=time.time()-started,error=repr(error),exit_code=1)
        write_json(journal_path,journal)
        raise
    finally:
        terminate_owned(process_list);stop.set();monitor_thread.join(timeout=10)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['dev','final'],required=True)
    parser.add_argument('--worker',action='store_true');parser.add_argument('--slot',type=int)
    parser.add_argument('--attempt',type=int);parser.add_argument('--tasks');parser.add_argument('--summary')
    parser.add_argument('--device-json');parser.add_argument('--memories');parser.add_argument('--frozen-sha')
    args=parser.parse_args()
    if args.worker:
        worker(args)
    else:
        try:
            main(args)
        except BaseException as error:
            # Allocation/projected-duration failures occur before the launcher
            # creates RUNNING. Make those visible to the single blocking waiter.
            path=ROOT/f'logs/improvement_{args.mode}_job.json'
            previous=json.loads(path.read_text()) if path.exists() else {}
            if previous.get('status')!='FAILED' or previous.get('pid')!=os.getpid():
                record=previous if previous.get('pid')==os.getpid() else dict(mode=args.mode,pid=os.getpid(),completed_units=0)
                record.update(status='FAILED',failed_at=now(),error=repr(error),exit_code=1)
                write_json(path,record)
            raise
