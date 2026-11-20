"""The single blocking shell waiter for a Stage4 controller attempt."""
import json
import os
import time
from stage4_common import ROOT, read

while True:
    path=ROOT/'logs/stage4_job.json'
    if path.exists():
        state=read(path)
        print(json.dumps({k:state.get(k) for k in ('updated_at','status','stage','condition','decoding','committed','expected','eta_minutes','server_ready','error')},ensure_ascii=False),flush=True)
        if state['status'] in ('COMPLETE','FAILED'):
            raise SystemExit(0 if state['status']=='COMPLETE' else 1)
        try:
            os.kill(state['controller_pid'],0)
        except ProcessLookupError:
            raise RuntimeError('Stage4 controller exited without a completion journal')
    else:
        print('Waiting for controller initialization',flush=True)
    time.sleep(30)
