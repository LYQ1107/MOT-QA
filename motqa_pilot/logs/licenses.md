# MOT-QA Pilot 许可盘点

核对日期：2026-11-04。下述内容记录发布者声明，区分原始视频、标注和代码；未将代码许可推广到数据。官方网页、README 和 LICENSE 快照保存在本项目 `sources/`，具体版本与 SHA256 见 `results/official_source_registry.json` 和 `logs/downloads.md`。

| 资源 | 发布者声明与简短摘录 | 对本项目的记录 |
|---|---|---|
| DanceTrack | 标注 CC BY 4.0；数据集 “available for non-commercial research purposes only”；代码 MIT。 | 保留作者引用、标注归属和视频的非商业研究限制；视频权利不归代码仓库所有。 |
| SportsMOT | CC BY-NC 4.0；另有 “not to distribute the SportsMOT dataset without prior written permission”。 | 同时记录非商业许可和单列的再分发条件；不把此项省略为 CC BY。 |
| MOT17 | MOTChallenge 官方站点声明 CC BY-NC-SA 3.0。 | 保留署名、非商业和相同方式共享条款；本轮只做本地盘点。 |
| LaMOT 语言标注 | 当前官方仓库没有单独 LICENSE，README 未给出语言标注的明确再分发许可。 | 许可状态记为未明确；不假定上游视频许可或其他仓库的 MIT 自动覆盖这些描述。 |
| Refer-Dance | iKUN 代码仓库 MIT；README 给出作者百度网盘发布链接，没有单列 Refer-Dance 语言标注许可。 | 原始 DanceTrack 视频沿用其条款；新增语言标注的再分发范围尚未明确。 |

来源：

- [DanceTrack 官方 Agreement](https://github.com/DanceTrack/DanceTrack#agreement)，固定代码版本 `44057dcc07e4bf6bcad2e6888c9d83ec63d4b1a3`；另见[项目主页 License](https://dancetrack.github.io/)。
- [SportsMOT 官方 Terms](https://github.com/MCG-NJU/SportsMOT#terms)，版本 `b06cfb4aacb0bb16c5778ac4ddb0d70ec6835444`。
- [MOTChallenge 官方站点](https://motchallenge.net/)：当前 HTTP 410 页面仍保留完整许可声明，已归档为 `sources/motchallenge_site.html`；[MOT17 静态数据页](https://motchallenge.net/data/MOT17/)正常返回。
- [LaMOT 官方仓库](https://github.com/Nathan-Li123/LaMOT)，版本 `5300242c06381c8d5ad36865dd88f4b62c2482bc`，完整文件树也已归档。
- [iKUN 官方仓库与发布链接](https://github.com/dyhBUPT/iKUN#data-preparation)，版本 `4db56bfaec703590e0fdfd1684d9769467a67e05`。

本轮没有对外发布或再分发任何数据。未来如拟公开试点集，应先明确 LaMOT、Refer-Dance 新增语言标注的许可，并逐项保留原始数据条款。
