# MOT-QA Pilot：公开跟踪器候选的官方资料核查

核查时间：2026-11-04T23:32:35.692464+08:00。本轮仅下载官方说明、代码配置与文件列表元数据；**没有下载任何跟踪权重、没有运行跟踪器**。
所有直连请求记录在`logs/downloads.md`与`logs/network_transfers.jsonl`，归档在`sources/trackers/`。
GitHub连接器读取文件元数据失败后，改用官方网页及不走代理的官方raw/API直连，没有改用第三方转存。

## 两个可选后端

| 后端 | 可确认的组件与适用范围 | 官方地址 | 许可 |
|---|---|---|---|
| OC-SORT | 纯运动关联，无独立ReID/关联网络权重；DanceTrack可用作者明确确认的train-only检测器；Sports可接下表train检测器，属于拟采用组合，未运行验证 | [官方仓库](https://github.com/noahcao/OC_SORT)、[训练/使用说明](https://github.com/noahcao/OC_SORT/blob/8462e7e729a93ccd3bd995c0a79a890336cb3a0b/docs/GET_STARTED.md) | [仓库MIT](https://github.com/noahcao/OC_SORT/blob/8462e7e729a93ccd3bd995c0a79a890336cb3a0b/LICENSE)；底层YOLOX另有Apache-2.0说明 |
| ByteTrack | 置信度分层框关联，无独立ReID网络；DanceTrack及Sports用下表各自train-only检测器 | [官方仓库](https://github.com/FoundationVision/ByteTrack)、[模型说明](https://github.com/FoundationVision/ByteTrack/blob/d1bf0191adff59bc8fcfeaa0b33d3d1642552a99/README.md) | [仓库MIT](https://github.com/FoundationVision/ByteTrack/blob/d1bf0191adff59bc8fcfeaa0b33d3d1642552a99/LICENSE)；不同外部权重许可单列 |

这是两个跟踪算法后端，不把同一算法在不同数据集上的配置算成不同算法。以下“可用”表示官方文档能确认训练来源符合对应目标split限制，不表示已下载、实物复核或证明从未使用验证集选超参数。

## 逐权重核查

| 权重/组合 | 官方确认的训练来源 | 适用性与状态 |
|---|---|---|
| DanceTrack原发布 `bytetrack_models/bytetrack_model.pth.tar` | COCO预训练，再DanceTrack train；[官方训练说明](https://github.com/DanceTrack/DanceTrack/blob/44057dcc07e4bf6bcad2e6888c9d83ec63d4b1a3/ByteTrack/README.md)、[配置](https://github.com/DanceTrack/DanceTrack/blob/44057dcc07e4bf6bcad2e6888c9d83ec63d4b1a3/ByteTrack/exps/example/dancetrack/yolox_x.py)及[转换脚本](https://github.com/DanceTrack/DanceTrack/blob/44057dcc07e4bf6bcad2e6888c9d83ec63d4b1a3/tools/convert_dance_to_coco.py)只读train | **DanceTrack val文档级可用**；[官方HF模型地址](https://huggingface.co/noahcao/dancetrack_models/tree/6487fc12a2fe13db44506592324cea83270f5812/bytetrack_models)。模型卡CC BY4.0；视频仍按DanceTrack非商业研究条件 |
| OC-SORT提供的DanceTrack检测器 `ocsort_dance_model.pth.tar`（历史命令亦名`bytetrack_dance_model.pth.tar`） | [维护者明确回复](https://github.com/noahcao/OC_SORT/issues/60#issuecomment-1319553251)确认只用DanceTrack train、未用val训练；[官方模型表](https://github.com/noahcao/OC_SORT/blob/8462e7e729a93ccd3bd995c0a79a890336cb3a0b/docs/MODEL_ZOO.md)列val/test；不能仅凭test字样推断用了train+val | **DanceTrack val文档级可用**；使用[官方模型表的Drive文件夹](https://drive.google.com/drive/folders/1LnhZVJlpufUnWuObZASIN1KwfhuvT_a8)。重命名文件未下载，不能声称其SHA与上行相同；外部重命名权重未另见独立许可声明 |
| MixSort官方检测器 `yolox_x_sports_train.pth.tar`，用于ByteTrack或OC-SORT关联 | COCO→CrowdHuman train+val→SportsMOT train；[官方README](https://github.com/MCG-NJU/MixSort/blob/a078f5bf6ae9fbeecbc1384479d5f02ab8b9e7f6/README.md)区分train和mix流程，[检测器配置](https://github.com/MCG-NJU/MixSort/blob/a078f5bf6ae9fbeecbc1384479d5f02ab8b9e7f6/exps/example/mot/yolox_x_sportsmot.py)为train.json/name=train，转换脚本按split分别输出 | **SportsMOT val文档级可用**；[官方文件](https://drive.google.com/file/d/1wLJOZHwUbSBmjOfWw8n3fAPo3fvLyzUd/view)在README链接的官方Drive文件夹中列出。采用该检测器不加载MixFormer或其他ReID权重；[仓库MIT](https://github.com/MCG-NJU/MixSort/blob/a078f5bf6ae9fbeecbc1384479d5f02ab8b9e7f6/LICENSE)，外部checkpoint未单列权重许可 |
| `yolox_x_sports_mix.pth.tar` | 官方流程明确混合SportsMOT train+val | **SportsMOT val不可用**；[官方模型文件](https://drive.google.com/file/d/1lMUAp6pm7vx2KAfmr7grMgF6t5hRCz7l/view)，本轮仅查看目录元数据 |
| 原ByteTrack `bytetrack_ablation.pth.tar` | README为CrowdHuman + MOT17 half train；实际[转换脚本](https://github.com/FoundationVision/ByteTrack/blob/d1bf0191adff59bc8fcfeaa0b33d3d1642552a99/tools/convert_mot17_to_coco.py)对0-based索引使用闭区间`0..N//2`，混合脚本读取train_half.json | **当前严格来源边界下不可用**：多包含本项目后半段首帧，见下表；不是“没有官方训练信息”，是有代码级边界冲突 |
| ByteTrack MOT17 test模型（如`bytetrack_x_mot17`） | 官方README明确含全部MOT17 train，另有CrowdHuman、Cityperson、ETHZ | **MOT17后半段不可用** |
| OpenMMLab ByteTrack half-train公开模型 | 官方模型表为CrowdHuman + MOT17-half-train；[其转换脚本](https://github.com/open-mmlab/mmdetection/blob/main/tools/dataset_converters/mot2coco.py#L152)同样以`N//2+1`切片 | **当前严格来源边界下不可用**，同一帧边界问题，不因换实现而自动通过 |
| MixSort `yolox_x_ch.pth.tar` | [官方训练配置](https://github.com/MCG-NJU/MixSort/blob/a078f5bf6ae9fbeecbc1384479d5f02ab8b9e7f6/exps/example/mot/yolox_x_ch.py)只读CrowdHuman mix.json；[混合脚本](https://github.com/MCG-NJU/MixSort/blob/a078f5bf6ae9fbeecbc1384479d5f02ab8b9e7f6/tools/mix_crowdhuman.py)为CrowdHuman train+val，README从COCO预训练后生成此checkpoint；官方Drive列出同名文件 | **不含任何MOT17训练帧的保守备选**；[官方文件](https://drive.google.com/file/d/1inCT7HeSJ08f27EfowABvjao0xYKtXz4/view)，可接上述两种无训练关联器。但它没有MOT17前半段适配，不能冒充用户举例的“前半段消融权重”；若要求必须经过前半段适配，本轮尚无可确认完全符合当前边界的权重 |

Dance原发布checkpoint的发布者元数据：大小792835731 bytes，发布SHA256 `b8d1afba08f801f3fe2cb122faf3fc9af6c7856405a0da94cf91cdd5eb9b3321`。
这里只读取官方LFS元数据，没有下载文件或宣称完成本地权重校验。Sports train/mix与CrowdHuman文件也只读官方目录元数据。

## MOT17边界冲突的直接计算

本项目锁定允许窗口为1-based `floor(N/2)+1..N`。ByteTrack官方转换器的train half为0-based `0..N//2`（包含末端），
即1-based `1..floor(N/2)+1`；因此每个序列有一帧交集。这是从官方代码及本项目窗口推得，不代表读取到了真实训练运行日志或权重内部数据。
在用户决定前不改本项目来源、GT、时间戳或窗口，不把“half train”文字说明直接当作无交集证明。

| MOT17序列 | 总帧数N | 项目后半段首帧 = 官方训练脚本包含的边界帧 |
|---|---:|---:|
| MOT17-02-FRCNN | 600 | 301 |
| MOT17-04-FRCNN | 1050 | 526 |
| MOT17-05-FRCNN | 837 | 419 |
| MOT17-09-FRCNN | 525 | 263 |
| MOT17-10-FRCNN | 654 | 328 |
| MOT17-11-FRCNN | 900 | 451 |
| MOT17-13-FRCNN | 750 | 376 |

## 未获确认的组件与使用边界

- 完整MixSort的MixFormer、Deep-OC-SORT/BoT-SORT/StrongSORT等ReID权重，不能仅凭检测器train-only就认定整个管线可用。本轮没有取得每个此类公开权重的完整训练split依据，**未确认的权重一律不可用**，不作猜测。
- 未将公开val结果、test榜单名或第三方fork描述作为无训练重叠证明。官方论文/模型表的分数仅作资料，不当作本试点结果；上述后端均未安装或运行。
- 官方文档中的val评估、早停/选checkpoint及调参记录未必完整。这里确认的是公开训练来源；尚不能证明验证集完全没有用于超参数或checkpoint选择，不宣称试点测试对调参也完全未见。
- 两个可选后端都可在DanceTrack/SportsMOT采用已核实检测器。MOT17若坚持前半段适配，待解决边界问题；外部CrowdHuman-only是另列的保守备选，本轮不替用户选定或运行。

官方材料固定revision及本地档案见`results/review/tracker_official_sources.json`；额外README/API评论、HF/Drive元数据均保留原文件与下载记录。没有运行新实验，也没有为凑候选数把未知训练来源的权重写成可用。
