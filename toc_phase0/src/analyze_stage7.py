"""Complete fixed-scope Stage 7 scoring; all labels remain offline."""
from collections import Counter
from datetime import datetime
import csv
import json
import os
from pathlib import Path
from stage6_common import *
from stage4_scores import inputs,groups,DIMENSIONS
from analyze_stage4 import paired,positive
from analyze_stage6 import load,condition_metrics,tool_stats,table
from stage7_diagnostics import classification
from stage7_parser import parse_fixed_call
from compute_metrics import is_correct


def examples(conditions,test,predictions):
    rd=[q for q in test if q['metadata']['dim']=='reappear_or_disappear']
    prompts={p['qa_id']:p for p in rows(ROOT/'results/stage6/prompts/T1.jsonl')}
    records=[]
    lines=['# 阶段七 R/D 完整交互','',
        '每个实际运行条件按qa_id排序取前3条正确、前3条错误，解析失败属于错误；不按推理是否漂亮替换。完整JSON保存系统消息、相同5个开发示范、原32帧路径、每轮生成、实际工具事实与用量。下文重复系统消息，并展示固定开发示范之后的实际题目交互。','',
        f'[固定开发示范]({ROOT}/results/stage6_demonstrations_locked.json)。']
    for condition in conditions:
        ps=predictions[condition]
        for correct in (True,False):
            chosen=[q for q in rd if is_correct(ps[q['qa_id']]['extracted_answer'],q)==correct][:3]
            for q in chosen:
                qid=q['qa_id'];p=ps[qid];path=ROOT/'results/stage7/predictions/main'/condition/f'{qid}.json'
                rec=dict(condition=condition,qa_id=qid,video_id=q['video_id'],correct=correct,truth=q['correct_answer'],prediction=p['extracted_answer'],
                    record_path=str(path),record_sha256=sha(path),raw_response=p['raw_response'],
                    returned_observations=[dict(name=c['result'].get('name'),arguments=c['result'].get('arguments'),
                        legal=c['result']['legal'],matched=c['result']['matched'],text=c['result']['text'],
                        images=c['result'].get('images',[])) for c in p['tool_calls']])
                records.append(rec)
                lines += ['',f"## {condition} / {qid} / "+('正确' if correct else '错误'),'',
                    f"视频：{q['video_id']}；真值：{q['correct_answer']}；预测：{p['extracted_answer']}；[完整JSON]({path})。",'']
                messages=[p['messages'][0]]+p['messages'][len(prompts[qid]['messages'])-1:]
                for m in messages:
                    lines += ['**'+m['role']+'**','']
                    if isinstance(m['content'],str):lines += ['```text',m['content'],'```','']
                    else:
                        images=[b for b in m['content'] if b['type']=='image_path']
                        if len(images)==32:lines += ['32帧原始路径与顺序完整见逐题JSON，未删帧。','']
                        else:
                            for image in images:lines += [f'[实际返回的工具图像]({image["path"]})','']
                        for b in m['content']:
                            if b['type']=='text':lines += ['```text',b['text'],'```','']
    write(ROOT/'results/stage7_RD_interactions.json',dict(created_at=now(),selection='First3 sorted correct and first3 sorted wrong for each active condition',records=records))
    (ROOT/'results/stage7_RD_interactions.md').write_text('\n'.join(lines)+'\n')
    return records


def extended_tool_stats(ps,ids):
    result=tool_stats(ps,ids);calls=[c for qid in ids for c in ps[qid]['tool_calls']]
    selected=[ps[qid] for qid in ids]
    result.update(questions_with_legal_execution=sum(any(c['result']['legal'] for c in p['tool_calls']) for p in selected),
        questions_with_matched_execution=sum(any(c['result']['legal'] and c['result']['matched'] for c in p['tool_calls']) for p in selected),
        recovered_calls=sum(parse_fixed_call(t['raw_response'])[2] for p in selected for t in p['turns'][:p['call_attempts']]),
        parse_errors=dict(Counter(c['parse_error'] for c in calls if c['parse_error'])),
        signature_errors=dict(Counter(c['result']['text'] for c in calls if c['parsed_call'] is not None and not c['result']['legal'])),
        actual_image_returning_calls=sum(bool(c['result'].get('images')) for c in calls),
        actual_image_returning_questions=sum(any(c['result'].get('images') for c in p['tool_calls']) for p in selected))
    return result


def final_resource_check():
    runtimes=[read(p) for p in sorted((ROOT/'logs').glob('stage7_runtime_attempt*.json'))]
    remaining=[]
    for runtime in runtimes:
        try:os.kill(runtime['pid'],0);remaining.append(runtime['pid'])
        except ProcessLookupError:pass
    assert not remaining,remaining
    import pynvml
    pynvml.nvmlInit();groups={r['pid'] for r in runtimes};owned=[];snapshot=[]
    try:
        for i in range(pynvml.nvmlDeviceGetCount()):
            handle=pynvml.nvmlDeviceGetHandleByIndex(i);uid=pynvml.nvmlDeviceGetUUID(handle)
            if isinstance(uid,bytes):uid=uid.decode()
            processes=pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
            for p in processes:
                try:group=os.getpgid(p.pid)
                except ProcessLookupError:continue
                if group in groups:owned.append(dict(pid=p.pid,group=group,gpu_uuid=uid))
            snapshot.append(dict(gpu_index=i,gpu_uuid=uid,used_MiB=pynvml.nvmlDeviceGetMemoryInfo(handle).used/1024**2,process_count=len(processes)))
    finally:pynvml.nvmlShutdown()
    assert not owned,owned
    value=dict(checked_at=now(),remaining_task_owned_pids=remaining,remaining_task_owned_gpu_processes=owned,runtimes=runtimes,snapshot=snapshot,foreign_jobs_untouched=True)
    write(ROOT/'results/stage7_final_resource_check.json',value)
    return value


def main():
    verify_stage5();protocol=read(ROOT/'results/stage7_protocol_locked.json');h=read(ROOT/'results/stage7_hypotheses_preregistered.json')
    assert sha(ROOT/'results/stage7_hypotheses_preregistered.json')==protocol['hypotheses']['sha256']
    for source,expected in protocol['source_sha256'].items():assert sha(ROOT/'src'/source)==expected,source
    assert sha(protocol['primary_T_none_path'])==protocol['primary_T_none_sha256']
    assert sha(ROOT/'results/stage6/main_T1_predictions.jsonl')==protocol['stage6_T1_sha256']
    assert sha(protocol['T1_prompt_path'])==protocol['T1_prompt_sha256']
    assert sha(ROOT/'results/stage7_majority_baselines_locked.json')==protocol['majority_baselines_sha256']
    majority_lock=read(ROOT/'results/stage7_majority_baselines_locked.json')
    assert sha(majority_lock['predictions_path'])==majority_lock['predictions_sha256']
    audit=protocol['offline_parser_audit'];assert sha(audit['path'])==audit['sha256']
    for name,expected in h['unchanged'].items():
        path={'frozen_config_sha256':'results/frozen_config_v1.json','split_sha256':'results/dev_test_split_locked.json',
              'trackable_sha256':'results/trackable_subset_preregistered.json','demonstrations_sha256':'results/stage6_demonstrations_locked.json',
              'T1_prompts_sha256':'results/stage6/prompts/T1.jsonl','final_answer_parser_sha256':'src/stage5_common.py'}[name]
        assert sha(ROOT/path)==expected
    state=read(ROOT/'logs/stage7_job.json');assert state['status']=='COMPLETE',state
    gate=read(ROOT/'results/stage7_controls_decision_locked.json')
    assert sha(ROOT/'results/stage7/main_T1_predictions.jsonl')==gate['T1_sha256']
    active=['T1']+(['T-ph','T-sh'] if gate['run_controls'] else [])
    scopes,trackable=inputs();test=scopes['test'];ids={q['qa_id'] for q in test};primary=[q for q in test if q['qa_id'] in trackable]
    primary_ids={q['qa_id'] for q in primary};num_ids={q['qa_id'] for q in test if q['format']=='numerical'}
    rd=[q for q in test if q['metadata']['dim']=='reappear_or_disappear']
    prompts=load(protocol['T1_prompt_path'],ids);main={};guided={};integrity_counts={}
    for c in active:
        main[c]=load(ROOT/'results/stage7'/f'main_{c}_predictions.jsonl',ids)
        guided[c]=load(ROOT/'results/stage7'/f'guided_{c}_predictions.jsonl',num_ids)
        for mode,ps in [('main',main[c]),('guided',guided[c])]:
            for qid,p in ps.items():
                assert p['error'] is None and p['protocol_sha256']==sha(ROOT/'results/stage7_protocol_locked.json')
                assert p['hypotheses_sha256']==protocol['hypotheses']['sha256']
                assert datetime.fromisoformat(p['started_at'])>datetime.fromisoformat(h['created_at'])
                initial=prompts[qid]['messages'];assert p['messages'][:len(initial)]==initial
                assert p['total_generated_tokens']==sum(t['usage']['completion_tokens'] for t in p['turns'])<=2048
                assert len(p['tool_calls'])==p['call_attempts']<=4 and len(p['turns'])<=5
                images=sum(b['type']=='image_path' for m in p['messages'] if isinstance(m['content'],list) for b in m['content'])
                assert 32<=images<=40
                for t in p['turns']:
                    requests=t.get('physical_requests')
                    if requests:
                        assert sum(r['usage']['completion_tokens'] for r in requests)==t['usage']['completion_tokens']
                        for r in requests:assert r['usage']['prompt_tokens']+r['max_tokens']<=65536
                    else:assert t['usage']['prompt_tokens']+t['max_tokens']<=65536
                for call in p['tool_calls']:
                    assert call['call_index']<=4
                extracted,_=final_answer(p['raw_response'],p['format'])
                if '<tool_call' in p['raw_response']:extracted=None
                assert extracted==p['extracted_answer']
            integrity_counts[mode+'/'+c]=dict(n=len(ps),parse_failures=sum(p['extracted_answer'] is None for p in ps.values()),
                budget_exhausted=sum(p['budget_exhausted'] for p in ps.values()),truncated=sum(p['finish_reason']=='length' for p in ps.values()),
                max_generated=max(p['total_generated_tokens'] for p in ps.values()),max_turns=max(len(p['turns']) for p in ps.values()),
                sha256=sha(ROOT/'results/stage7'/f'{mode}_{c}_predictions.jsonl'))
    reference_paths={'T-none':'results/stage6/main_T-none_predictions.jsonl','T1-original':'results/stage6/main_T1_predictions.jsonl',
        'Official A':'results/stage4/main_A_predictions.jsonl','Route':'results/stage4/routing_A_predictions.jsonl',
        'Frozen rule':'results/v1_rule_predictions.jsonl','Majority blind':'results/stage7/majority_blind_predictions.jsonl'}
    references={name:load(ROOT/path) for name,path in reference_paths.items()}
    predictions={**main,**references}
    order=['T-none','T1-original','T1',*active[1:],'Majority blind','Official A','Route','Frozen rule']
    metrics={name:condition_metrics(test,trackable,ps,reasoning=name not in ['Official A','Route','Frozen rule','Majority blind']) for name,ps in predictions.items()}
    paired_stats={}
    for group,qs in groups(test,trackable).items():
        if not qs:continue
        paired_stats[group]={name:paired(qs,ps,main['T1']) for name,ps in references.items()}
        for c in active[1:]:paired_stats[group][c]=paired(qs,main[c],main['T1'])
    h12=paired_stats['trackable']['T-none']
    assert h12['reference_correct']==73 and h12['other_correct']==gate['T1_correct']
    hypothesis=dict(id='H12',conclusion='supported' if positive(h12) else 'not_supported',comparison='repairedT1 minus reusedT-none',**h12)
    usage={mode:{c:{'all':extended_tool_stats(ps,ids if mode=='main' else num_ids),
        'trackable':extended_tool_stats(ps,primary_ids if mode=='main' else primary_ids&num_ids)} for c,ps in collection.items()}
        for mode,collection in [('main',main),('guided',guided)]}
    rd_recalls={name:classification(rd,ps,['fully_hidden','leaves_frame']) for name,ps in predictions.items()}
    count_metrics={c:dict(strict=condition_metrics(test,trackable,main[c]),
        guided=condition_metrics([q for q in test if q['format']=='numerical'],trackable,guided[c])) for c in active}
    write(ROOT/'results/stage7_metrics.json',dict(created_at=now(),primary='test trackable251',conditions=active,metrics=metrics,count_diagnosis=count_metrics,
        RD_class_recalls=rd_recalls,majority_baseline_policy=read(ROOT/'results/stage7_majority_baselines_locked.json')['primary_policy']))
    write(ROOT/'results/stage7_hypothesis_tests.json',dict(created_at=now(),hypotheses=[hypothesis],paired=paired_stats))
    write(ROOT/'results/stage7_tool_usage.json',dict(created_at=now(),statistics=usage,
        legal_execution='Valid tool name/signature executed, including no-track responses; matched-fact counts and unmatched ratios separate.',
        look='Tool shares among legally executed calls; look question rate among all questions; image-returning look also counted.'))
    selected=examples(active,test,main)
    with (ROOT/'results/stage7_comparison.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['condition','group','n','correct','accuracy','parse_failures']);writer.writeheader()
        for c,gs in metrics.items():
            for group,r in gs.items():writer.writerow(dict(condition=c,group=group,n=r['total'],correct=r['correct'],accuracy=r['accuracy'],parse_failures=r['parse_failures']))
    resource=final_resource_check()
    latest=max(datetime.fromisoformat(p['completed_at']) for collection in (main,guided) for ps in collection.values() for p in ps.values())
    elapsed=(latest-datetime.fromisoformat(h['created_at'])).total_seconds()
    integrity=dict(checked_at=now(),status='PASS',missing=0,duplicates=0,new_predictions=sum(r['n'] for r in integrity_counts.values()),
        counts=integrity_counts,original_stage6_predictions_unchanged=True,unchanged=h['unchanged'],
        hypotheses_sha256=protocol['hypotheses']['sha256'],protocol_sha256=sha(ROOT/'results/stage7_protocol_locked.json'),
        active_conditions=active,controls_decision=gate,example_records=len(selected),elapsed_registration_to_last_prediction_s=elapsed,
        no_training=True,no_new_tracking=True,resource_check=str(ROOT/'results/stage7_final_resource_check.json'))
    write(ROOT/'results/stage7_integrity.json',integrity)
    render_report(protocol,hypothesis,metrics,order,active,usage,count_metrics,rd_recalls,paired_stats,integrity)
    write(ROOT/'results/stage7_receipt.json',dict(status='STAGE7_MODEL_ANALYSIS_COMPLETE_AWAITING_MANUAL_REVIEW',completed_at=now(),hypothesis=hypothesis,
        integrity=str(ROOT/'results/stage7_integrity.json'),report=str(ROOT/'results/stage7_report.md'),new_predictions=integrity['new_predictions'],
        all_task_gpu_memory_released=True,elapsed_s=elapsed))
    print(json.dumps(dict(H12=hypothesis,primary={c:metrics[c]['trackable']['correct'] for c in order},tools={c:usage['main'][c]['all'] for c in active}),ensure_ascii=False),flush=True)


def render_report(protocol,hypothesis,metrics,order,active,usage,counts,recalls,paired_stats,integrity):
    lines=['# TOC-Bench 阶段七：轨迹信息诊断与接口修复','',
        '冻结v1、切分、可表达清单和5个示范不变；本轮不构建新数据、不训练、不重新跟踪。轨迹信息量分析为事后诊断；H12在新推理之前独立锁定。','',
        f"H12为{hypothesis['conclusion']}：修复T1在测试可表达251题上为{metrics['T1']['trackable']['correct']}/251，T-none为73/251。但需要将这个接口修复收益与真实轨迹的特异收益分开。",'',
        f"[H12预登记]({ROOT}/results/stage7_hypotheses_preregistered.json) SHA256 `{protocol['hypotheses']['sha256']}`。",'',
        '## 轨迹是否携带超出类别先验的信息','',
        '按冻结规则及指定指标，目前没有可靠测试证据支持超出类别先验的信息增益：R/D规则与同覆盖子集多数盲基线同为51/75，边缘与真值Fisher p=.2589；Count为18/81对32/81，规则更差（未校正McNemar p=.0161）；X-Order为7/9对5/9，但仅9题、p=.5。不能据此证明所有原始轨迹都绝无其他可用信息。','',
        f'[开发/测试混淆矩阵、平衡准确率、kappa、Fisher及分类别召回完整报告]({ROOT}/results/stage7_track_information_report.md)。','',
        f'![测试集规则混淆矩阵]({ROOT}/results/stage7/figures/test_rule_confusions.png)','',
        '## H12与测试可表达251题主表','',
        'T-none和T1-original复用阶段六；Official A和路由复用阶段四；冻结规则复用v1。新T1及触发的对照复用同一5示范和初始消息，改变的只是EOS调用恢复及指定的工具返回内容。主表各行使用相同251题。','']
    lines += table(metrics,order)
    r=hypothesis
    lines += ['',f"H12：**{r['conclusion']}**。修复T1−T-none：{r['effect_pp']:+.2f}pp，exact双侧McNemar p={r['mcnemar_exact_two_sided_p']:.6g}，配对bootstrap95%CI[{r['ci95_pp'][0]:+.2f},{r['ci95_pp'][1]:+.2f}]pp。1000次、seed42、题级重采样。",'',
        '多数盲基线在本轮推理前已锁定：只用开发集同维度/题型的多数类别；R/D和ReID按语义映射可见选项，其余用答案标签或排列。配对比较使用完全相同的题；不按测试题真值选择多数类别。','',
        '| 比较，修复T1−参照 | 差值pp | exact p | bootstrap95%CI pp |','|---|---:|---:|---|']
    for name in ['T-none','T1-original','Majority blind','Official A','Route','Frozen rule',*active[1:]]:
        p=paired_stats['trackable'][name]
        lines.append(f"| {name} | {p['effect_pp']:+.2f} | {p['mcnemar_exact_two_sided_p']:.6g} | [{p['ci95_pp'][0]:+.2f}, {p['ci95_pp'][1]:+.2f}] |")
    if 'T-ph' in active and 'T-sh' in active:
        ph=paired_stats['trackable']['T-ph'];sh=paired_stats['trackable']['T-sh'];blind=paired_stats['trackable']['Majority blind']
        lines += ['',f"真实T1与占位条件同为{metrics['T1']['trackable']['correct']}/251，逐题预测并不相同：T1相对占位纠正{ph['other_correct_reference_wrong']}题，也损失{ph['other_wrong_reference_correct']}题，净收益0，p={ph['mcnemar_exact_two_sided_p']:.6g}。相对打乱为{sh['effect_pp']:+.2f}pp，p={sh['mcnemar_exact_two_sided_p']:.6g}，同样没有可检出的真实轨迹优势。真实T1低于开发多数盲基线{metrics['Majority blind']['trackable']['correct']}/251，描述性配对差值{blind['effect_pp']:+.2f}pp，p={blind['mcnemar_exact_two_sided_p']:.6g}。不能把H12的提高归因于真实轨迹内容；这些非显著对照也不构成严格等效性证明。"]
    gate=integrity['controls_decision']
    lines += ['',f"对照门槛：修复T1={gate['T1_correct']}/251，T-none={gate['T_none_correct']}/251，run_controls={gate['run_controls']}。门槛仅看严格正确数是否更高，不以显著性代替原门槛；决定在任何对照推理前锁定。",'',
        '## 调用恢复与实际工具执行','',
        '原阶段六1801次尝试全部可恢复为完整JSON；实际离线回放1798次工具签名合法，1782次物体精确匹配。3次events使用了不支持的t_start/t_end，继续拒绝；16次合法签名物体未匹配，继续返回名称列表。没有模糊匹配、改写参数或强制工具调用。','',
        '| 条件，测试602题 | 调用题比例 | 合法执行/尝试 | 平均调用次数 | track/events/look占比 | 物体未匹配/合法 | look题比例 | 实际返回图片的题数 |',
        '|---|---:|---:|---:|---|---:|---:|---:|']
    def percent(x):return '—' if x is None else f'{100*x:.2f}%'
    for c in active:
        u=usage['main'][c]['all']
        shares='/'.join(percent(u['tool_shares'][t]) for t in ('track','events','look'))
        lines.append(f"| {c} | {percent(u['call_rate'])} | {u['legal_calls']}/{u['attempts']} ({percent(u['legal_call_rate'])}) | {u['mean_calls_all']:.3f} | {shares} | {u['object_unmatched']}/{u['legal_calls']} ({percent(u['object_unmatched_rate'])}) | {percent(u['look_question_rate'])} | {u['actual_image_returning_questions']} |")
    lines += ['',f'[全部/可表达、严格/计数约束的详细调用统计]({ROOT}/results/stage7_tool_usage.json)。合法执行包含合法名称查询后的no-tracks回复；真正匹配到主体的调用另列，不能把未匹配算作获得轨迹事实。占位对照也按实际合法调用统计，但返回内容没有事实。','',
        '## R/D分类别召回','',
        '| 条件 | 完全遮挡（68题） | 离开画面（33题） | 平衡准确率 |','|---|---:|---:|---:|']
    for c in order:
        r=recalls[c]
        lines.append('| '+c+' | '+' | '.join(f"{r['confusion_matrix'][label][label]}/{r['true_distribution'][label]} ({100*r['per_class_recall'][label]:.2f}%)" for label in ['fully_hidden','leaves_frame'])+f" | {100*r['balanced_accuracy']:.2f}% |")
    lines += ['',f'![R/D分类别召回率]({ROOT}/results/stage7/figures/RD_class_recalls.png)']
    lines += ['','R/D贡献了T1相对T-none的25个净增正确中的24个（22→46/101）：完全遮挡从13/68升至35/68，离开从9/33升至11/33。相对阶段六原T1，完全遮挡为9→35/68，离开反而为17→11/33。占位条件的两类召回为35/68和15/33、合计50/101，高于真实T1的46/101；改善不能据此解释为从真实轨迹中获得了额外判别信息。']
    lines += ['','## 测试全部602题','']+table(metrics,order,group='all')
    full=paired_stats['all']['T-none']
    lines += ['',f"补充范围中，真实T1−T-none为{full['effect_pp']:+.2f}pp（{full['other_correct']}/{full['n']} 对 {full['reference_correct']}/{full['n']}），exact p={full['mcnemar_exact_two_sided_p']:.6g}，95%CI[{full['ci95_pp'][0]:+.2f},{full['ci95_pp'][1]:+.2f}]pp；没有可检出提升。H12仍只按预登记的251题判定。"]
    lines += ['','## 计数最终字段约束：辅助诊断','',
        '与阶段六修正版相同：推理/工具阶段自由生成，出现Answer:后在同一assistant消息续写合法数值，所有物理请求共享2048预算。最终字段未出现、预算耗尽或解析失败照常计错，不强造答案。该结果不用于H12或对照门槛。','',
        '| 条件 | 范围 | 严格正确 | 严格合法率 | 最终字段约束正确 | 约束合法率 |','|---|---|---:|---:|---:|---:|']
    for c,r in counts.items():
        for group in ('trackable','all'):
            key='trackable_dimension:event_count' if group=='trackable' else 'dimension:event_count'
            a=r['strict'][key];b=r['guided'][key]
            lines.append(f"| {c} | {group} | {a['correct']}/{a['total']} | {percent(a['numerical_legal_ratio'])} | {b['correct']}/{b['total']} | {percent(b['numerical_legal_ratio'])} |")
    lines += ['','## 样例、完整性与资源','',
        f'[每条件R/D正确/错误各3条完整交互]({ROOT}/results/stage7_RD_interactions.md)；[样例索引及实际工具事实]({ROOT}/results/stage7_RD_interactions.json)。人工事实一致性复核在单独文件中保存，不根据是否一致替换样例。','',
        '| 运行 | 预测数 | 解析失败 | 总预算耗尽 | 最后轮截断 |','|---|---:|---:|---:|---:|']
    for name,r in integrity['counts'].items():lines.append(f"| {name} | {r['n']} | {r['parse_failures']} | {r['budget_exhausted']} | {r['truncated']} |")
    lines += ['',f"正式新增预测{integrity['new_predictions']}条，缺失0、重复0；原阶段六预测哈希不变。预登记到最后预测耗时{integrity['elapsed_registration_to_last_prediction_s']/3600:.3f}小时。调用≤4、assistant轮数≤5、总生成≤2048、原32帧和全部示范前缀完全一致，图片≤40，每轮实际输入+预算≤65536。",'',
        '仅解析器增加完整JSON到EOS的恢复；原闭合标签路径、工具实现、物体精确匹配、帧、时间戳、服务配置、最终Answer解析均保持不变。','']
    for path in sorted((ROOT/'logs').glob('stage7_gpu_memory_attempt*.json')):
        memory=read(path)
        lines += [f"{path.name}：本任务采样峰值{memory['own_peak_MiB']/1024:.2f}GiB；整卡采样峰值{memory['total_peak_MiB']/1024:.2f}GiB（包含共享任务）；GPU UUID `{memory['gpu_uuid']}`。",'']
    lines += [f'[完整性]({ROOT}/results/stage7_integrity.json)；[资源释放检查]({ROOT}/results/stage7_final_resource_check.json)；[所有指标]({ROOT}/results/stage7_metrics.json)；[统计检验]({ROOT}/results/stage7_hypothesis_tests.json)；[CSV]({ROOT}/results/stage7_comparison.csv)。','',
        '本任务模型服务已退出，最终NVML未发现本任务GPU进程；不停止其他共享进程。不进行新的数据构建或训练。']
    (ROOT/'results/stage7_report.md').write_text('\n'.join(lines)+'\n')


if __name__=='__main__':main()
