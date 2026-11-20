#!/usr/bin/env python3
"""Read-only check of archived MOT-QA source inventory under legacy path mappings."""
from pathlib import Path
from collections import Counter
import hashlib
import json

ROOT = Path('/data3/liuyeqiang/TOC_Bench_recovery_20261120')
project = ROOT/'motqa_nas_archive/home/user/motqa_pilot'
sequences = json.loads((project/'results/sequences.json').read_text())
issues = []
checked_gt = 0
sampled = set()
samples = []
for seq in sequences:
    if not seq.get('has_public_gt_file'):
        continue
    gt = Path(seq['gt_path'])
    if not gt.is_file() or gt.stat().st_size != seq['gt_bytes']:
        issues.append(dict(dataset=seq['dataset'], sequence=seq['sequence'], kind='gt_missing_or_size_mismatch', path=str(gt)))
    else:
        checked_gt += 1
    # Check all pre-inventoried source-frame paths and sizes, without copying frames.
    for sample in seq.get('sample_images', []):
        frame = Path(sample['path'])
        if not frame.is_file() or frame.stat().st_size != sample['bytes']:
            issues.append(dict(dataset=seq['dataset'], sequence=seq['sequence'], kind='source_frame_missing_or_size_mismatch', path=str(frame)))
        elif seq['dataset'] not in sampled:
            actual = hashlib.sha256(frame.read_bytes()).hexdigest()
            if actual != sample['sha256']:
                issues.append(dict(dataset=seq['dataset'], kind='sample_frame_hash_mismatch', path=str(frame)))
            samples.append(dict(dataset=seq['dataset'], path=str(frame), sha256=actual))
            sampled.add(seq['dataset'])
report = dict(status='VERIFIED' if not issues else 'INCOMPLETE_NAS_SOURCE_DATA',
              inventory_sequence_rows=len(sequences), checked_gt_files=checked_gt,
              gt_sequence_rows_by_dataset=dict(Counter(s['dataset'] for s in sequences if s.get('has_public_gt_file'))),
              image_sha256_samples=samples, all_source_frames_rehashed=False, issues=issues)
(ROOT/'motqa_raw_dataset_check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in {'issues','image_sha256_samples'}}))
print('Issues:',len(issues))
for issue in issues[:10]:print(issue)
