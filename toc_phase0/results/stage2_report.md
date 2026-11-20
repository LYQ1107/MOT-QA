# 阶段二：TOC-Bench Qwen2.5-VL-7B 官方基线复现

总体准确率 **26.82%**（623/2323），论文表2为27.0%，差值 -0.18 个百分点。落在 [24.0%, 30.0%] 验收区间，阶段二通过。

1,951 个视频全部按发布清单完成大小与 SHA256 核验；2,323 题均有唯一预测，无缺失、无重复。官方解析失败 **291/2323（12.53%）**，均保留原始输出并记错。

## 数据和解码审计

- 数据 revision：`da3065053d958c38151304e33a42e138b1899eaf`；视频共 15,235,916,868 bytes（15.24 GB）。
- 来源：`https://hf-mirror.com`，全程未使用代理。逐文件来源/大小/校验在 `logs/downloads.md`，完整回执为 `logs/video_download_receipt.json`。
- 官方采样器检查 1,951/1,951 个视频，共 62,428 帧；实际帧数分布：`{'32': 1949, '30': 2}`。解码失败或非预期漏读：**0**；原视频不足32帧：**2个**。
- 不足32帧的视频清单：`ovis_2b827e3a`：原始30帧/12fps，采样30帧；`ovis_f4b271d4`：原始30帧/12fps，采样30帧。严格执行官方N≤32取全部帧分支，未补帧、未跳过；推理前已向用户报告。
- 原始帧数范围 30–2617；采样 JPEG 缓存 1.96 GiB，未超过25 GiB限制。
- 全量审计先汇报，再启动推理。完整逐视频 FPS/帧数/索引/时间戳/尺寸保存在 `results/video_decode_audit.json`，异常列表为 `results/video_decode_anomalies.json`。

## 锁定的评测协议

- 官方代码 commit：`e4a10bc1fd31ec1af9482bcfc827e41f2fac769a`，上游文件未改动。
- 直接调用官方 `sample_frames_uniform`：N>32时floor(i*N/32)，N≤32时取全部帧，长边不超过720，JPEG质量85；推理复用该函数输出的相同 JPEG 字节。
- 直接调用官方 `build_prompt`、`call_openai_video`、`answer_extractor.extract` 和 `compute_metrics.py`。采样帧的image_url在前（通常32个、上述两个短视频各30个）、官方问题文本在后；阶段二不增加时间戳或证据。
- 温度0、种子42；普通题64 token、排序题256 token；未启用 guided choice、未使用其他模型专用的解析回退。
- 只将题目、选项和事件文本传给官方请求函数；不传metadata、答案或allowed_answers。已核对全部2,323题：移除这些字段后官方提示词逐字一致。
- 两个vLLM实例按排序后qa_id交替切分，每实例并发4。启动前已确认所选两张A800空闲；未运行MASA。
- 物理GPU/UUID：[{"physical_index": 0, "uuid": "GPU-bf21a95d-d96d-9ec5-cb15-b0fb7ad50536", "name": "NVIDIA A800-SXM4-80GB"}, {"physical_index": 5, "uuid": "GPU-c6523d98-cb2d-95ed-4cb2-a84936acceb6", "name": "NVIDIA A800-SXM4-80GB"}]。
- 运行环境：vLLM0.16.0 / torch2.9.1+CUDA12.8 / transformers4.57.6；BF16，TP=1，最大上下文32768，eager模式。未覆盖图像处理器参数；720×720仅用于启动时的模拟输入内存测量。
- vLLM沿用模型原始generation_config（含repetition_penalty=1.05）；请求显式覆盖temperature=0、seed=42和token预算。完整启动参数见 `logs/stage2_runtime_attempt*.json`。

## 与论文表2逐项比较

[论文表2](https://arxiv.org/html/2605.09904v2#S4.T2)。差值单位为百分点，参考值按论文公布的一位小数。

| 指标 | 正确/总数 | 本次 % | 论文 % | 差值 pp |
|---|---:|---:|---:|---:|
| overall | 623/2323 | 26.82 | 27.0 | -0.18 |
| event_existence | 88/219 | 40.18 | 40.6 | -0.42 |
| event_count | 2/300 | 0.67 | 0.7 | -0.03 |
| reappear_identity | 12/23 | 52.17 | 95.7 | -43.53 |
| reappear_or_disappear | 53/134 | 39.55 | 38.8 | +0.75 |
| cross_object_order | 84/187 | 44.92 | 43.3 | +1.62 |
| event_ordering | 15/105 | 14.29 | 14.3 | -0.01 |
| temporal_location | 153/587 | 26.06 | 25.9 | +0.16 |
| duration_category | 49/312 | 15.71 | 15.1 | +0.61 |
| conditional_state | 123/278 | 44.24 | 43.9 | +0.34 |
| relative_spatial_change | 44/178 | 24.72 | 25.8 | -1.08 |
| hda | — | 35.09 | 35.3 | -0.21 |

四个重点维度共726题：154/726，准确率 21.21%。ReID全部23题照常报告，作为次要维度，不据此提出主要结论。

## 分题型准确率

表2未列分题型结果；这里对应[论文附录G.1表6](https://arxiv.org/html/2605.09904v2#A7.T6)。

| 题型 | 正确/总数 | 本次 % | 论文表6 % | 差值 pp |
|---|---:|---:|---:|---:|
| mcq_4 | 369/1355 | 27.23 | 27.1 | +0.13 |
| sp | 237/563 | 42.10 | 43.3 | -1.20 |
| numerical | 2/300 | 0.67 | 0.7 | -0.03 |
| ordering_3 | 13/52 | 25.00 | 25.0 | +0.00 |
| ordering_4 | 2/53 | 3.77 | 3.8 | -0.03 |

## ReID差异核查

本次ReID为12/23（52.17%），明显低于论文95.7%；当前复现未验证“ReID基线接近满分”。总体通过既定验收标准，四个重点维度仍按用户决定保持不变；ReID差异单列，不作为主要结论依据。

- 23题均输出单个A/B，无解析失败；全部官方提示词与不含metadata/答案的输入构造一致，官方解析结果逐题等于原始字母。
- 对3个错误样例重新运行未修改的官方采样器，所得32张JPEG逐字节等于推理缓存；未发现这些样例的采样或缓存偏差。
- 从选项文本读取语义：模型22题选“同一物体”、1题选“不同物体”；发布标注为13题“同一”、10题“不同”。其中12/13个“同一”题答对，10个“不同”题全部答错。
- 以上说明本次输出存在明显的“同一物体”偏置；尚不能确定论文差异的来源。未改标注、解析或评分，也未使用metadata真值字段生成提示词。逐题记录和3个采样比对结果见 `results/stage2_reid_diagnostic.json`。

## 解析失败与运行错误

- 解析失败：291/2323。按题型：`{'numerical': 290, 'ordering_4': 1}`。
- 数值题原始输出中，`1`有220题、`0`有70题；二者均不在官方数值答案集合内，由官方解析器返回None并记错。
- 解析失败原文见 `results/stage2_parse_failures.json`；数值题完整原始输出分布见 `results/stage2_numerical_raw_counts.json`。未做选择约束或把非法数值改成合法答案。
- 最终预测HTTP/运行错误：0。已完成的推理调用回执：1份；所有中断错误（若有）保留于日志，不通过缺失行改变评分分母。
- 评测请求前启动失败：1次。首次原因为vLLM0.16不能将UUID形式的CUDA_VISIBLE_DEVICES转换为整数；改为数字掩码并核对实际CUDA UUID后继续。首次未产生预测，原日志和原因/修复回执见 `logs/stage2_failed_attempt1.json`；未修改模型或评测协议。

## 20条错误样例

固定种子42，按维度各取最多2条错误，不足20条时从剩余错误补齐。完整问题、选项、标注及原始输出见 `results/stage2_error_examples_20.json`。此处仅陈列可核实的输出错误，不把自动比对当作视觉原因判定。

### 1. `39e6c1c321a7` — event_existence / sp

视频：`charades_ECXEX`。问题：Does yellow bottle ever come back into view in the video?

标注：`"B"`；官方解析：`"A"`；类别：`wrong_answer`。

原始输出：

```text
A
```

### 2. `12fcfbaedfa3` — event_existence / sp

视频：`perception_test_video_6207`。问题：Does teabag box ever get fully hidden in the video?

标注：`"A"`；官方解析：`"B"`；类别：`wrong_answer`。

原始输出：

```text
B
```

### 3. `817c973dfc2e` — event_count / numerical

视频：`perception_test_video_2716`。问题：How many times does the white towel change abruptly in the video?

标注：`"3"`；官方解析：`null`；类别：`parse_failure`。

原始输出：

```text
1
```

### 4. `712260bf1958` — event_count / numerical

视频：`charades_RQRRD`。问题：How many times does the white shirt get partly hidden in the video?

标注：`"3"`；官方解析：`null`；类别：`parse_failure`。

原始输出：

```text
1
```

### 5. `5d35b80f555d` — reappear_identity / sp

视频：`charades_GL7E6`。问题：After the red cup comes back into view, is it the same cup as before, or a different one?

标注：`"B"`；官方解析：`"A"`；类别：`wrong_answer`。

原始输出：

```text
A
```

### 6. `5c92e154093b` — reappear_identity / sp

视频：`perception_test_video_7414`。问题：After brown medicine bottle comes back into view, is it the same bottle as before, or a different one?

标注：`"A"`；官方解析：`"B"`；类别：`wrong_answer`。

原始输出：

```text
B
```

### 7. `22cd8d7961ed` — reappear_or_disappear / sp

视频：`charades_WJ13E`。问题：When the soap bottle disappears, does it get fully blocked or left the frame?

标注：`"A"`；官方解析：`"B"`；类别：`wrong_answer`。

原始输出：

```text
B
```

### 8. `d69bd17512b5` — reappear_or_disappear / sp

视频：`perception_test_video_11514`。问题：When the green toothbrush disappears, does it get fully blocked or leave the frame?

标注：`"B"`；官方解析：`"A"`；类别：`wrong_answer`。

原始输出：

```text
A
```

### 9. `249a574204b2` — cross_object_order / sp

视频：`charades_2SIO0`。问题：Which event happens first in the video?

标注：`"B"`；官方解析：`"A"`；类别：`wrong_answer`。

原始输出：

```text
A
```

### 10. `9d99ed3cfaf9` — cross_object_order / sp

视频：`perception_test_video_2305`。问题：Which event happens first in the video?

标注：`"B"`；官方解析：`"A"`；类别：`wrong_answer`。

原始输出：

```text
A
```

### 11. `90d708e859f9` — event_ordering / ordering_4

视频：`charades_73J9F`。问题：Put the following events for blue spray bottle in order from earliest to latest.

标注：`["D", "A", "C", "B"]`；官方解析：`["D", "B", "C", "A"]`；类别：`wrong_answer`。

原始输出：

```text
D, B, C, A
```

### 12. `0adf492d0dfd` — event_ordering / ordering_3

视频：`perception_test_video_9131`。问题：Put the following events for laptop in order from earliest to latest.

标注：`["B", "C", "A"]`；官方解析：`["A", "B", "C"]`；类别：`wrong_answer`。

原始输出：

```text
A, B, C
```

### 13. `09ed55fc46bb` — temporal_location / mcq_4

视频：`charades_B4ED1`。问题：When in the video does bookshelf come back into view?

标注：`"C"`；官方解析：`"D"`；类别：`wrong_answer`。

原始输出：

```text
D
```

### 14. `186f2f3f5dcf` — temporal_location / mcq_4

视频：`charades_004QE`。问题：When in the video does shelf with toiletries get partly hidden?

标注：`"A"`；官方解析：`"B"`；类别：`wrong_answer`。

原始输出：

```text
B
```

### 15. `616809a35e35` — duration_category / mcq_4

视频：`perception_test_video_5791`。问题：How long is the pink napkin partly hidden?

标注：`"D"`；官方解析：`"B"`；类别：`wrong_answer`。

原始输出：

```text
B
```

### 16. `66b8a8aeacf7` — duration_category / mcq_4

视频：`charades_L1BNN`。问题：How long does clothes hanging stay out of the frame?

标注：`"D"`；官方解析：`"B"`；类别：`wrong_answer`。

原始输出：

```text
B
```

### 17. `d4c6775bd0b4` — conditional_state / mcq_4

视频：`charades_K0Z9V`。问题：At the moment the white door comes back into view, what is the state of the man in the gray t-shirt?

标注：`"B"`；官方解析：`"A"`；类别：`wrong_answer`。

原始输出：

```text
A
```

### 18. `fda3134d931e` — conditional_state / mcq_4

视频：`perception_test_video_1834`。问题：At the moment knife with black handle comes back into view, what is the state of man in red shirt?

标注：`"B"`；官方解析：`"C"`；类别：`wrong_answer`。

原始输出：

```text
C
```

### 19. `058b3c997560` — relative_spatial_change / mcq_4

视频：`charades_830OE`。问题：How does the man's arm move across the frame during the video?

标注：`"D"`；官方解析：`"C"`；类别：`wrong_answer`。

原始输出：

```text
C
```

### 20. `4d08f0e5e824` — relative_spatial_change / mcq_4

视频：`mose_yes1xec3`。问题：How does the red cherry move across the frame during the video?

标注：`"D"`；官方解析：`"B"`；类别：`wrong_answer`。

原始输出：

```text
B
```

## 耗时与交付状态

- 视频下载与逐文件校验：37.46 分钟。
- 全量官方采样解码与缓存阶段：17.55 分钟（与下载并行，含等待已校验文件到齐的时间）。
- 本次vLLM推理（不含启动，含收尾）：18.33 分钟；含启动/收尾：19.14 分钟。
- 总墙钟耗时（从视频下载启动到本报告生成）：65.20 分钟。下载起点按回执文件写入时间减去其精确计时恢复；并行阶段不重复相加。
- 完整唯一预测：`results/stage2_predictions.jsonl`；官方评分输出：`logs/stage2_official_metrics.log`；数值结果：`results/stage2_metrics.json`。
- 阶段二完成后停止，等待用户后续决定；阶段三未启动。阶段四主模板与补充模板将分开重新运行，包括重新运行条件A。
