"""One blocking shell waiter. All process/progress checks stay inside this command."""
import json
import os
import time
from stage6_common import ROOT,read

while True:
    p=ROOT/'logs/stage6_job.json'
    if p.exists():
        state=read(p)
        output={k:state.get(k) for k in ('updated_at','status','stage','tools_stage','tools_committed','tools_expected','tools_eta_min','lora_stage','lora_committed','lora_expected','lora_eta_min','error')}
        train=ROOT/'logs/stage6_training_job.json'
        if train.exists():
            d=read(train);output['training']={k:d.get(k) for k in ['status','stage','global_step','max_steps','epoch','error']}
        print(json.dumps(output,ensure_ascii=False),flush=True)
        if state['status'] in ['COMPLETE','FAILED']:raise SystemExit(0 if state['status']=='COMPLETE' else 1)
        try:os.kill(state['controller_pid'],0)
        except ProcessLookupError:raise RuntimeError('Controller exited without terminal journal')
    time.sleep(30)
