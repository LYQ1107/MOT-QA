"""One blocking waiter for a durable development/final tracking job."""
import argparse
import json
import os
import sys
import time
from run_stage3_masa import ROOT


def main(mode):
    path=ROOT/f'logs/improvement_{mode}_job.json';last_print=0
    while True:
        if path.exists():
            data=json.loads(path.read_text())
            if data['status'] in ('COMPLETE','FAILED'):
                print(json.dumps({k:v for k,v in data.items() if k not in ('records','workers')},ensure_ascii=False,indent=2),flush=True)
                return data['exit_code']
            if time.monotonic()-last_print>=30:
                print('WAIT_PROGRESS '+json.dumps({k:data[k] for k in ('mode','status','completed_units','expected_units','completed_frames')},ensure_ascii=False),flush=True)
                last_print=time.monotonic()
            try:os.kill(data['pid'],0)
            except ProcessLookupError:
                print('FAILED: tracking controller disappeared before completion; saved outputs remain intact',flush=True)
                return 1
        time.sleep(2)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['dev','final'],required=True)
    sys.exit(main(parser.parse_args().mode))
