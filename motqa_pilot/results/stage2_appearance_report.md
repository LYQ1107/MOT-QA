# 阶段二补充报告：DanceTrack 外观描述

完成时间：2026-11-04T14:32:33.345743+00:00。独立项目：`/home/user/motqa_pilot`。用户已批准原任务 3.4 节的强视觉模型补充方案。本轮已完成并停下，未进入阶段三。

处理 DanceTrack val 全部 **25 个视频、273 个 GT ID**。每个 ID 均有 3 张生成裁剪和 2 张来自不同帧的校验裁剪；GT、原始图像、原有语言描述与阶段二资源保持原样。模型仅生成外观描述和检查匹配，不生成问答或答案，不运行跟踪器、不训练。

## 数量与覆盖

| 指标 | 结果 |
|---|---:|
| 生成输出 / GT ID | 273 / 273 |
| 合法且非空的描述 | 272 |
| 同视频全部 ID 的盲匹配唯一通过 | 32 |
| 通过独立裁剪匹配、固定时刻整帧匹配及几何门槛 | **25 个 ID / 9 个视频** |
| 新增验证时刻 | 25；每个 ID 至多一个，均有后续 ≥3 秒 |
| 原有 Refer-Dance 的标注唯一覆盖 | 21 / 273 个 ID，7 / 25 视频 |
| 相对原覆盖新增的 ID | 15 |
| 原标注候选与新模型候选的去重并集 | 36 / 273 个 ID，10 / 25 视频 |
| 并集仍未覆盖 | 237 个 ID |
| 全部自动候选追加视觉审阅后无明显疑点 | **17 个 ID / 7 视频** |
| 自动通过但需用户复核后才能采用 | **8 条** |
| 无明显疑点候选相对旧资源新增 ID | 10 |
| 旧标注候选与无明显疑点新候选去重并集 | 31 /273 个 ID，9 /25 视频 |

两种来源的证据强度不同：旧资源只做过标注层面的唯一性检查，新资源通过了同一视觉模型的独立帧一致性检查；并集不能称为全部人工验证通过。新增记录仅绑定一个具体 `t_ref`，没有外推成连续唯一可见区间，也不能把它们直接当作独立题数。

最终状态分布：`{"global_ambiguous": 228, "global_wrong_or_missing_match": 12, "auto_pass": 25, "local_ambiguous": 4, "local_wrong_or_missing_match": 3, "unusable_or_invalid_phrase": 1}`。

## 固定方法

每条 GT 轨迹按时间划为五段，交替选出三张生成图、两张校验图；选帧只使用框面积、出画比例和与其他框的重叠代理量。全部 273 个 ID 的五张图互不复用。8 次选帧使用了预先规定的间距/空分段回退，逐条保留在 crop manifest；不存在少图后静默跳过。

生成图和匿名同视频人物图册用于产生 ≤30 词的英文外观短语，禁止位置、动作、时间或 GT 编号。校验图使用独立匿名顺序，要求模型返回全部匹配者和无法排除者；只有恰好匹配目标且无不确定者才通过。随后在预选的一个真实指代时刻，结合整帧和所有 GT-present 人物裁剪再次匹配。该时刻需剩余 ≥3 秒、框在画面内面积比例 ≥0.95、被其他框覆盖比例 ≤0.35、原框宽 ≥16 且高 ≥48 像素。237 个预选时刻满足几何门槛，4 个 ID 没有剩余3秒的校验帧。

这些是同模型视觉一致性检查，不能代替独立人工判断。统一服装、低分辨率、遮挡及相似发型会导致拒绝或误判；未通过记录和原始回答均完整保留。本轮没有根据输出反复改提示词、补生成细节或调整接收阈值。

本轮预先采用了比原任务“指代时刻唯一”更保守的筛选：先要求在整段视频的全部ID图册中唯一，且每ID只检查一个固定时刻。因此上述覆盖是本轮保守流程取得的候选规模，不能解读成每个未通过ID在任何时刻都不可能唯一指认；未做穷尽时刻搜索。

## 抽查

按锁定方法抽查 30 条：每个视频一条（有自动通过项时从通过项选），另加5条拒绝项。结果 `{"consistent_rejection": 20, "consistent": 4, "needs_review": 5, "model_match_disagreement": 1}`。其中9条为自动通过项，发现5条的附加外观细节有疑点。由于通过池仅25条，随后明确登记为**事后追加检查**其余16条；原始30条抽样清单没有修改，没有新增模型推理或放宽规则。共审阅46条，覆盖所有25条自动候选。

全部自动候选中，17条未见明显问题，8条需用户复核。疑点包括：粉色裤腰绳被归到连帽上衣、棒球帽说成渔夫帽、黄色帽标说成黄色帽檐、头发/发饰材质或发髻/马尾混称、白色领部或垂发被说成领结、内搭颜色未获图像支持。生成和校验使用同一个模型，确实发生了重复确认错误细节的情况。另有一条被拒绝项的红发匹配疑似选错人，作为可能的假拒绝单列，不擅自改成通过。

自动通过的25条和原始回答保留不变；无明显疑点的17条另存 `reference_resources_agent_cleared.jsonl`，标疑项保留在 `review_flags.json`，后续不得把全部25条直接当作已人工认证资源。这里的人工式观察由智能体完成，最终用户审核仍待完成；原30条是按视频/拒绝情形有意抽取，不能用来估计全273条描述的总体错误率。

原30条页面：`/home/user/motqa_pilot/results/stage2_appearance/visual_review/index.html`。全部25条自动候选及标疑理由：`/home/user/motqa_pilot/results/stage2_appearance/visual_review/all_auto_candidates.html`。逐条观察：`visual_review_notes.json`、`additional_candidate_review_notes.json`。

## 完整性、模型与资源

官方模型：[Qwen/Qwen3-VL-32B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-32B-Instruct)，BF16，ModelScope 固定 revision `8d6f46b05db6abe0cb3a5ca8c817929cc0fa2d5a`。下载 26 个运行所需文件（14个权重分片）、66,726,517,854 字节，逐文件核对官方 SHA256；直连，不使用代理，记录在 `logs/downloads.md`。权重保留在独立项目 models 目录。模型 Apache-2.0 条款见官方模型卡；视频继续遵守 DanceTrack 非商业研究条件。

环境：`{"torch": "2.9.1", "vllm": "0.16.0", "transformers": "4.57.6", "numpy": "2.2.6", "Pillow": "13.0.0", "httpx": "0.28.1"}`。服务参数：TP2、BF16、max_model_len32768、max_num_seqs4、image最多4、每图像素65536–2097152、temperature0、seed42、生成512 token/校验768 token。软件代码、提示词、几何阈值、选帧文件均有锁定哈希。生成图册包含目标自身的一份重复视图，推理前在 `inference_policy_locked.json` 明确告知；未在推理后修改。

请求数 577，分阶段 `{"generate": 273, "blind_match": 272, "reference_instant_match": 32}`；finish reason `{"stop": 577}`。输入 token 最大 3507，服务上下文未截断。所有273个ID有唯一生成记录，解析失败/拒绝不从分母移除；条件不适用的后续匹配阶段逐 ID 明确记录。原始回答对应的所有输入图像 SHA256 复核通过。

同视频规范化短语完全重复的组数 21；同一句话被自动判成多个不同唯一目标的矛盾组数 0。详见 `duplicate_phrase_audit.json`，不在事后通过改写描述掩盖冲突。

完整权重下载 18.29 分钟；模型服务启动至推理结束并清理 24.24 分钟。逐阶段请求时长分布和 token 总量见 `summary.json`；并发请求时长之和不等于墙钟耗时。两卡分配 `[(0, 'GPU-bf21a95d-d96d-9ec5-cb15-b0fb7ad50536'), (1, 'GPU-f35654b3-bbf5-7303-cfcb-9bd5d3e16e69')]`。显存峰值：`{"GPU-bf21a95d-d96d-9ec5-cb15-b0fb7ad50536": {"own_peak_MiB": 66610.0, "total_peak_MiB": 67385.0625}, "GPU-f35654b3-bbf5-7303-cfcb-9bd5d3e16e69": {"own_peak_MiB": 66610.0, "total_peak_MiB": 67385.0625}}`（MiB，区分本任务进程与整卡）。本任务服务已终止，显存释放核验见 `gpu_release_check.json`；他人进程未终止。

初次完整下载命令遗漏 `--download`，只重复了配置验证和测速；推理在缺少完整下载回执处停止，未占用 GPU、未生成输出。补上命令后继续，保留失败记录，不改变协议。

首次服务启动在模型加载前失败：vLLM0.16 的设备检查把 `CUDA_VISIBLE_DEVICES` 项转成整数，不接受 GPU UUID。仅把任务环境中的设备列表改为卡号，并保留启动前实际 CUDA UUID 对照；模型架构导入回归通过后重启。没有更改模型、精度、图像、提示词、种子或接收规则。初次回归脚本误用了需要额外参数的公开注册 API，改为调用实际架构检查路径后通过；两次脚本输出均保留。失败服务日志在 `logs/appearance_attempt1/`，修复和代码哈希记录在 `device_mapping_regression.json`、`inference_code_compatibility_revision.json`。

Stage1/Stage2 已锁定文件复核通过；唯一例外是按要求追加的下载日志，其旧字节已归档且与当前日志前缀完全一致。没有改写历史快照来掩盖正常追加。

## 逐视频覆盖

| 视频 | GT ID | 原标注覆盖 | 自动通过 | 自动候选并集 | 审阅无明显疑点 | 审阅后混合并集 |
|---|---:|---:|---:|---:|---:|---:|
| dancetrack0004 | 4 | 1 | 0 | 1 | 0 | 1 |
| dancetrack0005 | 4 | 3 | 1 | 3 | 1 | 3 |
| dancetrack0007 | 8 | 0 | 2 | 2 | 2 | 2 |
| dancetrack0010 | 6 | 2 | 4 | 4 | 3 | 3 |
| dancetrack0014 | 12 | 9 | 4 | 9 | 2 | 9 |
| dancetrack0018 | 8 | 1 | 1 | 1 | 0 | 1 |
| dancetrack0019 | 7 | 0 | 0 | 0 | 0 | 0 |
| dancetrack0025 | 9 | 0 | 0 | 0 | 0 | 0 |
| dancetrack0026 | 19 | 0 | 0 | 0 | 0 | 0 |
| dancetrack0030 | 6 | 0 | 0 | 0 | 0 | 0 |
| dancetrack0034 | 14 | 0 | 0 | 0 | 0 | 0 |
| dancetrack0035 | 8 | 0 | 1 | 1 | 0 | 0 |
| dancetrack0041 | 22 | 0 | 0 | 0 | 0 | 0 |
| dancetrack0043 | 14 | 0 | 0 | 0 | 0 | 0 |
| dancetrack0047 | 8 | 0 | 0 | 0 | 0 | 0 |
| dancetrack0058 | 7 | 3 | 5 | 6 | 5 | 6 |
| dancetrack0063 | 8 | 0 | 0 | 0 | 0 | 0 |
| dancetrack0065 | 5 | 0 | 0 | 0 | 0 | 0 |
| dancetrack0073 | 14 | 0 | 0 | 0 | 0 | 0 |
| dancetrack0077 | 9 | 0 | 0 | 0 | 0 | 0 |
| dancetrack0079 | 18 | 2 | 4 | 6 | 3 | 5 |
| dancetrack0081 | 20 | 0 | 0 | 0 | 0 | 0 |
| dancetrack0090 | 14 | 0 | 0 | 0 | 0 | 0 |
| dancetrack0094 | 25 | 0 | 0 | 0 | 0 | 0 |
| dancetrack0097 | 4 | 0 | 3 | 3 | 1 | 1 |

## 交付与停止点

- 全 ID 台账：`results/stage2_appearance/description_ledger.jsonl`，包含未通过项和全部匹配事实。
- 新增指代候选：`results/stage2_appearance/reference_resources_supplement.jsonl`，与旧文件分开保存。
- 全部25条经智能体视觉审阅后，17条无明显疑点候选与其余标疑项分开：`reference_resources_agent_cleared.jsonl`、`review_flags.json`。
- 协议/模板/代码与图像清单：`protocol_locked.json`、`prompts_locked.json`、`inference_policy_locked.json`、`preinference_snapshot.sha256`。
- 抽查页面和标疑项：`visual_review/index.html`、`visual_review_notes.json`、`review_flags.json`。

本轮完成后停下。阶段三候选题尚未生成；公开跟踪器选定后的训练/调参视频重叠核查仍待后续完成。
