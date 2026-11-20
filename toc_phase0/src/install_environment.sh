#!/usr/bin/env bash
set -euo pipefail
cd /data2/user/toc_phase0
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
export CUDA_VISIBLE_DEVICES=''
export PIP_CACHE_DIR=/data2/user/toc_phase0/cache/pip
export PIP_DISABLE_PIP_VERSION_CHECK=1
export PYTHONNOUSERSITE=1
indexes=(
  https://pypi.tuna.tsinghua.edu.cn/simple
  https://mirrors.aliyun.com/pypi/simple
  https://pypi.org/simple
)
for index in "${indexes[@]}"; do
  label=${index#https://}
  label=${label%%/*}
  printf 'Installing from %s directly, without proxy\n' "$index"
  if env/bin/python -m pip install --only-binary=:all: --retries 1 --timeout 25 \
      --progress-bar off --index-url "$index" --report logs/pip_install_report.json \
      --requirement requirements.txt > "logs/pip_install_${label}.log" 2>&1; then
    printf '%s\n' "$index" > logs/pip_index_used.txt
    env/bin/python -m pip check > logs/pip_check.txt
    env/bin/python -m pip freeze > requirements.lock.txt
    printf 'Package installation and dependency check complete\n'
    exit 0
  fi
  printf 'Index attempt failed: %s; see logs/pip_install_%s.log\n' "$index" "$label"
done
printf 'All direct package sources failed. No proxy was used.\n'
exit 1
