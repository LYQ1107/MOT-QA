# NAS 资产与公开仓库边界

## A100 上的位置

| 内容 | 路径 |
|---|---|
| 本仓库 Git 工作副本 | `/data3/liuyeqiang/MOT-QA` |
| 原恢复 TOC 工作目录 | `/data3/liuyeqiang/toc_phase0` |
| 原恢复 MOT-QA 工作目录 | `/data3/liuyeqiang/motqa_pilot` |
| 原恢复回执、原对话与兼容工具 | `/data3/liuyeqiang/TOC_Bench_recovery_20261120` |
| A800 NAS 备份挂载 | `/data3/liuyeqiang/nas/A800` |
| MOT-QA 归档只读访问 | `/data3/liuyeqiang/TOC_Bench_recovery_20261120/motqa_nas_archive/home/user/motqa_pilot` |

原恢复目录继续用于已有 NAS 访问与路径兼容。本仓库是供 GitHub 发布和后续版本管理的独立副本，修改本仓库不会自动同步回原恢复目录。

## 保留在 NAS 的资产

- TOC 官方视频、帧缓存、完整跟踪输出和历史逐题实验目录。
- Qwen2.5-VL-7B、MASA 和阶段六合成 LoRA 权重及 checkpoint。
- MOT 数据集原始帧、GT 大资产、派生二进制/帧缓存和大型候选中间池。
- MOT-QA 图片、视频、离线审阅 ZIP，以及浏览器测试和运行时文件。
- LaMOT 上游完整标注副本；仓库保留来源说明和元数据。

公开仓库保留了本机已有且适于版本管理的候选 JSONL、文本结果、配置、报告和代码。它不是全部 NAS 数据的镜像。仓库中没有提交 NAS 软链接，也未将权重加入 Git LFS。

TOC 原始镜像入口为 `/data3/liuyeqiang/nas/A800/data2/user/toc_phase0`。

MOT-QA 原归档为：

```text
/data3/liuyeqiang/nas/A800/motqa_pilot_migration_20261113/motqa_pilot_code_results.tar
```

该归档为 4,563,937,280 字节、28,112 个文件。恢复时在 NAS 主机重新计算 SHA256，与原迁移回执一致：

```text
2871eb1f6bfdd0c750271538b10644da7d17e52b728aa4e3fd2a585c9cacd18c
```

归档包含媒体，因此 GitHub 上的部分历史 HTML 审阅页需要在 A100 恢复目录及 NAS 资产可用时打开，不能仅凭公开代码副本完整播放。

## 核验范围

恢复核验见 [verification_report.json](../recovery/verification_report.json)、[archive_verification.json](../recovery/archive_verification.json) 和 [原始数据访问检查](../recovery/motqa_raw_dataset_check.json)。

恢复时已检查冻结配置和 8 个冻结源文件哈希，使用原官方评分器复算关键历史结果；TOC 的 1,951 个视频大小/数量匹配并抽取一个当前 SHA256 样本；模型分片索引与头部匹配，但未对所有权重重新做完整哈希。MOT-QA 选中文件与原备份逐文件 SHA256 匹配，整个归档 SHA256 当前复核通过。176 条 GT 路径及对应样例帧检查通过；未重新解码或哈希全部原始帧。

初次 GitHub 发布文件的来源与 SHA256 见 [source_manifest.json](source_manifest.json)。完整原对话导出留在本机，本仓库提供 [研究历程 TXT](research_history_20261120.txt)。
