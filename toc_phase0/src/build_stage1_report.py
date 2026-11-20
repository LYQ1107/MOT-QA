"""Write the stage-one handoff after all environment/model checks pass."""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return json.loads((ROOT / name).read_text())


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |',
                      '| ' + ' | '.join(['---'] * len(headers)) + ' |',
                      *['| ' + ' | '.join(map(str, row)) + ' |' for row in rows]])


def main():
    masa_receipt_path = ROOT / 'logs/masa_setup_receipt.json'
    masa = read('logs/masa_setup_receipt.json') if masa_receipt_path.exists() else {'status': 'MASA_PENDING'}
    stage_complete = (masa['status'] == 'MASA_SETUP_COMPLETE' and (ROOT / 'logs/masa_artifact_verification.json').exists()) or masa['status'] == 'MASA_INSTALL_FAILED_BACKUP_AUTHORIZED'
    stage_label = '阶段一完成；' if stage_complete else '阶段一进行中：MASA 安装与下载尚待完成；'
    stats = read('results/benchmark_inventory.json')
    env = read('logs/environment_validation.json')
    assert env['status'] == 'STAGE_ONE_CPU_ENVIRONMENT_CHECKS_PASSED'
    pins = read('logs/pinned_sources.json')
    artifacts = read('logs/artifact_verification.json')
    totals = read('logs/download_verification_summary.json')
    examples = read('results/qa_examples.json')
    bundle = read('data/toc_bench/answer_final.json')
    upstream = read('upstream/toc_bench/answer_final.json')
    assert bundle == upstream
    assert stats['five_tracking_dimensions_total'] == 749

    # Export the official prompt builder without importing an inference backend.
    tree = ast.parse((ROOT / 'upstream/toc_bench/eval_runner.py').read_text())
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in {'build_prompt', 'get_max_tokens'}]
    namespace = {}
    exec(compile(ast.Module(body=functions, type_ignores=[]), 'official_prompt_functions', 'exec'), namespace)
    prompts = {}
    for fmt in sorted(stats['formats']):
        item = next(item for item in bundle['items'] if item['format'] == fmt)
        system, user = namespace['build_prompt'](item)
        prompts[fmt] = dict(example_qa_id=item['qa_id'], system=system, user=user,
                            max_tokens=namespace['get_max_tokens'](fmt))
    (ROOT / 'results/official_prompt_examples.json').write_text(json.dumps(prompts, indent=2) + '\n')

    dimension_names = {
        'event_existence': 'Exist / 事件存在', 'event_count': 'Count / 事件计数',
        'reappear_identity': 'ReID / 重现身份', 'reappear_or_disappear': 'R/D / 重现或消失',
        'cross_object_order': 'X-Order / 跨对象顺序', 'event_ordering': 'Order / 事件排序',
        'temporal_location': 'T-Loc / 时间位置', 'duration_category': 'Dur / 持续时间',
        'conditional_state': 'Cond / 条件状态', 'relative_spatial_change': 'Move / 相对空间变化',
    }
    source_table = table(['来源', 'QA', '视频', '视频字节数', 'GB（十进制）'], [
        [source, row['qa_count'], row['video_count'], row['bytes'], f'{row["bytes"] / 1e9:.3f}']
        for source, row in stats['source_counts'].items()])
    dimension_table = table(['维度（实际字段值）', '含义', '题数'], [
        [f'`{dim}`', dimension_names[dim], count] for dim, count in stats['dimensions'].items()])
    format_table = table(['序列化题型', '题数'], [[f'`{fmt}`', count] for fmt, count in stats['formats'].items()])
    version_table = table(['软件', '版本'], list(env['versions'].items()))
    model_rows = []
    for dirname in ['Qwen2.5-VL-7B-Instruct', 'grounding-dino-base', 'MASA']:
        files = [item for item in artifacts if item['path'].startswith(f'models/{dirname}/')]
        if files:
            model_rows.append([dirname, len(files), sum(item['bytes'] for item in files), '全部通过'])
    model_table = table(['模型目录（位于 `models/`）', '文件数', '字节数', '校验'], model_rows)
    raw_examples = '\n\n'.join('```json\n' + json.dumps(item, indent=2, ensure_ascii=False) + '\n```' for item in examples)
    github = f'https://github.com/junzhe-c/toc_bench/blob/{pins["github_commit"]}'
    dino_source = (ROOT / 'logs/dino_source_used.txt').read_text().strip()
    qwen_source = (ROOT / 'logs/qwen_source_used.txt').read_text().strip()
    if masa['status'] == 'MASA_SETUP_COMPLETE':
        masa_section = f'''独立环境 `{ROOT}/env_masa` 已安装成功，主方案为官方 MASA-GroundingDINO unified，未启用备选。

{table(['MASA 软件', '版本'], list(masa['versions'].items()))}

代码来自 `https://github.com/siyuanliii/masa`，直连 clone 成功，固定 commit `{masa['official_code_commit']}`。按 `docs/install.md`、`environment.yml` 和官方手动安装路径安装，使用匹配 torch 2.1 / CUDA 11.8 的 MMCV 2.1.0 预编译 wheel，不改动 vLLM 环境。

统一权重：`{masa['weights']['path']}`，来源 `{masa['weights']['source']}`，{masa['weights']['bytes']:,} bytes，SHA256 `{masa['weights']['sha256']}`。额外 BERT 模型/词表来自 ModelScope `AI-ModelScope/bert-base-uncased`，逐文件对照发布 SHA256；来源见 `logs/masa_aux_downloads.json`。源码依赖各自固定 commit，见 `logs/masa_dependency_sources.json`。

验证：MMCV 编译的 CPU NMS 可运行，官方 `init_masa` 在 CPU 上加载完整统一模型；{masa['unified_checkpoint_keys']} 个 checkpoint 键与模型一致，无缺失、额外或形状不匹配。BERT 本地文本前向通过，输出 shape `{masa['bert_text_forward_shape']}`。没有运行 GPU 跟踪或基准 QA；GPU 耗时、显存和遮挡后新 ID 比例留到阶段三实际测量。

阶段三固定入口：`--unified --texts`，短语间以 ` . ` 分隔；视频先重采样为 5 fps，模型 tracker.fps 同步设 5；不传 `--sam_mask`，不调用 SAM2/SAM3。`--score-thr` 在官方 demo 中是可视化分数阈值，初始输出分数阈值按用户要求定 0.2，内部关联阈值另行记录，不能混为同一个值。抽查 20 个视频后如需调整，只在固定后运行完整协议；报告遮挡后重新出现被分配新 ID 的大致比例，并保留抽查依据。

两套环境运行时只通过磁盘轨迹 JSON 交互。GPU 分工沿用用户指定的 GPU0（vLLM）/GPU1（MASA）；本阶段验证未占用 GPU。每个（视频，短语）仍保存逐帧框、ID、置信度、时间戳，再按原 5.3 节序列化。具体版本与加载回执见 `logs/masa_setup_receipt.json`，配置快照见 `results/masa_unified_5fps_config.py`。'''
    else:
        masa_section = f'状态 `{masa["status"]}`。MASA 的独立环境、官方源码和统一权重准备尚未全部完成；完成前不将阶段一标记为成功。'
    recovery_note = ''
    if (ROOT / 'logs/dino_resume_receipt.json').exists():
        recovery = read('logs/dino_resume_receipt.json')
        assert recovery['status'] == 'DINO_RESUME_COMPLETE_SHA256_VERIFIED'
        recovery_note = ('Grounding DINO 的 HF 镜像请求失败，官方源整文件下载中途断流，保留了 80 MiB 有效断点。'
                         '1 MiB HTTP 206 范围请求验证通过后，从断点按 32 MiB 分段直连续传，最终与同一固定版本的原始 SHA256 一致。'
                         '初次失败见 `logs/download_dino_huggingface.co.log`，续传见 `logs/resume_dino.log` 和 `logs/dino_resume_receipt.json`。')
    report = f'''# TOC-Bench 阶段一：环境与数据

2026-10-31 启动，2026-11-01 更新。独立项目 `{ROOT}`。**{stage_label}尚未运行阶段二基线、跟踪或四条件实验。**

## 结果与研究可行性

- 原始 QA 共 **2,323** 题，**1,951** 个唯一视频，10 个诊断维度；canonical JSON、JSONL 的共同字段逐项相同，HF 与 GitHub canonical JSON 完全相同。
- 五个跟踪重点维度合计 **749** 题。公开发布物没有逐帧轨迹，条件 E 当前不可做。
- 视频全部随 HF artifact 发布，标注引用的视频均在远端清单中；无需另行拼接四个原始数据集。本阶段未下载视频。
- vLLM 独立 conda 环境、Qwen 与备选 Grounding DINO 已准备，下载与结构校验通过；MASA 状态见下文。验证全程 `CUDA_VISIBLE_DEVICES=''`，未占用 GPU；GPU 推理尚未验证。
- 论文的 Qwen2.5-VL-7B 32 帧结果是总体 27.0%、Count 0.7%、ReID **95.7%**。ReID 只有 23 题，按该成绩仅剩 1 题可提升，不能预设它会产生稳定的大幅增益；保留原实验条件和判断标准，不据此调整数据或指标。[论文表 2](https://arxiv.org/html/2605.09904v2#S4.T2)

## 固定版本与文件

- HF 数据：`{pins['dataset_repo']}`，revision `{pins['dataset_revision']}`。
- 官方代码：`junzhe-c/toc_bench`，commit `{pins['github_commit']}`；旧地址 `cjzcjz666/toc_bench` 自动重定向到此处。
- 原始标注：`data/toc_bench/answer_final.json` 与 `data/toc_bench/data/test.jsonl`。
- 官方说明：`data/toc_bench/README.md`；官方代码原样保存在 `upstream/toc_bench/`。
- 远端视频清单及预期大小/校验信息：`data/toc_bench/video_manifest.json`。清单完整性不等同于视频解码已验证。

## 字段说明

| 字段 | 含义与出现范围 |
| --- | --- |
| `qa_id`, `video_id`, `format`, `question` | 题目主键、视频主键、题型、原始问题；全部 2,323 题 |
| `video_path` | HF JSONL 额外提供的相对路径，如 `videos/charades_VYMZC.mp4`；canonical items 本身不含该字段 |
| `option_A`–`option_D` | 四选一选项，1,355 题 |
| `statement_A`, `statement_B` | 二选一陈述，563 题 |
| `correct_answer` | 非排序题真值，2,218 题；计数以字符串保存 |
| `allowed_answers` | 300 道计数题的 `2`, `3`, `4`, `5 or more` |
| `events` | 105 道排序题的 `label`、`event_text`；是候选事件描述，不是带时间戳的 GT 事件轨迹 |
| `correct_order` | 排序真值字母列表，105 题 |
| `metadata.dim`, `metadata.tier` | 诊断维度、推理层级 |
| `metadata.subject_label` | 构造时的目标短语；阶段三仍按任务要求从问题文本抽取，不能静默改用此字段 |
| `metadata.hallucination` | `null`: 1,830 题；`variant_a`: 208；`variant_b`: 285 |
| `metadata.has_hallucination_distractor` | 是否含幻觉干扰项 |
| `metadata.semantic_ground_truth`, `metadata.ground_truth_is_real` | 23 道 ReID 题的额外真值字段，不能送入模型证据 |
| `metadata.repair_log` | 100 题保留的上游修订记录；本项目未修订任何问题、选项或答案 |

完整字段计数见 `results/benchmark_inventory.json`。四种概念题型中，排序按 3/4 事件分成两个序列化标签。

## 题目数量

{dimension_table}

{format_table}

交叉表：`results/dimension_format_counts.csv`；单独计数：`results/dimension_counts.csv`、`results/format_counts.csv`。

## 三条原始 QA 示例

以下直接取自发布的 JSONL，未改写。

{raw_examples}

## 视频获取方式与大小

{source_table}

合计 **{stats['video_bytes']:,} bytes = {stats['video_bytes']/1e9:.3f} GB = {stats['video_bytes']/2**30:.3f} GiB**，共 1,951 个 MP4，远端预期文件大小之和。媒体路径为 HF 仓库 `videos/<video_id>.mp4`。

视频无需从 Charades、Perception Test、MOSE、OVIS 单独下载；仍遵循各源数据集条款。目前 HF API、README、标注与两套模型均已直连获取，未使用代理。视频实体尚未下载，不能把元数据直连成功当作所有视频 CDN 下载已验证。阶段二获准后按固定 revision 下载并核对清单，失败时原样汇报，不改用代理、不漏题。

## 逐帧轨迹与官方评测协议

HF 文件清单只包含 README、两个 QA 文件和视频；GitHub 公开的是构造/跟踪脚本与评测代码，没有轨迹产物。遍历全部 QA 字段也未发现逐帧框、轨迹、可见区间或时间戳。论文的“由轨迹构造”不等于逐帧轨迹已公开。当前主路线改为自行生成 MASA-GroundingDINO unified 轨迹；Grounding DINO + ByteTrack 仅在 MASA 确实无法安装时作为备选，不能把 SAM3 构造脚本当成已发布的 GT。

官方协议已定位：

- [提示词 `build_prompt`]({github}/eval_runner.py#L525)：按 `mcq_4`、`sp`、`numerical`、`ordering_3/4` 输出裸答案；不要求解释。已原样导出每种题型示例至 `results/official_prompt_examples.json`。
- [采样 `sample_frames_uniform`]({github}/eval_runner.py#L460)：`N > 32` 时索引为 `floor(i*N/32)`，`i=0..31`；不是覆盖末帧的 `linspace(0,N-1,32)`。`N <= 32` 时保留全部帧。长边最多 720，JPEG 质量 85，输入是顺序排列的 `image_url`。
- [生成设置]({github}/eval_runner.py#L730)：温度 0，种子 42；普通题最多 64 token，排序 256 token。Qwen2.5-VL-7B 没有启用数值题 guided choice，不能自行加上以提高计数分数。
- [答案解析]({github}/answer_extractor.py)：接受裸字母、裸数字/`5 or more`、完整排序；解析失败记错。[评分脚本]({github}/compute_metrics.py) 提供总体、维度、题型、来源和 HDA 等统计。

阶段二必须注意三处协议差异：

1. 附件中的“最后一行 `Answer:`”严格解析不能直接套用官方裸答案提示词。为复现论文，采用成套官方提示词和解析；若后续改用附件模板，需对所有条件使用同一模板和解析，并另跑 A。
2. 官方基线提示词没有 32 帧采样时间戳。阶段二保持官方原样；阶段四按附件给所有条件共同加入时间戳，因此阶段四 A 应重新运行，不能混用阶段二 A 的分数。
3. 官方评分会从分母中扣除缺失 prediction。运行前后必须确保全部 2,323 个 QA 都有唯一结果；失败输出保留并记错，禁止以缺失行跳过问题。官方采样中的解码失败也需在进入评分前排查，不能静默少帧或漏视频。

## 环境与模型校验

环境：`{ROOT}/env`；激活命令 `conda activate {ROOT}/env`，或直接使用 `env/bin/python`。

{version_table}

依赖选择：vLLM 0.16.0 + torch 2.9.1 使用 CUDA 12.8 依赖，适配现有 570.133.20 驱动；supervision 固定 0.26.1，保留 `supervision.ByteTrack`。完整冻结见 `requirements.lock.txt`，安装原始报告见 `logs/pip_install_report.json`；`pip check` 通过。

{model_table}

Qwen 来源：`{qwen_source}`；Grounding DINO 来源：`{dino_source}`，固定 HF revision `{read('logs/dino_hf_info.json')['sha']}`。Grounding DINO 只保留 safetensors 权重格式，不重复下载同内容的 `.bin`。

本次 CPU 验证：所有所需模块可导入，ByteTrack 可按 5 fps 构造，vLLM 注册表支持 `Qwen2_5_VLForConditionalGeneration`；Qwen 配置、处理器与 {env['qwen_shards']} 个分片的 {env['qwen_tensor_keys']} 个索引键一致；Grounding DINO 已用 transformers 从本地权重加载，模型为 `{env['dino_model_type']}`。未运行 GPU 推理，未报告任何复现准确率。

模型文件按发布 SHA256 或 Git blob 与大小核对；conda 包按其 repodata SHA256/大小核对；pip 缓存 wheel 实际 SHA256 与安装报告逐一匹配。机器可读证据在 `logs/artifact_verification.json`，明细在 `logs/downloads.md`。

下载验证汇总：{json.dumps(totals, ensure_ascii=False)}。

网络失败及处理均保留日志：HF 镜像获取标注返回 403，切换为 HF 官方直连成功；清华 conda 镜像 TLS EOF，Anaconda 官方 channel 提示 ToS 未接受，随后使用 conda-forge 直连创建环境成功。Python 包从清华 PyPI 直连安装成功。全程未启用代理，未接受新的 Anaconda ToS，未删除用户文件。

{recovery_note}

MASA 的 HF 镜像请求未成功，统一权重从 HF 官方源直连取得并核对原始 SHA256。`scalabel-evalAPI` 源码 ZIP 中途断流后改用 Git 直连取得同一固定 commit，已完成的源码归档均保留。最初的 PyTorch wheel 传输速度约 0.13 MiB/s 且发生过断流；保留 780,437,675 bytes 有效断点后主动终止该下载进程（退出 143），改用交大镜像直连续传同一 wheel。torch、torchvision、torchaudio 三个 CUDA 11.8 wheel 均与 PyTorch 官方索引公布的 SHA256 一致，版本未变。记录见 `logs/masa_slow_download_recovery.json`、`logs/masa_torch_wheel_downloads.json`，后续安装和依赖检查均成功。

## MASA 安装与统一模型

{masa_section}

## 阶段门

MASA 状态：`{masa['status']}`。2026-10-31 用户将主跟踪器改为 MASA-GroundingDINO unified，独立 `env_masa`；原 Grounding DINO + ByteTrack 仅在 MASA 确实无法安装时作为备选。此项完成前不能标记整个阶段一完成。

待阶段一完整交付并获用户确认后，阶段二下载清单中的视频、检查可用的两张 A800、固定任务局部 GPU 列表，按官方协议运行 2,323 题。总体须在论文 27.0% 的 ±3 个百分点内；否则排查采样、提示词和解析，不能进入阶段三。本项目本阶段未占用 GPU，未启动后台训练/推理服务，未声明实验增益。
'''
    (ROOT / 'results/stage1_report.md').write_text(report)
    receipt = dict(status='STAGE_ONE_COMPLETE_WAITING_USER_CONFIRMATION' if stage_complete else 'STAGE_ONE_IN_PROGRESS_MASA_PENDING', project_root=str(ROOT),
                   masa_status=masa['status'],
                   primary_tracker='MASA-GroundingDINO unified',
                   backup_route_used=masa.get('backup_route_used', False),
                   vllm_environment=str(ROOT / 'env'), masa_environment=str(ROOT / 'env_masa'),
                   qa_count=stats['qa_count'], video_count=stats['unique_videos'], videos_downloaded=0,
                   tracking_dimensions_qa_count=749, public_per_frame_tracks=False,
                   official_prompts_and_scoring=True, environment_checked=True,
                   model_artifacts_verified=True, gpu_inference_run=False,
                   next_stage_authorized=False, dataset_revision=pins['dataset_revision'],
                   official_code_commit=pins['github_commit'])
    (ROOT / 'results/stage1_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
