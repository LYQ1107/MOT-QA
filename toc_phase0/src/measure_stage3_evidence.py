"""CPU-only token lengths of raw-fact text; no vLLM/model inference or prompts."""
from collections import Counter
from datetime import datetime
from functools import lru_cache
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

os.environ['CUDA_VISIBLE_DEVICES']=''
from transformers import AutoTokenizer
from track_facts import serialize

ROOT=Path(__file__).resolve().parents[1]


def summary(values):
    values=sorted(values)
    return dict(count=len(values),minimum=values[0],median=values[len(values)//2],
                p95=values[int((len(values)-1)*.95)],maximum=values[-1],
                over_32768=sum(v>32768 for v in values))


def main():
    tokenizer=AutoTokenizer.from_pretrained(ROOT/'models/Qwen2.5-VL-7B-Instruct',local_files_only=True)
    index=json.loads((ROOT/'results/stage3_track_index.json').read_text())
    queries=json.loads((ROOT/'results/stage3_extracted_queries.json').read_text())
    lookup={}
    pair_rows=[]
    for row in index:
        doc=json.loads(Path(row['json_path']).read_text())
        text=serialize(doc)
        assert text==Path(row['text_path']).read_text()
        key=(row['video_id'],row['query']);lookup[key]=text
        pair_rows.append(dict(video_id=row['video_id'],query=row['query'],characters=len(text),
                              tokens=len(tokenizer.encode(text,add_special_tokens=False))))
    qa_rows=[]
    for row in queries:
        text='\n'.join(lookup[(row['video_id'],query)] for query in row['queries'])
        qa_rows.append(dict(qa_id=row['qa_id'],video_id=row['video_id'],characters=len(text),
                            tokens=len(tokenizer.encode(text,add_special_tokens=False))))
    result=dict(measured_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
                tokenizer=str(ROOT/'models/Qwen2.5-VL-7B-Instruct'),cpu_only=True,vllm_or_model_inference=False,
                metadata_or_answers_read=False,prompts_built=False,images_included=False,
                definition='unmodified raw-fact track text only, per question concatenate target blocks; excludes images, timestamps, question and evidence preface',
                per_query_tokens=summary([r['tokens'] for r in pair_rows]),
                per_question_tokens=summary([r['tokens'] for r in qa_rows]),
                per_question_characters=summary([r['characters'] for r in qa_rows]),
                query_rows=pair_rows,question_rows=qa_rows)
    (ROOT/'results/stage3_evidence_lengths.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if not k.endswith('_rows')},indent=2))


if __name__=='__main__':main()
