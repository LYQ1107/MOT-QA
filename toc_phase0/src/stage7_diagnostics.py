"""Post-hoc frozen-track information diagnostics; never used for inference."""
from collections import Counter
from functools import lru_cache
import math
from pathlib import Path
from scipy.stats import fisher_exact
from stage6_common import ROOT,LEGAL,read,rows,write,write_rows,now,immutable,sha
from stage4_scores import inputs
from analyze_stage4 import paired
from rule_prediction import timeline,near_edge
from stage3_text import question_subject

DIMS=('event_count','reappear_or_disappear','cross_object_order','event_ordering','reappear_identity')


def rd_meaning(q,answer):
    if answer not in ('A','B'):return 'invalid'
    text=(q.get('statement_'+answer) or q.get('option_'+answer) or '').lower()
    if 'left the frame' in text or 'leave the frame' in text or 'leaves the frame' in text:return 'leaves_frame'
    if any(s in text for s in ('fully blocked','fully hidden','fully occluded')):return 'fully_hidden'
    raise ValueError((q['qa_id'],answer,text))


def reid_meaning(q,answer):
    text=(q.get('statement_'+answer) or q.get('option_'+answer) or '').lower()
    if 'different one' in text:return 'different'
    if 'same one' in text:return 'same'
    raise ValueError((q['qa_id'],answer,text))


def label(q,answer):
    if q['metadata']['dim']=='reappear_or_disappear':return rd_meaning(q,answer)
    if q['metadata']['dim']=='reappear_identity' and answer in ('A','B'):return reid_meaning(q,answer)
    if isinstance(answer,list):return ','.join(answer)
    return str(answer) if answer is not None else 'invalid'


def truth(q):return q.get('correct_order') if q['format'].startswith('ordering') else q['correct_answer']


def majority(items):
    counts=Counter(label(q,truth(q)) for q in items)
    chosen=max(sorted(counts),key=counts.get) if counts else None
    return dict(n=len(items),class_counts=dict(counts),selected_class=chosen,ties='lexicographic class order')


def map_class(q,chosen):
    dim=q['metadata']['dim']
    if dim in ('reappear_or_disappear','reappear_identity'):
        function=rd_meaning if dim=='reappear_or_disappear' else reid_meaning
        matches=[a for a in 'AB' if function(q,a)==chosen]
        assert len(matches)==1
        return matches[0]
    if q['format'].startswith('ordering'):return chosen.split(',')
    return chosen


def prepare_majority():
    path=ROOT/'results/stage7_majority_baselines_locked.json'
    if path.exists():return read(path)
    scopes,_=inputs();rules={p['qa_id']:p for p in rows(ROOT/'results/v1_rule_predictions.jsonl')}
    full_priors={};covered_priors={}
    for dim in DIMS:
        for fmt in sorted({q['format'] for q in scopes['full'] if q['metadata']['dim']==dim}):
            key=dim+'/'+fmt
            dev=[q for q in scopes['dev'] if q['metadata']['dim']==dim and q['format']==fmt]
            full_priors[key]=majority(dev)
            covered_priors[key]=majority([q for q in dev if rules[q['qa_id']]['covered']])
            assert full_priors[key]['selected_class'] is not None,key
    predictions=[]
    for q in scopes['full']:
        key=q['metadata']['dim']+'/'+q['format'];chosen=full_priors[key]['selected_class']
        answer=map_class(q,chosen)
        predictions.append(dict(qa_id=q['qa_id'],format=q['format'],extracted_answer=answer,raw_response=str(answer),
            prior_key=key,fixed_class=chosen,selection_scope='all development questions of same dimension/format; no test labels'))
    prediction_path=ROOT/'results/stage7/majority_blind_predictions.jsonl';write_rows(prediction_path,predictions);prediction_path.chmod(0o444)
    value=dict(created_at=now(),posthoc=True,selection_uses_development_labels_only=True,
        primary_policy='Majority across all development questions in the dimension/format; semantic class for R/D and ReID, answer label/permutation for others; ties lexicographic. Apply to visible options only.',
        covered_policy='Additional diagnostic only: select majority among covered development questions; N/A where none. No test-subset fitted majority is used for comparisons.',
        priors=full_priors,covered_development_priors=covered_priors,predictions_path=str(prediction_path),
        predictions_sha256=sha(prediction_path),split_sha256=sha(ROOT/'results/dev_test_split_locked.json'))
    immutable(path,value)
    return value


def classification(qs,predictions,classes):
    if not qs:return dict(n=0,status='not_computable_empty_covered_subset',accuracy=None,balanced_accuracy=None,kappa=None)
    ys=[label(q,truth(q)) for q in qs]
    yh=[]
    for q in qs:
        p=predictions[q['qa_id']];answer=p['extracted_answer']
        if q['format']=='numerical' and answer is None and p.get('covered') and p.get('raw_response') in ('0','1'):
            answer=p['raw_response']
        yh.append(label(q,answer))
    columns=list(classes)+sorted(set(yh)-set(classes))
    matrix={y:{p:0 for p in columns} for y in classes}
    for y,p in zip(ys,yh):matrix[y][p]+=1
    recalls={y:(matrix[y].get(y,0)/ys.count(y) if ys.count(y) else None) for y in classes}
    valid=[v for v in recalls.values() if v is not None]
    n=len(qs);correct=sum(a==b for a,b in zip(ys,yh));gt=Counter(ys);pred=Counter(yh)
    pe=sum(gt[c]*pred[c] for c in set(ys)|set(yh))/n**2
    kappa=(correct/n-pe)/(1-pe) if pe<1 else None
    return dict(n=n,correct=correct,accuracy=correct/n,balanced_accuracy=sum(valid)/len(valid),kappa=kappa,
        truth_rows=list(classes),prediction_columns=columns,confusion_matrix=matrix,per_class_recall=recalls,
        true_distribution=dict(gt),predicted_distribution=dict(pred),
        metrics_note='Balanced accuracy averages recalls over true classes present; 0/1/invalid outputs remain errors. Kappa includes their prediction marginals; no legal-answer filtering.')


def main():
    scopes,trackable=inputs();baseline=prepare_majority()
    blind={p['qa_id']:p for p in rows(baseline['predictions_path'])}
    rules={p['qa_id']:p for p in rows(ROOT/'results/v1_rule_predictions.jsonl')}
    index={(r['video_id'],r['query']):r for r in read(ROOT/'results/v1_track_index.json')}
    @lru_cache(maxsize=8)
    def document(video,query):return read(index[video,query]['json_path'])
    diagnostic={};feature_records=[]
    for scope in ('dev','test'):
        diagnostic[scope]={}
        for dim in DIMS[:3]:
            all_items=[q for q in scopes[scope] if q['metadata']['dim']==dim]
            covered=[q for q in all_items if rules[q['qa_id']]['covered']]
            classes=['fully_hidden','leaves_frame'] if dim=='reappear_or_disappear' else list(LEGAL) if dim=='event_count' else ['A','B']
            result=dict(total=len(all_items),covered=len(covered),coverage=len(covered)/len(all_items),
                frozen_rule=classification(covered,rules,classes),majority_blind=classification(covered,blind,classes),
                rule_minus_development_majority=paired(covered,blind,rules) if covered else None)
            prior=baseline['covered_development_priors'][dim+'/'+all_items[0]['format']]
            result['covered_development_prior']=prior
            if prior['selected_class'] is not None and covered:
                extra={q['qa_id']:dict(extracted_answer=map_class(q,prior['selected_class'])) for q in covered}
                result['covered_dev_majority_blind']=classification(covered,extra,classes)
                result['rule_minus_covered_dev_majority']=paired(covered,extra,rules)
            if dim=='reappear_or_disappear':
                table=[[0,0],[0,0]]
                for q in covered:
                    query=question_subject(q['question']);doc=document(q['video_id'],query);line=timeline(doc)
                    gaps=line['gaps']
                    if q['question'].startswith('Before '):gaps=[g for g in gaps if not g['terminal']]
                    assert gaps
                    point=gaps[0]['before'];edge=near_edge(point,doc)
                    expected='leaves_frame' if edge else 'fully_hidden'
                    assert rd_meaning(q,rules[q['qa_id']]['extracted_answer'])==expected,q['qa_id']
                    actual=rd_meaning(q,q['correct_answer']);table[int(edge)][classes.index(actual)]+=1
                    feature_records.append(dict(scope=scope,qa_id=q['qa_id'],video_id=q['video_id'],query=query,
                        before_timestamp=point['timestamp_seconds'],before_box_xyxy=point['box_xyxy'],
                        near_edge=edge,rule_class=expected,truth_class=actual,terminal=gaps[0]['terminal']))
                odds,p=fisher_exact(table,alternative='two-sided') if covered else (None,None)
                result.update(edge_table=dict(rows=['not_near_edge','near_edge'],columns=classes,counts=table),
                    fisher_exact_two_sided_p=float(p) if p is not None else None,
                    fisher_odds_ratio=(float(odds) if odds is not None and math.isfinite(odds) else str(odds)),
                    feature_selection='Exactly first frozen-rule gap; Before questions exclude terminal gap; original edge center margin0.05')
            diagnostic[scope][dim]=result
    model_paths={'official_A':'results/stage4/main_A_predictions.jsonl',
        'official_B':'results/stage4/main_B_predictions.jsonl',
        'official_B-events':'results/stage5/official_main_B-events_predictions.jsonl',
        'reasoning_B-events':'results/stage5/reasoning_main_B-events_predictions.jsonl',
        'LoRA_reasoning_B-events':'results/stage6/main_LoRA-B-events_predictions.jsonl'}
    recall={}
    for scope in ('dev','test'):
        qs=[q for q in scopes[scope] if q['metadata']['dim']=='reappear_or_disappear'];recall[scope]={}
        for name,path in model_paths.items():
            ps={p['qa_id']:p for p in rows(ROOT/path)}
            if not all(q['qa_id'] in ps for q in qs):
                recall[scope][name]=dict(n=len(qs),status='not_evaluated_in_this_split; no new inference',missing=len([q for q in qs if q['qa_id'] not in ps]))
            else:recall[scope][name]=classification(qs,ps,['fully_hidden','leaves_frame'])
    routing_prior={}
    route={p['qa_id']:p for p in rows(ROOT/'results/stage4/routing_A_predictions.jsonl')}
    official_a={p['qa_id']:p for p in rows(ROOT/'results/stage4/main_A_predictions.jsonl')}
    from compute_metrics import is_correct
    for scope in ('dev','test'):
        qs=[q for q in scopes[scope] if q['metadata']['dim']=='reappear_or_disappear']
        parts={'rule_covered':[q for q in qs if rules[q['qa_id']]['covered']],
               'rule_uncovered':[q for q in qs if not rules[q['qa_id']]['covered']], 'all':qs}
        routing_prior[scope]={part:dict(n=len(items),**{name:sum(is_correct(ps[q['qa_id']]['extracted_answer'],q) for q in items)
            for name,ps in [('official_A',official_a),('frozen_rule',rules),('majority_blind',blind),('route',route)]}) for part,items in parts.items()}
    value=dict(created_at=now(),posthoc=True,no_new_model_inference=True,no_tuning=True,
        frozen_config_sha256=sha(ROOT/'results/frozen_config_v1.json'),split_sha256=sha(ROOT/'results/dev_test_split_locked.json'),
        majority_baseline_sha256=sha(ROOT/'results/stage7_majority_baselines_locked.json'),
        development_caveat='Development was used to tune v1 and to choose the majority class; development metrics are descriptive, not held-out evidence.',
        inference_caveat='Covered subsets are selected by frozen rules; association/accuracy on them does not imply full-benchmark utility or tracker perfection. Tests are post-hoc, question-level, unadjusted.',
        covered_rule_diagnostics=diagnostic,RD_model_class_recalls=recall,RD_edge_records=feature_records,
        RD_routing_prior_decomposition=routing_prior,
        source_prediction_sha256={name:sha(ROOT/path) for name,path in model_paths.items()})
    write(ROOT/'results/stage7_track_information_diagnostics.json',value)
    lines=['# 阶段七：轨迹信息量事后诊断','','仅复用已有标注、轨迹与预测；不运行模型、不修改v1。开发集参与过调参，只将测试结果视为留出证据。覆盖子集上的结果不外推到所有题。','',
        '| 范围 | 维度 | 覆盖/总数 | 规则正确 | 平衡准确率 | kappa | 开发多数基线正确 | 规则−盲基线pp | exact McNemar p |','|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for scope,dimensions in diagnostic.items():
        for dim,r in dimensions.items():
            a=r['frozen_rule'];b=r['majority_blind'];pair=r['rule_minus_development_majority']
            cells=[scope,dim,f"{r['covered']}/{r['total']}"]
            if pair:cells += [str(a['correct']),f"{a['balanced_accuracy']:.4f}",f"{a['kappa']:.4f}" if a['kappa'] is not None else '—',str(b['correct']),f"{pair['effect_pp']:+.2f}",f"{pair['mcnemar_exact_two_sided_p']:.6g}"]
            else:cells += ['—']*6
            lines.append('| '+' | '.join(cells)+' |')
    for scope,dimensions in diagnostic.items():
        for dim,r in dimensions.items():
            lines += ['',f'## {scope} / {dim}','','```json',__import__('json').dumps(r,ensure_ascii=False,indent=2),'```']
    lines += ['','## R/D分类别召回率','','完全遮挡/离开画面分别以各自真实类题数作分母；解析失败计错。LoRA未运行开发集，明确记为N/A。','',
        '| 范围 | 模型 | 完全遮挡召回 | 离开画面召回 | 平衡准确率 |','|---|---|---:|---:|---:|']
    for scope,models in recall.items():
        for model,r in models.items():
            if 'per_class_recall' not in r:cells=[scope,model,'—','—','—']
            else:cells=[scope,model]+[f"{r['confusion_matrix'][c][c]}/{r['true_distribution'][c]} ({100*r['per_class_recall'][c]:.2f}%)" for c in ['fully_hidden','leaves_frame']]+[f"{100*r['balanced_accuracy']:.2f}%"]
            lines.append('| '+' | '.join(cells)+' |')
    lines += ['','主要盲基线：只用开发集同维度/题型的多数类，R/D按语义映射可见选项；所有比较使用与规则完全相同的覆盖题。另给开发集覆盖题多数类的敏感性结果；开发集X-Order覆盖0题，因此该版本不可估计，主要盲基线使用全部开发X-Order的多数选项B。Count的0/1错误不删；其混淆矩阵额外保留0/1列，平衡准确率仍对真实四类平均。','',
        f'[完整统计与逐题边缘事实]({ROOT}/results/stage7_track_information_diagnostics.json)。']
    (ROOT/'results/stage7_track_information_report.md').write_text('\n'.join(lines)+'\n')
    print({scope:{dim:dict(covered=r['covered'],accuracy=r['frozen_rule']['accuracy'],balanced=r['frozen_rule']['balanced_accuracy'],kappa=r['frozen_rule']['kappa'],p=r.get('fisher_exact_two_sided_p')) for dim,r in dimensions.items()} for scope,dimensions in diagnostic.items()})


if __name__=='__main__':main()
