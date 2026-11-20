# 阶段三：MASA 轨迹与规则基线

完成 **749 题、689 个唯一视频、899 个视频—短语组合** 的 MASA 统一模型跟踪、逐帧 JSON 和原始事实文本。四个重点维度726题，另含ReID23题；阶段四未运行。报告生成时间：2026-11-01T18:26:16.264122+08:00。

抽取结果与 `subject_label` 的锚定目标规范化匹配为 **746/749（99.60%）**；预登记可表达子集为 **324题**，其中重点四维301题。规则覆盖 **220/749**，覆盖题准确率 **49.55%**；弃答计错后，全集 **109/749（14.55%）**，可表达子集 **109/324（33.64%）**。

## 数据范围与目标抽取

- 四个重点维度：726题/669视频；含ReID总计749题/689视频。源数据为407个Charades、275个PerceptionTest、7个MOSE视频。
- 按视频合并查询后共899个唯一视频—短语组合：489个视频1短语、190个2短语、10个3短语。每次MASA调用的多个短语用 ` . ` 连接。
- 抽取输入包括question、option_A–D、statement_A/B及events.event_text；排序事件中的it回指问题目标。先保存无metadata的输入投影与全部抽取结果，再读取subject_label做离线评估。未据评估标签修正查询。
- 跨对象187题均提取两个目标。该版本subject_label只记录一个锚定对象，因此本次可独立核对锚定对象召回，不能把它声称为完整双对象精确率。
- 分维度锚定目标规范化匹配：Count298/300、R/D134/134、X-Order186/187、Order105/105、ReID23/23。
- 当前749题的hallucination字段均为空，has_hallucination_distractor也均为False：幻觉变体样本数0，单列结果为N/A。

| 未精确匹配qa_id | 从题面抽取 | subject_label（仅评估） |
|---|---|---|
| c4ddf8a8ed26 | woman with purple hair | woman with blue hair |
| 8c489aafe4bb | brown ceramic mug | brown ceramic mugs |
| ef5beb6477fe | phone; wooden chair | glass |

前两条分别为题面/metadata颜色冲突与单复数差异，第三条为题面两个目标和metadata对象冲突。均保留题面抽取。
完整输入、抽取、评估分别见 [stage3_visible_inputs.jsonl](/data2/user/toc_phase0/results/stage3_visible_inputs.jsonl)、[stage3_extracted_queries.json](/data2/user/toc_phase0/results/stage3_extracted_queries.json)、[stage3_query_evaluation.json](/data2/user/toc_phase0/results/stage3_query_evaluation.json)。

## 事件类型与预登记

按全部可见文本中的谓词多标签分类，每种事件在同一题只计一次；同题可进入多行，列和不代表题目总数。

| 事件类型 | Count | R/D | X-Order | Order | ReID |
|---|---:|---:|---:|---:|---:|
| fully_hidden | 36 | 134 | 63 | 74 | 0 |
| changes_abruptly | 126 | 0 | 0 | 0 | 0 |
| comes_back_into_view | 70 | 68 | 8 | 83 | 23 |
| leaves_frame | 0 | 134 | 48 | 56 | 0 |
| disappears | 0 | 66 | 2 | 31 | 0 |
| partly_hidden | 68 | 0 | 149 | 82 | 0 |
| enters_frame | 0 | 0 | 27 | 29 | 0 |
| first_shows_up | 0 | 0 | 24 | 13 | 0 |

其中部分遮挡共299题：Count68、X-Order149、Order82；状态突变126题，均为Count。两类合计425题，不可由当前框/可见区间直接表达，序列化格式保持原约定。

| 维度 | 全集题数 | 预登记可表达题数 |
|---|---:|---:|
| event_count | 300 | 106 |
| reappear_or_disappear | 134 | 134 |
| cross_object_order | 187 | 38 |
| event_ordering | 105 | 23 |
| reappear_identity | 23 | 23 |

纳入规则：题面提到的全部事件均可用框的有无、可见区间或位置作代理；任一partly hidden、changes abruptly或other即排除。全遮挡与离开画面仅能通过位置近似区分，不等于有遮挡真值。
清单生成于 **2026-11-01T14:21:19.547890+08:00**，阶段四前已只读锁定；完成时确认内容不变。清单为 [trackable_subset_preregistered.json](/data2/user/toc_phase0/results/trackable_subset_preregistered.json)，锁定凭据为 [trackable_subset_lock.json](/data2/user/toc_phase0/logs/trackable_subset_lock.json)。阶段四须分别报告全集及该子集。

## MASA 运行与性能

- 官方MASA commit `c5472b9c7615f35abdf1188cb1a0c5408fe50d66`；unified `gdino_masa.pth`，自定义实体模式，FP16、种子42，不使用SAM mask、SAM2、SAM3或ByteTrack。
- 原视频先重采样为5 fps（ffmpeg fps=5:start_time=0，H.264 CRF18，保持空间分辨率），共101,359帧。派生视频4.24 GiB，转码墙钟19.69分钟；原始视频保留。
- 完成固定种子选取的20视频视觉抽查后，输出分数阈值固定为 **0.2**，时间为2026-11-01T15:07:03.260988+08:00。20视频中存在0.20–0.30的真实小目标/人物框，也有0.3以上的语义误框；提高统一分数阈值会损失真实观测且不能去除高分误框，因此保留初始0.2并固定。该决定仅依据图像与轨迹，未读取规则评分。
- 内部MasaTaoTracker沿用官方默认：init0.1、obj0.01、match0.5、memo10帧、momentum0.8、with_cats=False、max_distance100；fps设为5。memo10帧对应2秒，长遮挡后可能产生新ID。
- 直接使用官方统一推理API。保留每次检测原始置信度，不启用演示脚本中跨轨迹平均分等后处理；输出阈值只用于逐短语文件与文本过滤。
- 本阶段仅运行MASA，未启动vLLM；与vLLM环境的后续交互只通过磁盘JSON。按用户追加授权共享显卡，优先少进程且显存充足的卡，不终止其他任务。
- 20视频试跑墙钟 **4.53分钟**；全量续跑控制器（复用38个已完成视频，含20试跑）墙钟 **3.029小时**。各视频处理墙钟求和 **5.731卡时**，等效单进程吞吐4.91帧/秒；该时间含CPU解码/预处理及共享资源等待，不等于纯GPU内核用时。
- 两次完整结束的跟踪控制器墙钟合计 **3.105小时**；无效缓存试跑开销下文另列，转码等并行CPU工作不重复相加，配置与GPU回归等调试时间未计入跟踪墙钟。
- 首次全量控制终端收到SIGTERM（退出143，来源未确定），无Python异常/OOM日志；最后一条监控时已运行约7.31分钟。38个完整输出（含20试跑）检查通过后复用，未完成视频重算。随后改为独立tmux批作业和持久退出回执，完成后再评分，未跳过样本。含该次中断，跟踪控制器运行墙钟约3.226小时；不含图像审查与调试间隔。
- MASA单进程PyTorch峰值：allocated **1.60 GiB**、reserved **2.13 GiB**；单卡本任务进程由nvidia-smi观测的峰值 **2.64 GiB**。共享卡单卡总占用峰值 **20.86 GiB**，包括其他任务，不归因于MASA。
- 最后一次全量控制器设备：GPU2（GPU-c2484ded-5f87-237c-bbf0-d23fcb74fdb2）, GPU6（GPU-883c8be3-25b0-3d19-6fa8-4c2e335e67d2）。各阶段成功视频按物理GPU计数：`{"6": 310, "2": 361, "0": 18}`。分片按试跑速度估算，未试跑设备使用试跑汇总速度；分配快照和进程级显存记录保存在logs/stage3_*allocation*与*gpu_memory*。
- 完整性：689视频/899逐短语JSON与文本/749规则预测，无缺失或重复。过滤后222,258条观测；空轨迹组合28/899。轨迹可见间隔按>0.5秒断开，坐标为归一化中心、两位小数，文本不包含推导答案。
- 原生ID在同一视频中对应多个查询标签：未过滤原始数据为6751个ID/198视频；最终≥0.2观测为579个ID/120视频，原样保留。该统计描述标签变化，缺少逐帧真值验证，不称为真实身份切换率。见 [stage3_query_label_drift.json](/data2/user/toc_phase0/results/stage3_query_label_drift.json)。
- 原始轨迹目录 [tracks/raw](/data2/user/toc_phase0/tracks/raw)；逐短语文件目录 [tracks/by_query](/data2/user/toc_phase0/tracks/by_query)；索引 [stage3_track_index.json](/data2/user/toc_phase0/results/stage3_track_index.json)。
- 使用本地Qwen tokenizer在CPU测量逐题轨迹文本：中位数2,399 token、P95 7,658、最大37,404；仅轨迹文本超过阶段二服务32768上下文配置的有1题。这里不包含32张图像、问题、时间戳及证据前言，不能当作完整输入长度。未构造阶段四提示词、未截断文本、未运行vLLM/模型推理。详情见 [stage3_evidence_lengths.json](/data2/user/toc_phase0/results/stage3_evidence_lengths.json)。

启动失败及修复：第一次在模型构造阶段失败，原因是阶段一构造后导出的配置含MMDetection注入字段；改为从官方原始配置加载、覆盖本地BERT/fps后在构造前留快照，CPU针对性重建通过。自定义实体模式不使用NER，增加环境开关跳过导入时无关NLTK自动下载；未改模型算法。保留失败日志和 [masa_stage3_local_patch.diff](/data2/user/toc_phase0/logs/masa_stage3_local_patch.diff)。

第一批20视频虽通过结构检查，按查询汇总时暴露出官方跨视频文本缓存未失效：换prompt后只刷新token映射，缓存文本特征仍来自首个视频。已判为无效并完整保存在 [无效试跑诊断目录](/data2/user/toc_phase0/tracks/diagnostics/pilot_stale_text_cache)，不参与后续评分；其墙钟10.65分钟、推理耗时合计14.78 GPU分钟另计。修复是在每个视频开始时清空检测器四个文本缓存属性，保持模型、权重、提示词和算法一致。实际统一模型回归验证相同图像在修复后连续帧检测输出一致，再重跑相同20视频。证据见 [stage3_text_cache_regression.json](/data2/user/toc_phase0/logs/stage3_text_cache_regression.json)。

## 规则基线

规则只读取题面和轨迹，全部749题预测先落盘，再读取正确答案调用官方解析和评分。无法表达、事件未观察到或5fps下时间打平时弃答；弃答在全集准确率分母内计错。计数规则保留0/1，不强行映射为合法答案。
预先记录的规则：置信度总和最大的轨迹为主体，按间隔≤10秒、中心距离≤0.25、面积比≤3拼接非重叠碎片；可见间隔>0.5秒定义间断；边缘阈值0.05区分离框/全遮挡代理；排序容差0.2秒。ReID比较间断前后的原始ID，不合并ID后再回答同一性。

| 范围 | 题数 | 覆盖数 | 覆盖率 | 正确数 | 全集准确率 | 覆盖题准确率 |
|---|---:|---:|---:|---:|---:|---:|
| full_749 | 749 | 220 | 29.37% | 109 | 14.55% | 49.55% |
| trackable_324 | 324 | 220 | 67.90% | 109 | 33.64% | 49.55% |
| main_726 | 726 | 220 | 30.30% | 109 | 15.01% | 49.55% |
| main_trackable_301 | 301 | 220 | 73.09% | 109 | 36.21% | 49.55% |
| dimension:event_count | 300 | 106 | 35.33% | 30 | 10.00% | 28.30% |
| dimension:reappear_or_disappear | 134 | 102 | 76.12% | 71 | 52.99% | 69.61% |
| dimension:cross_object_order | 187 | 10 | 5.35% | 7 | 3.74% | 70.00% |
| dimension:event_ordering | 105 | 2 | 1.90% | 1 | 0.95% | 50.00% |
| dimension:reappear_identity | 23 | 0 | 0.00% | 0 | 0.00% | N/A |
| trackable_dimension:event_count | 106 | 106 | 100.00% | 30 | 28.30% | 28.30% |
| trackable_dimension:reappear_or_disappear | 134 | 102 | 76.12% | 71 | 52.99% | 69.61% |
| trackable_dimension:cross_object_order | 38 | 10 | 26.32% | 7 | 18.42% | 70.00% |
| trackable_dimension:event_ordering | 23 | 2 | 8.70% | 1 | 4.35% | 50.00% |
| trackable_dimension:reappear_identity | 23 | 0 | 0.00% | 0 | 0.00% | N/A |

计数合法集合为{2,3,4,5 or more}：规则合法答案 **80/300（26.67%）**；在106道规则已覆盖计数题中，合法比例为 **75.47%**。
按事件类型统计覆盖与准确率：

| 事件类型（重叠计数） | 总数 | 覆盖 | 正确 | 全集准确率 | 覆盖题准确率 |
|---|---:|---:|---:|---:|---:|
| changes_abruptly | 126 | 0 | 0 | 0.00% | N/A |
| comes_back_into_view | 252 | 118 | 46 | 18.25% | 38.98% |
| disappears | 99 | 58 | 48 | 48.48% | 82.76% |
| enters_frame | 56 | 1 | 0 | 0.00% | 0.00% |
| first_shows_up | 37 | 4 | 2 | 5.41% | 50.00% |
| fully_hidden | 307 | 148 | 87 | 28.34% | 58.78% |
| leaves_frame | 238 | 107 | 74 | 31.09% | 69.16% |
| partly_hidden | 299 | 0 | 0 | 0.00% | N/A |

完整弃答原因：`{"unsupported event type: changes_abruptly": 126, "no observed disappearance/reappearance gap": 23, "no disappearance event observed": 32, "unsupported event type: partly_hidden": 299, "at least one requested event was not observed": 20, "a cross-object event was not observed": 27, "cross-object event timestamps tied": 1, "event timestamps tied at 5 fps": 1}`。
规则参数与评分见 [stage3_rule_protocol.json](/data2/user/toc_phase0/results/stage3_rule_protocol.json)、[stage3_rule_metrics.json](/data2/user/toc_phase0/results/stage3_rule_metrics.json)；逐题预测见 [stage3_rule_predictions.jsonl](/data2/user/toc_phase0/results/stage3_rule_predictions.jsonl)。

## 视觉抽查与遮挡后新ID

先完成固定种子42选取的20视频阈值校准，再从非pilot且题面包含fully_hidden的计数视频中按seed42定向抽取10个视频。该10视频选取时未读取其跟踪结果、正确答案或metadata。先看源画面登记17个遮挡候选，再查看带框概览与遮挡前/中/后细图；无框密集复核确认其中2个柠檬片段仍露出目标边缘，最终完整遮挡分母为15。原17候选清单保留，修正与排除理由另存。10视频均实际查看带框图，其余7个视频没有可纳入本比例的明确且前后框可判读回合。此为定向审查，不是总体随机发生率估计。

| 视频 | 查询 | 抽查观察 | 可视化 |
|---|---|---|---|
| charades_2X7OY | pink sink | 洗手盆在开头定位正确，但ID由0变为19/27/37/38/42等；人物、椅子和桌面也被高于0.2的框命中。相机摇动与前景遮挡混合，不将所有ID变化归因于遮挡。 | [charades_2X7OY_overview.jpg](/data2/user/toc_phase0/results/stage3_visualizations/occlusion_audit/charades_2X7OY_overview.jpg) |
| charades_7R8ZU | black laptop | 前约14秒笔记本正确定位且多为ID0；转身放下并离开视野后出现橱柜、黑色电器等误框，以及人物大框。未确认完整物理遮挡后的重现事件。 | [charades_7R8ZU_overview.jpg](/data2/user/toc_phase0/results/stage3_visualizations/occlusion_audit/charades_7R8ZU_overview.jpg) |
| charades_CDNV7 | silver table leg | 前约18秒一根桌腿多为ID0，但场景有多根同类腿，后续为多个ID及部分人物误框；无法独立确认具体同一根腿的遮挡回合。 | [charades_CDNV7_overview.jpg](/data2/user/toc_phase0/results/stage3_visualizations/occlusion_audit/charades_CDNV7_overview.jpg) |
| charades_E184J | white cup | 小杯在人体转向的5.4–6.4秒遮挡前后为ID9→25，新ID首次在7.0秒出现；同时有持续覆盖整个人的高分误框，主体选择容易被其干扰。 | [charades_E184J_overview.jpg](/data2/user/toc_phase0/results/stage3_visualizations/occlusion_audit/charades_E184J_overview.jpg) |
| charades_ONA0S | door handle; wooden bench | 门把手开头多为ID1，后段为ID9；抓握、门转动与部分遮挡难区分，未计入确认完整遮挡比例。第二查询wooden bench大体命中坐面，另有门板/人体误框。 | [charades_ONA0S_overview.jpg](/data2/user/toc_phase0/results/stage3_visualizations/occlusion_audit/charades_ONA0S_overview.jpg) |
| charades_V3CWF | wooden shelf | 墙上搁板由ID0稳定跟踪全程，低处书架候选主要低于0.2；未见清楚的完整遮挡。该视频说明可获得稳定轨迹，但不能检验遮挡ReID。 | [charades_V3CWF_overview.jpg](/data2/user/toc_phase0/results/stage3_visualizations/occlusion_audit/charades_V3CWF_overview.jpg) |
| charades_YJV7W | cell phone | 手机开头ID0，中途旋转及穿衣过程碎片化；确认遮挡前9.0秒ID12、后13.0秒ID25，为新分配ID；更晚有多个碎片与误框。 | [charades_YJV7W_overview.jpg](/data2/user/toc_phase0/results/stage3_visualizations/occlusion_audit/charades_YJV7W_overview.jpg) |
| perception_test_video_10599 | yellow lemon | 柠檬全露/局部露出时常用不同旧ID，初次完整遮挡后ID0→11；目标隐藏时仍有手、金属件等同查询误框。13个可判读完整遮挡回合中4个前后ID不同，其中仅1个为重新分配的新ID，其余回到旧ID。 | [perception_test_video_10599_overview.jpg](/data2/user/toc_phase0/results/stage3_visualizations/occlusion_audit/perception_test_video_10599_overview.jpg) |
| perception_test_video_1952 | plant in the pot | 背景盆栽部分叶簇可见，但所有候选均低于0.2（概览约0.10–0.14），最终输出为空。衣物经过时完整与部分遮挡仍难区分，且前后均无合格目标框，因此不纳入遮挡后ID比例。 | [perception_test_video_1952_overview.jpg](/data2/user/toc_phase0/results/stage3_visualizations/occlusion_audit/perception_test_video_1952_overview.jpg) |
| perception_test_video_8048 | red bracelet; woman in pink shirt | 手链局部有正确细框（例如ID20/39/56），但大量同查询框覆盖整条手臂；手腕离框时红色杯子被高分误框（ID3/59，约0.76–0.80），使查询逐帧覆盖率达到100%、自动看不到任何缺口。画面主要为手臂，第二查询woman in pink shirt无≥0.2检测。离框不计完整物理遮挡。 | [perception_test_video_8048_overview.jpg](/data2/user/toc_phase0/results/stage3_visualizations/occlusion_audit/perception_test_video_8048_overview.jpg) |

10视频中，3个视频提供15次前后目标框均可判读的完整遮挡回合：6/15（40.0%）前后ID不同，其中3/15（20.0%）为遮挡后真正新分配ID（柠檬0→11、白杯9→25、手机12→25），另3次是恢复较早已存在的ID。9/15前后保持同ID。11次仅跨1个隐藏采样帧：2次ID变化、0次新建；4次跨多个隐藏采样帧：4次ID变化、3次新建。13/15回合来自同一柠檬视频，观察高度聚集，不能外推全库；采样帧数也不等于精确遮挡持续时间。部分遮挡的lemon_09/10排除在上述分母之外。

遮挡前／遮挡中／重现后带框对照：[第1页](/data2/user/toc_phase0/results/stage3_visualizations/occlusion_cases/occlusion_page00.jpg)、[第2页](/data2/user/toc_phase0/results/stage3_visualizations/occlusion_cases/occlusion_page01.jpg)、[第3页](/data2/user/toc_phase0/results/stage3_visualizations/occlusion_cases/occlusion_page02.jpg)、[第4页](/data2/user/toc_phase0/results/stage3_visualizations/occlusion_cases/occlusion_page03.jpg)、[第5页](/data2/user/toc_phase0/results/stage3_visualizations/occlusion_cases/occlusion_page04.jpg)。逐事件原始ID、首现帧和候选修正记录见 [stage3_occlusion_manual_events.json](/data2/user/toc_phase0/results/stage3_occlusion_manual_events.json)。

视觉审查由本代理依据保存的原画面与带框图完成，比例为小样本目视估计。源画面也出现只跨一个5fps采样帧的完整遮挡；按既定>0.5秒断开规则，这些短缺口可能在文本中被合并。预登记的“可表达”不保证检测成功、身份正确或这种短时事件在序列化后仍可分辨；本阶段保持清单与格式不变。

20视频阈值抽查见 [stage3_threshold_review_20.json](/data2/user/toc_phase0/results/stage3_threshold_review_20.json)。另一次10视频遮挡审查的逐事件证据与不确定项见 [stage3_manual_review.json](/data2/user/toc_phase0/results/stage3_manual_review.json)；抽样清单为 [stage3_occlusion_audit_selection.json](/data2/user/toc_phase0/results/stage3_occlusion_audit_selection.json)。自动检测到的时间间断不直接当作物理遮挡，漏检和离开画面单列。

## numerical官方提示词原文与阶段四分析约定

以下为官方build_prompt的完整numerical文本（图像块在user文本之前，{question}为实际题目）：

```text
[System]
You are a video understanding model. Follow output format exactly.

[User]
You will see a video and a counting question. Output ONLY a single integer (e.g., 2, 3, 4) or the phrase "5 or more". No other words.

Question: {question}
Answer:
```

它把2、3、4列为“e.g.”示例，并允许“5 or more”；没有明确将输出限定在四个合法值，也没有明文禁止0/1。官方解析却拒绝0/1。阶段二原始输出严格落入合法集合为8/300（2.67%），官方解析有效为10/300（3.33%，解析会把更大整数归一到5 or more）。
阶段四所有A/B/C/D的主结果保留官方无约束严格准确率；另报合法答案比例，并将全部计数题在四个条件下各做一次约束解码分析。主提示词与简短推理补充模板各自独立运行、分别报告。本阶段只记录 [stage4_numerical_analysis_plan.json](/data2/user/toc_phase0/results/stage4_numerical_analysis_plan.json)，未运行任何阶段四推理。

## ReID标注与repair_log诊断

23题的正确选项语义全部与semantic_ground_truth一致：13题same、10题different；ground_truth_is_real分别为True/False。字段仅用于离线诊断，不进入目标抽取、跟踪、规则或模型提示词。

| correct_answer | semantic_ground_truth | ground_truth_is_real | 数量 |
|---|---|---|---:|
| A | different | False | 5 |
| A | same | True | 6 |
| B | different | False | 5 |
| B | same | True | 7 |

23道ReID均无repair_log。全部100条repair_log记录也无ReID。维度分布：`{"event_existence": 26, "reappear_or_disappear": 21, "cross_object_order": 20, "temporal_location": 16, "duration_category": 7, "relative_spatial_change": 4, "conditional_state": 6}`；改动分布：`{"A2: SP A↔B flipped to balance": 67, "A4: MCQ_4 A↔D swap": 14, "A4: MCQ_4 A↔C swap": 13, "A4: MCQ_4 A↔B swap": 5, "A1: lowercased 'd' → 'D'": 1}`。主要为选项/陈述置换并同步正确字母，另有一条答案大小写修复。没有证据表明repair_log导致ReID差异。
阶段二预测22题选same、1题选different：按发布标注12/23=52.17%；若仅在诊断中假设23题语义答案全为same，则为22/23=95.65%，四舍五入恰好为论文95.7%。这个反事实在数值上可以解释差值，不能据此证明论文采用了该标注。原始标注未修改，ReID保留为次要维度。
逐题对应、全部100条修复及反事实评分见 [stage3_diagnostics.json](/data2/user/toc_phase0/results/stage3_diagnostics.json)。

## 环境与来源

- 独立MASA环境：python 3.11.18, torch 2.1.2+cu118, torchvision 0.16.2+cu118, mmcv 2.1.0, mmengine 0.10.7, mmdet 3.3.0, transformers 4.38.2, numpy 1.26.4。
- unified权重来自官方README指定的HF仓库 `dereksiyuanli/masa`，固定revision 25ed372c47f2c46cf36fd446d1b657b656bc7ea9；下载使用hf-mirror直连，BERT使用ModelScope，均在阶段一完成。代码、依赖和权重来源/大小/校验保存在 [downloads.md](/data2/user/toc_phase0/logs/downloads.md)，本阶段没有新增下载。

## 结论与阶段门

阶段三执行链路完整，当前轨迹与事件规则仍有明显瓶颈：Count在106道覆盖题仅30题正确（28.30%）；Order只覆盖2/105，ReID因没有>0.5秒的查询总体可见性缺口而0/23覆盖，不能据此声称已测得ReID的条件准确率。R/D覆盖102/134，覆盖题71/102正确（69.61%），X-Order覆盖题7/10正确但样本很少。视觉上已确认语义误框、身份碎片和短遮挡在序列化中合并；最终≥0.2观测中，120个视频有原生ID跨查询标签变化（描述性标签变化，不是有真值验证的身份切换率）。这些证据说明目前不能把轨迹当作稳定可靠的身份与事件证据，也不能据此否定“优质轨迹可帮助大模型”的假设。按原5.4节，应先诊断并改善跟踪/事件规则质量，再进入阶段四。此外1题仅轨迹文本就有37,404 token，超过阶段二服务的32,768上下文配置；未来运行前还需解决完整输入容量问题。本阶段不更改已锁定清单、阈值、序列化格式或标注，保存本次结果并停在阶段三。

阶段三所需跟踪、序列化、规则基线、预登记、可视化和诊断均已保存；当前停在阶段三，未进入阶段四。
