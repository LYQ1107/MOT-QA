"""Validate complete prediction coverage, then build the stage-two research report."""
from collections import Counter
from datetime import datetime, timezone
import csv
import json
from pathlib import Path
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'upstream/toc_bench'))
from answer_extractor import extract
from compute_metrics import compute_one_model, is_correct
from eval_runner import build_prompt

DIM_ORDER = ['event_existence', 'event_count', 'reappear_identity', 'reappear_or_disappear',
             'cross_object_order', 'event_ordering', 'temporal_location', 'duration_category',
             'conditional_state', 'relative_spatial_change']
MAIN = ['event_count', 'reappear_or_disappear', 'cross_object_order', 'event_ordering']
INPUT_FIELDS = ('qa_id', 'video_id', 'format', 'question', 'option_A', 'option_B',
                'option_C', 'option_D', 'statement_A', 'statement_B', 'events')


def dump(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


def main():
    items = json.loads((ROOT / 'data/toc_bench/answer_final.json').read_text())['items']
    predictions = [json.loads(line) for line in (ROOT / 'results/stage2_predictions.jsonl').read_text().splitlines()]
    ids = [p['qa_id'] for p in predictions]
    expected = {it['qa_id'] for it in items}
    assert len(predictions) == len(set(ids)) == len(expected) == 2323
    assert set(ids) == expected
    assert all(p['error'] is None and isinstance(p['raw_response'], str) for p in predictions)
    assert all(p['extracted_answer'] == extract(p['raw_response'], p['format']) for p in predictions)
    pred_by_id = {p['qa_id']: p for p in predictions}
    prompts = []
    for item in items:
        safe = {key: item[key] for key in INPUT_FIELDS if key in item}
        system, user = build_prompt(safe)
        assert (system, user) == build_prompt(item)
        prompts.append(dict(qa_id=item['qa_id'], system=system, user=user))
    (ROOT / 'results/stage2_prompt_texts.jsonl').write_text(''.join(json.dumps(p, ensure_ascii=False) + '\n' for p in prompts))
    result = compute_one_model(items, pred_by_id, 'qwen2.5-vl-7b')
    assert result['n_total'] == result['n_scored'] == 2323 and result['n_missing_preds'] == 0
    official = json.loads((ROOT / 'results/stage2_official_summary.json').read_text())[0]
    assert all(result[key] == value for key, value in official.items())
    dump(ROOT / 'results/stage2_metrics.json', result)
    ref = json.loads((ROOT / 'results/paper_qwen25vl7b_reference.json').read_text())
    downloads = json.loads((ROOT / 'logs/video_download_receipt.json').read_text())
    audit_document = json.loads((ROOT / 'results/video_decode_audit.json').read_text())
    audit = audit_document['summary']
    short_videos = [r for r in audit_document['videos'] if 0 < r['total_frames'] < 32]
    assert downloads['verified_count'] == 1951 and downloads['verified_bytes'] == 15235916868
    assert audit['audited_count'] == 1951
    assert all(r['sampled_count'] == min(32, r['total_frames']) > 0 for r in audit_document['videos'])
    assert audit['anomaly_count'] == len(short_videos)
    assert audit['total_sampled_frames'] == sum(min(32, r['total_frames']) for r in audit_document['videos'])
    inference_receipts = [json.loads(p.read_text()) for p in sorted((ROOT / 'logs').glob('stage2_inference_receipt_attempt*.json'))]
    failed_attempts = [json.loads(p.read_text()) for p in sorted((ROOT / 'logs').glob('stage2_failed_attempt*.json'))]
    assert inference_receipts
    inf = inference_receipts[-1]
    gpu = json.loads((ROOT / 'logs/stage2_gpu_allocation.json').read_text())
    runtime = json.loads((ROOT / f'logs/stage2_runtime_attempt{inf["attempt"]}.json').read_text())
    reid_diagnostic_path = ROOT / 'results/stage2_reid_diagnostic.json'
    reid_diagnostic = json.loads(reid_diagnostic_path.read_text()) if reid_diagnostic_path.exists() else None
    main_items = [it for it in items if it['metadata']['dim'] in MAIN]
    assert len(main_items) == 726
    main_correct = sum(is_correct(pred_by_id[it['qa_id']]['extracted_answer'], it) for it in main_items)
    passed = 24.0 <= result['overall'] * 100 <= 30.0
    errors = [it for it in items if not is_correct(pred_by_id[it['qa_id']]['extracted_answer'], it)]
    rng = random.Random(42)
    examples = []
    for dim in DIM_ORDER:
        candidates = sorted((it for it in errors if it['metadata']['dim'] == dim), key=lambda it: it['qa_id'])
        examples.extend(rng.sample(candidates, min(2, len(candidates))))
    if len(examples) < 20:
        selected = {it['qa_id'] for it in examples}
        examples.extend(rng.sample(sorted((it for it in errors if it['qa_id'] not in selected), key=lambda it: it['qa_id']), 20-len(examples)))
    assert len(examples) == 20
    error_records = []
    for it in examples:
        p = pred_by_id[it['qa_id']]
        error_records.append(dict(qa_id=it['qa_id'], video_id=it['video_id'], dimension=it['metadata']['dim'],
                                  format=it['format'], question=it['question'],
                                  options={key: it[key] for key in ('option_A', 'option_B', 'option_C', 'option_D', 'statement_A', 'statement_B', 'events') if key in it},
                                  ground_truth=it.get('correct_order', it.get('correct_answer')),
                                  raw_response=p['raw_response'], extracted_answer=p['extracted_answer'],
                                  failure_type='parse_failure' if p['extracted_answer'] is None else 'wrong_answer',
                                  hallucination=it['metadata'].get('hallucination')))
    dump(ROOT / 'results/stage2_error_examples_20.json', error_records)
    invalids = [p for p in predictions if p['extracted_answer'] is None]
    dump(ROOT / 'results/stage2_parse_failures.json', invalids)
    numeric_raw = Counter(p['raw_response'] for p in predictions if p['format'] == 'numerical')
    dump(ROOT / 'results/stage2_numerical_raw_counts.json', dict(numeric_raw.most_common()))
    table_rows = []
    for name in ['overall', *DIM_ORDER, 'hda']:
        current = result[name] if name in ('overall', 'hda') else result['per_dim'][name]
        paper = ref['table_2'][name]
        counts = result['per_dim_counts'].get(name, {})
        table_rows.append([name, counts.get('correct', sum(v['correct'] for v in result['per_dim_counts'].values())) if name == 'overall' or counts else '',
                           counts.get('total', 2323) if name == 'overall' or counts else '',
                           current * 100, paper, current * 100 - paper])
    with (ROOT / 'results/stage2_paper_comparison.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['metric', 'correct', 'total', 'reproduced_percent', 'paper_table2_percent', 'delta_pp'])
        writer.writerows(table_rows)
    lines = [
        '# 阶段二：TOC-Bench Qwen2.5-VL-7B 官方基线复现', '',
        f'总体准确率 **{result["overall"]*100:.2f}%**（{sum(v["correct"] for v in result["per_dim_counts"].values())}/2323），'
        f'论文表2为27.0%，差值 {result["overall"]*100-27.0:+.2f} 个百分点。'
        + ('落在 [24.0%, 30.0%] 验收区间，阶段二通过。' if passed else '超出 [24.0%, 30.0%] 验收区间，阶段二未通过，须先排查，不进入阶段三。'),
        '',
        '1,951 个视频全部按发布清单完成大小与 SHA256 核验；2,323 题均有唯一预测，无缺失、无重复。'
        f'官方解析失败 **{result["n_invalid_extraction"]}/2323（{result["invalid_rate"]*100:.2f}%）**，均保留原始输出并记错。',
        '', '## 数据和解码审计', '',
        f'- 数据 revision：`{downloads["dataset_revision"]}`；视频共 15,235,916,868 bytes（15.24 GB）。',
        f'- 来源：`{downloads["endpoint"]}`，全程未使用代理。逐文件来源/大小/校验在 `logs/downloads.md`，完整回执为 `logs/video_download_receipt.json`。',
        f'- 官方采样器检查 1,951/1,951 个视频，共 {audit["total_sampled_frames"]:,} 帧；实际帧数分布：`{audit["sampled_count_distribution"]}`。解码失败或非预期漏读：**0**；原视频不足32帧：**{len(short_videos)}个**。',
        '- 不足32帧的视频清单：' + '；'.join(f'`{r["video_id"]}`：原始{r["total_frames"]}帧/{r["fps"]:g}fps，采样{r["sampled_count"]}帧' for r in short_videos) + '。严格执行官方N≤32取全部帧分支，未补帧、未跳过；推理前已向用户报告。',
        f'- 原始帧数范围 {audit["total_frames_min"]}–{audit["total_frames_max"]}；采样 JPEG 缓存 {audit["cache_bytes"]/1024**3:.2f} GiB，未超过25 GiB限制。',
        '- 全量审计先汇报，再启动推理。完整逐视频 FPS/帧数/索引/时间戳/尺寸保存在 `results/video_decode_audit.json`，异常列表为 `results/video_decode_anomalies.json`。',
        '', '## 锁定的评测协议', '',
        '- 官方代码 commit：`e4a10bc1fd31ec1af9482bcfc827e41f2fac769a`，上游文件未改动。',
        '- 直接调用官方 `sample_frames_uniform`：N>32时floor(i*N/32)，N≤32时取全部帧，长边不超过720，JPEG质量85；推理复用该函数输出的相同 JPEG 字节。',
        '- 直接调用官方 `build_prompt`、`call_openai_video`、`answer_extractor.extract` 和 `compute_metrics.py`。采样帧的image_url在前（通常32个、上述两个短视频各30个）、官方问题文本在后；阶段二不增加时间戳或证据。',
        '- 温度0、种子42；普通题64 token、排序题256 token；未启用 guided choice、未使用其他模型专用的解析回退。',
        '- 只将题目、选项和事件文本传给官方请求函数；不传metadata、答案或allowed_answers。已核对全部2,323题：移除这些字段后官方提示词逐字一致。',
        '- 两个vLLM实例按排序后qa_id交替切分，每实例并发4。启动前已确认所选两张A800空闲；未运行MASA。',
        f'- 物理GPU/UUID：{json.dumps(gpu["selected"], ensure_ascii=False)}。',
        '- 运行环境：vLLM0.16.0 / torch2.9.1+CUDA12.8 / transformers4.57.6；BF16，TP=1，最大上下文32768，eager模式。未覆盖图像处理器参数；720×720仅用于启动时的模拟输入内存测量。',
        '- vLLM沿用模型原始generation_config（含repetition_penalty=1.05）；请求显式覆盖temperature=0、seed=42和token预算。完整启动参数见 `logs/stage2_runtime_attempt*.json`。',
        '', '## 与论文表2逐项比较', '',
        '[论文表2](https://arxiv.org/html/2605.09904v2#S4.T2)。差值单位为百分点，参考值按论文公布的一位小数。', '',
        '| 指标 | 正确/总数 | 本次 % | 论文 % | 差值 pp |',
        '|---|---:|---:|---:|---:|',
    ]
    for name, correct, total, current, paper, delta in table_rows:
        lines.append(f'| {name} | {correct}/{total}' if total else f'| {name} | —')
        lines[-1] += f' | {current:.2f} | {paper:.1f} | {delta:+.2f} |'
    lines += ['', f'四个重点维度共726题：{main_correct}/726，准确率 {100*main_correct/726:.2f}%。ReID全部23题照常报告，作为次要维度，不据此提出主要结论。',
              '', '## 分题型准确率', '',
              '表2未列分题型结果；这里对应[论文附录G.1表6](https://arxiv.org/html/2605.09904v2#A7.T6)。', '',
              '| 题型 | 正确/总数 | 本次 % | 论文表6 % | 差值 pp |',
              '|---|---:|---:|---:|---:|']
    for fmt, paper in ref['table_6_formats'].items():
        c = result['per_format_counts'][fmt]
        actual = result['per_format'][fmt] * 100
        lines.append(f'| {fmt} | {c["correct"]}/{c["total"]} | {actual:.2f} | {paper:.1f} | {actual-paper:+.2f} |')
    if reid_diagnostic:
        lines += ['', '## ReID差异核查', '',
                  '本次ReID为12/23（52.17%），明显低于论文95.7%；当前复现未验证“ReID基线接近满分”。总体通过既定验收标准，四个重点维度仍按用户决定保持不变；ReID差异单列，不作为主要结论依据。', '',
                  '- 23题均输出单个A/B，无解析失败；全部官方提示词与不含metadata/答案的输入构造一致，官方解析结果逐题等于原始字母。',
                  '- 对3个错误样例重新运行未修改的官方采样器，所得32张JPEG逐字节等于推理缓存；未发现这些样例的采样或缓存偏差。',
                  '- 从选项文本读取语义：模型22题选“同一物体”、1题选“不同物体”；发布标注为13题“同一”、10题“不同”。其中12/13个“同一”题答对，10个“不同”题全部答错。',
                  '- 以上说明本次输出存在明显的“同一物体”偏置；尚不能确定论文差异的来源。未改标注、解析或评分，也未使用metadata真值字段生成提示词。逐题记录和3个采样比对结果见 `results/stage2_reid_diagnostic.json`。']
    lines += ['', '## 解析失败与运行错误', '',
              f'- 解析失败：{len(invalids)}/2323。按题型：`{dict(Counter(p["format"] for p in invalids))}`。',
              f'- 数值题原始输出中，`1`有{numeric_raw.get("1",0)}题、`0`有{numeric_raw.get("0",0)}题；二者均不在官方数值答案集合内，由官方解析器返回None并记错。',
              '- 解析失败原文见 `results/stage2_parse_failures.json`；数值题完整原始输出分布见 `results/stage2_numerical_raw_counts.json`。未做选择约束或把非法数值改成合法答案。',
              f'- 最终预测HTTP/运行错误：0。已完成的推理调用回执：{len(inference_receipts)}份；所有中断错误（若有）保留于日志，不通过缺失行改变评分分母。',
              f'- 评测请求前启动失败：{len(failed_attempts)}次。首次原因为vLLM0.16不能将UUID形式的CUDA_VISIBLE_DEVICES转换为整数；改为数字掩码并核对实际CUDA UUID后继续。首次未产生预测，原日志和原因/修复回执见 `logs/stage2_failed_attempt1.json`；未修改模型或评测协议。' if failed_attempts else '- 无启动失败。',
              '', '## 20条错误样例', '',
              '固定种子42，按维度各取最多2条错误，不足20条时从剩余错误补齐。完整问题、选项、标注及原始输出见 `results/stage2_error_examples_20.json`。此处仅陈列可核实的输出错误，不把自动比对当作视觉原因判定。', '']
    for i, e in enumerate(error_records, 1):
        lines += [f'### {i}. `{e["qa_id"]}` — {e["dimension"]} / {e["format"]}', '',
                  f'视频：`{e["video_id"]}`。问题：{e["question"]}', '',
                  f'标注：`{json.dumps(e["ground_truth"], ensure_ascii=False)}`；官方解析：`{json.dumps(e["extracted_answer"], ensure_ascii=False)}`；类别：`{e["failure_type"]}`。', '',
                  '原始输出：', '', '```text', e['raw_response'], '```', '']
    active_s = downloads['elapsed_s'] + audit['elapsed_s'] + sum(r['invocation_total_s'] for r in inference_receipts)
    download_started_at = (ROOT / 'logs/video_download_receipt.json').stat().st_mtime - downloads['elapsed_s']
    wall_s = time.time() - download_started_at
    lines += ['## 耗时与交付状态', '',
              f'- 视频下载与逐文件校验：{downloads["elapsed_s"]/60:.2f} 分钟。',
              f'- 全量官方采样解码与缓存阶段：{audit["elapsed_s"]/60:.2f} 分钟（与下载并行，含等待已校验文件到齐的时间）。',
              f'- 本次vLLM推理（不含启动，含收尾）：{inf["inference_s"]/60:.2f} 分钟；含启动/收尾：{inf["invocation_total_s"]/60:.2f} 分钟。',
              f'- 总墙钟耗时（从视频下载启动到本报告生成）：{wall_s/60:.2f} 分钟。下载起点按回执文件写入时间减去其精确计时恢复；并行阶段不重复相加。',
              '- 完整唯一预测：`results/stage2_predictions.jsonl`；官方评分输出：`logs/stage2_official_metrics.log`；数值结果：`results/stage2_metrics.json`。',
              '- 阶段二完成后停止，等待用户后续决定；阶段三未启动。阶段四主模板与补充模板将分开重新运行，包括重新运行条件A。', '']
    (ROOT / 'results/stage2_report.md').write_text('\n'.join(lines))
    receipt = dict(status='STAGE_TWO_PASS_WAITING_USER_CONFIRMATION' if passed else 'STAGE_TWO_OUT_OF_RANGE_DIAGNOSIS_REQUIRED',
                   completed_at=datetime.now(timezone.utc).isoformat(), overall_percent=result['overall']*100,
                   paper_overall_percent=27.0, delta_pp=result['overall']*100-27.0, acceptance_percent=[24.0,30.0],
                   passed=passed, unique_predictions=2323, missing_predictions=0, duplicate_predictions=0,
                   parse_failures=len(invalids), parse_failure_percent=result['invalid_rate']*100,
                   failed_startup_attempts=len(failed_attempts),
                   reid_percent=result['per_dim']['reappear_identity']*100,
                   reid_paper_difference_unresolved=bool(reid_diagnostic),
                   verified_videos=1951, decode_anomalies=audit['anomaly_count'],
                   source_short_videos=[r['video_id'] for r in short_videos],
                   decode_failures=0, unexpected_missing_frames=0, error_examples=20,
                   main_dimensions_total=726, main_dimensions_correct=main_correct,
                   component_duration_sum_s=round(active_s, 3), total_wall_s=round(wall_s, 3),
                   decode_overlapped_with_download=True, stage_three_started=False,
                   stage_three_authorized=False, report=str(ROOT / 'results/stage2_report.md'))
    dump(ROOT / 'results/stage2_receipt.json', receipt)
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
