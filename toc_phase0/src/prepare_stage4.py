"""CPU-only preparation, then immutable hypotheses/D/prompt lock before inference."""
from collections import Counter, defaultdict
from copy import deepcopy
import json
from pathlib import Path
import random

from stage4_common import (ROOT, CONDITIONS, TRACKER_PREFACE, PLACEHOLDER, now, read,
    rows, write, write_rows, immutable, sha, digest, verify_prior, sampling, prompt, get_max_tokens)
from improvement_facts import serialize_compressed
from track_facts import visible_segments
from stage4_scores import route, development_count_confusion


def shuffled_intervals(document, rng):
    """Permute visible-span and empty-gap time tiles, retaining within-span observations.

    A single full-duration visible tile and empty tracks cannot be permuted;
    record these unchanged controls rather than inventing detections.
    """
    result = deepcopy(document)
    records = []
    for track in result['tracks']:
        original = deepcopy(track['observations'])
        segments = visible_segments(original)
        tiles, cursor = [], 0
        for segment in segments:
            first, last = segment[0]['frame_id'], segment[-1]['frame_id']
            if first > cursor:
                tiles.append(dict(start=cursor, length=first - cursor, points=[]))
            tiles.append(dict(start=first, length=last - first + 1, points=segment))
            cursor = last + 1
        if cursor < document['frame_count']:
            tiles.append(dict(start=cursor, length=document['frame_count'] - cursor, points=[]))
        order = list(range(len(tiles)))
        rng.shuffle(order)
        if len(order) > 1 and order == list(range(len(order))):
            order = order[1:] + order[:1]
        points, cursor = [], 0
        for tile_index in order:
            tile = tiles[tile_index]
            for point in tile['points']:
                point['frame_id'] = cursor + point['frame_id'] - tile['start']
                point['timestamp_seconds'] = point['frame_id'] / document['fps']
                points.append(point)
            cursor += tile['length']
        assert cursor == document['frame_count']
        points.sort(key=lambda p: p['frame_id'])
        assert len(points) == len(original)
        track['observations'] = points
        records.append(dict(track_id=track['track_id'], tile_order=order,
                            tiles=[dict(start=t['start'], length=t['length'], visible=bool(t['points'])) for t in tiles],
                            observation_timestamps_changed=[p['frame_id'] for p in original] != [p['frame_id'] for p in points]))
    return result, records


def main():
    frozen, frozen_sha = verify_prior()
    assert not (ROOT / 'logs/stage4_preinference_lock.json').exists(), 'Preparation already locked'
    prediction_root = ROOT / 'results/stage4/predictions'
    assert not prediction_root.exists() or not list(prediction_root.rglob('*.json')), 'Stage4 predictions already exist'
    visible = sorted(rows(ROOT / 'results/stage3_visible_inputs.jsonl'), key=lambda q: q['qa_id'])
    queries = {r['qa_id']: r['queries'] for r in read(ROOT / 'results/stage3_extracted_queries.json')}
    index = sorted(read(ROOT / 'results/v1_track_index.json'), key=lambda r: (r['video_id'], r['query']))
    lookup = {(r['video_id'], r['query']): r for r in index}
    pool = defaultdict(list)
    for row in index:
        assert row['frozen_config_sha256'] == frozen_sha
        pool[row['query']].append(row)
    # Deterministic assignment depends only on video, phrase, frozen tracks and seed.
    rng = random.Random(42)
    d_texts, assignments = {}, []
    d_files = []
    for pair_index, row in enumerate(index):
        key = (row['video_id'], row['query'])
        donors = [r for r in pool[row['query']] if r['video_id'] != row['video_id']]
        record = dict(video_id=row['video_id'], query=row['query'], source_text_sha256=sha(row['text_path']))
        if donors:
            donor = rng.choice(donors)
            text = Path(donor['text_path']).read_text()
            record.update(method='different_video_same_exact_phrase', donor_video_id=donor['video_id'],
                          donor_text_path=donor['text_path'], donor_text_sha256=sha(donor['text_path']))
        else:
            transformed, mapping = shuffled_intervals(read(row['json_path']), rng)
            text = serialize_compressed(transformed)
            record.update(method='within_video_visible_and_gap_tile_permutation', donor_video_id=None,
                          per_track_permutation=mapping, modified_tracks=sum(r['observation_timestamps_changed'] for r in mapping))
        record['text_changed_from_B'] = text != Path(row['text_path']).read_text()
        path = ROOT / 'results/stage4/d_evidence' / f'pair_{pair_index:04d}.txt'
        assert not path.exists()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        path.chmod(0o444)
        record.update(text_path=str(path), text_sha256=sha(path))
        d_files.append(dict(path=str(path), sha256=sha(path)))
        d_texts[key] = text
        assignments.append(record)
    assignment_value = dict(created_at=now(), seed=42, answers_or_metadata_read=False,
        sampling_unit='one assignment per unique (video, exact extracted phrase), reused across all its questions and guided decoding',
        donor_pool='all 689 frozen videos, any split, exact phrase match, excluding same video; no labels used',
        fallback='For each track, partition the complete video timeline into visible spans and empty gaps, randomly permute tiles (rotate one tile if identity permutation), and reserialize with frozen v1 serializer. Within-span observations, confidences and boxes are preserved. Empty or indivisible timelines may remain unchanged and are reported.',
        frozen_config_sha256=frozen_sha, method_counts=dict(Counter(r['method'] for r in assignments)),
        unchanged_pair_count=sum(not r['text_changed_from_B'] for r in assignments), assignments=assignments)
    artifacts = [immutable(ROOT / 'results/stage4_D_assignments_locked.json', assignment_value)]
    hypotheses = dict(created_at=now(), seed=42, inference_started=False,
        frozen_config_sha256=frozen_sha, split_sha256=frozen['split_sha256'],
        trackable_subset_sha256=frozen['preregistration_sha256'],
        primary_scope='test trackable subset (251 questions; main four dimensions 231; secondary ReID 20)',
        alpha=0.05, tests=dict(
            mcnemar='Exact two-sided conditional binomial test of discordant paired correctness; discordant count zero gives p=1. No continuity correction.',
            bootstrap='Paired question-level percentile 95% CI for accuracy(other)-accuracy(reference), 1000 resamples, numpy default_rng(42), sorted qa_id within each fixed subset. Question, not video, is the requested resampling unit.',
            comparisons='A vs B, A vs C, A vs D: primary test trackable aggregate and each dimension; also main-four aggregate. H4 also B vs frozen rule; H5 uses guided predictions and one-sided exact binomial vs 0.25.',
            multiplicity='Report unadjusted exact p values; additionally Holm-adjust the three aggregate A/B,C,D p values. Hypotheses are individually assessed at alpha .05; no claim of familywise significance for all per-dimension exploratory comparisons.',
            positive_effect='Positive accuracy difference, exact two-sided paired p<.05 and paired bootstrap lower bound>0.',
            null_caution='Failure to reject is not proof of equivalence or non-superiority; report uncertainty explicitly.'),
        hypotheses=[
            dict(id='H1', scope='test trackable reappear_or_disappear (101)', statement='B significantly exceeds A.',
                 criterion='positive_effect criterion on B-A; strict official decoding'),
            dict(id='H2', scope='test trackable aggregate (251)', statement='C and A show no clear difference, addressing mention-of-tracker effects.',
                 criterion='p>=.05 and CI includes 0 is compatible with H2 but is not equivalence proof; p<.05 contradicts H2; otherwise inconclusive.'),
            dict(id='H3', scope='test trackable aggregate (251)', statement='D does not exceed A, addressing trajectory-format placebo.',
                 criterion='Upper CI<=0 supports non-superiority; positive_effect contradicts H3; otherwise inconclusive (no inference from nonsignificance).'),
            dict(id='H4', scope='test trackable cross_object_order (30)', statement='B exceeds both A and the frozen rule.',
                 criterion='positive_effect for both B-A and B-rule; conjunctive assessment.'),
            dict(id='H5', scope='test trackable event_count (81), guided-choice decoding',
                 statement='B exceeds A and random 25%; strict-only improvement is not evidence.',
                 criterion='positive_effect on guided B-A, plus guided B accuracy>25% with one-sided exact binomial p<.05 and bootstrap accuracy lower bound>25%.')],
        secondary_scopes='All 602 test questions; full 749 and full trackable 324 supplemental, development contributed to tuning.',
        numerical_choices=['2','3','4','5 or more'], numerical_main='Unconstrained official strict accuracy, plus exact stripped raw legality; constrained runs remain diagnostic.',
        evidence_examples='Per dimension, first five sorted test qa_id in each direction B-correct/A-wrong and B-wrong/A-correct; if fewer, include all available and state shortage. Include whole B track text and both raw model outputs; full-set additional cases separately if needed.',
        supplemental_template='Do not run until main results have been completed and reported.')
    artifacts.append(immutable(ROOT / 'results/stage4_hypotheses_preregistered.json', hypotheses))
    for row in artifacts:
        Path(row['path'] + '.sha256').write_text(row['sha256'] + '  ' + Path(row['path']).name + '\n')
        Path(row['path'] + '.sha256').chmod(0o444)

    # Historical route and development-only diagnostic are completed before inference.
    routing = route(ROOT / 'results/stage2_predictions.jsonl', 'stage2')
    confusion = development_count_confusion()
    from transformers import AutoProcessor
    import numpy as np
    processor = AutoProcessor.from_pretrained(ROOT / 'models/Qwen2.5-VL-7B-Instruct', local_files_only=True)
    prior_lengths = {r['qa_id']: r for r in read(ROOT / 'results/v1_input_lengths.json')['rows']}
    prompt_rows = {condition: [] for condition in CONDITIONS}
    lengths, images = [], {}
    for item in visible:
        video = item['video_id']
        directory, sample = sampling(video)
        if video not in images:
            images[video] = dict(video_id=video, sampling_sha256=sha(directory / 'sampling.json'),
                files=[dict(path=str(directory / name), sha256=sha(directory / name)) for name in sample['jpeg_files']])
        true_tracks = '\n'.join(Path(lookup[(video, q)]['text_path']).read_text() for q in queries[item['qa_id']])
        shuffled_tracks = '\n'.join(d_texts[(video, q)] for q in queries[item['qa_id']])
        evidence = dict(A='', B=TRACKER_PREFACE + true_tracks, C=PLACEHOLDER, D=TRACKER_PREFACE + shuffled_tracks)
        counts = {}
        for condition in CONDITIONS:
            system, user = prompt(item, sample, evidence[condition])
            record = dict(qa_id=item['qa_id'], video_id=video, format=item['format'], condition=condition,
                system=system, user=user, evidence=evidence[condition],
                track_text=true_tracks if condition=='B' else shuffled_tracks if condition=='D' else '',
                max_tokens=get_max_tokens(item['format']), sampled_frames=sample['sampled_count'])
            record['prompt_sha256'] = digest(dict(system=system,user=user))
            placeholder_messages = [dict(role='system',content=system), dict(role='user',content=
                [dict(type='image') for _ in range(sample['sampled_count'])] + [dict(type='text',text=user)])]
            rendered = processor.apply_chat_template(placeholder_messages, tokenize=False, add_generation_prompt=True)
            counts[condition] = len(processor.tokenizer.encode(rendered, add_special_tokens=False)) + prior_lengths[item['qa_id']]['image_tokens'] - sample['sampled_count']
            record['expected_prompt_tokens'] = counts[condition]
            assert counts[condition] + record['max_tokens'] <= 65536
            if condition in ('A','B','C'):
                assert counts[condition] == prior_lengths[item['qa_id']]['complete_input_tokens'][condition]
            prompt_rows[condition].append(record)
        lengths.append(dict(qa_id=item['qa_id'], complete_input_tokens=counts, generation_budget=get_max_tokens(item['format'])))
    for condition in CONDITIONS:
        path = ROOT / 'results/stage4/prompts' / f'{condition}.jsonl'
        assert not path.exists()
        write_rows(path, prompt_rows[condition])
        path.chmod(0o444)
        artifacts.append(dict(path=str(path), sha256=sha(path), locked_at=now()))
    artifacts.append(immutable(ROOT / 'results/stage4_image_manifest_locked.json', dict(created_at=now(), videos=list(images.values()))))
    distributions = {c: dict(median=float(np.percentile([r['complete_input_tokens'][c] for r in lengths],50)),
                            p95=float(np.percentile([r['complete_input_tokens'][c] for r in lengths],95)),
                            maximum=max(r['complete_input_tokens'][c] for r in lengths)) for c in CONDITIONS}
    artifacts.append(immutable(ROOT / 'results/stage4_prompt_lengths.json', dict(created_at=now(), no_inference=True,
        image_token_validation_source='v1_input_lengths.json: eight actual HF pixel-grid/token checks; identical images/processor',
        max_model_len=65536, distributions=distributions, rows=lengths)))
    protocol = dict(created_at=now(), current_user_authorization='User confirmed frozen v1 and explicitly authorized Stage4 main on 2026-11-02; historical false authorization snapshots remain unchanged.',
        project_root=str(ROOT), conditions=list(CONDITIONS), total_questions=749, numerical_questions=300,
        main_test_questions=602, main_test_trackable_questions=251,
        checkpoint=str(ROOT / 'models/Qwen2.5-VL-7B-Instruct'), official_code_commit='e4a10bc1fd31ec1af9482bcfc827e41f2fac769a',
        format='Official build_prompt unchanged; same index/fps timestamps after images; evidence immediately before Question:. A empty, B v1, C omitted, D locked wrong timelines.',
        temperature=0, seed=42, normal_max_tokens=64, ordering_max_tokens=256,
        parser='Official answer_extractor.extract, no fallback', scorer='Official compute_metrics.is_correct; every expected QA required; invalid parses wrong',
        max_model_len=65536, dtype='bfloat16', tensor_parallel_size=1, gpu_memory_utilization=0.65,
        max_num_seqs=8, max_num_batched_tokens=32768, enforce_eager=True, generation_config='auto (original checkpoint default repetition_penalty 1.05)',
        multimodal_limits=dict(image=dict(count=32,width=720,height=720),video=0), mm_processor_overrides=None,
        image_caching='Reuse official original JPEG bytes, no resize or reencoding; verify image manifest before inference.',
        gpu_policy='Two A800 instances; may share when memory fits, prefer fewer foreign processes. Numeric CUDA_VISIBLE_DEVICES and PCI_BUS_ID with UUID check. Never stop foreign jobs.',
        endpoint_shards='Sorted all 749 qa_id alternating slots; same slot for that QA in every condition and decoding run.',
        request_concurrency_per_endpoint=4,
        guided_choice_adapter='vLLM0.16 structured_outputs.choice = [2,3,4,5 or more] strings; identical main messages, temperature, seed, token budget; numerical-only separate predictions.',
        run_order='Main official A then B then C then D; compute routing with A immediately after A completion; all four guided numerical conditions afterward.',
        frozen_config_sha256=frozen_sha, frozen_authorization_snapshot_note='frozen_config_v1.stage_four_inference_authorized=false describes pre-approval history; file is immutable, current authorization is above.',
        supplemental_template_started=False, B2_started=False)
    artifacts.append(immutable(ROOT / 'results/stage4_protocol_locked.json', protocol))
    # Preserve hashes of every D evidence text without making the common lock huge.
    artifacts.append(immutable(ROOT / 'results/stage4_D_text_manifest_locked.json', dict(files=d_files)))
    artifacts.append(dict(path=str(ROOT / 'results/stage4/routing_stage2_metrics.json'), sha256=sha(ROOT / 'results/stage4/routing_stage2_metrics.json')))
    artifacts.append(dict(path=str(ROOT / 'results/stage4/dev_count_rule_confusion.json'), sha256=sha(ROOT / 'results/stage4/dev_count_rule_confusion.json')))
    for a in artifacts:
        Path(a['path']).chmod(0o444)
    immutable(ROOT / 'logs/stage4_preinference_lock.json', dict(locked_at=now(), no_stage4_inference_at_lock=True,
        frozen_config_sha256=frozen_sha, artifacts=artifacts, qa_count=749, image_videos=len(images)))
    with (ROOT / 'research_log.md').open('a') as log:
        log.write('\n## ' + now() + ' — 阶段四主实验启动前锁定\n\n'
            '- 用户确认冻结v1并授权阶段四主实验。先完成阶段二回退路由和开发集计数混淆矩阵；冻结规则、切分、可表达清单保持原哈希。\n'
            '- 计划：锁定H1–H5、seed42打乱分配、统一提示词/图像清单及65536上下文；两实例固定QA分片运行A/B/C/D，再单独运行四条件计数guided choice；成对McNemar与题级1000次bootstrap后汇报停止。\n'
            '- D优先同短语异视频，否则对可见区间/空缺时间块做随机置换并用原序列化器重算；无法改变的空或整段轨迹透明报告。所有分配仅依赖可见文本与冻结轨迹，不读取真值。\n'
            '- H2未检出差异不等于证明等效；H3置信区间仍允许提升时报告不确定。主报告测试集可表达251题，四主维度231题；全集含调参开发集，仅附带报告。\n')
    print(json.dumps(dict(status='READY_BEFORE_ANY_INFERENCE', hypotheses_sha256=sha(ROOT/'results/stage4_hypotheses_preregistered.json'),
        d_sha256=sha(ROOT/'results/stage4_D_assignments_locked.json'), d_methods=assignment_value['method_counts'],
        d_unchanged_pairs=assignment_value['unchanged_pair_count'], lengths=distributions,
        dev_count_directions=confusion['error_direction'], routing_predictions=len(routing)), ensure_ascii=False))


if __name__ == '__main__':
    main()
