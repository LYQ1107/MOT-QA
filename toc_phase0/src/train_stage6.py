"""One-GPU LlamaFactory training API; only locked synthetic data are supplied."""
import json
import os
from pathlib import Path
import threading
import time
import traceback
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from stage4_common import read,write,sha,now


def main():
    state_path=ROOT/'logs/stage6_training_job.json'
    before=read(state_path) if state_path.exists() else {}
    state=dict(status='RUNNING',stage='initializing',controller_pid=os.getpid(),started_at=now(),
               prior_attempt=before if before.get('status')=='FAILED' else None)
    def journal(**extra):
        state.update(extra,updated_at=now());write(state_path,state)
    journal()
    start=time.monotonic();done=threading.Event();gpu_stats={}
    def monitor():
        import pynvml
        pynvml.nvmlInit();dev=pynvml.nvmlDeviceGetHandleByUUID(os.environ['STAGE6_GPU_UUID'])
        group=os.getpgid(0)
        gpu_stats.update(own_peak_MiB=0,total_peak_MiB=0,gpu_uuid=os.environ['STAGE6_GPU_UUID'])
        while not done.is_set():
            own=0
            for p in pynvml.nvmlDeviceGetComputeRunningProcesses(dev):
                try:
                    if os.getpgid(p.pid)==group:own+=p.usedGpuMemory/1024**2
                except ProcessLookupError:pass
            gpu_stats['own_peak_MiB']=max(gpu_stats['own_peak_MiB'],own)
            gpu_stats['total_peak_MiB']=max(gpu_stats['total_peak_MiB'],pynvml.nvmlDeviceGetMemoryInfo(dev).used/1024**2)
            done.wait(10)
        pynvml.nvmlShutdown()
    thread=threading.Thread(target=monitor,daemon=True);thread.start()
    try:
        manifest=read(ROOT/'results/stage6_training_data_locked.json')
        for key in ('train','dataset_info','config'):assert sha(manifest[key]['path'])==manifest[key]['sha256']
        assert sha(ROOT/'src/stage6_synthetic.py')==manifest['generation_source_sha256']
        cfg=read(manifest['config']['path'])
        from transformers import AutoTokenizer,TrainerCallback
        tokenizer=AutoTokenizer.from_pretrained(cfg['model_name_or_path'],local_files_only=True)
        data=read(manifest['train']['path']);assert len(data)==2000
        lengths=[]
        for row in data:
            messages=[dict(role='system',content=row['system']),dict(role='user',content=row['instruction']),dict(role='assistant',content=row['output'])]
            lengths.append(len(tokenizer.apply_chat_template(messages,tokenize=True)))
        assert max(lengths)<=cfg['cutoff_len'],('Synthetic truncation would violate protocol',max(lengths))
        write(ROOT/'results/stage6_training_token_lengths.json',dict(checked_at=now(),count=len(data),min=min(lengths),max=max(lengths),
              mean=sum(lengths)/len(lengths),above_cutoff=0,cutoff=cfg['cutoff_len']))
        from llamafactory.train.tuner import run_exp
        class Progress(TrainerCallback):
            def on_train_begin(self,args,state_,control,**kwargs):journal(stage='training',global_step=state_.global_step,max_steps=state_.max_steps)
            def on_log(self,args,state_,control,logs=None,**kwargs):
                journal(stage='training',global_step=state_.global_step,max_steps=state_.max_steps,epoch=state_.epoch,metrics=logs)
        checkpoints=sorted(Path(cfg['output_dir']).glob('checkpoint-*'),key=lambda p:int(p.name.split('-')[-1]))
        if checkpoints:
            cfg['resume_from_checkpoint']=str(checkpoints[-1]);journal(resuming=str(checkpoints[-1]))
        run_exp(args=cfg,callbacks=[Progress()])
        output=Path(cfg['output_dir']);trainer=read(output/'trainer_state.json')
        assert trainer['epoch']>=2.-1e-6 and (output/'adapter_model.safetensors').exists()
        receipt=dict(completed_at=now(),elapsed_s=round(time.monotonic()-start,3),epochs=trainer['epoch'],global_step=trainer['global_step'],
                     train_examples=2000,synthetic_only=True,adapter_path=str(output),adapter_sha256=sha(output/'adapter_model.safetensors'),
                     adapter_config_sha256=sha(output/'adapter_config.json'),data_manifest_sha256=sha(ROOT/'results/stage6_training_data_locked.json'),
                     hypotheses_sha256=sha(ROOT/'results/stage6_hypotheses_preregistered.json'))
        write(ROOT/'results/stage6_training_receipt.json',receipt);journal(status='COMPLETE',stage='training_complete',**receipt)
    except BaseException as error:
        journal(status='FAILED',stage='training_failed',error=repr(error),traceback=traceback.format_exc(),elapsed_s=round(time.monotonic()-start,3));raise
    finally:
        done.set();thread.join(timeout=15);write(ROOT/'logs/stage6_training_gpu_memory.json',gpu_stats)


if __name__=='__main__':main()
