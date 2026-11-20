# MOT-QA：身份关联视频问答研究

本仓库保存从 TOC-Bench 轨迹证据可行性实验，逐步转向 MOT-QA Pilot 的代码、冻结配置、阶段报告和研究记录。2026-11-20 从 A800 的 NAS 备份恢复到 A100，并整理为公开仓库。

**当前状态：TOC 阶段一至七已完成；MOT-QA 已形成 900 道 v3 候选，等待 12 题可辨认性补审。正式过滤、最终试点发布和 GT 轨迹模型对照实验尚未执行。**

## 阅读入口

- [完整研究历程 TXT：从最初目标、逐步验证到方法和下一步计划](docs/research_history_20261120.txt)（30 个章节，约 3.8 万字符）。
- [当前状态、关键结论与后续验收标准](docs/current_status.md)。
- [TOC 阶段七最终报告](toc_phase0/results/stage7_report.md)。
- [MOT-QA 最新可辨认性修订 v3 报告](motqa_pilot/results/stage3_readability_v3_report.md)。
- [900 道 v3 候选 JSONL](motqa_pilot/data/candidates_readability_v3.jsonl)。这仍是候选集。
- [数据与 checkpoint 的 NAS 位置、恢复边界](docs/nas_assets.md)。

阅读顺序建议为：本页 → 当前状态 → 研究历程 TXT → 对应阶段报告 → 源码与锁定文件。历史报告保留当时的结论；当前进度以本页及 v3 状态回执为准。

## 我们要回答什么

核心问题是：**有了能够保持跨帧身份的轨迹事实，大模型是否能在真正依赖身份关联的视频问答中获得可靠收益？**

TOC-Bench 实验先复现官方视频问答基线，再加入 MASA 轨迹、规则、事实表示、工具调用及合成 LoRA。多轮对照表明，某些设置相对弱基线的提升，尚不能归因于真实轨迹：占位、打乱和多数类基线同样重要。

因此后续转向 MOT-QA：基于 DanceTrack、SportsMOT 和 MOT17 的 GT 身份构造问答，明确时间、指代、可见性和答案规则，再用 GT 轨迹对照区分“证据质量不足”“模型不会使用”和“题目存在捷径”。

## 已有证据

TOC 官方基线为 623/2323（26.82%）。ReID 为 12/23，未复现论文的 22/23，原因尚未确定。

在同一测试可表达子集的 251 题上：

| 实验 | 条件 | 正确数 |
|---|---|---:|
| 阶段四 | A 无轨迹 / B 真实轨迹 / C 占位 / D 打乱 | 89 / 88 / 90 / 88 |
| 阶段七 | T-none 无工具 / T1 真实工具 / T-ph 占位 / T-sh 打乱 | 73 / 98 / 98 / 94 |
| 盲基线与路由 | 开发集多数类 / 路由 A | 126 / 112 |

阶段七 T1 相对 T-none 提升 9.96 个百分点，但没有显示优于占位或打乱。因此目前**没有建立真实轨迹带来可靠身份推理增益的证据**。阶段四与阶段七采用不同协议，不能把跨阶段数值直接当成同一次消融。

MOT-QA 当前 900 题来自 77 个视频：DanceTrack 360、SportsMOT 405、MOT17 135。v3 根据人审反馈修订了短间断、移动镜头、多人符合描述和指代难辨认等问题，保留 647 题原素材事实、替换 253 题。GT 重算与配额检查通过，人工可辨认性仍需补审。

## 目录

```text
toc_phase0/       TOC 阶段一至七代码、冻结配置、报告、上游代码快照
motqa_pilot/      GT 资源盘点、候选生成/审计、审阅页面、900 题及历史记录
docs/            当前进展、完整研究历程 TXT、NAS 资产说明、源码哈希清单
recovery/        A100 恢复脚本及核验回执
tools/           从 A100 原恢复目录生成本仓库快照的工具
```

两个原始工作目录分别为 `/data3/liuyeqiang/toc_phase0` 和 `/data3/liuyeqiang/motqa_pilot`。本仓库是独立 Git 工作副本，初次发布中的原项目文件保持原始字节，哈希见 [source_manifest.json](docs/source_manifest.json)。

## 下一步

1. 完成当前 12 题可辨认性补审，再进行正式过滤、平衡和试点定稿。
2. 在固定且相同的 32 帧、时间戳、参考帧及裁剪图上，比较 Qwen2.5-VL-7B 的 A、G、G-ph、G-sh，并运行同一操作定义的脚本 S 及盲基线。
3. 按已锁定标准先要求 S=100%；G−A 至少 15 个百分点、G−G-sh 至少 10 个百分点，才支持扩大规模。使用 exact McNemar 和按视频整群 bootstrap，不能提前把候选当作最终基准。
4. 确认 GT 身份信息有效后，再安排公开跟踪器以及离线和主动工具调用的公平比较。

具体标准见 [stage5_criteria_locked.json](motqa_pilot/results/stage5_criteria_locked.json) 和研究历程 TXT。以上是计划，并非已完成结果。

## 运行与资产边界

公开仓库包含代码、配置、候选及文本研究记录。原始视频/帧、完整轨迹、模型和 checkpoint、大型中间文件、媒体审阅包继续保留在 NAS；Git 不跟踪本机的 NAS 软链接。完整原对话导出仅在本机恢复目录保留，本仓库提供整理后的研究历程。

```bash
git clone https://github.com/LYQ1107/MOT-QA.git
```

克隆后可以直接阅读报告和源码；运行原实验仍需要 NAS 资产和相应 Python/GPU 环境。原代码中的 A800 绝对路径与冻结协议保留，A100 兼容入口见 [recovery/README.md](recovery/README.md)。此次恢复和发布没有运行新的模型推理、跟踪或训练。

上游代码和资料的来源与许可记录见项目内保留的许可证文件、`toc_phase0/logs/pinned_sources.json`、`toc_phase0/logs/masa_dependency_sources.json` 和 [MOT-QA 许可记录](motqa_pilot/logs/licenses.md)。
