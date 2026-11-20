"""Post-hoc descriptive checks only; never change primary predictions or hypotheses."""
from collections import Counter
from copy import deepcopy
from stage6_common import *
from stage5_common import extract
from stage4_scores import inputs
from analyze_stage4 import paired
from compute_metrics import is_correct
from stage6_eos_parser import parse_eos_call
from stage6_tools import Tools,normalized


def mapping(path):return {p['qa_id']:p for p in rows(path)}


def option_meaning(q,answer):
    text=(q.get('statement_'+answer) or q.get('option_'+answer) or '').lower()
    if any(s in text for s in ['left the frame','leave the frame','leaves the frame']):return 'leaves_frame'
    if any(s in text for s in ['fully blocked','fully hidden','fully occluded']):return 'fully_hidden'
    raise ValueError((q['qa_id'],answer,text))


def main():
    scopes,trackable=inputs();rd=[q for q in scopes['test'] if q['metadata']['dim']=='reappear_or_disappear']
    assert len(rd)==101
    before=mapping(ROOT/'results/stage5/reasoning_main_B-events_predictions.jsonl')
    after=mapping(ROOT/'results/stage6/main_LoRA-B-events_predictions.jsonl')
    rules=mapping(ROOT/'results/v1_rule_predictions.jsonl')
    prior_letters=Counter(q['correct_answer'] for q in rd)
    formats=Counter(q['format'] for q in rd)
    prior_meaning=Counter()
    for q in rd:
        answer=q['correct_answer'];text=(q.get('statement_'+answer) or q.get('option_'+answer) or '').lower()
        if any(s in text for s in ['left the frame','leave the frame','leaves the frame']):kind='leaves_frame'
        elif any(s in text for s in ['fully blocked','fully hidden','fully occluded']):kind='fully_hidden'
        else:kind='unclassified'
        prior_meaning[kind]+=1
    dev_rd=[q for q in scopes['dev'] if q['metadata']['dim']=='reappear_or_disappear']
    dev_letters=Counter(q['correct_answer'] for q in dev_rd)
    dev_meanings=Counter(option_meaning(q,q['correct_answer']) for q in dev_rd)
    majority_letter=max(sorted(dev_letters),key=dev_letters.get)
    majority_meaning=max(sorted(dev_meanings),key=dev_meanings.get)
    for q in dev_rd+rd:
        assert {option_meaning(q,'A'),option_meaning(q,'B')}=={'fully_hidden','leaves_frame'}
    blind_prior=dict(posthoc=True,selection_uses_development_labels_only=True,development_n=len(dev_rd),
        development_letters=dict(dev_letters),development_semantics=dict(dev_meanings),
        fixed_letter=majority_letter,fixed_semantics=majority_meaning,test_n=len(rd),
        fixed_letter_test_correct=sum(q['correct_answer']==majority_letter for q in rd),
        fixed_semantics_test_correct=sum(option_meaning(q,q['correct_answer'])==majority_meaning for q in rd),
        reads_video_or_tracks=False,changes_H11_threshold=False)
    decomposition=Counter();format_rows=[];relaxed={}
    for name,ps in [('before',before),('after',after)]:
        view=deepcopy(ps)
        for q in rd:
            p=view[q['qa_id']];region=p.get('final_answer_region')
            p['extracted_answer']=extract(region,q['format']) if region is not None else None
        relaxed[name]=view
    for q in rd:
        qid=q['qa_id'];bp=before[qid];ap=after[qid]
        bc=is_correct(bp['extracted_answer'],q);ac=is_correct(ap['extracted_answer'],q)
        key=('before_parsed' if bp['extracted_answer'] is not None else 'before_unparsed')+'/'+('after_parsed' if ap['extracted_answer'] is not None else 'after_unparsed')
        decomposition[key]+=1;decomposition[key+'/net_correct']+=int(ac)-int(bc)
        format_rows.append(dict(qa_id=qid,before_parsed=bp['extracted_answer'] is not None,after_parsed=ap['extracted_answer'] is not None,
            before_correct=bc,after_correct=ac,before_relaxed=relaxed['before'][qid]['extracted_answer'],after_relaxed=relaxed['after'][qid]['extracted_answer']))
    covered=[q for q in rd if rules[q['qa_id']]['covered']]
    semantic_confusions={}
    for name,ps in [('before',before),('after',after)]:
        confusion=Counter()
        for q in rd:
            answer=ps[q['qa_id']]['extracted_answer']
            confusion[option_meaning(q,q['correct_answer'])+' -> '+(option_meaning(q,answer) if answer in ['A','B'] else 'parse_failure')]+=1
        semantic_confusions[name]=dict(confusion)
    agreement={}
    for name,ps in [('before',before),('after',after)]:
        agreement[name]=dict(rule_covered=len(covered),strict_agree=sum(ps[q['qa_id']]['extracted_answer']==rules[q['qa_id']]['extracted_answer'] for q in covered),
            parsed=sum(ps[q['qa_id']]['extracted_answer'] is not None for q in covered),
            relaxed_agree=sum(relaxed[name][q['qa_id']]['extracted_answer']==rules[q['qa_id']]['extracted_answer'] for q in covered))
    tools=Tools();recoveries=Counter();requested_names=Counter();parser_mismatches=[]
    for condition in ['T-none','T0','T1']:
        ps=rows(ROOT/'results/stage6'/f'main_{condition}_predictions.jsonl')
        for p in ps:
            parsed,region=final_answer(p['raw_response'],p['format'])
            if parsed!=p['extracted_answer']:
                parser_mismatches.append(dict(condition=condition,qa_id=p['qa_id'],standalone_parser=parsed,
                    recorded=p['extracted_answer'],tool_turn='<tool_call' in p['raw_response'],raw=p['raw_response']))
            if condition!='T1':continue
            attempts=[t['raw_response'] for t in p['turns'] if '<tool_call' in t['raw_response']][:len(p['tool_calls'])]
            for raw in attempts:
                recoveries['attempts']+=1;call,error,recovered=parse_eos_call(raw)
                if recovered:
                    recoveries['complete_JSON_to_EOS_only']+=1
                    requested_names[call['name']]+=1
                    obj=call['arguments'].get('object')
                    if isinstance(obj,str) and any(normalized(obj)==normalized(q) for q in tools.names[p['video_id']]):recoveries['object_exact_match_if_recovered']+=1
    result=dict(created_at=now(),posthoc=True,descriptive_only=True,primary_predictions_or_H9_H11_changed=False,
        RD_formats=dict(formats),RD_correct_answer_distribution=dict(prior_letters),RD_correct_option_meaning_distribution=dict(prior_meaning),
        chance_by_declared_format=sum(.5 if q['format']=='sp' else .25 for q in rd)/len(rd),
        label_prior_note='Test-set majority distributions are descriptive post-hoc diagnostics, not fitted models or new acceptance thresholds.',
        development_majority_blind_baselines=blind_prior,semantic_confusions=semantic_confusions,
        formatting_decomposition=dict(decomposition),formatting_rows=format_rows,
        strict_before_after=paired(rd,before,after),
        relaxed_final_field_diagnostic=paired(rd,relaxed['before'],relaxed['after']),
        relaxed_after_vs_rule=paired(rd,rules,relaxed['after']),rule_agreement_on_covered=agreement,
        standalone_answer_parser_mismatches=parser_mismatches,
        hypothetical_EOS_JSON_recovery=dict(recoveries),
        hypothetical_recoverable_tool_name_counts=dict(requested_names),
        recovery_note='Offline syntax/matching audit only; these calls were NOT executed and no model answers were changed.')
    write(ROOT/'results/stage6_posthoc_diagnostics.json',result)
    print(__import__('json').dumps({k:v for k,v in result.items() if k not in ['formatting_rows','standalone_answer_parser_mismatches']},ensure_ascii=False))
    print('standalone_parser_mismatches',len(parser_mismatches))


if __name__=='__main__':main()
