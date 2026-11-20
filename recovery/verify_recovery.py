#!/usr/bin/env python3
"""Verify restored artifacts and replay historical scores without model inference."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import os
import struct
import sys

BASE = Path('/data3/liuyeqiang')
ROOT = BASE / 'toc_phase0'
MOTQA = BASE / 'motqa_pilot'
OUT = BASE / 'TOC_Bench_recovery_20261120'


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def rows(path):
    with Path(path).open() as f:
        return [json.loads(line) for line in f if line.strip()]


def main():
    report = {'status': 'RUNNING', 'new_model_inference': False, 'new_training': False}
    frozen = read(ROOT / 'results/frozen_config_v1.json')
    lock = read(ROOT / 'logs/frozen_config_v1_lock.json')
    assert sha(ROOT / 'results/frozen_config_v1.json') == lock['sha256']
    assert sha(ROOT / 'results/dev_test_split_locked.json') == frozen['split_sha256']
    assert sha(ROOT / 'results/trackable_subset_preregistered.json') == frozen['preregistration_sha256']
    for name, expected in frozen['source_sha256'].items():
        assert sha(ROOT / 'src' / name) == expected, name
    report['frozen_v1'] = dict(sha256=lock['sha256'], source_files=len(frozen['source_sha256']), split_and_subset_unchanged=True)
    print('Frozen configuration and source hashes match', flush=True)

    # The original scorer is stdlib-only; use it rather than a new scoring rule.
    sys.path.insert(0, str(ROOT / 'upstream/toc_bench'))
    from compute_metrics import is_correct
    bench = read(ROOT / 'data/toc_bench/answer_final.json')
    if isinstance(bench, dict):
        bench = bench.get('data', bench.get('questions', bench.get('items')))
    assert isinstance(bench, list) and len(bench) == 2323
    by_id = {q['qa_id']: q for q in bench}
    split = read(ROOT / 'results/dev_test_split_locked.json')
    expressible = set(read(ROOT / 'results/trackable_subset_preregistered.json')['trackable_qa_ids'])
    primary = set(split['test_qa_ids']) & expressible
    assert len(primary) == 251
    conditions = {
        'stage2_all': ('results/stage2_predictions.jsonl', set(by_id), 623),
        'stage4_A': ('results/stage4/main_A_predictions.jsonl', primary, 89),
        'stage4_B': ('results/stage4/main_B_predictions.jsonl', primary, 88),
        'stage4_C': ('results/stage4/main_C_predictions.jsonl', primary, 90),
        'stage4_D': ('results/stage4/main_D_predictions.jsonl', primary, 88),
        'stage7_T_none': ('results/stage6/main_T-none_predictions.jsonl', primary, 73),
        'stage7_T1': ('results/stage7/main_T1_predictions.jsonl', primary, 98),
        'stage7_T_ph': ('results/stage7/main_T-ph_predictions.jsonl', primary, 98),
        'stage7_T_sh': ('results/stage7/main_T-sh_predictions.jsonl', primary, 94),
        'majority_blind': ('results/stage7/majority_blind_predictions.jsonl', primary, 126),
        'route_A': ('results/stage4/routing_A_predictions.jsonl', primary, 112),
    }
    score_report = {}
    for name, (relative, wanted, expected) in conditions.items():
        predictions = rows(ROOT / relative)
        counts = Counter(p['qa_id'] for p in predictions)
        assert all(v == 1 for v in counts.values()), name
        lookup = {p['qa_id']: p for p in predictions}
        assert not wanted - lookup.keys(), name
        correct = sum(is_correct(lookup[qid]['extracted_answer'], by_id[qid]) for qid in wanted)
        assert correct == expected, (name, correct, expected)
        score_report[name] = dict(correct=correct, total=len(wanted), accuracy=correct/len(wanted), unique_prediction_rows=len(predictions))
        print(f'{name}: {correct}/{len(wanted)}', flush=True)
    report['historical_scores_replayed'] = score_report

    video_manifest = read(ROOT / 'data/toc_bench/video_manifest.json')
    videos_root = ROOT / 'data/toc_bench/videos'
    actual = {e.name: e.stat().st_size for e in os.scandir(videos_root) if e.name.endswith('.mp4')}
    errors = []
    for item in video_manifest:
        name = Path(item['rfilename']).name
        if actual.get(name) != item['size']:
            errors.append(dict(name=name, expected=item['size'], actual=actual.get(name)))
    assert not errors, errors[:10]
    # One current read-back sample complements full size/count verification and old full SHA receipts.
    sample = video_manifest[0]
    assert sha(ROOT / 'data/toc_bench' / sample['rfilename']) == sample['lfs']['sha256']
    report['nas_videos'] = dict(expected=len(video_manifest), present=len(actual), bytes=sum(x['size'] for x in video_manifest), size_mismatches=errors,
                                current_sha256_samples=1, current_full_video_sha256_rerun=False,
                                original_full_verification_receipt=str(ROOT / 'results/stage2_receipt.json'))
    print(f'NAS videos: {len(video_manifest)} sizes match; one sample SHA256 matches', flush=True)

    model = ROOT / 'models/Qwen2.5-VL-7B-Instruct'
    index = read(model / 'model.safetensors.index.json')
    shards = sorted(set(index['weight_map'].values()))
    shard_report = []
    for name in shards:
        path = model / name
        with path.open('rb') as f:
            header_size = struct.unpack('<Q', f.read(8))[0]
            assert 0 < header_size < 20_000_000
            header = json.loads(f.read(header_size))
        keys = [k for k in header if k != '__metadata__']
        expected_keys = {k for k, v in index['weight_map'].items() if v == name}
        assert set(keys) == expected_keys, name
        data_size = path.stat().st_size - 8 - header_size
        assert max(header[k]['data_offsets'][1] for k in keys) == data_size, name
        shard_report.append(dict(name=name, bytes=path.stat().st_size, tensors=len(keys)))
    adapter = ROOT / 'models/stage6_lora_r8/adapter_model.safetensors'
    assert adapter.exists() and adapter.resolve().is_relative_to(BASE / 'nas')
    report['nas_models'] = dict(qwen_shards=shard_report, qwen_weight_index_and_headers_match=True,
                                full_weight_sha256_rerun=False, masa_bytes=(ROOT/'models/MASA/gdino_masa.pth').stat().st_size,
                                lora_adapter_target=str(adapter.resolve()), lora_adapter_bytes=adapter.stat().st_size,
                                qwen3_vl_32b='Not included in original MOT-QA backup; deferred by original transfer policy')
    print('NAS model shard index/headers and repaired LoRA link are valid', flush=True)

    candidates = rows(MOTQA / 'data/candidates_readability_v3.jsonl')
    assert len(candidates) == 900
    report['motqa'] = dict(candidates_v3=len(candidates), example_keys=list(candidates[0]),
                           review12_zip_exists=(MOTQA/'results/motqa_readability_v3_review12_zh.zip').is_file(),
                           human_review12_received=False, filtering_completed=False, gt_comparison_completed=False)
    manifest = read(OUT / 'restore_manifest.json')
    for item in manifest['files']:
        assert sha(item['destination']) == item['sha256'], item['destination']
    broken_links = [x for x in manifest['nas_links'] if not Path(x['path']).exists()]
    assert not broken_links, broken_links
    report['local_files'] = dict(count=manifest['local_files'], bytes=manifest['local_bytes'], all_match_restore_manifest=True,
                                 motqa_matches_original_backup_sha256=True, top_level_nas_links=len(manifest['nas_links']), broken_links=broken_links)
    report['status'] = 'VERIFIED'
    (OUT / 'verification_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print('VERIFIED: ' + str(OUT / 'verification_report.json'), flush=True)


if __name__ == '__main__':
    main()
