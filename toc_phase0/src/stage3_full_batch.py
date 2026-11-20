"""Detached full-stage batch; persist exit status independently of the terminal."""
import argparse
import os
import subprocess
import sys
import time

from run_stage3_masa import ROOT,now,write_json


def main(attempt):
    receipt_path=ROOT/f'logs/stage3_full_batch_attempt{attempt}.json'
    receipt=dict(status='RUNNING',started_at=now(),pid=os.getpid(),attempt=attempt,steps=[])
    write_json(receipt_path,receipt)
    begin=time.time()
    steps=[('tracking','run_stage3_masa.py',['--phase','full']),
           ('serialization','serialize_tracks.py',[]),('rules','run_rule_baseline.py',[]),
           ('validation','validate_stage3.py',[])]
    for name,script,extra in steps:
        command=[sys.executable,'-u',str(ROOT/'src'/script),*extra]
        step=dict(name=name,started_at=now(),command=command)
        print('BATCH_STEP '+name+' START',flush=True)
        start=time.time()
        result=subprocess.run(command,cwd=ROOT)
        step.update(exit_code=result.returncode,elapsed_s=time.time()-start,finished_at=now())
        receipt['steps'].append(step)
        if result.returncode:
            receipt.update(status='FAILED',exit_code=result.returncode,finished_at=now(),elapsed_s=time.time()-begin)
            write_json(receipt_path,receipt)
            raise SystemExit(result.returncode)
        write_json(receipt_path,receipt)
        print('BATCH_STEP '+name+' COMPLETE',flush=True)
    receipt.update(status='COMPLETE',exit_code=0,finished_at=now(),elapsed_s=time.time()-begin)
    write_json(receipt_path,receipt)
    print('BATCH_COMPLETE',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',type=int,required=True)
    main(parser.parse_args().attempt)
