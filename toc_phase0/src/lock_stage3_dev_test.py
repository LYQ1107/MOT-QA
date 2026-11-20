"""Lock the video-level split before the bounded development round."""
import hashlib
import json
from pathlib import Path
import random

from run_stage3_masa import ROOT, now


def main():
    target = ROOT / 'results/dev_test_split_locked.json'
    receipt = ROOT / 'logs/dev_test_split_lock.json'
    if target.exists():
        lock = json.loads(receipt.read_text())
        assert hashlib.sha256(target.read_bytes()).hexdigest() == lock['sha256']
        assert target.stat().st_mode & 0o222 == 0
        print(json.dumps(lock, ensure_ascii=False, indent=2))
        return
    tasks = json.loads((ROOT / 'results/stage3_tracking_tasks.json').read_text())
    inputs = [json.loads(line) for line in (ROOT / 'results/stage3_visible_inputs.jsonl').read_text().splitlines()]
    videos = sorted(task['video_id'] for task in tasks)
    assert len(videos) == len(set(videos)) == 689
    shuffled = list(videos)
    random.Random(42).shuffle(shuffled)
    ndev = round(0.2 * len(videos))
    dev, test = set(shuffled[:ndev]), set(shuffled[ndev:])
    rows = [dict(qa_id=item['qa_id'], video_id=item['video_id'],
                 split='dev' if item['video_id'] in dev else 'test') for item in inputs]
    assert len(rows) == len({row['qa_id'] for row in rows}) == 749
    assert {row['video_id'] for row in rows} == set(videos)
    result = dict(created_at=now(), seed=42, split_unit='video_id',
                  algorithm='random.Random(42).shuffle(sorted(video_ids)); first round(0.2*N) videos are development',
                  dataset_revision='da3065053d958c38151304e33a42e138b1899eaf',
                  answers_or_metadata_read=False, dev_video_ids=sorted(dev), test_video_ids=sorted(test),
                  dev_qa_ids=sorted(row['qa_id'] for row in rows if row['split']=='dev'),
                  test_qa_ids=sorted(row['qa_id'] for row in rows if row['split']=='test'), rows=rows,
                  policy='immutable; all questions of one video stay together; new parameter decisions use development only; test accuracy is evaluated only after frozen_config_v1 is locked',
                  prior_exposure='The accepted stage-three report and its full-corpus aggregates/visual examples existed before this split. This round forbids further test-accuracy use for tuning.')
    content = (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)+'\n').encode()
    with target.open('xb') as stream:
        stream.write(content)
    target.chmod(0o444)
    lock = dict(locked_at=now(), path=str(target), sha256=hashlib.sha256(content).hexdigest(),
                seed=42, dev_videos=len(dev), test_videos=len(test),
                dev_questions=len(result['dev_qa_ids']), test_questions=len(result['test_qa_ids']),
                video_overlap=0, read_only=True)
    with receipt.open('x') as stream:
        json.dump(lock, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    receipt.chmod(0o444)
    print(json.dumps(lock, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
