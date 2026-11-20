#!/usr/bin/env bash
set -euo pipefail
cd /data2/user/toc_phase0
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
export CUDA_VISIBLE_DEVICES='' PYTHONNOUSERSITE=1
export MODELSCOPE_CACHE=/data2/user/toc_phase0/cache/modelscope
export HF_HOME=/data2/user/toc_phase0/cache/huggingface
export HF_HUB_DISABLE_XET=1 HF_HUB_DOWNLOAD_TIMEOUT=60 HF_HUB_ETAG_TIMEOUT=30
export HF_ENDPOINT=https://hf-mirror.com

if env/bin/modelscope download --model Qwen/Qwen2.5-VL-7B-Instruct \
    --local_dir models/Qwen2.5-VL-7B-Instruct > logs/download_qwen_modelscope.log 2>&1; then
  printf 'modelscope\n' > logs/qwen_source_used.txt
  printf 'Qwen ModelScope download completed\n'
else
  printf 'ModelScope direct download failed; trying HF endpoints without proxy\n'
  qwen_revision=$(env/bin/python -c "import json; print(json.load(open('logs/qwen_hf_info.json'))['sha'])")
  qwen_complete=false
  for endpoint in https://hf-mirror.com https://huggingface.co; do
    export HF_ENDPOINT="$endpoint"
    label=${endpoint#https://}
    if env/bin/huggingface-cli download Qwen/Qwen2.5-VL-7B-Instruct \
        --revision "$qwen_revision" --local-dir models/Qwen2.5-VL-7B-Instruct \
        > "logs/download_qwen_${label}.log" 2>&1; then
      printf '%s\n' "$endpoint" > logs/qwen_source_used.txt
      qwen_complete=true
      break
    fi
  done
  if [ "$qwen_complete" != true ]; then
    printf 'Qwen unavailable from all direct sources. Stop; proxy not used.\n'
    exit 1
  fi
fi

dino_revision=$(env/bin/python -c "import json; print(json.load(open('logs/dino_hf_info.json'))['sha'])")
for endpoint in https://hf-mirror.com https://huggingface.co; do
  export HF_ENDPOINT="$endpoint"
  label=${endpoint#https://}
  if env/bin/huggingface-cli download IDEA-Research/grounding-dino-base \
      --revision "$dino_revision" --local-dir models/grounding-dino-base \
      --include '*.json' '*.safetensors' '*.txt' README.md \
      > "logs/download_dino_${label}.log" 2>&1; then
    printf '%s\n' "$endpoint" > logs/dino_source_used.txt
    printf 'Grounding DINO download completed\n'
    exit 0
  fi
  printf 'Grounding DINO direct endpoint failed: %s\n' "$endpoint"
done
printf 'Grounding DINO unavailable from all direct sources. Stop; proxy not used.\n'
exit 1
