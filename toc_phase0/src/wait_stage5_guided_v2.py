"""One blocking waiter; progress and process checks remain inside this shell job."""
import json
import os
import time
from stage5_common import ROOT,read

while True:
    path=ROOT/'logs/stage5_guided_v2_job.json'
    if path.exists():
        state=read(path)
        print(json.dumps({k:state.get(k) for k in ('updated_at','status','stage','template','condition','decoding','committed','expected','eta_minutes','server_ready','error')},ensure_ascii=False),flush=True)
        if state['status'] in ('COMPLETE','FAILED'):raise SystemExit(0 if state['status']=='COMPLETE' else 1)
        try:os.kill(state['controller_pid'],0)
        except ProcessLookupError:raise RuntimeError('Controller exited without completion journal')
    else:print('Waiting for controller initialization',flush=True)
    time.sleep(30)
