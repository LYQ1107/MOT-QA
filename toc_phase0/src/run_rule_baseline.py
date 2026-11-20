"""Write all metadata-free rule predictions before offline official scoring."""
from collections import Counter
from datetime import datetime
from functools import lru_cache
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

from rule_prediction import PARAMETERS,predict

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'upstream/toc_bench'))
from answer_extractor import extract
from compute_metrics import compute_one_model,is_correct


def dump(path,data):path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')


@lru_cache(maxsize=64)
def read_trajectory(path):return json.loads(Path(path).read_text())


def main():
    inputs=[json.loads(s) for s in (ROOT/'results/stage3_visible_inputs.jsonl').read_text().splitlines()]
    queries={q['qa_id']:q['queries'] for q in json.loads((ROOT/'results/stage3_extracted_queries.json').read_text())}
    index={(r['video_id'],r['query']):r for r in json.loads((ROOT/'results/stage3_track_index.json').read_text())}
    predictions=[]
    for item in inputs:
        docs={query:read_trajectory(index[(item['video_id'],query)]['json_path']) for query in queries[item['qa_id']]}
        result=predict(item,docs)
        answer=result.pop('answer')
        raw=None if answer is None else ', '.join(answer) if isinstance(answer,list) else str(answer)
        predictions.append(dict(qa_id=item['qa_id'],model='MASA_rule',format=item['format'],raw_response=raw,
                                extracted_answer=extract(raw,item['format']) if raw is not None else None,
                                error=None,**result))
    assert len(predictions)==len({r['qa_id'] for r in predictions})==749
    output=ROOT/'results/stage3_rule_predictions.jsonl'
    output.write_text(''.join(json.dumps(p,ensure_ascii=False)+'\n' for p in predictions))
    # Ground truth is first opened after every rule prediction has been saved.
    all_items=json.loads((ROOT/'data/toc_bench/answer_final.json').read_text())['items']
    by_id={p['qa_id']:p for p in predictions}
    items=[q for q in all_items if q['qa_id'] in by_id]
    registration=json.loads((ROOT/'results/trackable_subset_preregistered.json').read_text())
    trackable=set(registration['trackable_qa_ids'])
    def score(rows):
        total=len(rows);covered=sum(by_id[q['qa_id']]['covered'] for q in rows)
        correct=sum(is_correct(by_id[q['qa_id']]['extracted_answer'],q) for q in rows)
        return dict(total=total,covered=covered,coverage=covered/total if total else None,correct=correct,
                    accuracy_all=correct/total if total else None,accuracy_on_covered=correct/covered if covered else None)
    groups={'full_749':items,'trackable_324':[q for q in items if q['qa_id'] in trackable],
            'main_726':[q for q in items if q['metadata']['dim']!='reappear_identity'],
            'main_trackable_301':[q for q in items if q['metadata']['dim']!='reappear_identity' and q['qa_id'] in trackable]}
    groups.update({'dimension:'+dim:[q for q in items if q['metadata']['dim']==dim] for dim in sorted({q['metadata']['dim'] for q in items})})
    groups.update({'trackable_dimension:'+dim:[q for q in items if q['metadata']['dim']==dim and q['qa_id'] in trackable] for dim in sorted({q['metadata']['dim'] for q in items})})
    stats={name:score(rows) for name,rows in groups.items()}
    by_type={}
    item_map={q['qa_id']:q for q in items}
    kinds=sorted({kind for r in registration['rows'] for kind in r['event_types']})
    for kind in kinds:
        by_type[kind]=score([item_map[r['qa_id']] for r in registration['rows'] if kind in r['event_types']])
    legal={'2','3','4','5 or more'}
    numeric=[p for p in predictions if p['format']=='numerical'];covered_numeric=[p for p in numeric if p['covered']]
    numeric_legal=sum(p['raw_response'] in legal for p in numeric)
    result=dict(generated_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),groups=stats,event_types=by_type,
                event_type_counting='multi-label; totals overlap',rule_parameters=PARAMETERS,
                numerical=dict(total=300,covered=len(covered_numeric),legal=numeric_legal,
                               legal_ratio_all=numeric_legal/300,
                               legal_ratio_covered=numeric_legal/len(covered_numeric) if covered_numeric else None,
                               raw_answers=dict(Counter(str(p['raw_response']) for p in numeric))),
                abstention_reasons=dict(Counter(p['reason'] for p in predictions if not p['covered'])),
                main_official_metrics=compute_one_model(items,by_id,'MASA_rule'),
                trackable_official_metrics=compute_one_model(groups['trackable_324'],by_id,'MASA_rule'),
                missing_predictions=0,metadata_used_by_predictor=False,raw_integer_counts_preserved=True)
    dump(ROOT/'results/stage3_rule_metrics.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('main_official_metrics','trackable_official_metrics')},indent=2,ensure_ascii=False))


if __name__=='__main__':main()
