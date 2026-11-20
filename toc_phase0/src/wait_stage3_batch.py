"""One blocking waiter; log progress stays inside this shell command."""
import argparse
import json
import time

from run_stage3_masa import ROOT


def main(attempt):
    receipt=ROOT/f'logs/stage3_full_batch_attempt{attempt}.json'
    log=ROOT/f'logs/stage3_full_batch_attempt{attempt}.log'
    records=[json.loads(p.read_text()) for p in (ROOT/'tracks/raw').glob('*.json')]
    seen={r['video_id'] for r in records};frames=sum(r['frame_count'] for r in records)
    offset=0;partial='';last_emit=0;phase='tracking';begin=time.time()
    while True:
        if log.exists():
            with log.open() as handle:
                handle.seek(offset);chunk=handle.read();offset=handle.tell()
            lines=(partial+chunk).split('\n');partial=lines.pop()
            for line in lines:
                if line.startswith('PROGRESS '):
                    row=json.loads(line[9:])
                    if row.get('completed') and row['video_id'] not in seen:
                        seen.add(row['video_id']);frames+=row['frame_count']
                elif line.startswith('BATCH_STEP '):
                    print(line,flush=True);phase=line.split()[1]
        if time.time()-last_emit>=30:
            print('BATCH_PROGRESS '+json.dumps(dict(videos_complete=len(seen),total=689,frames_complete=frames,
                  phase=phase,wait_elapsed_s=round(time.time()-begin))),flush=True)
            last_emit=time.time()
        if receipt.exists():
            row=json.loads(receipt.read_text())
            if row['status'] in ('COMPLETE','FAILED'):
                print(json.dumps(row,indent=2),flush=True)
                raise SystemExit(row['exit_code'])
        time.sleep(2)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',type=int,required=True)
    main(parser.parse_args().attempt)
