#!/bin/sh
# Preserve legacy paths inside this process without editing locked experiment files.
set -eu
recovery_dir=/data3/liuyeqiang/TOC_Bench_recovery_20261120
"$recovery_dir/mount_assets.sh"
export PYTHONPYCACHEPREFIX="$recovery_dir/pycache"
export HF_HOME="$recovery_dir/cache/huggingface"
python_executable="${TOC_A100_PYTHON:-/data3/liuyeqiang/.venvs/trackocd-a100/bin/python}"
exec "$recovery_dir/proot_runtime/usr/bin/proot" \
    -b /data3/liuyeqiang/nas/A800/data2/user:/data2/user \
    -b /data3/liuyeqiang/nas/A800/data1/user:/data1/user \
    -b /data3/liuyeqiang/nas/A800/data3/user:/data3/user \
    -b /data3/liuyeqiang/nas/A800:/data2/user/nas/A800 \
    -b /data3/liuyeqiang/toc_phase0:/data2/user/toc_phase0 \
    -b /data3/liuyeqiang/motqa_pilot:/home/user/motqa_pilot \
    "$python_executable" "$@"
