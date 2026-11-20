# MOT-QA Pilot 阶段一盘点报告

生成时间：2026-11-04T20:20:26.124241+08:00。项目目录经用户确认改为 `/home/user/motqa_pilot`：原定 `/data2` 当时只余约 499 MiB，`/home/user` 所在盘约余 366 GiB。本轮已完成公开 GT 所需数据及语言标注的本地盘点，停在阶段一。未生成问题、基础事件或候选集，未运行跟踪器、训练、过滤模型或被评测模型。

本地共核实 **169 个唯一视频、134,083 帧**：其中 **162 个视频有公开 GT**，另有 7 个 MOT17 test 视频无公开 GT。三套 MOT17 检测器目录去重前共有 197 个目录。DanceTrack/SportsMOT 的无公开 GT test 图像不在本地，也没有作为试点候选下载；对应条目和未核验项在下表明确列出。

已按限定深度搜索 `/data0`—`/data3`、用户家目录及常见目录；后续只检查命中的数据根。所有原始文件均只读复用。新下载只有官方文档、文件树、序列列表和校验元数据，均直连且留有日志。LaMOT 完整包此前已在本地，本轮只向新项目解压了一份标注副本。

数据位置与版本记录如下；字节数为所用原始压缩包总量，Refer-Dance 则是所用语言标注文件合计，不包含另一套重复图像。

| 资源 | 本地路径 | 大小（bytes） | 来源与核验 |
|---|---|---|---|
| DanceTrack | `/data2/user/LocateMOT/data/DanceTrack/{train,val}`（序列软链接指向 downloads 下原始解压目录） | 11115406874 | 官方 noahcao/dancetrack；3 个完整压缩包 SHA256 与发布者 LFS 一致 |
| SportsMOT | `/data2/user/LocateMOT_FullDataV2_spill/datasets/SportsMOT/{train,val}` | 13296068096 | [官方发布渠道](https://github.com/MCG-NJU/SportsMOT#download)；本地 train/val.tar 建立完整 SHA256 |
| MOT17 | `/data2/user/LocateMOT/data/MOT17/MOT17/{train,test}` | 5860214001 | [官方 MOT17.zip](https://motchallenge.net/data/MOT17/)；建立完整 SHA256 |
| LaMOT | `/data2/user/TTA-RMOT-assets/flexhook/lamot_20261101/lamot_github/LaMOT-main.zip` | 6635937 | 完整官方 zip 版本与当前 GitHub HEAD 一致；7,556 份标注及 README 逐文件通过 Git blob 核对 |
| Refer-Dance | `/data2/user/TTA-RMOT-assets/flexhook/refer-dance-official/Refer-Dance` | 168835336 | [iKUN 作者百度网盘发布](https://github.com/dyhBUPT/iKUN#data-preparation)；表达式、labels.json、seqmap.txt 逐文件 SHA256 清单 |

完整路径、来源、字节数与 SHA256 在 [data_sources.json](data_sources.json)、[local_archive_checksums.json](local_archive_checksums.json)、[refer_annotation_manifest.json](refer_annotation_manifest.json)；下载记录见 [downloads.md](../logs/downloads.md)。SportsMOT/MOT17 的本地摘要作为版本指纹，未声称已经与发布者独立提供的摘要清单比对。

三个 DanceTrack 压缩包与发布者 `noahcao/dancetrack` revision `a0ba42ac690c41e9850a20e76a0b9450a6fb6a47` 的完整 SHA256/大小一致。LaMOT revision 为 `5300242c06381c8d5ad36865dd88f4b62c2482bc`，完整标注副本位于本项目 `sources/LaMOT-5300242c06381c8d5ad36865dd88f4b62c2482bc/`；旧解压目录只含 SportsMOT val，现已通过完整官方 zip 补齐其余标注。

本地 split 实测如下。MOT17 的 DPM/FRCNN/SDP 是同一视频的三套检测结果目录，已核对帧文件名/大小、首中末像素摘要和 GT 完全一致；下表按原视频去重，后续固定采用 FRCNN 路径。

| 数据集 | split | 唯一序列数 | 帧数 | fps | 分辨率 | 公开 GT |
|---|---|---|---|---|---|---|
| DanceTrack | train | 40（目录 40） | 41,796 | 20: 40序列 | 1280x720: 12序列; 1920x1080: 27序列; 1920x988: 1序列 | 40/40 |
| DanceTrack | val | 25（目录 25） | 25,508 | 20: 25序列 | 1920x1080: 19序列; 1280x720: 5序列; 1440x1080: 1序列 | 25/25 |
| SportsMOT | train | 45（目录 45） | 28,574 | 25: 45序列 | 1280x720: 45序列 | 45/45 |
| SportsMOT | val | 45（目录 45） | 26,970 | 25: 45序列 | 1280x720: 45序列 | 45/45 |
| MOT17 | train | 7（目录 21） | 5,316 | 30: 5序列; 14: 1序列; 25: 1序列 | 1920x1080: 6序列; 640x480: 1序列 | 7/7 |
| MOT17 | test | 7（目录 21） | 5,919 | 30: 5序列; 14: 1序列; 25: 1序列 | 1920x1080: 6序列; 640x480: 1序列 | 0/7 |

DanceTrack 官方 test 为 35 序列，SportsMOT 官方 test 为 150 序列，均不提供公开 GT。DanceTrack test 的 38,551 帧由论文全量 105,855 减去本地 train/val 67,304 推得；SportsMOT test 的 94,835 帧由论文全量 150,379 减去本地 train/val 55,544 推得，属于**来源推算，未在本地逐帧实测**。DanceTrack 论文声明标注帧率 20，未逐序列核对 test 分辨率；SportsMOT 论文声明全部片段 1280×720、25fps。没有把未知 test 的机位标签或元数据补造成实测值。[DanceTrack 论文](https://arxiv.org/html/2111.14690v3)，[SportsMOT 论文](https://arxiv.org/html/2304.05170v2)。

图像逐文件核对帧名、数量和大小；每序列首/中/末帧核对可解码及分辨率，机位估计额外解码分布采样帧。197 个目录未发现缺帧、多帧、元数据分辨率不符或 `(frame, ID)` 重复。**未做全帧逐像素解码或每张图像内容哈希**。原始 zip/tar 与本地解压的 373 份 GT/seqinfo 内容摘要、197 个图像目录的文件名/大小清单全部一致，见 [archive_local_verification.json](archive_local_verification.json)。

三套 GT 都是 MOT 风格 `frame,id,x,y,w,h,flag,class,last_column` CSV；帧号从 1 开始，ID 只在各视频内部有意义，DanceTrack/SportsMOT 的 ID 可为 0。标注约定存在以下实质差异。

| 项目 | DanceTrack | SportsMOT | MOT17 |
|---|---|---|---|
| 目标 | 舞者/参与者；本地 class=1, flag=1 | 只标场内运动员，不含裁判、观众、教练；class=1, flag=1 | 多类别原始标注；正式行人是 flag=1 且 class=1 |
| 遮挡 | 部分遮挡标全身框；完全遮挡不标，之后可见时保留原 ID | 仍有可见身体部分时推断全身框；半个躯干出画时不标；过小框按发布者标准移除 | 位置可确定时可跨遮挡继续标注；有真实变化的 visibility 字段 |
| 第九列 | 全部恒为1，不是实测可见率 | 全部恒为1，不是实测可见率 | visibility 为0到1；正式行人有10,485行 visibility=0 |
| 离开/再入的身份 | 论文明确保证完全遮挡再现保持 ID；未单独承诺所有出画再入保持同一 ID | 论文要求每名运动员在整个片段有唯一 ID | 官方明确出画后再入分配新 ID；长且身份不明的遮挡也可能换 ID |

MOT17 原始 train（去重后）共有 204,701 行，正式行人 112,297 行/546 个轨迹 ID，其余 92,404 行为忽略/其他类，不能当成被追踪行人。类别包含 person-on-vehicle、static person、distractor、reflection、车辆与 occluder 等。MOT17 官方坐标采用 1-based 像素约定，框可延伸出画面。上述差异只记入阶段一，没有擅自修改 GT 或锁定阶段二可见阈值。[MOTChallenge 官方作者论文附录 C](https://arxiv.org/html/2010.07548v2)，[DanceTrack 标注约定](https://arxiv.org/html/2111.14690v3)，[SportsMOT 标注约定](https://arxiv.org/html/2304.05170v2)。

**对后续问题的影响：**MOT17 的轨迹 ID 不是跨出画再入的终身人物身份。仅凭“原 ID 不再出现”不能断言此人没有回来，也不能直接把跨出画的不同 GT ID 数当作真实不同人物数。阶段二须据此给相应操作登记适用范围；本轮不重标或自行拼接真实身份。DanceTrack 对出画再入的承诺也应与其明确的“完全遮挡后同 ID”区分。

机位粗分类在全部 169 个本地唯一视频上完成。每视频均匀取12对、约0.2秒间隔、缩至640宽，遮去 GT 框附近，再用背景角点光流与鲁棒仿射估计平移/旋转/缩放。单位为每秒图像对角线位移：中位数≥0.005或P90≥0.015标为 moving，否则 static；不足4对可靠估计则查看分布采样拼图。移动包括可检测的摇摄、缩放、倾斜或晃动，不等同于摄影机物理位置必然移动。MOT17 最终采用作者论文表9的明确机位标签，保留自动结果用于复核。

| 数据集/split | static | moving | 未决 |
|---|---|---|---|
| DanceTrack/train | 11 | 29 | 0 |
| DanceTrack/val | 11 | 14 | 0 |
| MOT17/test | 3 | 4 | 0 |
| MOT17/train | 3 | 4 | 0 |
| SportsMOT/train | 0 | 45 | 0 |
| SportsMOT/val | 0 | 45 | 0 |

5 段 DanceTrack 背景纹理不足，智能体查看每段6帧后完成标签：0015=static（中等把握，白色影棚且固定墙面结构基本不变），0044/0005/0034/0063=moving。另查看0001和0008作基本检查。自动估计未覆盖的 DanceTrack/SportsMOT test 未纳入此统计。逐序列结果、原始变换和修改理由分别见 [sequence_inventory.csv](sequence_inventory.csv)、[camera_motion_reviewed.json](camera_motion_reviewed.json)、[camera_manual_review.json](camera_manual_review.json)；拼图在 `results/camera_review/`。这只是粗机位标签，不是精确相机运动补偿。

语言资源计数使用大小写折叠、首尾及连续空白规范化，不做语义归并。`(视频, 文本)`去重与“独立文本”分开报告；相同文本若目标/时间范围不同，保留原标注，不静默合并。每条描述的原文、来源、GT ID、每个 ID 的连续帧范围均已写入 [language_descriptions.jsonl](language_descriptions.jsonl)。平均目标数是整条描述跨标注帧的目标 ID 并集大小。

| 资源/分组 | 视频 | 描述条目 | 独立文本 | 视频+文本 | 含目标 | 非空描述平均目标数 | 整段单ID条目 |
|---|---|---|---|---|---|---|---|
| LaMOT / MOT17语言train | 5 | 32 | 18 | 32 | 32 | 20.375 | 0 |
| LaMOT / MOT17语言val | 2 | 5 | 4 | 5 | 5 | 22.600 | 0 |
| LaMOT / SportsMOT train | 45 | 496 | 109 | 454 | 496 | 8.024 | 114 |
| LaMOT / SportsMOT val | 45 | 508 | 101 | 466 | 508 | 7.907 | 113 |
| Refer-Dance / DanceTrack train | 40 | 1560 | 39 | 1560 | 62 | 6.419 | 18 |
| Refer-Dance / DanceTrack val | 25 | 425 | 17 | 425 | 40 | 6.300 | 12 |

LaMOT 完整发布共 **7,556 条描述、3,693 条独立规范化文本、7,470 个视频+文本组合**，目标/帧范围一致性去重后的条目数见 [language_statistics_extended.json](language_statistics_extended.json)。实际覆盖 **1,647 个视频**，包含 MOT17 7、SportsMOT 90、VisDrone 62、TAO 1,488；本地官方版本与 README 概述的1,660不是同一个实测数，差异如实保留。TAO 有6,370条描述，VisDrone145条；这些原始视频不属于本次三个 MOT 数据集的盘点/候选范围，未补下载。LaMOT 的 MOT17 语言 train/val 分别覆盖原始 MOT17 train 中的5/2个序列，**不是 MOT17 的 train/test 对应关系**。[官方文件组织说明](https://github.com/Nathan-Li123/LaMOT)。

Refer-Dance 是 40×39 + 25×17 = **1,985 个视频—描述组合**，全局48个独立文本。原工作将 DanceTrack 的25个 val 视频称为 Refer-Dance test。1,883个组合无目标，102个含目标；这是对共享查询集合逐视频给出零/多目标标签的发布格式，不是1,985条独立人物外观描述。全部条目平均目标数0.327，非空条目平均6.373。val 的425个组合中385个为空，40个非空，12个整段只有单一ID；尚未执行阶段二的“t_ref 恰好一个可见目标”筛选。因此50%外观指代能否满足仍有风险，不能按425个有效人物描述估算，也不能直接把12条当作最终可出题数。[iKUN 原工作数据说明](https://arxiv.org/html/2312.16245v2)。

相同视频/规范化文本但目标帧标注不同的分组有 **44** 个，原条目和变体清单保留在 [language_same_text_target_variants.json](language_same_text_target_variants.json)；这类重复也意味着“单条文件只有一个ID”尚不保证措辞唯一。没有为了提高唯一性而改写描述或丢弃冲突标注。

三个目标 MOT 数据集对应的全部 **4,472,553 个语言标注 `(frame, GT ID)` 引用均匹配原始 GT**，没有做 ID 偏移或强行重映射。TAO/VisDrone 未下载的视频不包含在这个核对分母中。全量语言统计见 [language_summary.json](language_summary.json)。

许可摘要：DanceTrack 标注 CC BY 4.0，视频数据限非商业研究；SportsMOT CC BY-NC 4.0，作者另列未经书面许可不得再分发数据的条件；MOT17 CC BY-NC-SA 3.0。LaMOT 新增语言标注无独立明确许可；iKUN 的 MIT 是代码许可，未找到单列的 Refer-Dance 新增语言标注许可。本轮只在本地只读复用，不对外发布。原文短摘与官方链接见 [licenses.md](../logs/licenses.md)。

本轮只登记临时来源约束：DanceTrack val 25、SportsMOT val 45、MOT17 train 7段各后半段，共 **77 个原视频**。MOT17 半段范围固定写为1-based `floor(N/2)+1..N`，共 2659 帧，详细范围见 [provisional_source_eligibility.json](provisional_source_eligibility.json)。这份清单是来源记录，**没有生成任何候选题，也不代表已排除跟踪器训练泄漏**。

需要用户在进入阶段二前确认：自己的跟踪器，以及相关检测/ReID模块，训练和调参使用了哪些数据集、split/视频？尤其 DanceTrack val、SportsMOT val 是否用过，MOT17 是否用过完整 train？如用过完整 MOT17 train，后半段也不能自动视作未见数据。原始划分和来源均保留，待用户说明后决定可用范围。

已知限制留给阶段二：外观描述的即时唯一性尚未评估；GT 标注身份定义不完全一致；机位标签是粗分档；无 GT test 的帧没有下载/逐序列检查。没有用模型补描述或擅自开始基础事件抽取。

资源与运行记录：主盘点脚本耗时 **101.2 秒**（含本地完整压缩包哈希；官方文档获取、视觉查看和报告另计）；仅CPU，机位估计最多4个CPU工作线程，GPU使用0。未新建或混装环境，复用已有Python 3.11/OpenCV 5.0.0/NumPy 2.2.6进行CPU处理。一次 HF mirror 元数据请求因系统Python 3.10未处理HTTP308失败，已最小修复为标准直连重定向后成功；原失败保留在下载日志中。未启用代理、未删除文件，也没有启动单步预计超过6小时的操作。

所有阈值和统计口径保存在 [stage1_inventory_protocol.json](stage1_inventory_protocol.json)，SHA256见同名 `.sha256` 文件。原始自动机位结果保持原样，5段视觉复核在独立文件中留痕。阶段一完成后停止，等待确认再进入阶段二。
