"""Actual unified-model regression for consecutive videos with different text."""
import json
import os
from pathlib import Path
import sys

from run_stage3_masa import ROOT,cuda_uuid,now,pick_devices,reset_video_text_cache,write_json


def main():
    device=pick_devices('cache_regression',1)[0]
    os.environ.update(CUDA_VISIBLE_DEVICES=str(device['physical_index']),CUDA_DEVICE_ORDER='PCI_BUS_ID',
                      HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',MASA_SKIP_NLTK_DOWNLOAD='1',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4')
    assert cuda_uuid()==device['uuid']
    sys.path.insert(0,str(ROOT/'upstream/masa'))
    import cv2
    import torch
    import masa
    from masa.apis import init_masa,inference_masa,build_test_pipeline
    from mmengine.config import Config
    torch.manual_seed(42)
    cfg=Config.fromfile(ROOT/'upstream/masa/configs/masa-gdino/masa_gdino_swinb_inference.py')
    cfg.model.detector.language_model.name=str(ROOT/'models/MASA/bert-base-uncased')
    cfg.model.tracker.fps=5
    model=init_masa(cfg,str(ROOT/'models/MASA/gdino_masa.pth'),device='cuda:0')
    pipeline=build_test_pipeline(model.cfg,with_text=True)
    def frame(video):
        cap=cv2.VideoCapture(str(ROOT/'data/toc_bench/videos_5fps'/(video+'.mp4')))
        ok,img=cap.read();cap.release();assert ok
        return img
    def infer(img,prompt,frame_id):
        out=inference_masa(model,img,frame_id=frame_id,video_len=2,test_pipeline=pipeline,
                           text_prompt=prompt,custom_entities=True,fp16=True)
        pred=out[0].pred_instances
        top={str(label):float(pred.scores[pred.labels==label].max().cpu()) for label in pred.labels.unique().tolist()}
        return dict(top_confidence_by_query=top,boxes=pred.bboxes.cpu().float(),scores=pred.scores.cpu().float(),labels=pred.labels.cpu())
    a=frame('charades_PKEZI');b=frame('perception_test_video_8100')
    infer(a,'flower vase',0)
    stale_shape=list(model.detector.track_text_dict['embedded'].shape)
    first=infer(b,'purple spray can . wooden cup',0)
    stale=infer(b,'purple spray can . wooden cup',1)
    reset_video_text_cache(model)
    fixed_first=infer(b,'purple spray can . wooden cup',0)
    fixed_repeat=infer(b,'purple spray can . wooden cup',1)
    fixed_shape=list(model.detector.track_text_dict['embedded'].shape)
    assert stale_shape!=fixed_shape,(stale_shape,fixed_shape)
    for key in ('boxes','scores','labels'):
        assert fixed_first[key].shape==fixed_repeat[key].shape
        assert torch.allclose(fixed_first[key].float(),fixed_repeat[key].float(),atol=1e-4,rtol=1e-4),key
    assert torch.equal(first['labels'],fixed_first['labels']) and torch.allclose(first['scores'],fixed_first['scores'],atol=1e-4,rtol=1e-4)
    receipt=dict(status='CROSS_VIDEO_TEXT_CACHE_REGRESSION_PASSED',checked_at=now(),device=device,
                 stale_cached_embedding_shape=stale_shape,fixed_embedding_shape=fixed_shape,
                 changed_prompt_first_frame=first['top_confidence_by_query'],
                 changed_prompt_second_frame_stale_cache=stale['top_confidence_by_query'],
                 fixed_first_frame=fixed_first['top_confidence_by_query'],fixed_second_frame=fixed_repeat['top_confidence_by_query'],
                 repeated_identical_image_detector_outputs_match=True,fix='clear detector text cache at video start')
    write_json(ROOT/'logs/stage3_text_cache_regression.json',receipt)
    print(json.dumps(receipt,indent=2),flush=True)


if __name__=='__main__':main()
