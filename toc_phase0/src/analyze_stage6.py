"""Offline registered scoring, tool-use summaries and reproducible full interactions."""
from collections import Counter
from datetime import datetime
import csv
import json
import os
from pathlib import Path

from stage6_common import *
from stage4_scores import inputs,groups,summarize,DIMENSIONS
from analyze_stage4 import paired,holm
from compute_metrics import is_correct

LABELS=dict(event_count='Count',reappear_or_disappear='R/D',cross_object_order='X-Order',event_ordering='Order',reappear_identity='ReID')


def load(path,expected=None):
    values=rows(path);result={p['qa_id']:p for p in values}
    assert len(values)==len(result),path
    if expected is not None:assert set(result)==set(expected),(str(path),len(result),len(expected))
    return result


def final_view(predictions):
    return {qid:dict(p,raw_response=p.get('final_answer_region')) for qid,p in predictions.items()}


def condition_metrics(items,trackable,predictions,reasoning=True):
    view=final_view(predictions) if reasoning else predictions
    return {group:summarize(qs,view) for group,qs in groups(items,trackable).items()}


def tool_stats(predictions,qids):
    ps=[predictions[qid] for qid in sorted(qids)]
    calls=[c for p in ps for c in p['tool_calls']]
    legal=[c for c in calls if c['result']['legal']]
    matched=[c for c in legal if c['result']['matched']]
    uses=Counter(c['result']['name'] for c in legal)
    n=len(ps);ncalled=sum(bool(p['tool_calls']) for p in ps)
    nlook=sum(any(c['result']['legal'] and c['result']['name']=='look' for c in p['tool_calls']) for p in ps)
    return dict(questions=n,questions_with_call=ncalled,call_rate=ncalled/n if n else None,
        attempts=len(calls),legal_calls=len(legal),legal_call_rate=len(legal)/len(calls) if calls else None,
        mean_calls_all=len(calls)/n if n else None,mean_calls_called=len(calls)/ncalled if ncalled else None,
        matched_calls=len(matched),object_unmatched=len(legal)-len(matched),
        object_unmatched_rate=(len(legal)-len(matched))/len(legal) if legal else None,
        tool_counts={name:uses[name] for name in ['track','events','look']},
        tool_shares={name:uses[name]/len(legal) if legal else None for name in ['track','events','look']},
        questions_with_look=nlook,look_question_rate=nlook/n if n else None,
        generated_tokens_total=sum(p['total_generated_tokens'] for p in ps),
        mean_generated_tokens=sum(p['total_generated_tokens'] for p in ps)/n if n else None,
        budget_exhausted=sum(p['budget_exhausted'] for p in ps),
        final_turn_rejected_extra_call=sum('rejected_after_call_budget' in p for p in ps))


def pct(x):return '—' if x is None else f'{100*x:.2f}%'


def table(metrics,order,group='trackable'):
    lines=['| 条件 | Count | R/D | X-Order | Order | ReID | 合计 |','|---|---:|---:|---:|---:|---:|---:|']
    prefix='trackable_dimension:' if group=='trackable' else 'dimension:'
    for name in order:
        cells=[f'{metrics[name][prefix+dim]["correct"]}/{metrics[name][prefix+dim]["total"]} ({pct(metrics[name][prefix+dim]["accuracy"])})' for dim in DIMENSIONS]
        total=metrics[name][group]
        lines.append('| '+name+' | '+' | '.join(cells)+f' | {total["correct"]}/{total["total"]} ({pct(total["accuracy"])}) |')
    return lines


def examples(conditions,items,predictions):
    rd=[q for q in items if q['metadata']['dim']=='reappear_or_disappear'];result=[]
    lines=['# 阶段六 R/D 完整交互抽查','',
        '选样固定为每个条件按qa_id排序的前3条正确、前3条错误，解析失败属于错误。逐题JSON保留完整messages、32帧路径、全部工具返回与生成用量。',
        'T1及其对照的固定开发示范前缀见[锁定文件](/data2/user/toc_phase0/results/stage6_demonstrations_locked.json)；下文展示该前缀之后的实际题目交互。','']
    for condition in conditions:
        ps=predictions[condition]
        for correct in [True,False]:
            chosen=[q for q in rd if is_correct(ps[q['qa_id']]['extracted_answer'],q)==correct][:3]
            for q in chosen:
                p=ps[q['qa_id']];path=ROOT/'results/stage6/predictions/main'/condition/f'{q["qa_id"]}.json'
                result.append(dict(condition=condition,qa_id=q['qa_id'],video_id=q['video_id'],correct=correct,
                    truth=q.get('correct_answer'),prediction=p['extracted_answer'],record_path=str(path),record_sha256=sha(path)))
                lines += [f'## {condition} / {q["qa_id"]} / '+('正确' if correct else '错误'),'',
                    f'视频：{q["video_id"]}；真值：{q.get("correct_answer")}；解析：{p["extracted_answer"]}；[完整JSON]({path})。','']
                messages=p['messages']
                if condition!='LoRA-B-events':
                    base='T-none' if condition=='T-none' else read(ROOT/'results/stage6_controls_decision_locked.json')['best'] if condition in ['T-ph','T-sh'] else condition
                    prompt=next(x for x in rows(ROOT/'results/stage6/prompts'/f'{base}.jsonl') if x['qa_id']==q['qa_id'])
                    # System and fixed demonstrations are fully preserved in JSON; avoid reprinting five examples for every case.
                    messages=[messages[0]]+messages[len(prompt['messages'])-1:]
                for message in messages:
                    lines += ['**'+message['role']+'**','']
                    content=message['content']
                    if isinstance(content,str):lines += ['```text',content,'```','']
                    else:
                        image_blocks=[b for b in content if b['type']=='image_path']
                        if len(image_blocks)==32:lines+=['原始32帧的文件顺序及路径完整保存在逐题JSON中。','']
                        else:
                            for image_block in image_blocks:lines += [f'[工具图像]({image_block["path"]})','']
                        for block in content:
                            if block['type']=='text':lines+=['```text',block['text'],'```','']
    write(ROOT/'results/stage6_RD_interactions.json',dict(created_at=now(),selection='first3 sorted correct and first3 sorted wrong per active condition',records=result))
    (ROOT/'results/stage6_RD_interactions.md').write_text('\n'.join(lines)+'\n')
    return result


def main():
    verify_stage5();protocol=read(ROOT/'results/stage6_protocol_locked.json');h=read(ROOT/'results/stage6_hypotheses_preregistered.json')
    for name,digest_ in protocol['source_sha256'].items():assert sha(ROOT/'src'/name)==digest_
    sc,trackable=inputs();test=sc['test'];test_ids={q['qa_id'] for q in test};primary=[q for q in test if q['qa_id'] in trackable]
    primary_ids={q['qa_id'] for q in primary};rd=[q for q in primary if q['metadata']['dim']=='reappear_or_disappear']
    nums={q['qa_id'] for q in test if q['format']=='numerical'}
    decision=read(ROOT/'results/stage6_controls_decision_locked.json')
    conditions=['T-none','T0','T1']+(['T-ph','T-sh'] if decision['run_controls'] else [])
    preds={c:load(ROOT/'results/stage6'/f'main_{c}_predictions.jsonl',test_ids) for c in conditions}
    guided={c:load(ROOT/'results/stage6'/f'guided_{c}_predictions.jsonl',nums) for c in conditions}
    preds['Official A']=load(ROOT/'results/stage4/main_A_predictions.jsonl')
    preds['Frozen rule']=load(ROOT/'results/v1_rule_predictions.jsonl')
    preds['Route']=load(ROOT/'results/stage5/official_routing_predictions.jsonl')
    order=conditions+['Official A','Route','Frozen rule']
    metrics={c:condition_metrics(test,trackable,p,c in conditions) for c,p in preds.items()}
    guided_items=[q for q in test if q['format']=='numerical']
    guided_metrics={c:condition_metrics(guided_items,trackable,p) for c,p in guided.items()}
    assert metrics['Official A']['trackable']['correct']==89 and metrics['Route']['trackable']['correct']==112
    assert metrics['Frozen rule']['trackable_dimension:reappear_or_disappear']['correct']==51
    stats={}
    for scope,items in [('test_trackable',primary),('test_all',test)]:
        stats[scope]={}
        comps=[('H9_T0_minus_A','Official A','T0'),('H10_T1_minus_T0','T0','T1'),
               ('T0_minus_Tnone','T-none','T0'),('T1_minus_Tnone','T-none','T1'),
               ('T0_minus_route','Route','T0'),('T1_minus_route','Route','T1')]
        if decision['run_controls']:comps += [('best_minus_placeholder','T-ph',decision['best']),('best_minus_shuffled','T-sh',decision['best'])]
        for name,ref,other in comps:
            stats[scope][name]=dict(all=paired(items,preds[ref],preds[other]),
                dimensions={d:paired([q for q in items if q['metadata']['dim']==d],preds[ref],preds[other]) for d in DIMENSIONS})
    adjusted=holm({k:stats['test_trackable'][k]['all']['mcnemar_exact_two_sided_p'] for k in ['H9_T0_minus_A','H10_T1_minus_T0']})
    hypotheses={}
    for hid,key in [('H9','H9_T0_minus_A'),('H10','H10_T1_minus_T0')]:
        st=stats['test_trackable'][key]['all'];positive=st['effect_pp']>0 and st['mcnemar_exact_two_sided_p']<.05 and st['ci95_pp'][0]>0
        hypotheses[hid]=dict(conclusion='supported' if positive else 'not_supported',comparison=st,holm_two_p=adjusted[key])
    before=load(ROOT/'results/stage5/reasoning_main_B-events_predictions.jsonl')
    after=load(ROOT/'results/stage6/main_LoRA-B-events_predictions.jsonl',primary_ids)
    learning={c:condition_metrics(primary,trackable,p,c!='Frozen rule') for c,p in [('Before B-events',before),('After LoRA B-events',after),('Frozen rule',preds['Frozen rule'])]}
    prepost={name:paired(qs,before,after) for name,qs in [('all',primary)]+[(d,[q for q in primary if q['metadata']['dim']==d]) for d in DIMENSIONS]}
    vsrule=paired(rd,preds['Frozen rule'],after)
    rd_correct=learning['After LoRA B-events']['dimension:reappear_or_disappear']['correct']
    hypotheses['H11']=dict(conclusion='empirical_target_reached' if rd_correct>=45 else 'empirical_target_not_reached',
        target=45,observed=rd_correct,n=101,before_correct=29,rule_correct=51,
        before_after=prepost['reappear_or_disappear'],after_minus_rule=vsrule)
    use={c:{scope:tool_stats(preds[c],qids) for scope,qids in [('test_all',test_ids),('test_trackable',primary_ids)]} for c in conditions}
    use_guided={c:tool_stats(guided[c],nums) for c in conditions}
    write(ROOT/'results/stage6_metrics.json',dict(created_at=now(),conditions=conditions,metrics=metrics,guided=guided_metrics,
        learning=learning,controls_decision=decision,scope='test602 and primary trackable251; no development evaluation inference'))
    write(ROOT/'results/stage6_hypothesis_tests.json',dict(created_at=now(),hypotheses=hypotheses,paired=stats,learning_prepost=prepost))
    write(ROOT/'results/stage6_tool_usage.json',dict(created_at=now(),definitions=dict(call_rate='QA with any attempted tagged call /allQA',
         legal_call_rate='documented name and valid argument signature with tools available /all attempts; unmatched valid names remain legal',
         unmatched='unmatched object phrases /legal calls; no fuzzy matching',tool_shares='legal requests by tool /all legal requests',
         look_rate='QA with legal look call /allQA'),main=use,guided=use_guided))
    example_ps={c:preds[c] for c in conditions};example_ps['LoRA-B-events']=after
    selected=examples(conditions+['LoRA-B-events'],test,example_ps)
    raw_counts={};completion=[]
    for mode,collection in [('main',{c:preds[c] for c in conditions}),('guided',guided)]:
        for condition,ps in collection.items():
            for qid,p in ps.items():
                assert p['total_generated_tokens']==sum(t['usage']['completion_tokens'] for t in p['turns'])<=2048
                assert p['call_attempts']==len(p['tool_calls'])<=4 and len(p['turns'])<=5
                images=sum(b['type']=='image_path' for m in p['messages'] if isinstance(m['content'],list) for b in m['content'])
                assert 32<=images<=40
                assert p['hypotheses_sha256']==sha(ROOT/'results/stage6_hypotheses_preregistered.json')
                assert p['protocol_sha256']==sha(ROOT/'results/stage6_protocol_locked.json')
                for t in p['turns']:
                    if t.get('physical_requests'):
                        for request in t['physical_requests']:assert request['usage']['prompt_tokens']+request['max_tokens']<=65536
                    else:assert t['usage']['prompt_tokens']+t['max_tokens']<=65536
            raw_counts[mode+'/'+condition]=dict(n=len(ps),parse_failures=sum(p['extracted_answer'] is None for p in ps.values()),
                budget_exhausted=sum(p['budget_exhausted'] for p in ps.values()),max_generated=max(p['total_generated_tokens'] for p in ps.values()),
                max_turns=max(len(p['turns']) for p in ps.values()),max_calls=max(p['call_attempts'] for p in ps.values()))
            completion += [p['started_at'] for p in ps.values()]
    for p in after.values():assert p['max_tokens']==1024 and p['usage']['prompt_tokens']+1024<=65536
    raw_counts['main/LoRA-B-events']=dict(n=len(after),parse_failures=sum(p['extracted_answer'] is None for p in after.values()),
                                        truncated=sum(p['finish_reason']=='length' for p in after.values()))
    train=read(ROOT/'results/stage6_training_receipt.json');assert train['epochs']>=2-1e-6 and train['train_examples']==2000
    assert sha(Path(train['adapter_path'])/'adapter_model.safetensors')==train['adapter_sha256']
    guidance_fix=read(ROOT/'results/stage6_final_field_guidance_v2_locked.json')
    for preserved in guidance_fix['primary_and_training_reused'].values():assert sha(preserved['path'])==preserved['sha256']
    assert datetime.fromisoformat(h['created_at'])<min(datetime.fromisoformat(t) for t in completion)
    state=read(ROOT/'logs/stage6_job.json');assert state['status']=='COMPLETE'
    jobs=[read(path) for path in sorted((ROOT/'logs').glob('stage6_job_attempt*.json'))]
    remaining=[];runtimes=[]
    for pattern in ['stage6_runtime_base_attempt*.json','stage6_runtime_lora_attempt*.json','stage6_runtime_training_attempt*.json']:
        for path in sorted((ROOT/'logs').glob(pattern)):
            d=read(path);runtimes.append(dict(path=str(path),**d))
            try:os.kill(d['pid'],0);remaining.append(d['pid'])
            except ProcessLookupError:pass
    assert not remaining,('Task-owned processes still exist',remaining)
    latest_time=max(datetime.fromisoformat(p['completed_at']) for c in conditions for p in preds[c].values())
    latest_time=max(latest_time,max(datetime.fromisoformat(p['completed_at']) for c in conditions for p in guided[c].values()))
    latest_time=max(latest_time,max(datetime.fromisoformat(p['completed_at']) for p in after.values()))
    latest_time=max(latest_time,datetime.fromisoformat(state['updated_at']))
    elapsed=(latest_time-datetime.fromisoformat(h['created_at'])).total_seconds()
    integrity=dict(checked_at=now(),status='PASS',missing=0,duplicates=0,conditions=conditions,counts=raw_counts,
        total_unique_new_predictions=sum(len(preds[c]) for c in conditions)+sum(len(guided[c]) for c in conditions)+len(after),
        hypotheses_sha256=sha(ROOT/'results/stage6_hypotheses_preregistered.json'),protocol_sha256=sha(ROOT/'results/stage6_protocol_locked.json'),
        frozen_config_sha256=sha(ROOT/'results/frozen_config_v1.json'),split_sha256=sha(ROOT/'results/dev_test_split_locked.json'),
        trackable_sha256=sha(ROOT/'results/trackable_subset_preregistered.json'),demonstrations_sha256=sha(ROOT/'results/stage6_demonstrations_locked.json'),
        training_receipt=train,runtimes=runtimes,remaining_task_owned_pids=remaining,total_elapsed_s=elapsed,jobs=jobs,
        examples=len(selected),no_tracking_rerun=True,no_frozen_changes=True,
        final_field_guidance_sha256=sha(ROOT/'results/stage6_final_field_guidance_v2_locked.json'),
        original_auxiliary_records_archived=guidance_fix['original_diagnostic_records'],primary_and_training_sha256_unchanged=True)
    write(ROOT/'results/stage6_integrity.json',integrity)
    with (ROOT/'results/stage6_comparison.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['condition','scope','dimension','n','correct','accuracy','parse_failures']);writer.writeheader()
        for c in order:
            for group in ['trackable','all']:
                for dim in ['all',*DIMENSIONS]:
                    key=group if dim=='all' else ('trackable_dimension:' if group=='trackable' else 'dimension:')+dim;m=metrics[c][key]
                    writer.writerow(dict(condition=c,scope=group,dimension=dim,n=m['total'],correct=m['correct'],accuracy=m['accuracy'],parse_failures=m['parse_failures']))
    lines=['# TOC-Bench 阶段六：零训练工具调用与可学性检验','',
        f'已完成，停止后续实验。冻结v1、视频切分和可表达清单未改；主范围测试可表达251题，工具实验覆盖测试全部602题。预登记时间：{h["created_at"]}。','',
        f'[H9–H11预登记]({ROOT/"results/stage6_hypotheses_preregistered.json"}) SHA256 `{sha(ROOT/"results/stage6_hypotheses_preregistered.json")}`。',
        f'[工具与提示词协议]({ROOT/"results/stage6_protocol_locked.json"}) SHA256 `{sha(ROOT/"results/stage6_protocol_locked.json")}`。','',
        '## 主表：测试可表达251题','']+table(metrics,order)+['',
        'Official A、路由和冻结规则复用已有结果。路由固定为规则覆盖时用规则，未覆盖时用官方A；工具条件没有规则答案输入。',
        'H9跨模板比较官方A，因此还报告同模板T-none以识别提示词变化。条件对照只按预登记门槛触发，没有根据测试结果调参。','',
        '## H9–H11','',
        '| 假设/比较 | 判定 | 差值（百分点） | exact McNemar p | bootstrap95%CI（百分点） |',
        '|---|---|---:|---:|---|']
    for hid in ['H9','H10']:
        value=hypotheses[hid];s=value['comparison'];lines.append(f'| {hid} | {value["conclusion"]} | {s["effect_pp"]:+.2f} | {s["mcnemar_exact_two_sided_p"]:.6g} | [{s["ci95_pp"][0]:+.2f}, {s["ci95_pp"][1]:+.2f}] |')
    for name,s in [('H11: LoRA−微调前',prepost['reappear_or_disappear']),('H11: LoRA−规则',vsrule)]:
        lines.append(f'| {name} | {hypotheses["H11"]["conclusion"]} | {s["effect_pp"]:+.2f} | {s["mcnemar_exact_two_sided_p"]:.6g} | [{s["ci95_pp"][0]:+.2f}, {s["ci95_pp"][1]:+.2f}] |')
    lines += ['',f'H11观察终点：{rd_correct}/101，预设门槛45/101，微调前29/101，规则51/101。门槛判断为经验计数；未把达到门槛解释为总体准确率的置信下界。',
        'exact McNemar双侧；配对题级bootstrap1000次，seed42、排序qa_id。H9/H10的Holm校正p及各维度、测试全部题比较见[统计JSON]('+str(ROOT/'results/stage6_hypothesis_tests.json')+')。','',
        '## 同模板比较与工具事实对照','',f'触发决策：`{json.dumps(decision,ensure_ascii=False)}`。','',
        '| 比较，测试可表达251题 | 差值（百分点） | exact p | 95%CI |','|---|---:|---:|---|']
    for key in ['T0_minus_Tnone','T1_minus_Tnone','T0_minus_route','T1_minus_route']+(['best_minus_placeholder','best_minus_shuffled'] if decision['run_controls'] else []):
        s=stats['test_trackable'][key]['all'];lines.append(f'| {key} | {s["effect_pp"]:+.2f} | {s["mcnemar_exact_two_sided_p"]:.6g} | [{s["ci95_pp"][0]:+.2f}, {s["ci95_pp"][1]:+.2f}] |')
    lines += ['', '## 工具使用统计','',
        '下表为测试602题的非约束主运行；调用包含非法尝试，合法签名但物体未匹配单列。平均次数以全部题为分母；工具占比以合法调用为分母。',
        '| 条件 | 调用率 | 合法调用率 | 平均次数 | track/events/look | 物体未匹配 | 使用look的题比例 |','|---|---:|---:|---:|---|---:|---:|']
    for c in conditions:
        u=use[c]['test_all'];lines.append(f'| {c} | {pct(u["call_rate"])} | {pct(u["legal_call_rate"])} | {u["mean_calls_all"]:.3f} | '+ '/'.join(pct(u['tool_shares'][name]) for name in ['track','events','look'])+f' | {pct(u["object_unmatched_rate"])} | {pct(u["look_question_rate"])} |')
    lines += ['', '[可表达子集与约束解码调用统计]('+str(ROOT/'results/stage6_tool_usage.json')+')。',
        'track/events仅查询锁定v1结果，look使用5fps视频与主体框；规范化精确匹配，无模糊匹配。D对照使用阶段四已锁分配；899个重建D文档与原D文本逐字一致。','',
        '## 计数严格口径、合法率与仅最终答案约束','',
        '| 条件 | 范围 | 严格正确 | 严格合法率 | 约束正确 | 约束合法率 |','|---|---|---:|---:|---:|']
    for c in conditions:
        for scope,key in [('测试可表达81','trackable_dimension:event_count'),('测试全部242','dimension:event_count')]:
            raw=metrics[c][key];g=guided_metrics[c][key]
            lines.append(f'| {c} | {scope} | {raw["correct"]}/{raw["total"]} ({pct(raw["accuracy"])}) | {pct(raw["numerical_legal_ratio"])} | {g["correct"]}/{g["total"]} ({pct(g["accuracy"])}) | {pct(g["numerical_legal_ratio"])} |')
    lines += ['', '有效修正版使用两段生成：工具与推理保持普通自由解码及原EOS；出现Answer:后，续写同一assistant消息，只把最终数值限制为2/3/4/5 or more。两段实际completion用量合计仍受2048约束；所有物理请求的原文、用量和ID均保留。数值续写阶段沿用额外EOS屏蔽。截断和解析失败均计错，不从分母移除。','',
        '## 可学性：纯合成LoRA前后','']+table(learning,['Before B-events','After LoRA B-events','Frozen rule'])
    lines += ['',f'训练耗时 {train["elapsed_s"]/60:.2f}分钟；rank8、2epoch，最终步数{train["global_step"]}。2000条全部纯合成（R/D800、X-Order600、Count600），无任何基准标签；固定取第二轮最终适配器，没有基准验证选模。',
        'LlamaFactory0.9.3训练API、bf16、语言层LoRA，视觉塔和投影冻结；学习率1e-4，alpha16，batch2×accum8，seed42。评测严格复用阶段五B-events带帧提示词及1024生成上限。',
        '[数据与训练配置锁]('+str(ROOT/'results/stage6_training_data_locked.json')+')；[训练回执]('+str(ROOT/'results/stage6_training_receipt.json')+')；[分维度成对检验]('+str(ROOT/'results/stage6_hypothesis_tests.json')+')。',
        '训练环境按[LlamaFactory官方仓库](https://github.com/hiyouga/LLaMA-Factory/tree/v0.9.3)的Qwen2.5-VL LoRA示例配置，推理环境保持独立。','',
        '## 测试全部602题','']+table(metrics,order,'all')
    lines += ['', '## R/D完整交互与资源完整性','',
        '[每条件正确/错误各3条完整交互]('+str(ROOT/'results/stage6_RD_interactions.md')+')；[样例索引及JSON路径]('+str(ROOT/'results/stage6_RD_interactions.json')+')。样例按qa_id排序固定选择，解析失败属于错误。','',
        '| 运行 | 题数 | 解析失败 | 耗尽生成预算/截断 |','|---|---:|---:|---:|']
    for name,c in raw_counts.items():lines.append(f'| {name} | {c["n"]} | {c["parse_failures"]} | {c.get("budget_exhausted",c.get("truncated",0))} |')
    lines += ['',f'新增唯一预测{integrity["total_unique_new_predictions"]}条；每条件每qa_id唯一，缺失0、重复0。预登记至最后预测墙钟{elapsed/3600:.3f}小时；全部attempt、训练、服务启动和显存记录保留。',
        '唯一统一调整为用户确认的图片上限32→40；原32帧字节、顺序、时间戳保留，max_model_len65536及其他服务参数同阶段五。LoRA实例仅增加加载适配器所需参数。',
        '输入长度CPU保守上界最大35248；运行时每轮检查prompt+剩余生成≤65536、原32帧始终保留、图像≤40、总生成≤2048、调用≤4。',
        '[完整性与全部运行记录]('+str(ROOT/'results/stage6_integrity.json')+')；[全部指标]('+str(ROOT/'results/stage6_metrics.json')+')；[对比CSV]('+str(ROOT/'results/stage6_comparison.csv')+')。',
        '所有已知本任务训练和服务进程已退出，显存释放；不停止其他共享进程。按要求完成后停止。','']
    lines += ['## 辅助实现修正与原始记录','',
        '原辅助union grammar额外要求闭合工具标签，导致模型的错误调用不能正常EOS，出现addCriterion或空行长尾。受控中断后，原514条计数记录（T-none242、T0242、T1部分30）完整归档；它们不混入最终比较。',
        '中间的工具轮regex草案仅做CPU检查，模型请求0。最终两段生成方法在所有替代推理前独立锁定，三组计数各242题统一重跑；条件对照也使用同一方法。主1806条和LoRA251条逐文件SHA256核对不变，未重训、未修改主预测。',
        '[有效辅助协议]('+str(ROOT/'results/stage6_final_field_guidance_v2_locked.json')+') SHA256 `'+sha(ROOT/'results/stage6_final_field_guidance_v2_locked.json')+'`；[原版归档]('+str(ROOT/'results/stage6_guided_initial_implementation')+')。',
        '此外，首次前台attempt在任何测试预测前因本地客户端继承SOCKS环境而停止；仅设置trust_env=False修复。训练的首2步没有形成检查点，按同一seed42重新完成250步/2epoch，所有失败与中断日志保留。','']
    memories=[]
    for path in sorted((ROOT/'logs').glob('stage6_gpu_memory_attempt*.json')):
        for uid,m in read(path).items():memories.append(dict(file=str(path),uuid=uid,**m));lines.append(f'- {path.name} / {uid}：本任务观测峰值{m["own_peak_MiB"]/1024:.2f}GiB；整卡{m["total_peak_MiB"]/1024:.2f}GiB（含共享任务）。')
    (ROOT/'results/stage6_report.md').write_text('\n'.join(lines)+'\n')
    write(ROOT/'results/stage6_receipt.json',dict(status='STAGE6_COMPLETE_STOPPED',completed_at=now(),hypotheses=hypotheses,
        report=str(ROOT/'results/stage6_report.md'),integrity=str(ROOT/'results/stage6_integrity.json'),
        new_predictions=integrity['total_unique_new_predictions'],remaining_owned_pids=remaining,elapsed_s=elapsed,training_elapsed_s=train['elapsed_s']))
    with (ROOT/'research_log.md').open('a') as stream:stream.write('\n## '+now()+' — 阶段六完成并停止\n\n'+
        '- H9/H10与H11结果：'+json.dumps({k:v['conclusion'] for k,v in hypotheses.items()},ensure_ascii=False)+'。测试可表达各条件分数：'+
        json.dumps({c:metrics[c]['trackable']['correct'] for c in order},ensure_ascii=False)+f'；LoRA R/D {rd_correct}/101。\n'+
        '- 工具/训练全部固定协议完成，缺失重复0；完整对比、约束诊断、交互记录、训练及资源日志见results/stage6_report.md。未重跟踪、未改冻结配置，所有本任务服务退出。\n')
    print(json.dumps(dict(status='STAGE6_COMPLETE_STOPPED',hypotheses=hypotheses,main={c:metrics[c]['trackable']['correct'] for c in order},
                         lora_RD=rd_correct,new_predictions=integrity['total_unique_new_predictions'],elapsed_h=elapsed/3600),ensure_ascii=False))


if __name__=='__main__':main()
