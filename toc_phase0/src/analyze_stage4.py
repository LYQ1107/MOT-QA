"""Score completed Stage 4 runs and evaluate the pre-inference hypotheses.

This program never changes tracking parameters, assignments, labels or prompts.
It requires complete predictions for all conditions before paired comparisons.
"""
from collections import Counter
import csv
from datetime import datetime
import json
import os
from pathlib import Path

import numpy as np
from scipy.stats import binomtest

from stage4_common import ROOT, CONDITIONS, LEGAL, now, read, rows, write, write_rows, sha, verify_stage4
from stage4_scores import DIMENSIONS, inputs, groups, summarize, score_all, route
from compute_metrics import is_correct, compute_one_model

LABELS = dict(event_count='Count', reappear_or_disappear='R/D', cross_object_order='X-Order',
              event_ordering='Order', reappear_identity='ReID')


def paired(items, reference, other):
    items = sorted(items, key=lambda q: q['qa_id'])
    n = len(items)
    assert n
    ref = np.asarray([is_correct(reference[q['qa_id']]['extracted_answer'], q) for q in items], dtype=np.int8)
    alt = np.asarray([is_correct(other[q['qa_id']]['extracted_answer'], q) for q in items], dtype=np.int8)
    won = int(((ref==0)&(alt==1)).sum())
    lost = int(((ref==1)&(alt==0)).sum())
    discordant = won+lost
    p = float(binomtest(won, discordant, .5, alternative='two-sided').pvalue) if discordant else 1.0
    rng = np.random.default_rng(42)
    resamples = rng.integers(0,n,size=(1000,n))
    differences = alt-ref
    samples = differences[resamples].mean(axis=1)
    lo,hi = np.percentile(samples,[2.5,97.5])
    return dict(n=n,reference_correct=int(ref.sum()),other_correct=int(alt.sum()),
        reference_accuracy=float(ref.mean()),other_accuracy=float(alt.mean()),
        other_correct_reference_wrong=won,other_wrong_reference_correct=lost,
        both_correct=int(((ref==1)&(alt==1)).sum()),both_wrong=int(((ref==0)&(alt==0)).sum()),
        effect_pp=100*float(differences.mean()),ci95_pp=[100*float(lo),100*float(hi)],
        mcnemar_exact_two_sided_p=p,bootstrap_resamples=1000,bootstrap_seed=42,resampling_unit='question')


def bootstrap_accuracy(items,predictions):
    items=sorted(items,key=lambda q:q['qa_id'])
    values=np.asarray([is_correct(predictions[q['qa_id']]['extracted_answer'],q) for q in items],dtype=np.int8)
    n=len(values); indices=np.random.default_rng(42).integers(0,n,size=(1000,n))
    low,high=np.percentile(values[indices].mean(axis=1),[2.5,97.5])
    return dict(n=n,correct=int(values.sum()),accuracy=float(values.mean()),
        ci95=[float(low),float(high)],chance=.25,
        exact_binomial_greater_than_chance_p=float(binomtest(int(values.sum()),n,.25,alternative='greater').pvalue))


def holm(values):
    ordered=sorted(values,key=values.get)
    adjusted={}; last=0
    for i,key in enumerate(ordered):
        last=max(last,min(1.,values[key]*(len(ordered)-i)))
        adjusted[key]=last
    return adjusted


def positive(result):
    return result['effect_pp']>0 and result['mcnemar_exact_two_sided_p']<.05 and result['ci95_pp'][0]>0


def pct(metric):
    return f"{metric['correct']}/{metric['total']} ({100*metric['accuracy']:.2f}%)" if metric['total'] else '—'


def comparison_table(metrics,scope,trackable):
    prefix='trackable_dimension:' if trackable else 'dimension:'
    aggregate='trackable' if trackable else 'all'
    main='main_trackable' if trackable else 'main'
    heading=['条件 / 基线']+[LABELS[d] for d in DIMENSIONS]+['主要四维','五维合计']
    lines=['| '+' | '.join(heading)+' |','|'+'|'.join(['---']+['---:']*(len(heading)-1))+'|']
    order=(('A','A 无工具'),('B','B 真实轨迹'),('C','C 占位符'),('D','D 打乱轨迹'),
           ('frozen_rule','冻结规则（弃答计错）'),('routing_stage2','路由（阶段二回退）'),('routing_A','路由（A回退）'))
    for key,label in order:
        metric=metrics[key][scope]
        cells=[pct(metric[prefix+d]) for d in DIMENSIONS]+[pct(metric[main]),pct(metric[aggregate])]
        lines.append('| '+' | '.join([label]+cells)+' |')
    return '\n'.join(lines)


def examples(scopes,trackable,main):
    prompts={p['qa_id']:p for p in rows(ROOT/'results/stage4/prompts/B.jsonl')}
    visible={q['qa_id']:q for q in rows(ROOT/'results/stage3_visible_inputs.jsonl')}
    dev_ids={q['qa_id'] for q in scopes['dev']}
    selections=[]; availability=[]
    for dimension in DIMENSIONS:
        for direction in ('B_correct_A_wrong','B_wrong_A_correct'):
            def qualifies(q):
                a=is_correct(main['A'][q['qa_id']]['extracted_answer'],q)
                b=is_correct(main['B'][q['qa_id']]['extracted_answer'],q)
                return q['metadata']['dim']==dimension and ((b and not a) if direction=='B_correct_A_wrong' else (a and not b))
            test=sorted([q for q in scopes['test'] if qualifies(q)],key=lambda q:q['qa_id'])
            dev=sorted([q for q in scopes['dev'] if qualifies(q)],key=lambda q:q['qa_id'])
            chosen=[(q,'test') for q in test[:5]]
            supplemental=[(q,'dev supplemental; not held-out example') for q in dev[:max(0,5-len(chosen))]]
            availability.append(dict(dimension=dimension,direction=direction,test_available=len(test),
                full_available=len(test)+len(dev),test_selected=len(chosen),dev_supplemental_selected=len(supplemental),
                shortage_after_full_supplement=max(0,5-len(test)-len(dev))))
            for item,scope in chosen+supplemental:
                qid=item['qa_id']
                selections.append(dict(qa_id=qid,video_id=item['video_id'],dimension=dimension,direction=direction,scope=scope,
                    trackable=qid in trackable,visible_input=visible[qid],
                    correct_answer=item.get('correct_order') if item['format'].startswith('ordering') else item.get('correct_answer'),
                    A_raw_output=main['A'][qid]['raw_response'],B_raw_output=main['B'][qid]['raw_response'],
                    A_extracted=main['A'][qid]['extracted_answer'],B_extracted=main['B'][qid]['extracted_answer'],
                    track_text=prompts[qid]['track_text'],prompt_B_sha256=prompts[qid]['prompt_sha256']))
    write(ROOT/'results/stage4_AB_examples.json',dict(generated_at=now(),selection_rule='Preregistered first five sorted test qa_id per dimension and direction; supplement only shortages with explicitly marked development cases. Never fabricate missing directions.',
        availability=availability,examples=selections))
    lines=['# A/B 成对差异样例','',
           '先列按 qa_id 排序的测试题，每维度每方向最多5条；不足时另列开发集补充，并注明最终不足数。保留完整冻结轨迹文本和两个模型原始输出。','',
           '| 维度 | 方向 | 测试集可用 | 测试选取 | 开发集补充 | 全集仍不足5条 |',
           '|---|---|---:|---:|---:|---:|']
    for r in availability:
        lines.append(f"| {LABELS[r['dimension']]} | {r['direction']} | {r['test_available']} | {r['test_selected']} | {r['dev_supplemental_selected']} | {r['shortage_after_full_supplement']} |")
    for example in selections:
        lines+=['',f"## {LABELS[example['dimension']]} / {example['direction']} / {example['qa_id']}",'',
            f"范围：{example['scope']}；可表达：{example['trackable']}；视频：{example['video_id']}。",'',
            '模型可见问题 / 选项 / 事件：','', '```json',json.dumps(example['visible_input'],ensure_ascii=False,indent=2),'```','',
            f"真值：`{example['correct_answer']}`。A解析：`{example['A_extracted']}`；B解析：`{example['B_extracted']}`。",'',
            'A 原始输出：','', '```text',example['A_raw_output'],'```','',
            'B 原始输出：','', '```text',example['B_raw_output'],'```','',
            '完整轨迹文本：','', '```text',example['track_text'],'```']
    (ROOT/'results/stage4_AB_examples.md').write_text('\n'.join(lines)+'\n')
    return availability,selections


def main():
    lock=verify_stage4()
    job=read(ROOT/'logs/stage4_job.json')
    assert job['status']=='COMPLETE',job
    assert (ROOT/'logs/stage4_main_complete.json').exists() and (ROOT/'logs/stage4_guided_complete.json').exists()
    scopes,trackable=inputs()
    all_ids={q['qa_id'] for q in scopes['full']}
    count_ids={q['qa_id'] for q in scopes['full'] if q['format']=='numerical'}
    main_predictions={}; guided_predictions={}; integrity={}
    for condition in CONDITIONS:
        condition_prompts={p['qa_id']:p for p in rows(ROOT/'results/stage4/prompts'/f'{condition}.jsonl')}
        for mode,target,ids in [('main',main_predictions,all_ids),('guided',guided_predictions,count_ids)]:
            path=ROOT/'results/stage4'/f'{mode}_{condition}_predictions.jsonl'
            predictions=rows(path)
            assert len(predictions)==len({p['qa_id'] for p in predictions})==len(ids)
            assert {p['qa_id'] for p in predictions}==ids
            for p in predictions:
                assert p['error'] is None and p['condition']==condition and p['decoding']==mode
                assert p['prompt_sha256']==condition_prompts[p['qa_id']]['prompt_sha256']
                assert p['usage']['prompt_tokens']==condition_prompts[p['qa_id']]['expected_prompt_tokens']
                assert p['hypotheses_sha256']==job['hypotheses_sha256']
                assert p['d_assignment_sha256']==job['d_assignment_sha256']
                if mode=='guided':assert p['raw_response'].strip() in LEGAL
            target[condition]={p['qa_id']:p for p in predictions}
            integrity[mode+'_'+condition]=dict(predictions=len(predictions),unique=len(predictions),missing=0,
                parse_failures=sum(p['extracted_answer'] is None for p in predictions),sha256=sha(path),
                exact_input_token_matches=len(predictions),finish_reason_counts=dict(Counter(p['finish_reason'] for p in predictions)))
    # Recompute A routing again as a deterministic integrity check, not a new inference.
    routed=route(ROOT/'results/stage4/main_A_predictions.jsonl','A')
    other=dict(frozen_rule={p['qa_id']:p for p in rows(ROOT/'results/v1_rule_predictions.jsonl')},
        routing_stage2={p['qa_id']:p for p in rows(ROOT/'results/stage4/routing_stage2_predictions.jsonl')},
        routing_A={p['qa_id']:p for p in routed},
        stage2={p['qa_id']:p for p in rows(ROOT/'results/stage2_predictions.jsonl')})
    all_predictions={**main_predictions,**other}
    metrics={name:score_all(predictions) for name,predictions in all_predictions.items()}
    official={}
    for condition in CONDITIONS:
        official[condition]=compute_one_model(scopes['full'],main_predictions[condition],condition)
        assert official[condition]['n_missing_preds']==0
        assert official[condition]['overall']==metrics[condition]['full']['all']['accuracy']
    write(ROOT/'results/stage4_official_metrics.json',official)
    guided_metrics={}
    for condition in CONDITIONS:
        guided_metrics[condition]={scope:{name:summarize([q for q in items if q['format']=='numerical'],guided_predictions[condition])
            for name,items in groups(scope_items,trackable).items()} for scope,scope_items in scopes.items()}
    write(ROOT/'results/stage4_metrics.json',dict(generated_at=now(),primary_scope='test trackable',metrics=metrics,
        guided_metrics=guided_metrics,full_scope_caveat='Development contributed to parameter selection; full-set scores are supplemental.',
        denominators='Complete fixed groups; illegal outputs, parse failures and rule abstentions all count wrong.'))
    comparisons=[]
    for name,model_metrics in metrics.items():
        for scope,scoped in model_metrics.items():
            for group,values in scoped.items():comparisons.append(dict(model=name,scope=scope,group=group,**values))
    with (ROOT/'results/stage4_comparison.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(comparisons[0]));writer.writeheader();writer.writerows(comparisons)

    stats={}
    for scope in ('test','full'):
        stats[scope]={}
        for group,items in groups(scopes[scope],trackable).items():
            if not items:continue
            stats[scope][group]={condition:paired(items,main_predictions['A'],main_predictions[condition]) for condition in ('B','C','D')}
    primary=stats['test']['trackable']
    adjusted=holm({c:primary[c]['mcnemar_exact_two_sided_p'] for c in ('B','C','D')})
    for condition,value in adjusted.items():primary[condition]['holm_three_aggregate_comparisons_p']=value
    test_track=groups(scopes['test'],trackable)
    h1=stats['test']['trackable_dimension:reappear_or_disappear']['B']
    h2=primary['C'];h3=primary['D']
    x=test_track['trackable_dimension:cross_object_order']
    h4_a=stats['test']['trackable_dimension:cross_object_order']['B']
    h4_rule=paired(x,other['frozen_rule'],main_predictions['B'])
    counts=test_track['trackable_dimension:event_count']
    h5_pair=paired(counts,guided_predictions['A'],guided_predictions['B'])
    h5_chance=bootstrap_accuracy(counts,guided_predictions['B'])
    h2_compatible=h2['mcnemar_exact_two_sided_p']>=.05 and h2['ci95_pp'][0]<=0<=h2['ci95_pp'][1]
    hypotheses=[
        dict(id='H1',conclusion='supported' if positive(h1) else 'not_supported',comparisons=dict(B_minus_A=h1)),
        dict(id='H2',conclusion='compatible_but_not_equivalence_proof' if h2_compatible else 'contradicted' if h2['mcnemar_exact_two_sided_p']<.05 else 'inconclusive',comparisons=dict(C_minus_A=h2)),
        dict(id='H3',conclusion='supported_non_superiority' if h3['ci95_pp'][1]<=0 else 'contradicted' if positive(h3) else 'inconclusive',comparisons=dict(D_minus_A=h3)),
        dict(id='H4',conclusion='supported' if positive(h4_a) and positive(h4_rule) else 'not_supported',comparisons=dict(B_minus_A=h4_a,B_minus_rule=h4_rule)),
        dict(id='H5',conclusion='supported' if positive(h5_pair) and h5_chance['accuracy']>.25 and h5_chance['exact_binomial_greater_than_chance_p']<.05 and h5_chance['ci95'][0]>.25 else 'not_supported',
             comparisons=dict(guided_B_minus_A=h5_pair),guided_B_vs_chance=h5_chance,
             strict_only_gain_is_evidence=False)]
    guided_pairs={}
    for scope,items in [('test_trackable',counts),('test_all',[q for q in scopes['test'] if q['format']=='numerical']),
                        ('full_trackable',[q for q in scopes['full'] if q['qa_id'] in trackable and q['format']=='numerical']),
                        ('full_all',[q for q in scopes['full'] if q['format']=='numerical'])]:
        guided_pairs[scope]={c:paired(items,guided_predictions['A'],guided_predictions[c]) for c in ('B','C','D')}
    write(ROOT/'results/stage4_paired_statistics.json',dict(generated_at=now(),
        hypotheses_preregistration_sha256=job['hypotheses_sha256'],comparisons=stats,
        hypotheses=hypotheses,guided_comparisons=guided_pairs,
        bootstrap=dict(unit='question',resamples=1000,seed=42,interval='percentile95'),
        p_values='Exact two-sided McNemar; one-sided exact binomial for H5 chance test. Holm adjusted for three primary aggregate pairs also provided.'))
    statrows=[]
    for scope,grouped in stats.items():
        for group,conditions in grouped.items():
            for condition,result in conditions.items():
                r=dict(scope=scope,group=group,reference='A',other=condition,**result)
                r['ci95_lower_pp'],r['ci95_upper_pp']=r.pop('ci95_pp')
                statrows.append(r)
    with (ROOT/'results/stage4_paired_statistics.csv').open('w',newline='') as stream:
        fields=list(dict.fromkeys(key for r in statrows for key in r))
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(statrows)
    availability,selected=examples(scopes,trackable,main_predictions)
    prereg=read(ROOT/'results/stage4_hypotheses_preregistered.json')
    d=read(ROOT/'results/stage4_D_assignments_locked.json')
    lengths=read(ROOT/'results/stage4_prompt_lengths.json')
    confusion=read(ROOT/'results/stage4/dev_count_rule_confusion.json')
    receipts=[read(ROOT/'logs'/f'stage4_{mode}_{c}_receipt.json') for mode in ('main','guided') for c in CONDITIONS]
    requested_n=4*749+4*300
    assert requested_n==sum(r['predictions'] for r in receipts)==4196
    stage4_end=datetime.fromisoformat(now())
    stage4_start=datetime.fromisoformat(d['created_at'])
    owned=[]
    for runtime_path in sorted((ROOT/'logs').glob('stage4_runtime_attempt*.json')):
        for server in read(runtime_path)['servers']:
            try:
                os.kill(server['pid'],0)
                owned.append(server['pid'])
            except ProcessLookupError:
                pass
    assert not owned,owned
    integrity_result=dict(status='PASS',checked_at=now(),expected_total=4196,predictions=integrity,
        all_unique=True,missing=0,immutable_locks_verified=True,frozen_config_sha256=job['frozen_config_sha256'],
        all_input_tokens_match_exact_processor_count=True,remaining_owned_server_pids=owned,
        hypotheses_registered_at=prereg['created_at'],D_registered_at=d['created_at'],
        first_inference_started_at=min(p['started_at'] for c in CONDITIONS for p in main_predictions[c].values()),
        supplemental_template_started=False,tracking_or_rules_modified=False)
    assert integrity_result['first_inference_started_at']>prereg['created_at'] and integrity_result['first_inference_started_at']>d['created_at']
    write(ROOT/'results/stage4_integrity.json',integrity_result)

    report=['# TOC-Bench 阶段四官方格式主实验','',f'完成时间：{stage4_end.isoformat()}。冻结配置v1保持不变；补充推理模板尚未运行。','',
        f"主分析为测试集可表达251题（主要四维231题、次要ReID20题）。A={pct(metrics['A']['test']['trackable'])}；B={pct(metrics['B']['test']['trackable'])}；B−A={primary['B']['effect_pp']:+.2f}个百分点，McNemar p={primary['B']['mcnemar_exact_two_sided_p']:.6g}，bootstrap95%CI [{primary['B']['ci95_pp'][0]:+.2f}, {primary['B']['ci95_pp'][1]:+.2f}]个百分点。",'',
        '所有主推理使用官方裸答案格式与官方解析。计数约束解码单列为诊断，不替代主分数。任何真值metadata均未进入模型输入；本文所有标签仅用于离线评分。','',
        '## 1. 推理前完成与锁定','',
        f"- 假设预登记时间：{prereg['created_at']}；[文件]({ROOT}/results/stage4_hypotheses_preregistered.json)，SHA256 `{job['hypotheses_sha256']}`。",
        f"- D一次性seed42分配时间：{d['created_at']}；[分配表]({ROOT}/results/stage4_D_assignments_locked.json)，SHA256 `{job['d_assignment_sha256']}`。",
        f"- 冻结配置SHA256 `{job['frozen_config_sha256']}`；切分与可表达清单保持原哈希。",
        '- 推理前已完成阶段二回退路由与开发集计数混淆矩阵；A完成后已以新A回退重算路由。路由只按covered标记，不依据答案合法性或对错回退。',
        f"- D共有899个视频—短语对：同短语异视频{d['method_counts']['different_video_same_exact_phrase']}，自身时间块置换{d['method_counts']['within_video_visible_and_gap_tile_permutation']}，文本与B相同{d['unchanged_pair_count']}。该部分不是有效的错误时间对照，削弱D对照的纯度。",
        '- D供体池使用全部冻结视频，排除本视频，仅按同一短语匹配，不读取标签；同一视频/短语的分配在所有题和两种解码下复用。',
        '- 无同短语供体时，将每条轨迹的可见跨度与空缺时间块置换，保留块内框/分数/相对时序，用冻结序列化器重算可见区间、首末与间断。空轨迹或单一整段块可能无法改变，原样记录。','',
        '## 2. 统一推理协议与完整性','',
        '- Qwen2.5-VL-7B-Instruct，独立vLLM0.16环境；两实例均BF16、TP1、max_model_len=65536、max_num_seqs8、batched_tokens32768、gpu_memory_utilization0.65、eager；所有条件同配置。',
        '- 官方floor(i*N/32)采样、长边720、JPEG85的缓存原字节；短视频仍按官方min(32,N)分支，不补帧或跳过。统一时间戳为官方索引/源fps，保留三位小数。',
        '- build_prompt原文不变，仅在帧后加时间戳、Question前加各自证据；temperature0、seed42，普通题64/排序256 token；checkpoint默认generation_config（repetition_penalty1.05）。',
        '- guided通过vLLM0.16的structured_outputs.choice实现，集合为2/3/4/5 or more，消息、图像、seed和token预算与同条件主推理一致。',
        '- 749题×4主条件 + 300题×4独立guided = 4196条唯一预测；无缺失、无重复。解析失败原始输出保留且计错。',
        f"- 所有4196条请求的vLLM实际输入token数与CPU处理器计数完全一致；[完整性]({ROOT}/results/stage4_integrity.json)。",
        f"- [统一协议]({ROOT}/results/stage4_protocol_locked.json)、[提示词]({ROOT}/results/stage4/prompts)、[原始预测目录]({ROOT}/results/stage4/predictions)。",'',
        '| 条件 | 主预测数 | 主解析失败 | 解析失败率 | guided预测数 | guided解析失败 |',
        '|---|---:|---:|---:|---:|---:|']
    for c in CONDITIONS:
        m=metrics[c]['full']['all']
        report.append(f"| {c} | 749 | {m['parse_failures']} | {100*m['parse_failure_rate']:.2f}% | 300 | {integrity['guided_'+c]['parse_failures']} |")
    report+=['','## 3. 主表：测试集可表达子集','',comparison_table(metrics,'test',True),'',
        '冻结规则的未覆盖题按错误计入分母。路由阶段二版本仅为无需新推理的历史对照；路由A版本使用同格式新A答案。ReID是次要维度，主要四维与五维合计同时列出。','',
        '规则在测试可表达子集的覆盖：'+ '；'.join(f"{LABELS[d]} {metrics['frozen_rule']['test']['trackable_dimension:'+d]['covered']}/{metrics['frozen_rule']['test']['trackable_dimension:'+d]['total']}" for d in DIMENSIONS)+'。','',
        '## 4. 预登记假设检验','',
        '按预登记：显著提升要求效应为正、双侧exact McNemar p<0.05且题级bootstrap下界>0。bootstrap为成对题级重采样1000次、seed42、百分位95%CI；不是视频聚类CI。各假设p值为未调整值，主聚合的三对比较另给Holm值。未检出差异不能证明等效。','',
        '| 假设 | 结论 | 比较 / 范围 | 效应（百分点） | McNemar p | bootstrap95%CI（百分点） |',
        '|---|---|---|---:|---:|---|']
    conclusion_cn=dict(supported='支持',not_supported='未获支持',compatible_but_not_equivalence_proof='相容，未证明等效',contradicted='反驳',
                       inconclusive='不确定',supported_non_superiority='支持未优于A')
    for h in hypotheses:
        for comparison,result in h['comparisons'].items():
            report.append(f"| {h['id']} | {conclusion_cn[h['conclusion']]} | {comparison}, n={result['n']} | {result['effect_pp']:+.2f} | {result['mcnemar_exact_two_sided_p']:.6g} | [{result['ci95_pp'][0]:+.2f}, {result['ci95_pp'][1]:+.2f}] |")
    report+=['',f"H5的B对随机25%：{h5_chance['correct']}/{h5_chance['n']}（{100*h5_chance['accuracy']:.2f}%），单侧exact binomial p={h5_chance['exact_binomial_greater_than_chance_p']:.6g}；B准确率bootstrap95%CI [{100*h5_chance['ci95'][0]:.2f}%, {100*h5_chance['ci95'][1]:.2f}%]。严格计数分数的单独提升不用于支持H5。",'',
        '主聚合251题的配对比较：','',
        '| 比较 | 其他对/A错 | 其他错/A对 | 效应（百分点） | exact p | Holm p（3对） | 95%CI（百分点） |',
        '|---|---:|---:|---:|---:|---:|---|']
    for c,r in primary.items():
        report.append(f"| {c}−A | {r['other_correct_reference_wrong']} | {r['other_wrong_reference_correct']} | {r['effect_pp']:+.2f} | {r['mcnemar_exact_two_sided_p']:.6g} | {r['holm_three_aggregate_comparisons_p']:.6g} | [{r['ci95_pp'][0]:+.2f}, {r['ci95_pp'][1]:+.2f}] |")
    report+=['','各维度的测试可表达成对比较：','',
        '| 维度 | 比较 | n | 效应（百分点） | exact McNemar p | 95%CI（百分点） |',
        '|---|---|---:|---:|---:|---|']
    for dim in DIMENSIONS:
        for c,r in stats['test']['trackable_dimension:'+dim].items():
            report.append(f"| {LABELS[dim]} | {c}−A | {r['n']} | {r['effect_pp']:+.2f} | {r['mcnemar_exact_two_sided_p']:.6g} | [{r['ci95_pp'][0]:+.2f}, {r['ci95_pp'][1]:+.2f}] |")
    report+=['',f'[全部范围与维度成对统计]({ROOT}/results/stage4_paired_statistics.json)；[CSV]({ROOT}/results/stage4_paired_statistics.csv)。','',
        '## 5. 计数诊断','',
        '合法答案比例按整个原始输出strip后是否精确属于合法集合计；官方严格准确率仍由官方extract/is_correct计算，二者分开。guided仅作分析。','',
        '| 范围 | 条件 | 严格正确 | 原始合法输出 | 合法比例 | guided正确 | guided合法比例 |',
        '|---|---|---|---:|---:|---|---:|']
    for scope,group,label in [('test','trackable_dimension:event_count','测试可表达81'),('test','dimension:event_count','测试全部Count242'),
                              ('full','trackable_dimension:event_count','全集可表达106（含开发）'),('full','dimension:event_count','全集Count300（含开发）')]:
        for c in CONDITIONS:
            m=metrics[c][scope][group];g=guided_metrics[c][scope][group]
            report.append(f"| {label} | {c} | {pct(m)} | {m['numerical_legal']}/{m['numerical_total']} | {100*m['numerical_legal_ratio']:.2f}% | {pct(g)} | {100*g['numerical_legal_ratio']:.2f}% |")
    report+=['','计数真值类别分布（只用于诊断，不进入提示词）：','',
        '| 范围 | 2 | 3 | 4 | 5 or more | 最频类别准确率 |',
        '|---|---:|---:|---:|---:|---:|']
    for label,items in [('测试可表达81',counts),('测试全部Count242',[q for q in scopes['test'] if q['format']=='numerical'])]:
        frequencies=Counter(str(q['correct_answer']) for q in items)
        report.append('| '+' | '.join([label]+[str(frequencies[c]) for c in LEGAL]+[f'{100*max(frequencies.values())/len(items):.2f}%'])+' |')
    report+=['','官方numerical提示词完整模板：','','```text',
        'You will see a video and a counting question. Output ONLY a single integer (e.g., 2, 3, 4) or the phrase "5 or more". No other words.',
        '','Question: {question}','Answer:','```','',
        '它以2/3/4为例、明确允许5 or more，但未明确排除0/1；主推理保留该原文。约束解码仅改变输出允许集合。','',
        '开发集冻结规则计数混淆矩阵（行真值、列原始规则预测；58题，未再次调参）：','',
        '| 真值 | 0 | 1 | 2 | 3 | 4 | 5 or more | 未覆盖 | 其他 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for gt in LEGAL:
        report.append('| '+' | '.join([gt]+[str(confusion['confusion_matrix'][gt][c]) for c in confusion['prediction_columns']])+' |')
    directions=confusion['error_direction']
    report+=['',f"规则覆盖25/58：同档正确{directions.get('same_bucket',0)}，低估{directions.get('undercount',0)}，高估{directions.get('overcount',0)}；未覆盖{directions.get('uncovered',0)}。在15个可判方向的覆盖错误中，低估9、高估6；两侧都有错误，小样本不能据此称为随机分布。5 or more为顶端合并档，同档不表示精确无界计数。",'',
        '## 6. 测试全集与附带全集结果','',
        '测试全部602题（包括轨迹不可直接表达的题）：','',comparison_table(metrics,'test',False),'',
        '以下全集含参与调参的开发集，只作附带，不替代测试主结果。','',
        '全集可表达324题：','',comparison_table(metrics,'full',True),'',
        '全集全部749题：','',comparison_table(metrics,'full',False),'',
        f'[全部模型、路由、范围与维度指标]({ROOT}/results/stage4_metrics.json)；[对比CSV]({ROOT}/results/stage4_comparison.csv)。','',
        '## 7. A/B 差异样例','',
        f'每维度先选测试集两个方向各最多5题；开发补充明确区分。完整问题、选项/事件、轨迹文本、A/B原始输出见 [样例全文]({ROOT}/results/stage4_AB_examples.md) 与 [JSON]({ROOT}/results/stage4_AB_examples.json)。不足的方向保留实际数量，不放宽标准。','',
        '| 维度 | 方向 | 测试可用 | 测试选取 | 开发补充 | 全集仍不足数 |',
        '|---|---|---:|---:|---:|---:|']
    for r in availability:
        report.append(f"| {LABELS[r['dimension']]} | {r['direction']} | {r['test_available']} | {r['test_selected']} | {r['dev_supplemental_selected']} | {r['shortage_after_full_supplement']} |")
    report+=['','## 8. 输入长度、资源与耗时','',
        '| 条件 | 完整输入中位数 | P95 | 最大token |',
        '|---|---:|---:|---:|']
    for c,v in lengths['distributions'].items():report.append(f"| {c} | {v['median']:.1f} | {v['p95']:.1f} | {v['maximum']} |")
    report+=['','所有输入连同64/256 token生成预算均低于65536，无截断。B轨迹文本本身P95=2068.6、最大3784token；冻结序列化保持不变。','',
        '| 阶段 | 新请求数 | 各条件本次墙钟合计（秒） |',
        '|---|---:|---:|']
    for mode in ('main','guided'):
        mode_receipts=[r for r in receipts if r['decoding']==mode]
        report.append(f"| {mode} | {sum(r['new_predictions'] for r in mode_receipts)} | {sum(r['elapsed_this_attempt_s'] for r in mode_receipts):.1f} |")
    report+=['',f"最终完整推理任务墙钟（含模型启动和停止）：{job['elapsed_s']:.1f}秒；本轮从D锁定至本报告：{(stage4_end-stage4_start).total_seconds():.1f}秒。若有失败恢复，原错误、有效预测和各attempt日志全部保留，最终回执的本次时间不包含旧attempt。",'',
        f"设备、UUID、共享前显存及服务器参数见 [运行日志目录]({ROOT}/logs) 的stage4_allocation/runtime文件；GPU内存峰值为每5秒NVML观测，区分本任务与整卡。",'']
    for path in sorted((ROOT/'logs').glob('stage4_gpu_memory_attempt*.json')):
        memory=read(path)
        for uid,v in memory.get('devices',{}).items():
            report.append(f"- {path.name} / {uid}：本任务峰值{v['own_peak_MiB']/1024:.2f}GiB，整卡峰值{v['total_peak_MiB']/1024:.2f}GiB（含共享任务）。")
    report+=['','本任务vLLM服务器已退出。冻结配置、分割、预登记可表达子集、假设和D分配哈希均复核一致。阶段四补充简短推理模板尚未运行；按要求在主实验汇报后停止，等待后续确认。']
    (ROOT/'results/stage4_main_report.md').write_text('\n'.join(report)+'\n')
    receipt=dict(status='STAGE4_MAIN_COMPLETE_STOP_BEFORE_SUPPLEMENT',completed_at=now(),
        report=str(ROOT/'results/stage4_main_report.md'),main_predictions=2996,guided_predictions=1200,
        primary_test_trackable={c:metrics[c]['test']['trackable'] for c in CONDITIONS},
        hypotheses=[dict(id=h['id'],conclusion=h['conclusion']) for h in hypotheses],
        frozen_config_unchanged=True,supplemental_template_started=False,missing_predictions=0,
        elapsed_inference_s=job['elapsed_s'],elapsed_from_preregistration_s=(stage4_end-stage4_start).total_seconds())
    write(ROOT/'results/stage4_main_receipt.json',receipt)
    with (ROOT/'research_log.md').open('a') as stream:
        stream.write('\n## '+now()+' — 阶段四官方主实验完成\n\n'
            f"- 四条件749题主推理与各300题guided计数诊断共4196条完整唯一预测；所有实际输入token与锁定CPU计数一致。冻结参数和标注无改动。\n"
            f"- 测试可表达251题：A {metrics['A']['test']['trackable']['correct']}、B {metrics['B']['test']['trackable']['correct']}、C {metrics['C']['test']['trackable']['correct']}、D {metrics['D']['test']['trackable']['correct']}题正确；B-A {primary['B']['effect_pp']:+.2f}pp，p={primary['B']['mcnemar_exact_two_sided_p']:.6g}。\n"
            '- 假设结论：'+'；'.join(h['id']+' '+h['conclusion'] for h in hypotheses)+'。\n'
            '- 已输出测试/全集、全集/可表达、各维度的规则与双版本路由对比、配对检验和完整证据样例。D不可改时间结构的36对原样单列。\n'
            '- 主实验完成后停止；补充简短推理模板与B2均未运行。\n')
    print(json.dumps(receipt,ensure_ascii=False))


if __name__=='__main__':
    main()
