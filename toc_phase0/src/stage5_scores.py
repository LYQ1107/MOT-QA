"""Offline scoring and template-specific rule routing; never imported for requests."""
from stage5_common import ROOT,read,rows,write,write_rows,now
from stage4_scores import inputs,groups,summarize


def scoring_view(predictions,template):
    if template!='reasoning':return predictions
    return {qid:dict(p,raw_response=p.get('final_answer_region')) for qid,p in predictions.items()}


def score(predictions,template):
    scopes,trackable=inputs()
    view=scoring_view(predictions,template)
    return {scope:{name:summarize(items,view) for name,items in groups(qa,trackable).items()}
            for scope,qa in scopes.items()}


def routing(template):
    scopes,_=inputs()
    rules={p['qa_id']:p for p in rows(ROOT/'results/v1_rule_predictions.jsonl')}
    fallback_path=(ROOT/'results/stage4/main_A_predictions.jsonl' if template=='official' else ROOT/'results/stage5/reasoning_main_A_predictions.jsonl')
    fallback={p['qa_id']:p for p in rows(fallback_path)}
    result=[]
    for q in scopes['full']:
        qid=q['qa_id'];p=rules[qid] if rules[qid]['covered'] else fallback[qid]
        result.append(dict(qa_id=qid,format=q['format'],raw_response=p['raw_response'],
            final_answer_region=p.get('final_answer_region',p['raw_response']),extracted_answer=p['extracted_answer'],
            error=None,template=template,routing_source='frozen_rule' if rules[qid]['covered'] else 'template_A',rule_covered=rules[qid]['covered']))
    write_rows(ROOT/'results/stage5'/f'{template}_routing_predictions.jsonl',result)
    write(ROOT/'results/stage5'/f'{template}_routing_metrics.json',dict(generated_at=now(),
        policy='Use frozen rule exactly when covered, even if illegal; otherwise this template A.',
        metrics=score({p['qa_id']:p for p in result},template)))
    return {p['qa_id']:p for p in result}
