"""Offline analysis of both complete six-condition Stage5 matrices."""
from collections import Counter
import csv
from datetime import datetime
import json
from pathlib import Path
import re

import numpy as np

from stage5_common import *
from stage5_scores import score,scoring_view,routing
from stage4_scores import inputs,groups,summarize,DIMENSIONS
from analyze_stage4 import paired,positive,holm,pct,LABELS
from compute_metrics import is_correct


def negative(stat):
    return stat['effect_pp']<0 and stat['mcnemar_exact_two_sided_p']<.05 and stat['ci95_pp'][1]<0


def table(metrics,template,scope,trackable):
    prefix='trackable_dimension:' if trackable else 'dimension:'
    aggregate='trackable' if trackable else 'all';main='main_trackable' if trackable else 'main'
    heading=['条件']+[LABELS[d] for d in DIMENSIONS]+['主要四维','五维合计']
    lines=['| '+' | '.join(heading)+' |','|'+'|'.join(['---']+['---:']*(len(heading)-1))+'|']
    for name in (*CONDITIONS,'frozen_rule','routing'):
        m=metrics[template][name][scope]
        cells=[pct(m[prefix+d]) for d in DIMENSIONS]+[pct(m[main]),pct(m[aggregate])]
        label='冻结规则（弃答计错）' if name=='frozen_rule' else '路由（本模板A回退）' if name=='routing' else name
        lines.append('| '+' | '.join([label]+cells)+' |')
    return '\n'.join(lines)


def collect_examples(scopes,trackable,predictions):
    prompts={p['qa_id']:p for p in rows(ROOT/'results/stage5/prompts/reasoning/B.jsonl')}
    selected=[];availability={}
    test=sorted([q for q in scopes['test'] if q['metadata']['dim']=='reappear_or_disappear'],key=lambda q:q['qa_id'])
    for wanted in (True,False):
        eligible=[q for q in test if is_correct(predictions[q['qa_id']]['extracted_answer'],q)==wanted]
        availability['correct' if wanted else 'wrong']=len(eligible)
        for q in eligible[:5]:
            qid=q['qa_id'];p=predictions[qid];prompt=prompts[qid]
            text=p['raw_response']
            selected.append(dict(qa_id=qid,video_id=q['video_id'],correct=wanted,trackable=qid in trackable,
                question=q['question'],option_A=q.get('option_A') or q.get('statement_A'),option_B=q.get('option_B') or q.get('statement_B'),
                truth=q['correct_answer'],prediction=p['extracted_answer'],parse_failed=p['extracted_answer'] is None,
                raw_model_output=text,track_text=prompt['track_text'],prompt_sha256=prompt['prompt_sha256'],
                visible_reference_indicators=dict(mentions_track_word=bool(re.search(r'\btrack(?:s|er|ing)?\b',text,re.I)),
                    explicit_track_ids=re.findall(r'\btrack\s*#?\s*(\d+)',text,re.I),
                    explicit_seconds=re.findall(r'\b\d+(?:\.\d+)?\s*(?:s|sec|seconds)\b',text,re.I))))
    write(ROOT/'results/stage5_reasoning_RD_examples.json',dict(generated_at=now(),
        selection='Preregistered first5 sorted held-out R/D correct and first5 wrong; no manual cherry picking.',
        availability=availability,examples=selected))
    lines=['# 简短推理模板B：R/D答对与答错样例','',
           '各取测试集按qa_id排序的前5条；保留完整输出和轨迹文本。文中是否引用证据及引用是否准确，在主报告中人工核对；不把模型写出的解释视为其内部机制的证明。','']
    for q in selected:
        lines += [f"## {'答对' if q['correct'] else '答错'}：{q['qa_id']}",'',f"视频：{q['video_id']}。问题：{q['question']}",'',
            f"A. {q['option_A']}",f"B. {q['option_B']}",'',f"真值：{q['truth']}；解析：{q['prediction']}；解析失败：{q['parse_failed']}。",'',
            '完整模型输出：','','```text',q['raw_model_output'],'```','','完整轨迹证据：','','```text',q['track_text'],'```','']
    (ROOT/'results/stage5_reasoning_RD_examples.md').write_text('\n'.join(lines)+'\n')
    return selected


def main():
    lock=verify_stage5();job=read(ROOT/'logs/stage5_job.json')
    assert job['status']=='COMPLETE'
    scopes,trackable=inputs();all_ids={q['qa_id'] for q in scopes['full']};numeric_ids={q['qa_id'] for q in scopes['full'] if q['format']=='numerical'}
    predictions={};guided={};integrity={};new_count=0;reuse_count=0
    for template in ('official','reasoning'):
        predictions[template]={};guided[template]={}
        for condition in CONDITIONS:
            reused=template=='official' and condition in ('A','B','C','D')
            for mode,target,ids in [('main',predictions,all_ids),('guided',guided,numeric_ids)]:
                path=(ROOT/'results/stage4'/f'{mode}_{condition}_predictions.jsonl' if reused else ROOT/'results/stage5'/f'{template}_{mode}_{condition}_predictions.jsonl')
                records=rows(path)
                assert len(records)==len({p['qa_id'] for p in records})==len(ids) and {p['qa_id'] for p in records}==ids
                if not reused:
                    prompts={p['qa_id']:p for p in rows(ROOT/'results/stage5/prompts'/template/f'{condition}.jsonl')}
                    for p in records:
                        assert p['error'] is None and p['hypotheses_sha256']==sha(ROOT/'results/stage5_hypotheses_preregistered.json')
                        assert p['representation_manifest_sha256']==sha(ROOT/'results/stage5_representations_locked.json')
                        assert p['prompt_sha256']==prompts[p['qa_id']]['prompt_sha256']
                        assert p['usage']['prompt_tokens']==prompts[p['qa_id']]['expected_prompt_tokens']
                        if template=='reasoning':assert final_answer(p['raw_response'],p['format'])==(p['extracted_answer'],p['final_answer_region'])
                    new_count+=len(records)
                else:reuse_count+=len(records)
                target[template][condition]={p['qa_id']:p for p in records}
                view=scoring_view(target[template][condition],template)
                numerical=[q for q in scopes['full'] if q['qa_id'] in ids and q['format']=='numerical']
                integrity[template+'_'+mode+'_'+condition]=dict(total=len(records),unique=len(records),missing=0,reused_stage4=reused,
                    source=str(path),sha256=sha(path),parse_failures=sum(p['extracted_answer'] is None for p in records),
                    finish_reasons=dict(Counter(p['finish_reason'] for p in records)),
                    numerical_legal=summarize(numerical,view)['numerical_legal'],
                    constraint_violations=sum(p.get('constraint_violation',False) for p in records),
                    completion_tokens=dict(median=float(np.percentile([p['usage']['completion_tokens'] for p in records if p['usage']['completion_tokens'] is not None],50)) if not reused else None,
                        p95=float(np.percentile([p['usage']['completion_tokens'] for p in records if p['usage']['completion_tokens'] is not None],95)) if not reused else None,
                        maximum=max(p['usage']['completion_tokens'] for p in records if p['usage']['completion_tokens'] is not None),
                        unavailable=sum(p['usage']['completion_tokens'] is None for p in records)))
    assert new_count==8392 and reuse_count==4196
    for f in read(ROOT/'results/stage5_stage4_reuse_locked.json')['files']:assert sha(f['path'])==f['sha256']
    rules={p['qa_id']:p for p in rows(ROOT/'results/v1_rule_predictions.jsonl')}
    metrics={};guided_metrics={};routes={}
    for template in ('official','reasoning'):
        routes[template]=routing(template)
        metrics[template]={c:score(predictions[template][c],template) for c in CONDITIONS}
        metrics[template]['frozen_rule']=score(rules,'official')
        metrics[template]['routing']=score(routes[template],template)
        guided_metrics[template]={}
        for c in CONDITIONS:
            view=scoring_view(guided[template][c],template)
            guided_metrics[template][c]={scope:{name:summarize([q for q in qa if q['format']=='numerical'],view)
                for name,qa in groups(items,trackable).items()} for scope,items in scopes.items()}
    write(ROOT/'results/stage5_metrics.json',dict(generated_at=now(),metrics=metrics,guided_metrics=guided_metrics,
        primary='test trackable251; main-four231 separately; R/D101',full_note='Includes prior tuning development set; supplemental.',
        legality='Reasoning: exact final Answer value membership; official: entire stripped response membership. Strict correctness always uses the preregistered template parser.'))
    comparison_rows=[]
    for template,conditions in metrics.items():
        for condition,scoped in conditions.items():
            for scope,grouped in scoped.items():
                for group,values in grouped.items():comparison_rows.append(dict(template=template,condition=condition,scope=scope,group=group,**values))
    with (ROOT/'results/stage5_comparison.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(comparison_rows[0]));writer.writeheader();writer.writerows(comparison_rows)
    stats={};h7_rows={};h8_rows={}
    for template in ('official','reasoning'):
        stats[template]={}
        for scope in ('test','full'):
            stats[template][scope]={}
            for group,qa in groups(scopes[scope],trackable).items():
                if not qa:continue
                by_a={c:paired(qa,predictions[template]['A'],predictions[template][c]) for c in CONDITIONS if c!='A'}
                rd=[q for q in qa if q['metadata']['dim']=='reappear_or_disappear']
                extra={}
                if rd:
                    extra=dict(main_minus_B=paired(rd,predictions[template]['B'],predictions[template]['B-main']),
                        events_minus_main=paired(rd,predictions[template]['B-main'],predictions[template]['B-events']),
                        events_minus_rule=paired(rd,rules,predictions[template]['B-events']))
                stats[template][scope][group]=dict(versus_A=by_a,RD_representation=extra)
        primary_rd=stats[template]['test']['trackable']['RD_representation']
        transitions=[primary_rd['main_minus_B'],primary_rd['events_minus_main']]
        observed=all(r['effect_pp']>=0 for r in transitions)
        conclusion='supported' if all(positive(r) for r in transitions) else 'contradicted' if any(negative(r) for r in transitions) else 'observed_monotonic_only' if observed else 'inconclusive'
        h7_rows[template]=dict(observed_monotonic=observed,conclusion=conclusion,comparisons={k:primary_rd[k] for k in ('main_minus_B','events_minus_main')})
        h8=primary_rd['events_minus_rule']
        h8_rows[template]=dict(observed_at_least_rule=h8['effect_pp']>=0,
            conclusion='supported' if positive(h8) else 'contradicted' if negative(h8) else 'inconclusive_noninferiority',comparison=h8)
    adjusted=holm({template+':'+name:value['mcnemar_exact_two_sided_p'] for template,row in h7_rows.items() for name,value in row['comparisons'].items()})
    for template,row in h7_rows.items():
        for name,value in row['comparisons'].items():value['holm_four_H7_p']=adjusted[template+':'+name]
    h6=stats['reasoning']['test']['trackable']['versus_A']['B']
    hypotheses=dict(H6=dict(conclusion='supported' if positive(h6) else 'not_supported',comparison=h6),H7=h7_rows,H8=h8_rows)
    write(ROOT/'results/stage5_hypothesis_tests.json',dict(generated_at=now(),hypotheses=hypotheses,all_comparisons=stats,
        bootstrap=dict(unit='question',resamples=1000,seed=42,interval='percentile95'),preregistered_sha256=sha(ROOT/'results/stage5_hypotheses_preregistered.json')))
    statrows=[]
    for template,scoped in stats.items():
        for scope,grouped in scoped.items():
            for group,tests in grouped.items():
                for reference,values in [('A',tests['versus_A']),('RD representation',tests['RD_representation'])]:
                    for comparison,result in values.items():
                        r=dict(template=template,scope=scope,group=group,reference=reference,comparison=comparison,**result)
                        r['ci95_lower_pp'],r['ci95_upper_pp']=r.pop('ci95_pp');statrows.append(r)
    with (ROOT/'results/stage5_paired_statistics.csv').open('w',newline='') as stream:
        fields=list(dict.fromkeys(k for r in statrows for k in r));writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(statrows)
    examples=collect_examples(scopes,trackable,predictions['reasoning']['B'])
    report=['# TOC-Bench：补充推理模板与表示梯度诊断','',f'统计完成时间：{now()}。冻结v1、既定视频切分与324题可表达清单保持不变。','',
        '## 1. 推理前预登记与运行范围','',
        f"H6–H8预登记时间：{read(ROOT/'results/stage5_hypotheses_preregistered.json')['created_at']}；SHA256 `{sha(ROOT/'results/stage5_hypotheses_preregistered.json')}`。",
        f"[预登记]({ROOT}/results/stage5_hypotheses_preregistered.json)、[表示锁定清单]({ROOT}/results/stage5_representations_locked.json)、[统一协议与解析]({ROOT}/results/stage5_protocol_locked.json)。",
        '六条件为A/B/C/D/B-main/B-events；两模板分别报告。官方A/B/C/D及其guided计数复用阶段四锁定结果；其余全部新跑。新增8392条、复用4196条，完整矩阵12588条（raw8988、guided3600）。',
        '主范围为测试可表达251题（四重点维度231、次要ReID20），测试全部602及全集749另报。全集含参与先前调参的开发集，只作附带。','',
        '## 2. 表示、提示词与解析','',
        'B-main直接调用冻结representative函数：选置信度总和最大的原生轨迹，按原几何条件贪心拼接不重叠碎片；用原序列化器输出一条主体链，注明涉及的原生ID和其他轨迹省略数。没有重新过滤或重跟踪。',
        'B-events调用同一冻结timeline：间断>0.5秒，消失时间为末次观测+0.2秒，重现取下一段首帧；末尾缺失>0.5秒才记终末消失。只给first appears/disappears/reappears/last seen、位置及原精度计算的0.05边缘布尔值；不写遮挡/离框结论、事件计数或选项映射。unsupported事件题也照常生成。',
        '简短推理模板采用原7.1系统提示词与各题型Think briefly/最后一行Answer指令，六条件max_tokens均1024。官方新增条件保留阶段四官方裸答案和64/256预算。32帧JPEG、时间戳、65536上下文及其他所有服务器参数与阶段四相同。',
        '推理模板只解析最后一个非空行的Answer:，字母/合法计数/完整排序必须满足锁定格式；不从解释或早期行回退找答案。官方仍用原extract。解析失败、截断或规则弃答均保留并计错。',
        '推理计数guided按用户确认保留自由推理，用单次structured_outputs.regex约束最终Answer数值；总预算1024，未完成的截断保留失败。官方计数仍用structured_outputs.choice。',
        '两模板对比同时改变系统/答案格式、推理预算等协议要素，不将跨模板差异唯一归因为模型内部推理。','']
    for template,label in [('official','官方裸答案模板'),('reasoning','简短推理模板')]:
        report += [f'## 3.{1 if template=="official" else 2} 主表：{label}，测试可表达251题','',table(metrics,template,'test',True),'']
    report += ['## 4. H6–H8检验','',
        'exact McNemar为双侧条件二项检验；配对题级bootstrap1000次、seed42、百分位95%CI。≥同时报告观察排序和统计不确定性，未预设不劣界值，因此未显著不等于证明不劣。','',
        '| 假设 | 模板 | 比较 | 结论 | 观察差值（百分点） | exact p | 95%CI（百分点） |',
        '|---|---|---|---|---:|---:|---|']
    labels=dict(supported='支持',not_supported='未获支持',contradicted='反驳',observed_monotonic_only='观察单调，统计支持未充分',inconclusive='不确定',inconclusive_noninferiority='不劣仍不确定')
    def statline(hid,template,name,conclusion,r):
        return f"| {hid} | {template} | {name}, n={r['n']} | {labels[conclusion]} | {r['effect_pp']:+.2f} | {r['mcnemar_exact_two_sided_p']:.6g} | [{r['ci95_pp'][0]:+.2f}, {r['ci95_pp'][1]:+.2f}] |"
    report.append(statline('H6','推理','B−A',hypotheses['H6']['conclusion'],h6))
    for template,row in h7_rows.items():
        for name,r in row['comparisons'].items():report.append(statline('H7',template,name,row['conclusion'],r))
    for template,row in h8_rows.items():report.append(statline('H8',template,'B-events−冻结规则',row['conclusion'],row['comparison']))
    report += ['',f'[全部检验及范围]({ROOT}/results/stage5_hypothesis_tests.json)；[成对CSV]({ROOT}/results/stage5_paired_statistics.csv)。H7四个相邻比较的Holm校正p同时保存在JSON。','',
        '## 5. 计数严格口径、合法率与约束解码','',
        '| 模板 | 范围 | 条件 | 严格正确 | 最终答案合法比例 | 约束解码正确 | 约束合法比例 |',
        '|---|---|---|---|---:|---|---:|']
    for template in ('official','reasoning'):
        for scope,group,label in [('test','trackable_dimension:event_count','测试可表达81'),('test','dimension:event_count','测试全部242'),
                                  ('full','trackable_dimension:event_count','全集可表达106（含开发）'),('full','dimension:event_count','全集300（含开发）')]:
            for c in CONDITIONS:
                raw=metrics[template][c][scope][group];con=guided_metrics[template][c][scope][group]
                report.append(f"| {template} | {label} | {c} | {pct(raw)} | {raw['numerical_legal']}/{raw['numerical_total']} ({100*raw['numerical_legal_ratio']:.2f}%) | {pct(con)} | {con['numerical_legal']}/{con['numerical_total']} ({100*con['numerical_legal_ratio']:.2f}%) |")
    report += ['','官方合法率按整个strip输出计，推理模板按最后Answer值计；不是用推理正文中的数字凑合法答案。两套guided结果保持独立诊断地位。','',
        '## 6. 整幅画面疑似误检（仅描述）','',
        '对B保留的原生轨迹，若某观测框中心x/y均距0.50不超过0.05，且框面积≥画面80%，记为疑似整幅框观测。报告至少一次与至少半数观测触发的轨迹比例；不是经真值确认的误检率。按维度去重(video,query,native ID)，跨维度可能重复。此统计未用于任何删除或调参。','',
        '| 维度 | 原生轨迹 | 至少一次触发 | 比例 | 半数以上触发 | 比例 | 观测触发比例 |',
        '|---|---:|---:|---:|---:|---:|---:|']
    descriptive=read(ROOT/'results/stage5_full_frame_track_descriptives.json')
    for name,r in [('overall',descriptive['overall']),*descriptive['per_dimension'].items()]:
        report.append(f"| {name} | {r['retained_native_tracks']} | {r['any_suspicious']} | {100*r['any_ratio']:.2f}% | {r['majority_suspicious']} | {100*r['majority_ratio']:.2f}% | {100*r['observation_ratio']:.2f}% |")
    report += ['','## 7. 测试全部题与附带全集','']
    for template in ('official','reasoning'):
        for scope,subset,label in [('test',False,'测试全部602'),('full',True,'全集可表达324（含开发）'),('full',False,'全集749（含开发）')]:
            report += [f'### {template} / {label}','',table(metrics,template,scope,subset),'']
    report += ['## 8. 推理B的R/D样例','',
        f'按预登记先选测试R/D答对和答错各5题，共{len(examples)}题。完整可见推理过程、选项、答案和轨迹文本见 [样例全文]({ROOT}/results/stage5_reasoning_RD_examples.md) 和 [JSON]({ROOT}/results/stage5_reasoning_RD_examples.json)。人工引用核查在最终复核后附于本报告。','',
        '## 9. 完整性、长度与耗时','',
        '| 模板 | 条件 | raw解析失败/749 | raw截断 | guided解析失败/300 | guided截断 | raw生成token P95 |',
        '|---|---|---:|---:|---:|---:|---:|']
    for template in ('official','reasoning'):
        for c in CONDITIONS:
            r=integrity[template+'_main_'+c];g=integrity[template+'_guided_'+c]
            report.append(f"| {template} | {c} | {r['parse_failures']} | {r['finish_reasons'].get('length',0)} | {g['parse_failures']} | {g['finish_reasons'].get('length',0)} | {r['completion_tokens']['p95'] if r['completion_tokens']['p95'] is not None else '阶段四复用'} |")
    report += ['','所有新请求实际输入token均与推理前锁定的处理器计数一致，完整输入加生成预算均≤65536。每个template/condition/decoding/qa_id恰一条预测，缺失0、重复0；所有失败输出仍在原始记录中。','',
        '| 分组 | 请求数 | 各条件墙钟合计（分钟） |',
        '|---|---:|---:|']
    receipts=[]
    for template,conditions in [('official',NEW_OFFICIAL),('reasoning',CONDITIONS)]:
        for mode in ('main','guided'):
            subset=[read(ROOT/'logs'/f'stage5_{template}_{mode}_{c}_receipt.json') for c in conditions];receipts+=subset
            report.append(f"| {template}/{mode} | {sum(r['predictions'] for r in subset)} | {sum(r['elapsed_this_attempt_s'] for r in subset)/60:.2f} |")
    report += ['',f"最终完整推理attempt墙钟（含GPU资源等待、模型启动/停止）：{job['elapsed_s']/60:.2f}分钟。此前失败/等待记录保留在logs/stage5_job_attempt*.json及执行日志中；未改服务配置。",'']
    for path in sorted((ROOT/'logs').glob('stage5_gpu_memory_attempt*.json')):
        memory=read(path)
        for uid,r in memory.get('devices',{}).items():report.append(f"- {path.name} / {uid}：本任务观测峰值{r['own_peak_MiB']/1024:.2f}GiB，整卡{r['total_peak_MiB']/1024:.2f}GiB（含其他任务）。")
    report += ['',f'[全部指标]({ROOT}/results/stage5_metrics.json)、[对比CSV]({ROOT}/results/stage5_comparison.csv)。','',
        '本轮全部表示与解析在推理前固定；原冻结配置、标注、D分配和可表达清单保持不变。待完成10条可见推理引用的人工复核后停止汇报，不追加调参。']
    (ROOT/'results/stage5_report.md').write_text('\n'.join(report)+'\n')
    write(ROOT/'results/stage5_integrity.json',dict(status='PASS',checked_at=now(),new_predictions=new_count,reused_predictions=reuse_count,
        total_matrix_predictions=new_count+reuse_count,missing=0,duplicate=0,records=integrity,
        hypotheses_sha256=sha(ROOT/'results/stage5_hypotheses_preregistered.json'),
        representations_sha256=sha(ROOT/'results/stage5_representations_locked.json'),frozen_config_sha256=lock['frozen_config_sha256'],
        actual_input_tokens_match_locked_counts=True,all_original_stage4_predictions_unchanged=True,manual_reasoning_review_pending=True))
    write(ROOT/'results/stage5_analysis_receipt.json',dict(status='ANALYZED_PENDING_10_EXAMPLE_MANUAL_REVIEW',at=now(),hypotheses=hypotheses,
        new_predictions=new_count,reused_predictions=reuse_count,report=str(ROOT/'results/stage5_report.md'),examples=len(examples)))
    print(json.dumps(dict(status='ANALYZED_PENDING_MANUAL_REVIEW',hypotheses=hypotheses,
        reasoning_primary={c:metrics['reasoning'][c]['test']['trackable'] for c in CONDITIONS}),ensure_ascii=False))


if __name__=='__main__':main()
