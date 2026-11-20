# Research log

## 2026-10-31 — 阶段一启动

- 假设：完整视频上的 MOT 轨迹文本可补充视频大模型 32 帧采样中缺失的跨帧身份信息；本阶段仅准备验证条件，不报告准确率。
- 用户确认改为 `/data2/user` 下独立项目，创建 `/data2/user/toc_phase0`。
- 已只读核实：HF 数据仓库公开且包含 `videos/`；原 GitHub 地址重定向至 `junzhe-c/toc_bench`，提供官方推理、提示词、答案提取和评分代码。
- 直连 HF/GitHub 成功，未使用代理。磁盘 `/data2` 可用约 91 GiB；当前阶段不下载全量视频、不占用 GPU。
- 下一步：固定源版本并下载标注/代码，准备独立环境与两套模型，生成阶段一报告后停下。

## 2026-10-31 — 数据核对与环境完成，模型获取中

- 固定 HF revision `da3065053d958c38151304e33a42e138b1899eaf`、官方代码 commit `e4a10bc1fd31ec1af9482bcfc827e41f2fac769a`。2,323 题、1,951 视频、五个重点维度 749 题；HF/GitHub canonical 完全相同，JSONL 共同字段逐项一致，所有视频引用均在远端清单内。
- 视频清单总计 15,235,916,868 bytes，本阶段不下载视频；HF 和 GitHub 均未发布逐帧轨迹产物。
- 网络失败保留：HF 镜像标注 403，HF 官方直连成功；清华 conda 镜像 TLS EOF；Anaconda 官方 channel 要求接受 ToS，未接受，改用 conda-forge 直连成功。没有启用代理。
- 独立 Python 3.11.18 conda 环境已建好。清华 PyPI 直连安装完成，`pip check` 通过。选择 vLLM 0.16.0 / torch 2.9.1 CUDA 12.8 / transformers 4.57.6，以匹配现有 570 驱动；supervision 0.26.1 保留 ByteTrack API。
- 论文复核：Qwen2.5-VL-7B 32 帧 Overall 27.0%、Count 0.7%、ReID 95.7%（22/23）。ReID 仅剩一题提升空间，应如实披露上限，不调整基准或验收标准。
- 官方提示词要求裸答案，采样是 `floor(i*N/32)`。阶段二应成套使用官方提示词/解析；阶段四加入共同时间戳后重跑 A。评分前确保全部 2,323 题都有唯一预测，避免官方脚本扣除缺失行的分母行为。
- 当前模型下载仍由原阻塞 shell 等待，尚未运行 GPU 推理或训练；完成后进行模型文件完整性及离线加载检查。

## 2026-10-31 — Grounding DINO 直连断流与针对性续传

- Qwen ModelScope CLI 下载成功（17 个文件，约 5 分钟）。DINO HF 镜像因文件元数据检查失败；HF 官方源的整文件响应发生 `ChunkedEncodingError / IncompleteRead`，原下载 shell 退出 1，未当作成功。
- 检查后保留了 83,886,080 bytes 有效 `.incomplete` 前缀，七个小配置/词表文件已完整下载。问题是大文件传输中断；此时没有证据表明需要代理。
- 最小恢复：只恢复同一固定 revision 的 DINO 权重。先请求断点后的 1 MiB，HTTP 206、Content-Range 和长度均通过，再使用 32 MiB 范围请求续传；结束后必须匹配原始 933,400,872 bytes 和发布的 SHA256。
- 原失败日志、范围测试、续传日志均保留。未调整数据、指标、种子或模型；阶段二尚未开始。

## 2026-10-31 — 用户将主跟踪器改为 MASA

- 阶段一增加 MASA 独立环境、官方代码和 `gdino_masa.pth` 下载及版本/来源汇报。vLLM 保持在原 `env`，MASA 另用 `env_masa`，只通过磁盘轨迹 JSON 交互。
- 主路线改为 MASA-GroundingDINO `--unified --texts`，多短语用 ` . ` 分隔，5 fps，不启用 SAM mask，禁止 SAM2/SAM3。原 Grounding DINO + ByteTrack 仅在 MASA 确实无法安装时作为备选；已下载的备选权重保留。
- 主方案先用官方示例约 0.2 阈值，在阶段三抽查 20 个视频后再固定；后续报告增加遮挡后新 ID 的大致比例和 MASA 时间/显存。
- 已修改阶段一完成门：MASA 准备尚未完成时只生成进行中报告，不能沿用旧方案标记整个阶段一完成。

## 2026-11-01 — 原环境验证完成，MASA 资源就绪

- Qwen 与备选 DINO、主环境 CUDA 扩展/架构支持、离线处理器/模型加载、729 个 Qwen 权重键及所有包缓存校验通过。未运行 GPU 推理，阶段一状态仍为 `MASA_PENDING`。
- MASA 官方代码 commit `c5472b9c7615f35abdf1188cb1a0c5408fe50d66` 已直连 clone。按官方 Python 3.11 / torch 2.1.2 CUDA 11.8 / MMCV 2.1.0 / MMDetection 3.3.0 在独立 `env_masa` 安装，不改原 vLLM 环境。
- `gdino_masa.pth` 完整 1,091,120,775 bytes，SHA256 `15f4380ae4b17ac98c80a9a56bf6e569bac5bc21592906ccd3945a97438424ad` 已验证。BERT 来自 ModelScope，发布 SHA256 验证通过。
- scalabel-evalAPI ZIP 传输在约 13 MB 后中断；仅该依赖改走 Git 直连，核对 commit `78b26be9800596a3c0c2a999f9e04deb8e3fc29a` 后继续，保留已完成的前三个源码归档。其余源码与 BERT 已完成；未启用代理、未启用备选。
- 待 MASA 包安装完成后，运行编译算子与完整 unified checkpoint 的 CPU 加载检查，再合并来源/版本并出最终阶段一报告。

## 2026-11-01 — 阶段一完成，保留 MASA 主路线

- PyTorch 官方站最初约 0.13 MiB/s，且在约 300 MB 发生断流；发现交大镜像直连支持范围请求后，保留 780,437,675 bytes 有效断点，主动停止原下载（143），续传同一官方 wheel。三个 CUDA 11.8 wheel 与官方索引 SHA256 全部一致；不是依赖版本变更，也未启用代理。
- `env_masa` 安装完成：torch 2.1.2+cu118、MMCV 2.1.0、MMEngine 0.10.7、MMDetection 3.3.0、transformers 4.38.2、numpy 1.26.4；官方六个源码依赖按固定 commit 安装。独立于 vLLM 的 torch 2.9.1 / transformers 4.57.6。两环境 `pip check` 均通过，完整冻结及来源已保存。
- MASA 编译 CPU NMS 通过；官方 unified 模型在 CPU 加载，checkpoint 1170 个键无缺失/额外/形状不匹配，BERT 本地文本前向输出 `[1, 6, 768]`。因此保留 MASA 主方案，备选 DINO + ByteTrack 仅保留已下载资源，未使用。
- 模型文件共 32 个、19,062,611,338 bytes；软件包与源码下载证据已合并到 `logs/downloads.md` 和 `logs/artifact_verification.json`。全部资源最终通过直连获取，原失败与恢复日志保留。
- 阶段一交付 `results/stage1_report.md`（字段、3 条原始 QA、维度/题型数量、视频获取方式、轨迹公开状态、官方协议、双环境版本与来源）、`results/stage1_receipt.json`。2,323 QA / 1,951 视频 / 跟踪五维度 749 题；视频未下载，GPU 推理与阶段二评测未启动。
- 研究假设尚未被实验验证；ReID 论文基线 22/23 的上限限制如实保留。按用户阶段门停止，等待确认进入阶段二。

## 2026-11-01 — 阶段一获确认，开始阶段二

- 已阅读固定版本官方采样、提示词、请求、解析及评分代码。按最新决定完全复现官方协议：32 帧 floor(i*N/32)、长边 720/JPEG85、温度 0/种子42、64/256 token；不启用 numerical guided choice，Qwen 使用官方原始 extract。
- 简短执行计划：固定 revision 下载 1,951 个视频并逐个核对 manifest 大小/SHA256；用官方采样函数完成全量解码审计并先汇报；启动前确认两张 A800 空闲，以 qa_id 固定分片推理全部 2,323 题；唯一性/完整分母检查后运行官方评分，比较论文并保存20条错误样例。
- 主分析调整为 Count、R/D、X-Order、Order 共726题；ReID23题保留运行报告。metadata 与所有真值字段不进入模型输入。subject_label 仅允许未来阶段三评估短语抽取；部分遮挡题数量也留至阶段三统计。
- 已记录阶段四主协议（统一增加时间戳/证据，A重跑）和后续独立补充模板；当前不实施。阶段二不运行 MASA，完成后停止，不进入阶段三。
- 下载与准备同步进行，先对首个已完整校验的视频 `charades_004QE` 试跑官方采样路径：918帧/30fps，实际返回32张JPEG，无异常；该结果纳入随后全量审计，复用相同JPEG，不重新编码。未进行GPU推理。
- 下载到1,200个视频后，将全量CPU解码审计与余下网络传输流水执行：只读取下载器通过大小/SHA256后原子发布的文件；未到齐的视频在同一阻塞任务内部等待。仍须全部1951个审计完成、汇报后才推理。总耗时按墙钟记录，避免把并行阶段重复相加。
- 审计发现 `ovis_f4b271d4` 与 `ovis_2b827e3a` 原视频各只有30帧/12fps，官方采样实际各返回30帧；属于官方N≤32分支，无漏读。已向用户报告并保留异常记录。原先准备的“每视频必须32帧”工程断言与该分支不一致，修正为min(32,N)，不改官方采样器、不补帧、不跳过；其它解码/漏读异常仍阻止推理。

- 全量下载/校验完成：1951个、15,235,916,868 bytes，hf-mirror直连，2247.645秒，无下载失败。官方采样审计完成：1949个×32帧+2个×30帧=62,428帧，缓存2,103,059,760 bytes；无解码失败或非预期漏读。两项原始短视频清单已向用户完整汇报。
- 已按阶段二授权进入推理：启动前由脚本检查两张空闲A800并登记UUID；仅运行两个vLLM实例，不运行MASA，按排序qa_id交替分片。

- 首次vLLM启动失败，未发送评测请求：0.16设备映射助手对CUDA_VISIBLE_DEVICES直接int()，拒绝UUID。两个实例均已停止，GPU0/3显存已释放；原始启动日志保留。最小修复为数字掩码+PCI_BUS_ID顺序，分别通过PyTorch核对实际UUID与登记GPU一致（单设备、sm80；归一化可选GPU-前缀）；评测协议和权重不变，继续从未开始的2323题运行。

## 2026-11-01 — 阶段二完成，通过总体验收并停止

- 第二次启动前重新检查空闲卡，选用物理GPU0/5（UUID见分配回执），每实例单卡、按排序qa_id交替分片。2323个请求均成功完成，无缺失或重复；模型原始输出全部保留。未运行MASA、未改题目/选项/答案、未启用数值guided choice、未将metadata/真值加入提示词。
- 官方评分总体623/2323=26.8188%，相对论文27.0%低0.1812个百分点，落在24%–30%内，通过既定标准。Count2/300=0.67%、R/D53/134=39.55%、X-Order84/187=44.92%、Order15/105=14.29%；四个重点维度154/726=21.21%。
- 解析失败291/2323=12.5269%并全部计错：数值题290个（原始1有220个、0有70个，均在官方合法空间外），ordering_4有1个。未使用缺失预测缩小分母。
- ReID仅12/23=52.17%，低于论文95.7%；其余9维差值均小于1.63个百分点。23个ReID原始输出均为单字母、提示词/官方解析逐题核对通过；3个错误视频重新调用官方采样器，JPEG字节与缓存完全一致。模型22次选same、1次选different；当前标注13same/10different，正确12same/0different。保留该差异，来源未确定，不修改标注或评分，不把论文ReID天花板视为本次复现事实，主分析四维保持用户决定。
- 实际推理（含收尾、不含启动）1099.604秒=18.33分钟，含成功启动1148.168秒=19.14分钟；下载与CPU解码并行，总墙钟在最终报告记录。已检查两个vLLM实例退出，物理GPU0/5均0MiB、无本任务CUDA进程；其它作业未干预。
- 交付完整官方分维度/分题型比较、解析失败原文、2个原始短视频列表和固定种子42选取的20个错误样例。阶段二停止，阶段三未启动，等待用户后续确认。

## 2026-11-01 — 阶段二获确认，开始阶段三

- 已确认独立项目仍为 `/data2/user/toc_phase0`，沿用用户在 `/data2/user` 下新建目录的授权。阶段三范围749题/689个唯一视频；四个主要维度726题/669个视频。
- 阅读官方MASA统一推理API、tracker reset/label/fps路径及原规则/序列化约定。简短执行计划：保存全部题面文本的无metadata投影并规则抽取目标；用subject_label仅作抽取后评估；按可见谓词分类并预登记可表达子集；完成numerical原文和ReID诊断；空闲双卡做20视频MASA初查后固定阈值、全量跟踪、序列化与按事件类型规则基线；保存10视频可视化和遮挡后新ID抽查，完成报告后停止。
- 本阶段不运行vLLM。阶段四数值题新增合法答案比例及A/B/C/D全部条件的约束解码分析另跑，仍保留无约束官方严格准确率为主结果；只记录后续协议，本阶段不执行。
- 题面规则抽取完成：749题/689视频/899个视频-短语，跨对象题187/187均有两个目标；subject_label规范化精确匹配746/749。未据metadata改查询：两条题面与subject_label对象/颜色冲突、一条单复数不同。当前范围幻觉变体为0。
- 已预登记并只读锁定可表达子集324题，其中主要四维301题；含partly_hidden的299题、changes_abruptly的126题不直接表达。生成时间与单一清单指纹在logs/trackable_subset_lock.json；后续不得按阶段四结果修改。
- 第一轮MASA pilot在模型构造时失败，尚无视频结果：阶段一导出的配置已被MMDetection构造器注入bbox_head内部字段，不能直接重建。改为每worker从官方原始配置加载再覆盖本地BERT/fps5，并在构造前留快照；权重和结构不变。另加MASA_SKIP_NLTK_DOWNLOAD导入开关，显式custom_entities模式不使用NER，跳过两个无关NLTK自动下载，避免启动时网络访问。保留失败日志和本地源码diff。
- 修复后CPU针对性重建/统一权重加载通过。重新分配时仅物理GPU6空闲，未占用其它卡；将可选双卡调度改为按实际1–2张空闲卡执行，先单卡完成20视频试跑，全量前重新检查并按实测耗时执行6小时约定。
- 用户追加授权：只要显存能放得下，允许与其它进程共享显卡，优先少进程的卡。已停止仅等待空闲的本任务控制器（未启动worker），调度改为至少20 GiB剩余显存、按进程数/利用率/剩余显存排序取最多两张A800；不终止其它作业。显存监控分别记录本任务进程、PyTorch峰值及共享卡总占用。
- 20视频试跑结构检查通过，但按短语汇总发现所有跨对象视频的第二目标几乎只在首帧有检测。定位到官方GroundingDINOMasa缓存：换prompt时仅在track_text_dict为None才存新文本特征；复用模型处理新视频后，首帧正确、后续帧可能沿用第一视频文本。该批20视频判为无效诊断输出，完整移动保留在tracks/diagnostics/pilot_stale_text_cache，不用于评分；每视频开始清空四个文本缓存属性后做实测回归，再重跑相同20视频。阈值和子集均未调整。
- 实际GPU回归通过：同一张双目标图在跨视频缓存故障时第2目标从首帧0.95267变为后续无检测；清空缓存后连续相同帧的框/类别/分数一致，两帧第2目标均0.95267，缓存token长度由5正确变为9。结果保存在logs/stage3_text_cache_regression.json。相同20视频已重新启动，启动时GPU2空闲、GPU0共享且显存充足；本任务仍最多两张卡。
- 修复后相同20视频完成：2790帧、271.569秒墙钟、476.465秒推理求和，GPU2/0。已逐一查看全部20个带框概览，记录results/stage3_threshold_review_20.json。真实弱目标存在0.20–0.30分，语义误框亦可超过0.3，单纯提阈值不能分离，故输出阈值保留0.2并固定；内部tracker参数保留官方默认、fps5。尚未读取规则评分。视觉上已见语义误检、同词多实例和ID碎片，最终将如实报告，不据此修改子集。
- 全量控制终端在38个完整视频输出时返回143（SIGTERM）；无Python traceback/OOM信息，外部信号来源未知。本任务控制器和worker均已退出，已完成38个JSON检查通过，未完成单元未发布。改为独立tmux后台批作业并保存每步退出状态，单个阻塞等待器读取其日志/回执；恢复全部未完成视频，参数/种子/指标不变。中断回执和首次全量日志全部保留。
- 为最终10视频遮挡身份审查，另从可见题面谓词fully_hidden的计数题按seed42选10个非pilot视频，不读取它们的轨迹/答案/metadata；选择在results/stage3_occlusion_audit_selection.json。此前广泛10视频名单和20校准图保留。此定向审查用于确认遮挡片段，比例不作为全库发生率；不改已锁定阈值或可表达子集。
- 10视频源画面概览与必要的5fps放大图完成，先不看其跟踪ID/正确答案，保存17个明确完整遮挡候选（柠檬15、杯子1、手机1），其它离框/物体转面/多实例/完整与部分难区分的情况另记。很多柠檬遮挡只占一个5fps采样帧，原>0.5秒可见间隔定义会合并这些短缺口；该表达限制将报告，不修改锁定子集或既定格式。前后均能视觉匹配目标框时才比较ID，漏检和不确定项单列。
- 带框密集复核后，原17候选中lemon_09/10仍露出黄色边缘；再看无框原图确认是部分遮挡，保留原候选文件并在最终事件审查中剔除这2条。其余15次完整遮挡（3视频，其中13次来自同一柠檬视频）前后目标框均可判读：6/15前后ID不同，其中3/15为遮挡后新分配ID，另3次恢复较早旧ID。11个单采样帧遮挡没有新建ID，4个多采样帧遮挡中3次新建ID；仅作定向小样本描述，不外推全库。逐事件原始ID和首现帧见results/stage3_occlusion_manual_events.json。10个带框概览已实际查看8个，另2个仍待全量跟踪完成。

## 2026-11-01 — 阶段三完成，停在阶段四之前

- 独立tmux续跑于18:20全部完成，跟踪、序列化、规则评分和完整性检查退出码均为0。689视频/101,359帧、899逐短语JSON和文本、749唯一规则预测无缺失；预登记324题（重点四维301题）保持原始只读内容。最终0.2过滤后222,258条观测，28个空查询组合。本任务MASA worker已退出，未启动vLLM或阶段四推理。
- 规则全集覆盖220/749=29.37%，覆盖题109/220=49.55%；弃答计错后全集109/749=14.55%，可表达子集109/324=33.64%。主要四维分别为109/726=15.01%、109/301=36.21%。Count覆盖106/300、正确30/106；R/D覆盖102/134、正确71/102；X-Order覆盖10/187、正确7/10；Order覆盖2/105、正确1/2；ReID23题均无查询总体>0.5秒可见性缺口而弃答，不把空覆盖当成身份条件准确率0。计数合法输出80/300=26.67%，已覆盖计数题中80/106=75.47%。未按评分调整规则、阈值或标注。
- 全量续跑控制器3.029小时，含20视频pilot和首次中断最后监控时长的有效跟踪墙钟约3.226小时；无效缓存试跑10.65分钟另列。全689视频处理墙钟求和5.731卡时，含CPU/共享等待。单进程Torch allocated/reserved峰值1.60/2.13GiB，单卡本任务nvidia-smi峰值2.64GiB；共享卡总占用峰值20.86GiB不归因于本任务。续跑GPU2/6，最终有效视频分布GPU2=361、GPU6=310、GPU0=18。
- 10视频可视化第一次提前运行因plant视频raw尚未完成而退出，未把局部图当作完整10视频回执；全量完成后重跑成功，现已逐一实际查看全部10个带框概览及5页遮挡前/中/后图。红手链查询把红杯高分框出，导致查询100%帧有框；白杯查询出现持续人物大框；盆栽检测全低于0.2而为空。稳定搁板ID的正例也保留。可视化结论和排除项见results/stage3_manual_review.json。
- 原生未过滤数据有6751个ID/198视频跨查询标签；最终≥0.2观测为579个ID/120视频。此为同ID标签变化的描述性统计，没有真值身份验证，不等同真实ID-switch率。统计见results/stage3_query_label_drift.json。
- 仅用CPU本地Qwen tokenizer测量轨迹文本，未构造阶段四提示词或加载推理模型：逐题中位数2399 token、P95 7658、最大37404，1题仅轨迹文本已超过阶段二32768服务配置，图像/问题等尚未计入。不截断、不改序列化。
- numerical完整官方原文已保存：2/3/4只是示例，未明文禁止0/1；阶段四所有条件的合法率和另跑guided choice分析仅登记，未执行。ReID标注13same/10different，与semantic_ground_truth全部一致；23题及全部100条repair均无ReID修复。反事实全same时阶段二预测22/23=95.65%，可数值解释论文95.7%但不能证明历史标注，原始标注不改。
- 结论：执行产物完整，但Count条件准确率偏低、Order/ReID覆盖不足，已见误框/碎片/短遮挡被合并；当前不能当作稳定身份与事件证据。按原5.4应先改善跟踪/事件规则，再进入阶段四，也需解决输入容量。保留当前结果与锁定清单，交付results/stage3_report.md、results/stage3_receipt.json后停止，不进入阶段四。

## 2026-11-01 — 用户确认阶段三，开始限时一轮改进

- 用户授权一轮约1–2天的改进，冻结后全部689视频重新跟踪，报告后仍等待阶段四确认。既有R/D规则52.99%已有可用信号，本轮不追求完美，不改变任何标注或原预登记子集。
- 首先按sorted视频列表、random.Random(42).shuffle、round(0.2×689)切分并只读锁定：开发138视频/147题，测试551视频/602题，同视频无跨侧；split SHA256为e1d87675aca7e69d57a5ac99dc7ecdedaf8ca8c4efb1588bb86f42066fce80b3。此前阶段三总体报告已看过，如实登记；从本轮起只用开发集选参数，冻结前不看新测试规则分数。
- 24小时上限、小网格和决策顺序写入results/improvement_plan_locked.json：memo10/25/50；短弱轨迹(<0.6秒且mean<0.3)、Top5/Top10；legacy与公开3fps/最短2帧/重现确认2可见帧事件规则。主要依据开发集重点四维可表达子集的含弃答准确率，再看覆盖率和固定代理指标。主序列化只保留原始事实，不做B2主流程替换。
- 用阶段二与已接受阶段三的现有预测保存324题及分维度同分母对比，无新推理；全局历史表仅供报告不显示给选择器。开发73题可表达子集：Qwen22/73、原规则29/73。公开阈值已核实TOC-Bench附录A表3；MASA始终5fps，候选事件规则投影至3fps最近采样网格后使用最短2缺失采样和2连续可见采样确认，不能等同于基准的mask可见性真值。
- GPU开发试验以独立tmux任务启动，memo25/50各运行开发138视频，原memo10仅复用开发原始轨迹作对照。所有结果写tracks/development；最终冻结版本另用tracks/v1，全部689视频须重新计算。本阶段不运行vLLM，不使用SAM2/SAM3，不停止其它进程；按追加授权共享显存足够且进程少的卡。

### 2026-11-01T19:25:25.880396+08:00 — bounded development round
- Video split locked first: 138 dev / 551 test videos, 147 / 602 QA; no new test rule scoring before freeze. Existing full-subset baseline comparison was saved for later reporting.
- Original dev predictions exactly reproduce all 147 accepted rule outputs. Three public temporal-threshold sanity cases pass. Memo25/50 run in isolated dev output namespaces; final all689 will be fresh.
- Source-only dev audit: 9 videos / 18 overview pages plus 12 dense pages; two clear full-hidden return windows registered before examining new tracker IDs. Partial/ambiguous cases excluded from physical ID rate.
- CPU token audit initially requested numpy tensors from the installed fast image processor, which only supports PyTorch tensors; corrected that diagnostic call. Eight image shapes now match actual pixel-grid and expanded prompt token counts. Uncompressed dev QA evidence max17338 tokens, complete input plus reserve max37351: compression/context adjustment required.

### 2026-11-01T20:32:22.933291+08:00 — development selection and immutable freeze
- Memo10/25/50: main-trackable dev correct29/28/29 of70, coverage52/52/53. Fixed81 geometry windows fresh IDs23/19/19; selected50 by registered accuracy then coverage, not by any test score.
- Short-weak only:29/70; top5 and top10 both30/70, covered52; chose top5 by registered tie-break. Dev QA evidence P95=2072.2, max3141 tokens, versus unfiltered memo50 P95=7322.2/max17413.
- Public3fps/min2/confirm2 event proxy decreased dev correct30->23 and covered52->49; retained original gap>0.5s protocol. Negative result retained in artifacts.
- Two independently source-confirmed physical windows retain the identifiable pre-gap native ID for all memories (0/2 new), but both are shorter than2s. A false blue-cup detection on a plastic bottle and an unmatched second egg were explicitly excluded from identity matching.
- frozen_config_v1 and hash receipt written read-only before any new test rule scoring. Common future context65536 reserved; all689 videos now require fresh final-namespace tracking. B2 deferred.

### 2026-11-02T00:42:44.190053+08:00 — single round complete, no further tuning
- Fresh frozen run finished:689 videos /899 query pairs /101359 frames, all749 unique predictions committed before scoring; dev147/147 predictions reproduce the selected trial. Full run3.996h on GPU2/4; own NVML observed peak2.87GiB, allocated1.60GiB. Owned workers exited.
- Main-trackable test drops80/231->76/231 (34.63%->32.90%, -1.73pp), while secondary ReID adds3 correct. All-trackable test79/251 (31.47%) versus original80/251 (31.87%); full324 subset remains109/324 (33.64%), with dev included. Do not roll back using test scores.
- Count test18/81 and R/D51/101 retain signals above historical Qwen1/81 and38/101; X-Order7/30 and Order0/19 remain weak. Main inference with evidence has not been run.
- Length goal met:per-QA track text P95=2068.6/max3784; complete-input D bound plus1024 reserve max25848. Frozen common context65536 retained; measured minimum candidate32768. No vLLM inference.
- Proxy negatives explicitly reported: fresh IDs23/81->19/81, different IDs29/81->31/81. Manual source windows contain3 physical candidates:2 linked pairs preserve IDs,1 left egg has unmatched pre-gap identity and is not counted as success. Small short windows do not establish long-occlusion recovery.
- Split, preregistration and frozen config remain read-only/hash-matched; all8 frozen source hashes match. Frozen SHA256 7f0dbd16926026fa087ac4bb84fb1f3dce142ee903e5cf16c9e8eb1b7a62d93d.
- Keep the development-selected configuration, B2 deferred. Complete report:results/stage3_improvement_report.md. Stop here pending user confirmation for stage four.

## 2026-11-02T10:06:01.179083+08:00 — 阶段四主实验启动前锁定

- 用户确认冻结v1并授权阶段四主实验。先完成阶段二回退路由和开发集计数混淆矩阵；冻结规则、切分、可表达清单保持原哈希。
- 计划：锁定H1–H5、seed42打乱分配、统一提示词/图像清单及65536上下文；两实例固定QA分片运行A/B/C/D，再单独运行四条件计数guided choice；成对McNemar与题级1000次bootstrap后汇报停止。
- D优先同短语异视频，否则对可见区间/空缺时间块做随机置换并用原序列化器重算；无法改变的空或整段轨迹透明报告。所有分配仅依赖可见文本与冻结轨迹，不读取真值。
- H2未检出差异不等于证明等效；H3置信区间仍允许提升时报告不确定。主报告测试集可表达251题，四主维度231题；全集含调参开发集，仅附带报告。

## 2026-11-02T11:18:46.724160+08:00 — 阶段四官方主实验完成

- 四条件749题主推理与各300题guided计数诊断共4196条完整唯一预测；所有实际输入token与锁定CPU计数一致。冻结参数和标注无改动。
- 测试可表达251题：A 89、B 88、C 90、D 88题正确；B-A -0.40pp，p=1。
- 假设结论：H1 not_supported；H2 compatible_but_not_equivalence_proof；H3 inconclusive；H4 not_supported；H5 not_supported。
- 已输出测试/全集、全集/可表达、各维度的规则与双版本路由对比、配对检验和完整证据样例。D不可改时间结构的36对原样单列。
- 主实验完成后停止；补充简短推理模板与B2均未运行。

## 2026-11-02T11:25:40.662564+08:00 — 阶段四主报告离线复核

- 官方直接答复证据融合未提升主子集：B88/A89；主要四维B78/A77也无明显净收益。R/D规则51>A39>B37，A回退路由63，轨迹信号仍可由显式规则利用。
- 全测试计数严格B83>A54，但guided B97<A102；主计数81题guided B33/A30不显著（p=.5078），B72条回答2，恒答2即32题正确。未将严格格式提升作为轨迹增益证据。
- 旧阶段二与新A的749份可见字段、去时间戳提示词逐项一致；记录新A计数涨幅及共同协议变化，未追加推理做因素归因。
- D主子集5题全部块与B相同，6题至少一块相同，局限如实披露。差异样例40条，稀缺方向不足数明确。
- 原始预测started_at字段为响应记录构建时刻，补充说明时间语义；preregistration早于服务器启动已用runtime独立验证，原始预测不改写。
- 服务器及EngineCore均退出，冻结与锁定哈希不变。只做CPU汇报复核；补充模板未运行，停止等待用户。

## 2026-11-02T16:02:50.107182+08:00 — 阶段五推理前预登记与表示锁定

- 已确认项目为独立toc_phase0，冻结v1、分割、可表达清单、阶段四原预测和D分配均保持不变。用户确认只约束推理模板的最终Answer，保留推理，总预算1024。
- 计划：H6推理模板B>A；H7两模板R/D表示梯度；H8事件表示对冻结规则。≥同时报告观察排序和统计不确定性，不从未显著差异推导不劣。
- 新表示直接复用原representative与timeline函数，unsupported题也输出原始事件；未调用predict或真值/选项映射。锁定899对表示、5992份新提示词及最终行解析。
- 新推理8392条（raw5992，guided2400）；官方A/B/C/D复用阶段四。服务参数与阶段四相同，按已授权GPU共享策略启动；逐条件预计小于6小时，实测进度记录于控制器。
- 整幅画面几何疑似误检仅统计，不调整、过滤或重跟踪。完成后停止。

- 阶段五首个启动在GPU预检停止，无推理/无预测：第二候选卡距原65%显存预算+6GiB余量门槛差148MiB。仅增加控制器内部资源等待并保留失败attempt，不改服务参数/证据/解析/假设，不影响其他进程。

- 资源等待后仅将调度启动余量6GiB改为5.5GiB：第二候选卡有5996MiB预算外余量，原门槛差148MiB。模型gpu_memory_utilization仍.65，全部服务器参数、科学协议和锁定输入不变；此前尚无任何推理预测。

## 2026-11-02T18:21:33.789463+08:00 — 推理计数约束的结束token修复

- 新增raw5992条全部完成。guided推理A的第一个异常响应因151643额外EOS绕过自由前缀regex提前结束；CPU复现primary EOS被拒、额外EOS仍接受。
- 仅在guided reasoning请求用bad_words屏蔽151643，保留真正EOS151645及原regex。CPU实测vLLM屏蔽为负无穷，完整合法最终行才允许primary EOS。
- 44条有效预测保留；1条异常从原错误日志恢复为唯一正式预测，原始输出不改，按固定解析计错，不重跑该题。1条completion-token usage不可恢复，明确记缺失；输入token原等值断言已通过。
- 不改任何raw主结果、假设/表示/解析、温度/种子/预算或服务参数。修复独立只读登记并有哈希，随后仅续跑未完成单位。

## 2026-11-02T20:57:42.746429+08:00 — 计数约束实现v2独立修正

- 原regex强制Answer之前存在换行，排除了固定解析允许的单行Answer响应；实际原版推理guided截断1131/1800。该实现问题不影响5992条raw主结果或H6–H8。
- v2只把推理前缀设为可选，合法答案集合、原最终行解析、1024预算、EOS修复和服务参数不变。CPU回归验证4种单行/带推理合法值可结束，0/1/2.0/9不允许。修正协议在新推理前单独只读锁定。
- 对六条件全部1800题统一重跑；原1800条作为原版实现诊断完整保留、原异常继续计错，不选择性替换旧分数。报告明确区别原预登记raw主结果与修正版guided辅助结果。

- v2模型启动前CPU回归确认：行首Answer:必须提交为最终字段，避免通配前缀吞掉Answer:0/1。保留零行或多行自由推理，终结字段仅四种合法数值。最终修正另行只读锁定，初步可选前缀草案未运行模型，全部原始结果保留。

## 2026-11-02T21:34:52.726880+08:00 — 阶段五全部完成并停止

- 严格主口径H6 B80/A58，+8.76pp，p=.00535；Count贡献21/22净增，B与D探索性差异不显著。R/D表示梯度官方37→34→36、推理30→15→29，均非单调；推理H7被反驳，H8事件29低于规则51（p=.01408）。
- 格式敏感性仅作事后诊断：R/D宽松最终字段33→24→35，严格差距受格式遵循影响；不改主表或假设判定。预登记10样例全部无可见解释/引用。
- 原版guided1800完整保留；终结字段提交语义与额外EOS修正后，六条件全部1800统一重跑。此后注册的辅助修正与原主预登记分开报告。实际新增计算10192条，复用4196，完整最终矩阵12588，另归档原版诊断1800。
- 预登记至最终复核5.539小时，所有服务器参数逐项等于阶段四，所有已知服务器/EngineCore退出。冻结配置和主预登记哈希复核不变，原始数据/失败输出保留。目标完成，停止。

阶段五报告最终复核：H7 的 B-main→B-events 为显著回升，整体单调假设由 B→B-main 的下降反驳；已在表中明确。修正版计数约束解码的事后配对诊断（测试可表达81题）B−A +6.17pp，p=.3593，95%CI [−4.94,+16.05]；B−D −1.23pp，p=1.0。仅辅助解释，原始预测、预登记H6–H8、冻结配置均未改；结果已链接至最终报告。全部实验完成，停止。

## 2026-11-04T09:53:15.333244+08:00 — 阶段六预登记与研究计划

- 在独立toc_phase0复用v1，禁止重跟踪、重分割或修改可表达清单。先锁H9–H11、纯合成2000条、开发集5完整示范；再并行运行自写多轮工具实验与另一张卡的rank8/2epoch LoRA。
- 主范围测试可表达251，工具条件覆盖测试602；每题最多4调用，总生成2048，解析完全复用阶段五。计数另做仅限制最终答案的诊断。对照按预登记观察分数触发，不调参。
- 训练仅合成事实与自动答案，无基准标签；最终二轮适配器固定用于带帧B-events评测。保留全部错误、多轮记录、调用统计和资源耗时，完成停止。
- look追加图片与原32张服务上限存在技术冲突，已提请一次澄清；工具推理等待最终图片协议，独立CPU/训练准备继续。

阶段六启动修正：后台shell启动未创建任务状态或任何模型输出，改为受管理的前台长会话；协议、模型和科学参数不变。保留空启动日志，不将其当作完成实验。

阶段六attempt1：两卡模型启动成功、训练进入250步计划，但本地OpenAI兼容客户端继承SOCKS环境导致初始化失败（缺socksio），尚无测试预测。最小修复为DefaultHttpxClient(trust_env=False)，CPU验证即使设SOCKS也不读取代理；不安装/使用代理。训练随控制器终止，未形成epoch检查点，按原seed42从头恢复；原日志/训练中断状态保留。

## 2026-11-04T12:11:08.493995+08:00 — 阶段六辅助计数约束的工具轮修复

- T1主运行463/602题有工具尝试，共1801次，均缺少闭合标签而被固定解析器拒绝；模型错误保留，不补标签。T0主运行无工具调用。尚未据此改变提示词或任何主流程。
- 原辅助grammar额外强制闭合标签且单行JSON，拒绝主循环可处理的错误调用EOS，导致addCriterion/空行长尾。修正为工具轮完全交原解析器，仅Answer轮限制合法值；CPU确认真实未闭合调用可正常EOS，非法Answer0/2.0仍不能EOS。
- 停止原辅助计算；原三组共514条（T1部分）完整归档。主1806条、LoRA251条和训练适配器原样复用；三组计数242各统一重跑，控制条件用同一修正版。新协议独立只读锁定，SHA256 4250b96d440025684e7d815d022b73e9c533e2d1da94425a91c11627879a1de8。

阶段六有效辅助修正版在任何新推理前锁定：工具轮完全自由解码，遇到Answer:后才对同一assistant的数值续写使用guided choice；总预算仍2048，保存全部物理请求与用量。CPU确认续写渲染完全等于原提示词+前缀、未闭合调用原样返回、20+2token预算不重置。此前工具轮regex草案仅CPU测试、模型请求0。有效协议SHA256 a06952e83c73a19d62bb8a6695305dd83610ddbb0b3a9e0e5a30d46933e1431f。

## 2026-11-04T12:53:53.954591+08:00 — 阶段六完成并停止

- H9/H10与H11结果：{"H9": "not_supported", "H10": "not_supported", "H11": "empirical_target_not_reached"}。测试可表达各条件分数：{"T-none": 73, "T0": 66, "T1": 71, "Official A": 89, "Route": 112, "Frozen rule": 79}；LoRA R/D 40/101。
- 工具/训练全部固定协议完成，缺失重复0；完整对比、约束诊断、交互记录、训练及资源日志见results/stage6_report.md。未重跟踪、未改冻结配置，所有本任务服务退出。


### 阶段六最终复核（2026-11-04）

T0没有尝试调用；T1的1801次尝试均因闭合标签缺失而非法，未传入真实工具事实，未触发T-ph/T-sh。H9反向显著，H10无显著增益。合成LoRA训练35.67分钟，R/D29→40/101，未达45；全251题83→83。两个合成样例与一个开发视频的HF/PEFT、vLLM适配器输出逐字一致，未发现加载差异，不重训、不改参数。人工复核保留24例，LoRA正确样例也出现虚构事件和选项映射问题。事后按开发多数语义固定选完全遮挡，测试68/101，高于路由63/101；该诊断不修改主假设或分割。2783条正式预测完整唯一，旧514条辅助记录独立保留。最终本任务CPU/GPU服务均已退出，冻结v1和全部主预测哈希不变，EOS容错仅离线原型未推理，停止。

## 2026-11-04T17:06:31.612805+08:00 — 阶段七计划与H12锁定

先按冻结规则覆盖子集计算R/D边缘列联与Count/X-Order混淆、平衡准确率、kappa、与开发多数类的配对比较，全部标事后诊断；另列不同模型的R/D类别召回。原T1的1801次调用离线完整JSON恢复成功1801次，实际工具签名合法1798，短语精确匹配1782。3次events调用含不支持的t_start/t_end，照原规则拒绝；阶段六的1785仅为短语字符串匹配，未检查签名，本次实际回放使口径更明确。锁H12后只重跑T1及原门槛触发的占位/打乱对照，保持5示范、32原帧、40图上限、2048总生成和4次调用。计数沿用修正版最终字段约束作辅助；不训练、不改轨迹、切分或清单。长任务单阻塞命令等待，完成释放显存并停止。

## 2026-11-04T18:59:07.834887+08:00 — 阶段七最终结果与停止

H12 supported：修复T1=98/251 vsT-none73，差值+9.96pp，exact p=0.0114563，95%CI[2.788844621513944, 16.743027888446203]；开发多数盲基线126/251、路由112/251。冻结规则信息量诊断：R/D与多数类同51/75，BA.5441、kappa.1071、Fisher p.2589；Count规则18对盲基线32/81，BA.2398、kappa.0789、p.0161；X-Order7对5/9、BA.75、kappa.5263、p.5，开发覆盖0，不外推信息不存在。
T1：合法执行567/567，物体未匹配4/567，look题0/602。
T-ph：合法执行475/475，物体未匹配4/475，look题0/602。
T-sh：合法执行568/568，物体未匹配4/568，look题0/602。
18条固定样例全部人工核验，错误/不一致照实报告；正式预测2532条，缺失0重复0，先前主预测与适配器SHA不变。无新训练/跟踪/数据构建，全部任务GPU服务已退出，停止。
