"""Generate the Stage 1 report from measured inventory, without building QA."""
from pathlib import Path
from collections import Counter, defaultdict
import csv
import datetime
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "results"


def load(name):
    return json.loads((R / name).read_text())


def dump(name, value):
    (R / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def md_table(headers, values):
    return "| " + " | ".join(headers) + " |\n|" + "|".join("---" for _ in headers) + "|\n" + "\n".join("| " + " | ".join(map(str, row)) + " |" for row in values) + "\n"


def aggregate(records):
    positive = [r for r in records if r["n_unique_targets"]]
    signatures = {json.dumps([r["dataset"], r["sequence"], r["normalized_text"], r["per_target_frame_ranges"]], sort_keys=True) for r in records}
    return dict(descriptions=len(records), sequences=len({(r["dataset"], r["sequence"]) for r in records}),
                unique_texts=len({r["normalized_text"] for r in records}),
                unique_sequence_texts=len({(r["dataset"], r["sequence"], r["normalized_text"]) for r in records}),
                unique_target_frame_annotations=len(signatures),
                positive_descriptions=len(positive), empty_descriptions=len(records)-len(positive),
                mean_unique_targets=sum(r["n_unique_targets"] for r in records)/len(records),
                mean_unique_targets_positive=sum(r["n_unique_targets"] for r in positive)/len(positive),
                single_target_descriptions=sum(r["n_unique_targets"] == 1 for r in records),
                gt_references=sum(r.get("gt_references", 0) for r in records),
                gt_reference_matches=sum(r.get("gt_reference_matches", 0) for r in records))


def main():
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
    rows = load("sequences.json")
    splits = load("split_summary.json")
    language = [json.loads(s) for s in (R / "language_descriptions.jsonl").read_text().splitlines()]
    camera = load("camera_motion_reviewed.json")
    # Preserve original automatic estimates; visual review is a separate explicit artifact.
    review = load("camera_manual_review.json")
    for record in review:
        record["reviewer"] = "Codex visual inspection"
    dump("camera_manual_review.json", review)
    for record in camera:
        if record["label_source"] == "manual six-frame background review":
            record["label_source"] = "agent six-frame visual review"
    dump("camera_motion_reviewed.json", camera)
    motion_lookup = {(r["dataset"], r["video_key"]): r for r in camera}
    keys = ["dataset", "source_split", "sequence", "video_key", "is_canonical", "path", "resolved_path", "actual_frames", "fps", "width", "height", "has_public_gt_file", "gt_rows", "target_gt_rows", "camera_motion", "camera_label_source", "gt_sha256", "image_manifest_sha256"]
    with (R / "sequence_inventory.csv").open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            record = {k: row.get(k, "") for k in keys}
            m = motion_lookup[(row["dataset"], row["video_key"])]
            record.update(is_canonical=row["dataset"] != "MOT17" or row["sequence"].endswith("FRCNN"),
                          camera_motion=m["camera_motion"], camera_label_source=m["label_source"])
            writer.writerow(record)
    extended = {}
    for resource in ("LaMOT", "Refer-Dance"):
        records = [r for r in language if r["resource"] == resource]
        extended[resource] = aggregate(records)
    by_text = defaultdict(list)
    for record in language:
        by_text[(record["resource"], record["dataset"], record["sequence"], record["normalized_text"])].append(record)
    variants = []
    for key, values in by_text.items():
        targets = {json.dumps(r["per_target_frame_ranges"], sort_keys=True) for r in values}
        if len(targets) > 1:
            variants.append(dict(resource=key[0], dataset=key[1], sequence=key[2], normalized_text=key[3],
                                 variants=[{k: r[k] for k in ("source_path", "target_ids", "per_target_frame_ranges")} for r in values]))
    extended["same_sequence_text_with_different_target_frame_annotations"] = len(variants)
    dump("language_statistics_extended.json", extended)
    dump("language_same_text_target_variants.json", variants)
    registry = json.loads((ROOT / "results/official_source_registry.json").read_text())
    sources = dict(generated_at=now, project_root=str(ROOT), original_sources_read_only=True,
                   local_search_roots=["/data0", "/data1", "/data2", "/data3", "/home/user", "/mnt"],
                   local_search_max_depth=5,
                   canonical_roots={
                       "DanceTrack": "/data2/user/LocateMOT/data/DanceTrack",
                       "SportsMOT": "/data2/user/LocateMOT_FullDataV2_spill/datasets/SportsMOT",
                       "MOT17": "/data2/user/LocateMOT/data/MOT17/MOT17",
                       "LaMOT_archive": "/data2/user/TTA-RMOT-assets/flexhook/lamot_20261101/lamot_github/LaMOT-main.zip",
                       "LaMOT_complete_copy": str(ROOT / "sources/LaMOT-5300242c06381c8d5ad36865dd88f4b62c2482bc"),
                       "Refer-Dance": "/data2/user/TTA-RMOT-assets/flexhook/refer-dance-official/Refer-Dance"},
                   official_repositories=registry,
                   missing_local=[dict(dataset="DanceTrack", split="test", sequences=35, public_gt=False,
                                       reason="private GT; not eligible for this pilot; official sequence map inventoried, frames not downloaded"),
                                  dict(dataset="SportsMOT", split="test", sequences=150, public_gt=False,
                                       reason="private GT; not eligible for this pilot; official publication inventoried, frames not downloaded")],
                   checksum_scope="archive bytes fully hashed; local frames verified against release paths/sizes, not every pixel; every GT and language JSON hashed")
    dump("data_sources.json", sources)
    archive_rows = load("local_archive_checksums.json")
    sums = {name: sum(r["bytes"] for r in archive_rows if r["dataset"] == name) for name in ("DanceTrack", "SportsMOT", "MOT17", "LaMOT", "Refer-Dance")}
    refs = sum(r.get("gt_references", 0) for r in language)
    matched = sum(r.get("gt_reference_matches", 0) for r in language)
    assert refs == matched == 4472553
    assert not load("inventory_anomalies.json")
    assert len(camera) == 169 and all(r["camera_motion"] in {"static", "moving"} for r in camera)
    cm_counts = Counter((r["dataset"], r["source_split"], r["camera_motion"]) for r in camera)
    eligible = load("provisional_source_eligibility.json")
    body = f"""# MOT-QA Pilot 阶段一盘点报告

生成时间：{now}。项目目录经用户确认改为 `/home/user/motqa_pilot`：原定 `/data2` 当时只余约 499 MiB，`/home/user` 所在盘约余 366 GiB。本轮已完成公开 GT 所需数据及语言标注的本地盘点，停在阶段一。未生成问题、基础事件或候选集，未运行跟踪器、训练、过滤模型或被评测模型。

本地共核实 **169 个唯一视频、134,083 帧**：其中 **162 个视频有公开 GT**，另有 7 个 MOT17 test 视频无公开 GT。三套 MOT17 检测器目录去重前共有 197 个目录。DanceTrack/SportsMOT 的无公开 GT test 图像不在本地，也没有作为试点候选下载；对应条目和未核验项在下表明确列出。

已按限定深度搜索 `/data0`—`/data3`、用户家目录及常见目录；后续只检查命中的数据根。所有原始文件均只读复用。新下载只有官方文档、文件树、序列列表和校验元数据，均直连且留有日志。LaMOT 完整包此前已在本地，本轮只向新项目解压了一份标注副本。

数据位置与版本记录如下；字节数为所用原始压缩包总量，Refer-Dance 则是所用语言标注文件合计，不包含另一套重复图像。

"""
    body += md_table(["资源", "本地路径", "大小（bytes）", "来源与核验"], [
        ["DanceTrack", "`/data2/user/LocateMOT/data/DanceTrack/{train,val}`（序列软链接指向 downloads 下原始解压目录）", sums["DanceTrack"], "官方 noahcao/dancetrack；3 个完整压缩包 SHA256 与发布者 LFS 一致"],
        ["SportsMOT", "`/data2/user/LocateMOT_FullDataV2_spill/datasets/SportsMOT/{train,val}`", sums["SportsMOT"], "[官方发布渠道](https://github.com/MCG-NJU/SportsMOT#download)；本地 train/val.tar 建立完整 SHA256"],
        ["MOT17", "`/data2/user/LocateMOT/data/MOT17/MOT17/{train,test}`", sums["MOT17"], "[官方 MOT17.zip](https://motchallenge.net/data/MOT17/)；建立完整 SHA256"],
        ["LaMOT", "`/data2/user/TTA-RMOT-assets/flexhook/lamot_20261101/lamot_github/LaMOT-main.zip`", sums["LaMOT"], "完整官方 zip 版本与当前 GitHub HEAD 一致；7,556 份标注及 README 逐文件通过 Git blob 核对"],
        ["Refer-Dance", "`/data2/user/TTA-RMOT-assets/flexhook/refer-dance-official/Refer-Dance`", sums["Refer-Dance"], "[iKUN 作者百度网盘发布](https://github.com/dyhBUPT/iKUN#data-preparation)；表达式、labels.json、seqmap.txt 逐文件 SHA256 清单"]])
    body += """
完整路径、来源、字节数与 SHA256 在 [data_sources.json](data_sources.json)、[local_archive_checksums.json](local_archive_checksums.json)、[refer_annotation_manifest.json](refer_annotation_manifest.json)；下载记录见 [downloads.md](../logs/downloads.md)。SportsMOT/MOT17 的本地摘要作为版本指纹，未声称已经与发布者独立提供的摘要清单比对。

三个 DanceTrack 压缩包与发布者 `noahcao/dancetrack` revision `a0ba42ac690c41e9850a20e76a0b9450a6fb6a47` 的完整 SHA256/大小一致。LaMOT revision 为 `5300242c06381c8d5ad36865dd88f4b62c2482bc`，完整标注副本位于本项目 `sources/LaMOT-5300242c06381c8d5ad36865dd88f4b62c2482bc/`；旧解压目录只含 SportsMOT val，现已通过完整官方 zip 补齐其余标注。

本地 split 实测如下。MOT17 的 DPM/FRCNN/SDP 是同一视频的三套检测结果目录，已核对帧文件名/大小、首中末像素摘要和 GT 完全一致；下表按原视频去重，后续固定采用 FRCNN 路径。

"""
    split_rows = []
    for r in sorted(splits, key=lambda r: ({"DanceTrack": 0, "SportsMOT": 1, "MOT17": 2}[r["dataset"]], {"train": 0, "val": 1, "test": 2}[r["split"]])):
        split_rows.append([r["dataset"], r["split"], f"{r['unique_sequences']}（目录 {r['sequence_directories']}）", f"{r['frames']:,}",
                           "; ".join(f"{float(k):g}: {v}序列" for k, v in r["fps"].items()),
                           "; ".join(f"{k}: {v}序列" for k, v in r["resolutions"].items()),
                           f"{r['gt_sequences']}/{r['unique_sequences']}"])
    body += md_table(["数据集", "split", "唯一序列数", "帧数", "fps", "分辨率", "公开 GT"], split_rows)
    body += """
DanceTrack 官方 test 为 35 序列，SportsMOT 官方 test 为 150 序列，均不提供公开 GT。DanceTrack test 的 38,551 帧由论文全量 105,855 减去本地 train/val 67,304 推得；SportsMOT test 的 94,835 帧由论文全量 150,379 减去本地 train/val 55,544 推得，属于**来源推算，未在本地逐帧实测**。DanceTrack 论文声明标注帧率 20，未逐序列核对 test 分辨率；SportsMOT 论文声明全部片段 1280×720、25fps。没有把未知 test 的机位标签或元数据补造成实测值。[DanceTrack 论文](https://arxiv.org/html/2111.14690v3)，[SportsMOT 论文](https://arxiv.org/html/2304.05170v2)。

图像逐文件核对帧名、数量和大小；每序列首/中/末帧核对可解码及分辨率，机位估计额外解码分布采样帧。197 个目录未发现缺帧、多帧、元数据分辨率不符或 `(frame, ID)` 重复。**未做全帧逐像素解码或每张图像内容哈希**。原始 zip/tar 与本地解压的 373 份 GT/seqinfo 内容摘要、197 个图像目录的文件名/大小清单全部一致，见 [archive_local_verification.json](archive_local_verification.json)。

三套 GT 都是 MOT 风格 `frame,id,x,y,w,h,flag,class,last_column` CSV；帧号从 1 开始，ID 只在各视频内部有意义，DanceTrack/SportsMOT 的 ID 可为 0。标注约定存在以下实质差异。

"""
    body += md_table(["项目", "DanceTrack", "SportsMOT", "MOT17"], [
        ["目标", "舞者/参与者；本地 class=1, flag=1", "只标场内运动员，不含裁判、观众、教练；class=1, flag=1", "多类别原始标注；正式行人是 flag=1 且 class=1"],
        ["遮挡", "部分遮挡标全身框；完全遮挡不标，之后可见时保留原 ID", "仍有可见身体部分时推断全身框；半个躯干出画时不标；过小框按发布者标准移除", "位置可确定时可跨遮挡继续标注；有真实变化的 visibility 字段"],
        ["第九列", "全部恒为1，不是实测可见率", "全部恒为1，不是实测可见率", "visibility 为0到1；正式行人有10,485行 visibility=0"],
        ["离开/再入的身份", "论文明确保证完全遮挡再现保持 ID；未单独承诺所有出画再入保持同一 ID", "论文要求每名运动员在整个片段有唯一 ID", "官方明确出画后再入分配新 ID；长且身份不明的遮挡也可能换 ID"]])
    body += """
MOT17 原始 train（去重后）共有 204,701 行，正式行人 112,297 行/546 个轨迹 ID，其余 92,404 行为忽略/其他类，不能当成被追踪行人。类别包含 person-on-vehicle、static person、distractor、reflection、车辆与 occluder 等。MOT17 官方坐标采用 1-based 像素约定，框可延伸出画面。上述差异只记入阶段一，没有擅自修改 GT 或锁定阶段二可见阈值。[MOTChallenge 官方作者论文附录 C](https://arxiv.org/html/2010.07548v2)，[DanceTrack 标注约定](https://arxiv.org/html/2111.14690v3)，[SportsMOT 标注约定](https://arxiv.org/html/2304.05170v2)。

**对后续问题的影响：**MOT17 的轨迹 ID 不是跨出画再入的终身人物身份。仅凭“原 ID 不再出现”不能断言此人没有回来，也不能直接把跨出画的不同 GT ID 数当作真实不同人物数。阶段二须据此给相应操作登记适用范围；本轮不重标或自行拼接真实身份。DanceTrack 对出画再入的承诺也应与其明确的“完全遮挡后同 ID”区分。

机位粗分类在全部 169 个本地唯一视频上完成。每视频均匀取12对、约0.2秒间隔、缩至640宽，遮去 GT 框附近，再用背景角点光流与鲁棒仿射估计平移/旋转/缩放。单位为每秒图像对角线位移：中位数≥0.005或P90≥0.015标为 moving，否则 static；不足4对可靠估计则查看分布采样拼图。移动包括可检测的摇摄、缩放、倾斜或晃动，不等同于摄影机物理位置必然移动。MOT17 最终采用作者论文表9的明确机位标签，保留自动结果用于复核。

"""
    body += md_table(["数据集/split", "static", "moving", "未决"], [[f"{d}/{s}", cm_counts[(d, s, "static")], cm_counts[(d, s, "moving")], 0] for d, s in sorted({(r["dataset"], r["source_split"]) for r in camera})])
    body += """
5 段 DanceTrack 背景纹理不足，智能体查看每段6帧后完成标签：0015=static（中等把握，白色影棚且固定墙面结构基本不变），0044/0005/0034/0063=moving。另查看0001和0008作基本检查。自动估计未覆盖的 DanceTrack/SportsMOT test 未纳入此统计。逐序列结果、原始变换和修改理由分别见 [sequence_inventory.csv](sequence_inventory.csv)、[camera_motion_reviewed.json](camera_motion_reviewed.json)、[camera_manual_review.json](camera_manual_review.json)；拼图在 `results/camera_review/`。这只是粗机位标签，不是精确相机运动补偿。

语言资源计数使用大小写折叠、首尾及连续空白规范化，不做语义归并。`(视频, 文本)`去重与“独立文本”分开报告；相同文本若目标/时间范围不同，保留原标注，不静默合并。每条描述的原文、来源、GT ID、每个 ID 的连续帧范围均已写入 [language_descriptions.jsonl](language_descriptions.jsonl)。平均目标数是整条描述跨标注帧的目标 ID 并集大小。

"""
    lang_rows = []
    for label, resource, dataset, split in [("LaMOT / MOT17语言train", "LaMOT", "MOT17", "train"),
                                           ("LaMOT / MOT17语言val", "LaMOT", "MOT17", "val"),
                                           ("LaMOT / SportsMOT train", "LaMOT", "SportsMOT", "train"),
                                           ("LaMOT / SportsMOT val", "LaMOT", "SportsMOT", "val"),
                                           ("Refer-Dance / DanceTrack train", "Refer-Dance", "DanceTrack", "train"),
                                           ("Refer-Dance / DanceTrack val", "Refer-Dance", "DanceTrack", "val")]:
        selected = [r for r in language if r["resource"] == resource and r["dataset"] == dataset and
                    (r["language_split"] == split if resource == "LaMOT" else r["source_split"] == split)]
        a = aggregate(selected)
        lang_rows.append([label, a["sequences"], a["descriptions"], a["unique_texts"], a["unique_sequence_texts"],
                          a["positive_descriptions"], f"{a['mean_unique_targets_positive']:.3f}", a["single_target_descriptions"]])
    body += md_table(["资源/分组", "视频", "描述条目", "独立文本", "视频+文本", "含目标", "非空描述平均目标数", "整段单ID条目"], lang_rows)
    body += f"""
LaMOT 完整发布共 **7,556 条描述、3,693 条独立规范化文本、7,470 个视频+文本组合**，目标/帧范围一致性去重后的条目数见 [language_statistics_extended.json](language_statistics_extended.json)。实际覆盖 **1,647 个视频**，包含 MOT17 7、SportsMOT 90、VisDrone 62、TAO 1,488；本地官方版本与 README 概述的1,660不是同一个实测数，差异如实保留。TAO 有6,370条描述，VisDrone145条；这些原始视频不属于本次三个 MOT 数据集的盘点/候选范围，未补下载。LaMOT 的 MOT17 语言 train/val 分别覆盖原始 MOT17 train 中的5/2个序列，**不是 MOT17 的 train/test 对应关系**。[官方文件组织说明](https://github.com/Nathan-Li123/LaMOT)。

Refer-Dance 是 40×39 + 25×17 = **1,985 个视频—描述组合**，全局48个独立文本。原工作将 DanceTrack 的25个 val 视频称为 Refer-Dance test。1,883个组合无目标，102个含目标；这是对共享查询集合逐视频给出零/多目标标签的发布格式，不是1,985条独立人物外观描述。全部条目平均目标数0.327，非空条目平均6.373。val 的425个组合中385个为空，40个非空，12个整段只有单一ID；尚未执行阶段二的“t_ref 恰好一个可见目标”筛选。因此50%外观指代能否满足仍有风险，不能按425个有效人物描述估算，也不能直接把12条当作最终可出题数。[iKUN 原工作数据说明](https://arxiv.org/html/2312.16245v2)。

相同视频/规范化文本但目标帧标注不同的分组有 **{len(variants)}** 个，原条目和变体清单保留在 [language_same_text_target_variants.json](language_same_text_target_variants.json)；这类重复也意味着“单条文件只有一个ID”尚不保证措辞唯一。没有为了提高唯一性而改写描述或丢弃冲突标注。

三个目标 MOT 数据集对应的全部 **{refs:,} 个语言标注 `(frame, GT ID)` 引用均匹配原始 GT**，没有做 ID 偏移或强行重映射。TAO/VisDrone 未下载的视频不包含在这个核对分母中。全量语言统计见 [language_summary.json](language_summary.json)。

许可摘要：DanceTrack 标注 CC BY 4.0，视频数据限非商业研究；SportsMOT CC BY-NC 4.0，作者另列未经书面许可不得再分发数据的条件；MOT17 CC BY-NC-SA 3.0。LaMOT 新增语言标注无独立明确许可；iKUN 的 MIT 是代码许可，未找到单列的 Refer-Dance 新增语言标注许可。本轮只在本地只读复用，不对外发布。原文短摘与官方链接见 [licenses.md](../logs/licenses.md)。

本轮只登记临时来源约束：DanceTrack val 25、SportsMOT val 45、MOT17 train 7段各后半段，共 **77 个原视频**。MOT17 半段范围固定写为1-based `floor(N/2)+1..N`，共 {sum(w['frames'] for w in eligible['MOT17']['windows'])} 帧，详细范围见 [provisional_source_eligibility.json](provisional_source_eligibility.json)。这份清单是来源记录，**没有生成任何候选题，也不代表已排除跟踪器训练泄漏**。

需要用户在进入阶段二前确认：自己的跟踪器，以及相关检测/ReID模块，训练和调参使用了哪些数据集、split/视频？尤其 DanceTrack val、SportsMOT val 是否用过，MOT17 是否用过完整 train？如用过完整 MOT17 train，后半段也不能自动视作未见数据。原始划分和来源均保留，待用户说明后决定可用范围。

已知限制留给阶段二：外观描述的即时唯一性尚未评估；GT 标注身份定义不完全一致；机位标签是粗分档；无 GT test 的帧没有下载/逐序列检查。没有用模型补描述或擅自开始基础事件抽取。

资源与运行记录：主盘点脚本耗时 **{load('stage1_inventory_receipt.json')['elapsed_seconds']:.1f} 秒**（含本地完整压缩包哈希；官方文档获取、视觉查看和报告另计）；仅CPU，机位估计最多4个CPU工作线程，GPU使用0。未新建或混装环境，复用已有Python 3.11/OpenCV 5.0.0/NumPy 2.2.6进行CPU处理。一次 HF mirror 元数据请求因系统Python 3.10未处理HTTP308失败，已最小修复为标准直连重定向后成功；原失败保留在下载日志中。未启用代理、未删除文件，也没有启动单步预计超过6小时的操作。

所有阈值和统计口径保存在 [stage1_inventory_protocol.json](stage1_inventory_protocol.json)，SHA256见同名 `.sha256` 文件。原始自动机位结果保持原样，5段视觉复核在独立文件中留痕。阶段一完成后停止，等待确认再进入阶段二。
"""
    (R / "stage1_report.md").write_text(body)
    (ROOT / "README.md").write_text("# MOT-QA Pilot\n\nProject root: `/home/user/motqa_pilot` (user approved storage relocation).\n\nCurrent status: Stage 1 complete; stopped awaiting confirmation. No QA data, events, model inference, tracker runs or training generated.\n\n- [Stage 1 report](results/stage1_report.md)\n- [Sequence inventory](results/sequence_inventory.csv)\n- [Language mappings](results/language_descriptions.jsonl)\n- [Licenses](logs/licenses.md)\n- [Downloads](logs/downloads.md)\n- [Original request](task_request.txt)\n\nRaw datasets are referenced read only; all derived files remain in this project. Provisional sources and unresolved tracker training overlap are documented in the report.\n")
    with (ROOT / "research_log.md").open("a") as stream:
        stream.write(f"\n## Stage 1 result — {now}\n\n162 public-GT videos plus 7 MOT17 test videos inventoried; no frame-count or sampled-decode anomalies. All 373 GT/seqinfo files and 197 image-tree manifests match local release archives; DanceTrack complete archive checksums match publisher LFS. Complete LaMOT archive recovered from existing partial extraction: 7,556 annotation files verified against official Git blobs. All 4,472,553 relevant language frame/ID references match original GT.\n\nAppearance resource risk: Dance val has 425 query combinations but only 40 positive and 12 single-ID-over-whole-clip entries. MOT17 deliberately assigns new IDs after leaving/re-entry, so future natural-person reappearance/unique-person questions need scope restrictions; no GT changed. Camera labels: 28 static/141 moving, including 5 explicit agent visual resolutions; thresholds unchanged. Keep the inventory and stop before Stage 2.\n\nFailure and fix: an extra publisher-metadata request failed on HTTP308 under system Python3.10; added standard 308 redirect dispatch, retried direct, obtained official checksums. No proxy, dataset deletion, training or GPU work.\n")
    artifacts = {}
    for path in sorted(list((ROOT / "src").glob("*.py")) + [p for p in R.iterdir() if p.is_file() and p.name not in {"stage1_receipt.json", "stage1_snapshot.sha256"}] + [ROOT / "logs/licenses.md", ROOT / "logs/downloads.md"]):
        artifacts[str(path.relative_to(ROOT))] = dict(bytes=path.stat().st_size, sha256=checksum(path))
    receipt = dict(status="STAGE1_COMPLETE_STOPPED_AWAITING_CONFIRMATION", completed_at=now,
                   project_root=str(ROOT), unique_videos=169, public_gt_videos=162, provisional_source_videos=77,
                   missing_gt_test_image_sets=["DanceTrack/test", "SportsMOT/test"],
                   qa_generated=0, events_generated=False, model_inference=False, training=False, tracker_runs=False,
                   gpu_used=False, raw_data_modified=False, unresolved_questions=["tracker train/tune overlap", "confirm Stage 2 scope after GT conventions review"],
                   artifacts=artifacts)
    dump("stage1_receipt.json", receipt)
    (R / "stage1_snapshot.sha256").write_text("".join(f"{r['sha256']}  {name}\n" for name, r in artifacts.items()) + f"{checksum(R / 'stage1_receipt.json')}  results/stage1_receipt.json\n")
    print(json.dumps({k: v for k, v in receipt.items() if k != "artifacts"},ensure_ascii=False))
    print("report",R / "stage1_report.md", "artifacts",len(artifacts))


if __name__ == "__main__":
    main()
