"""Stage-one CPU-only checks; do not launch inference or allocate a GPU."""
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform

ROOT = Path(__file__).resolve().parents[1]


def main():
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    modules = ['torch', 'torchvision', 'vllm', 'transformers', 'av', 'supervision',
               'modelscope', 'huggingface_hub', 'pandas', 'numpy', 'accelerate']
    versions = {'python': platform.python_version()}
    for name in modules:
        importlib.import_module(name)
        versions[name] = importlib.metadata.version(name)
        print(f'{name}=={versions[name]}', flush=True)
    import torch
    importlib.import_module('vllm._C')
    import supervision as sv
    from transformers import AutoConfig, AutoProcessor, AutoModelForZeroShotObjectDetection
    from transformers import Qwen2_5_VLForConditionalGeneration
    from vllm.model_executor.models import ModelRegistry
    from safetensors import safe_open

    assert hasattr(sv, 'ByteTrack')
    sv.ByteTrack(frame_rate=5)
    supported = sorted(ModelRegistry.get_supported_archs())
    assert 'Qwen2_5_VLForConditionalGeneration' in supported
    qwen_dir = ROOT / 'models/Qwen2.5-VL-7B-Instruct'
    dino_dir = ROOT / 'models/grounding-dino-base'
    qwen_config = AutoConfig.from_pretrained(qwen_dir, local_files_only=True)
    qwen_processor = AutoProcessor.from_pretrained(qwen_dir, local_files_only=True)
    index = json.loads((qwen_dir / 'model.safetensors.index.json').read_text())
    expected_by_shard = {}
    for key, shard in index['weight_map'].items():
        expected_by_shard.setdefault(shard, set()).add(key)
    for shard, expected in expected_by_shard.items():
        with safe_open(qwen_dir / shard, framework='pt', device='cpu') as weights:
            assert set(weights.keys()) == expected, shard
    dino_processor = AutoProcessor.from_pretrained(dino_dir, local_files_only=True)
    dino = AutoModelForZeroShotObjectDetection.from_pretrained(
        dino_dir, local_files_only=True, use_safetensors=True,
    )
    receipt = dict(status='STAGE_ONE_CPU_ENVIRONMENT_CHECKS_PASSED', versions=versions,
                   torch_cuda_build=torch.version.cuda, cuda_visible_devices=os.environ['CUDA_VISIBLE_DEVICES'],
                   cuda_device_count=torch.cuda.device_count(), vllm_qwen_architecture_supported=True,
                   vllm_cuda_extension_imported=True,
                   qwen_model_class=Qwen2_5_VLForConditionalGeneration.__name__,
                   qwen_config_type=type(qwen_config).__name__, qwen_processor_type=type(qwen_processor).__name__,
                   qwen_shards=len(expected_by_shard), qwen_tensor_keys=len(index['weight_map']),
                   dino_model_type=type(dino).__name__, dino_processor_type=type(dino_processor).__name__,
                   dino_parameters=sum(parameter.numel() for parameter in dino.parameters()),
                   bytetrack_frame_rate=5, gpu_inference_run=False)
    (ROOT / 'logs/environment_validation.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2), flush=True)


if __name__ == '__main__':
    main()
