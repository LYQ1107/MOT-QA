#!/usr/bin/env bash
set -euo pipefail
cd /data2/user/toc_phase0
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
export CUDA_VISIBLE_DEVICES='' PYTHONNOUSERSITE=1
export PIP_CACHE_DIR=/data2/user/toc_phase0/cache/pip_masa
export PIP_DISABLE_PIP_VERSION_CHECK=1
export TMPDIR=/data2/user/toc_phase0/cache/masa_pip_tmp
mkdir -p "$TMPDIR"
env_masa/bin/python -m pip install --only-binary=:all: --progress-bar off \
  --timeout 40 --retries 1 --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
  --report logs/masa_torch_install_report.json \
  cache/masa_wheels/torch-2.1.2+cu118-cp311-cp311-linux_x86_64.whl \
  cache/masa_wheels/torchvision-0.16.2+cu118-cp311-cp311-linux_x86_64.whl \
  cache/masa_wheels/torchaudio-2.1.2+cu118-cp311-cp311-linux_x86_64.whl \
  numpy==1.26.4 sympy==1.12 > logs/masa_torch_install_resumed.log 2>&1
printf 'MASA torch 2.1.2 CUDA 11.8 installed\n'
env_masa/bin/python -m pip install --progress-bar off --timeout 40 --retries 1 --no-build-isolation \
  --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
  --report logs/masa_core_install_report.json \
  --requirement requirements_masa_core.txt > logs/masa_core_install.log 2>&1
printf 'MASA core dependencies installed\n'
