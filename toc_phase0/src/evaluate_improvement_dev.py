"""Write development predictions before scoring; never evaluate test here."""
import argparse
from collections import Counter
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import sys

from improvement_events import identity_segments,timeline_public
from improvement_facts import filter_document,serialize_compressed
from rule_prediction import predict
from run_stage3_masa import ROOT,now,write_json
from track_facts import query_document,serialize

sys.path.insert(0,str(ROOT/'upstream/toc_bench'))
from answer_extractor import extract
from compute_metrics import is_correct


@lru_cache(maxsize=4)
def documents(memory,video):
    directory=ROOT/'tracks/raw' if memory==10 else ROOT/f'tracks/development/memo{memory}/raw'
    raw=json.loads((directory/(video+'.json')).read_text())
    return {query:query_document(raw,i,0.2) for i,query in enumerate(raw['queries'])}


def summarize(items,by_id):
    total=len(items);covered=sum(by_id[q['qa_id']]['covered'] for q in items)
    correct=sum(is_correct(by_id[q['qa_id']]['extracted_answer'],q) for q in items)
    return dict(total=total,covered=covered,correct=correct,coverage=covered/total if total else None,
                accuracy_all=correct/total if total else None,accuracy_on_covered=correct/covered if covered else None)


def main(args):
    split_path=ROOT/'results/dev_test_split_locked.json'
    lock=json.loads((ROOT/'logs/dev_test_split_lock.json').read_text())
    assert hashlib.sha256(split_path.read_bytes()).hexdigest()==lock['sha256']
    split=json.loads(split_path.read_text());dev_ids=set(split['dev_qa_ids'])
    plan=json.loads((ROOT/'results/improvement_plan_locked.json').read_text())
    filters={r['name']:r for r in plan['filter_trials']}
    filters['short_weak_top3']=dict(name='short_weak_top3',short_seconds=0.6,low_confidence=0.3,top_k=3)
    parameters=filters[args.filter]
    visible=[json.loads(line) for line in (ROOT/'results/stage3_visible_inputs.jsonl').read_text().splitlines()]
    visible=[q for q in visible if q['qa_id'] in dev_ids]
    queries={r['qa_id']:r for r in json.loads((ROOT/'results/stage3_extracted_queries.json').read_text()) if r['qa_id'] in dev_ids}
    target=ROOT/'results/improvement/dev'/args.label;target.mkdir(parents=True,exist_ok=True)
    predictions=[];index=[];seen=set()
    for item in visible:
        original=documents(args.memory,item['video_id'])
        docs={query:(document if args.filter=='none' else filter_document(document,parameters)) for query,document in original.items()}
        result=(predict(item,docs) if args.events=='legacy_gap_0.5' else
                predict(item,docs,timeline_fn=timeline_public,identity_segments_fn=identity_segments))
        answer=result.pop('answer');raw=None if answer is None else ', '.join(answer) if isinstance(answer,list) else str(answer)
        predictions.append(dict(qa_id=item['qa_id'],raw_response=raw,
                                extracted_answer=extract(raw,item['format']) if raw is not None else None,
                                format=item['format'],error=None,**result))
        for query in queries[item['qa_id']]['queries']:
            key=(item['video_id'],query)
            if key in seen:continue
            seen.add(key);doc=docs[query]
            q_index=list(original).index(query)
            path=target/'by_query'/item['video_id']/f'query_{q_index:02d}.json'
            write_json(path,doc)
            text_path=path.with_suffix('.txt')
            text_path.write_text(serialize(doc) if args.filter=='none' else serialize_compressed(doc))
            index.append(dict(video_id=item['video_id'],query=query,json_path=str(path),text_path=str(text_path)))
    assert len(predictions)==len({r['qa_id'] for r in predictions})==len(dev_ids)==147
    prediction_path=target/'predictions.jsonl'
    prediction_path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in predictions))
    write_json(target/'track_index.json',index)
    if args.memory==10 and args.filter=='none' and args.events=='legacy_gap_0.5':
        old={r['qa_id']:r for r in map(json.loads,(ROOT/'results/stage3_rule_predictions.jsonl').read_text().splitlines()) if r['qa_id'] in dev_ids}
        fields=('raw_response','extracted_answer','covered','reason')
        mismatches=[p['qa_id'] for p in predictions if any(p[k]!=old[p['qa_id']][k] for k in fields)]
        assert not mismatches,mismatches
        write_json(ROOT/'results/improvement_legacy_regression.json',dict(status='PASS',checked_at=now(),dev_questions=147,matching_predictions=147,test_questions_examined=0))
    # Open correct answers only after every development prediction is saved.
    qa=json.loads((ROOT/'data/toc_bench/answer_final.json').read_text())['items']
    qa=[q for q in qa if q['qa_id'] in dev_ids]
    assert len(qa)==147 and all(q['qa_id'] not in set(split['test_qa_ids']) for q in qa)
    registration=json.loads((ROOT/'results/trackable_subset_preregistered.json').read_text())
    trackable=set(registration['trackable_qa_ids']);by_id={p['qa_id']:p for p in predictions}
    groups={'all':qa,'main':[q for q in qa if q['metadata']['dim']!='reappear_identity'],
            'trackable':[q for q in qa if q['qa_id'] in trackable],
            'main_trackable':[q for q in qa if q['qa_id'] in trackable and q['metadata']['dim']!='reappear_identity']}
    for dim in sorted({q['metadata']['dim'] for q in qa}):
        groups['dimension:'+dim]=[q for q in qa if q['metadata']['dim']==dim]
        groups['trackable_dimension:'+dim]=[q for q in groups['dimension:'+dim] if q['qa_id'] in trackable]
    numeric=[p for p in predictions if p['format']=='numerical'];legal={'2','3','4','5 or more'}
    nlegal=sum(p['raw_response'] in legal for p in numeric);ncovered=sum(p['covered'] for p in numeric)
    result=dict(generated_at=now(),label=args.label,scope='dev',memory=args.memory,filter=parameters,event_mode=args.events,
                split_sha256=lock['sha256'],test_accuracy_computed=False,groups={name:summarize(rows,by_id) for name,rows in groups.items()},
                numerical=dict(total=len(numeric),covered=ncovered,legal=nlegal,legal_ratio_all=nlegal/len(numeric),legal_ratio_covered=nlegal/ncovered if ncovered else None),
                abstention_reasons=dict(Counter(p['reason'] for p in predictions if not p['covered'])))
    write_json(target/'metrics.json',result)
    print(json.dumps(dict(label=args.label,main_trackable=result['groups']['main_trackable'],all=result['groups']['all'],test_accuracy_computed=False),ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--memory',type=int,choices=[10,25,50],required=True)
    parser.add_argument('--filter',required=True);parser.add_argument('--events',choices=['legacy_gap_0.5','public_3fps_min2_confirm2'],required=True)
    parser.add_argument('--label',required=True);main(parser.parse_args())
