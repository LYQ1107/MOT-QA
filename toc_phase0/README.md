# TOC-Bench 轨迹证据可行性实验

独立项目目录：`/data2/user/toc_phase0`。2026-10-31 用户指定在 `/data2/user` 下新建，来源任务保存在 `task_request.txt`。

阶段七已完成并停止。冻结v1、切分、可表达清单及5示范不变。接口增加完整JSON到EOS的恢复后，测试可表达T1为98/251，T-none73/251，开发多数类盲基线126/251，路由112/251；H12=supported，p=0.0114563。同子集占位98/251、打乱94/251，真实轨迹无可检出的特异优势。轨迹事后诊断中R/D边缘与标签Fisher p=.2589、规则与盲基线均51/75；Count18/81低于盲基线32/81；X-Order仅覆盖9题，7/9对5/9的配对p=.5，尚无可靠超出类别先验的证据。全部交互和人工事实核查已保存，本任务GPU进程已退出。完整报告：[stage7_report.md](/data2/user/toc_phase0/results/stage7_report.md)。阶段六历史报告：[stage6_report.md](/data2/user/toc_phase0/results/stage6_report.md)。

## 阶段一简短计划

1. 阅读固定版本的官方数据说明和评测代码，下载标注、README 与文件清单；保留原始 QA。
2. 新建独立 Python 3.11 conda 环境，安装支持 Qwen2.5-VL 的 vLLM、transformers、PyAV、supervision、ModelScope、HF Hub、pandas，验证导入并记录版本。
3. 按 ModelScope 优先、HF 镜像次选获取 Qwen2.5-VL-7B-Instruct；保留 transformers 格式 Grounding DINO base 作备选。按用户补充，主跟踪器为 MASA-GroundingDINO unified：另建独立 `env_masa`，按官方 README 安装并下载 `gdino_masa.pth`，只通过磁盘轨迹 JSON 与 vLLM 交互。下载均直连，来源、字节数与完整性校验写入 `logs/downloads.md`。
4. 汇总数据字段、3 条原始 QA、维度/题型分布、视频清单总大小、轨迹公开状态及官方提示词/评分协议，保存阶段一报告。

固定随机种子 42。阶段一设置 `CUDA_VISIBLE_DEVICES=''`，不占用 GPU。后续按已授权的共享策略登记最多两张 A800，优先进程少且显存足够的卡；不干预现有进程。长任务由一个阻塞 shell 等待完成，输出保存日志。任何资源确实无法直连获取、需要删除文件或预计单步超过 6 小时，按任务约定停止并汇报。

## 当前状态（2026-11-02）

视频切分已只读锁定：开发138视频/147题，测试551视频/602题；固定可表达子集324题保持不变。v1参数为memo50、5fps、0.2、FP16、unified；过滤观测时长<0.6秒且均置信度<0.3的轨迹，再按置信度×观测时长保留top5；事件规则保留间断>0.5秒。配置及哈希见 [frozen_config_v1.json](/data2/user/toc_phase0/results/frozen_config_v1.json) 和 [锁定回执](/data2/user/toc_phase0/logs/frozen_config_v1_lock.json)。测试主要四维可表达76/231（32.90%），低于原规则80/231（34.63%）；测试全部可表达79/251（31.47%）。全集可表达109/324（33.64%），全集包含参与调参的开发集。本轮主要产出是输入压缩：每题合并轨迹文本P95=2068.6、最大3784 token；完整输入含D上界及生成预留最大25848，阶段四四条件共同使用max_model_len=65536，实测32768也可容纳。B2面积比变体为待办。

阶段一历史报告为 `results/stage1_report.md`。阶段二锁定协议见 `results/stage2_protocol.json`，完成回执为 `results/stage2_receipt.json`。1,951个视频全部通过发布大小/SHA256校验；官方采样得到1,949×32帧和2×30帧，无解码失败或非预期漏帧。2,323题均有唯一预测，解析失败291题计错。两个vLLM实例使用启动前空闲的物理GPU0/5，完成后均已退出并释放显存；阶段二未运行MASA。

ReID本次12/23（52.17%），未复现论文95.7%；其余9个维度与论文的差异均在1.63个百分点内。已核对全部23题的提示词/解析，并对3个错误视频重新采样确认JPEG字节一致，未发现协议偏差；差异来源未确定，逐题诊断见 `results/stage2_reid_diagnostic.json`。四个重点维度仍按用户决定为Count、R/D、X-Order、Order，共726题，本次154/726（21.21%）。

直接运行使用独立的 env/bin/python（vLLM/CPU长度核算）与 env_masa/bin/python（MASA），通过磁盘轨迹交互。阶段四应读取 [v1_track_index.json](/data2/user/toc_phase0/results/v1_track_index.json)，证据位于 tracks/v1/by_query；未过滤每查询JSON位于 tracks/v1/unfiltered_by_query，全部原始逐帧输出位于 tracks/v1/raw。tracks/raw、tracks/by_query 和 results/stage3_report.md 保留初版历史，不作为新主实验的证据源。MASA重建须从官方原始配置开始，再覆盖本地BERT、fps5及冻结参数；results/masa_stage3_fresh_config.py 是初版memo10快照，不能代替v1。每视频须清空检测器全部文本缓存并重置跟踪状态。GPU共享显存充足、优先进程少的卡已获用户授权；冻结重跟踪使用GPU2/4，阶段四推理使用GPU4/6，均已退出本任务GPU进程。下载来源、版本和校验见 logs/downloads.md、requirements_masa.lock.txt 与阶段一报告。

阶段四可复核入口：`src/prepare_stage4.py`生成且锁定假设、D、图像和提示词（已经锁定，不要重跑覆盖）；`src/run_stage4_inference.py`读取锁定输入并支持已提交单元恢复；`src/analyze_stage4.py`离线评分；`src/finalize_stage4_report.py`离线协议核对与报告复核。当前实验已完成，无需再启动推理。


阶段五交付：results/stage5_report.md、stage5_metrics_final.json、stage5_hypothesis_tests.json、stage5_final_integrity.json、stage5_reasoning_RD_examples.md、stage5_reasoning_manual_review.json。原版计数约束结果保留于stage5_metrics.json；最终计数诊断采用事后独立锁定的guided_v2_commit协议，raw主结果和H6–H8不变。
