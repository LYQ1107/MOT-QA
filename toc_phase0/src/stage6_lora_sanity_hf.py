"""HF/PEFT loading sanity on two synthetic examples and one development video."""
import json
import os
from pathlib import Path
import time

ROOT=Path(__file__).resolve().parents[1]


def main():
    import torch
    from transformers import AutoProcessor,Qwen2_5_VLForConditionalGeneration
    from peft import PeftModel
    from PIL import Image
    torch.manual_seed(42)
    model_path=ROOT/'models/Qwen2.5-VL-7B-Instruct'
    processor=AutoProcessor.from_pretrained(model_path,local_files_only=True)
    model=Qwen2_5_VLForConditionalGeneration.from_pretrained(model_path,torch_dtype=torch.bfloat16,
              device_map={'':0},attn_implementation='sdpa',local_files_only=True)
    model=PeftModel.from_pretrained(model,ROOT/'models/stage6_lora_r8',is_trainable=False).eval()
    cases=json.loads((ROOT/'results/stage6_lora_sanity_protocol_locked.json').read_text())['cases']
    for case in cases:
        images=[Image.open(path).convert('RGB') for path in case['images']]
        content=[dict(type='image',image=image) for image in images]+[dict(type='text',text=case['user'])]
        messages=[dict(role='system',content=case['system']),dict(role='user',content=content)]
        text=processor.apply_chat_template(messages,tokenize=False,add_generation_prompt=True)
        kwargs=dict(text=[text],return_tensors='pt')
        if images:kwargs['images']=images
        inputs=processor(**kwargs).to('cuda');start=time.monotonic()
        with torch.inference_mode():out=model.generate(**inputs,max_new_tokens=1024,do_sample=False,
             repetition_penalty=1.05,eos_token_id=[151645,151643],pad_token_id=151643,use_cache=True)
        tokens=out[0,inputs['input_ids'].shape[1]:]
        result=dict(case=case['id'],backend='transformers4.52.4_peft0.15.2',raw_response=processor.tokenizer.decode(tokens,skip_special_tokens=True),
                    generated_tokens=len(tokens),input_tokens=int(inputs['input_ids'].shape[1]),elapsed_s=time.monotonic()-start)
        path=ROOT/'results/stage6_loading_sanity'/f'{case["id"]}.hf.json';path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(dict(case=case['id'],backend='HF',generated_tokens=len(tokens)),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
