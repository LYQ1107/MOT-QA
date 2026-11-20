# A100 恢复入口

此目录保存 2026-11-20 的恢复脚本和核验回执。它们记录已有 A100 布局，不是可以在任意新机器上一键运行的安装器。

原恢复目录为 `/data3/liuyeqiang/TOC_Bench_recovery_20261120`。原 TOC 和 MOT-QA 目录分别为 `/data3/liuyeqiang/toc_phase0`、`/data3/liuyeqiang/motqa_pilot`。

在已有 A100 环境中：

```bash
# 重新建立 MOT-QA 归档只读挂载（依赖已有 ratarmount 环境和归档索引）
/data3/liuyeqiang/TOC_Bench_recovery_20261120/mount_assets.sh

# 在进程内映射旧绝对路径（依赖已有 proot 和 CPU Python 环境）
/data3/liuyeqiang/TOC_Bench_recovery_20261120/python_a100.sh /path/to/script.py
```

本仓库未附带 NAS 凭据、SSH 私钥、Python 环境、proot 二进制、归档 SQLite 索引或权重。`python_a100.sh` 当前默认使用 CPU 分析解释器，可通过 `TOC_A100_PYTHON` 指定其他已有解释器。

恢复工具保留了原科学文件的内容与绝对路径。vLLM、MASA 和训练环境仍需重建并验证 A100 40 GB 显存容量。不要将 CPU 恢复核验通过理解为新的 GPU 实验已经运行。

详见 [NAS 资产说明](../docs/nas_assets.md) 和 [当前研究状态](../docs/current_status.md)。
