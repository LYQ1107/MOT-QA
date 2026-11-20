"""Validate MASA's separate environment and unified checkpoint on CPU."""
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import random
import sys
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'upstream/masa'
sys.path.insert(0, str(SOURCE))
assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
dependency_check = subprocess.run([sys.executable, '-m', 'pip', 'check'], text=True, capture_output=True)
(ROOT / 'logs/masa_pip_check.txt').write_text(dependency_check.stdout + dependency_check.stderr)
assert dependency_check.returncode == 0, dependency_check.stdout + dependency_check.stderr

import torch
import numpy as np
random.seed(42)
np.random.seed(42)
torch.manual_seed(42)
import mmcv
import mmengine
import mmdet
from mmcv.ops import nms
from mmdet.apis import init_detector
import masa
from masa.apis import init_masa
from mmengine.config import Config

names = ['torch', 'torchvision', 'torchaudio', 'mmcv', 'mmengine', 'mmdet',
         'transformers', 'huggingface_hub', 'numpy', 'opencv-python', 'supervision',
         'nltk', 'h5py', 'einops', 'seaborn', 'fairscale', 'scalabel', 'lvis', 'openmim']
versions = {'python': platform.python_version(), 'masa_source': '0.1.0'}
for name in names:
    versions[name] = importlib.metadata.version(name)
    print(f'{name}=={versions[name]}', flush=True)
assert torch.__version__ == '2.1.2+cu118'
assert torch.version.cuda == '11.8'
assert mmcv.__version__ == '2.1.0' and mmdet.__version__ == '3.3.0'
boxes = torch.tensor([[0., 0., 5., 5.], [10., 10., 15., 15.]])
_, keep = nms(boxes, torch.tensor([0.9, 0.8]), 0.5)
assert keep.tolist() == [0, 1]

config = Config.fromfile(SOURCE / 'configs/masa-gdino/masa_gdino_swinb_inference.py')
config.model.detector.language_model.name = str(ROOT / 'models/MASA/bert-base-uncased')
config.model.tracker.fps = 5
checkpoint_path = ROOT / 'models/MASA/gdino_masa.pth'
model = init_masa(config, str(checkpoint_path), device='cpu')
checkpoint = torch.load(checkpoint_path, map_location='cpu')
state = checkpoint.get('state_dict', checkpoint)
actual = {key.removeprefix('module.'): value for key, value in state.items()}
expected = model.state_dict()
missing = sorted(set(expected) - set(actual))
unexpected = sorted(set(actual) - set(expected))
shape_mismatches = [key for key in set(actual) & set(expected)
                    if actual[key].shape != expected[key].shape]
assert not missing, ('Missing unified checkpoint keys', missing)
assert not unexpected, ('Unexpected unified checkpoint keys', unexpected)
assert not shape_mismatches, shape_mismatches
with torch.no_grad():
    language_output = model.detector.language_model(['apple . person .'])
assert language_output['embedded'].shape[0] == 1

weight = json.loads((ROOT / 'logs/masa_weight_download_receipt.json').read_text())
receipt = dict(status='MASA_SETUP_COMPLETE', environment=str(ROOT / 'env_masa'), versions=versions,
               seed=42,
               official_code_commit='c5472b9c7615f35abdf1188cb1a0c5408fe50d66',
               torch_cuda_build=torch.version.cuda, mmcv_compiled_cpu_nms_passed=True,
               unified_model_type=type(model).__name__, unified_checkpoint_keys=len(actual),
               missing_checkpoint_keys=missing, unexpected_checkpoint_keys=unexpected,
               shape_mismatches=shape_mismatches, unified_model_loaded_on='cpu',
               bert_text_forward_shape=list(language_output['embedded'].shape),
               weights=weight, local_bert=str(ROOT / 'models/MASA/bert-base-uncased'),
               tracker_fps=5, phrase_separator=' . ', initial_output_score_threshold=0.2,
               internal_tracker_thresholds=dict(config.model.tracker),
               sam_mask=False, sam2_or_sam3_used=False, backup_route_used=False,
               gpu_inference_run=False, toc_videos_processed=0,
               runtime_interaction='trajectory JSON files only; no shared Python runtime')
(ROOT / 'logs/masa_setup_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
config.dump(ROOT / 'results/masa_unified_5fps_config.py')
print(json.dumps(receipt, indent=2), flush=True)
