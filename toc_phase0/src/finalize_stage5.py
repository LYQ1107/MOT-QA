"""Finalize the report with the uniform corrected guided diagnostic and trace review."""
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import json
import os
import re

from stage5_common import *
from stage5_scores import scoring_view
from stage4_scores import inputs,groups,summarize
from analyze_stage4 import paired,pct
from compute_metrics import is_correct


def main():
    original_lock=verify_stage5()
    corrected_job=read(ROOT/'logs/stage5_guided_v2_job.json');assert corrected_job['status']=='COMPLETE'
    protocol_path=ROOT/'results/stage5_guided_v2_commit_protocol_locked.json';protocol=read(protocol_path)
    assert protocol_path.stat().st_mode&0o222==0
    scopes,trackable=inputs()
    numeric_ids={q['qa_id'] for q in scopes['full'] if q['format']=='numerical'}
    original=read(ROOT/'results/stage5_metrics.json')
    metrics=deepcopy(original)
    metrics['guided_initial_implementation']=deepcopy(original['guided_metrics']['reasoning'])
    v2_integrity={};v2_predictions={}
    for c in CONDITIONS:
        path=ROOT/'results/stage5_guided_v2'/f'reasoning_guided_{c}_predictions.jsonl'
        ps=rows(path);assert len(ps)==len({p['qa_id'] for p in ps})==300 and {p['qa_id'] for p in ps}==numeric_ids
        for p in ps:
            assert p['guidance_protocol_sha256']==sha(protocol_path)
            assert final_answer(p['raw_response'],p['format'])==(p['extracted_answer'],p['final_answer_region'])
            assert not p['constraint_violation']
            if p['finish_reason']!='length':assert re.fullmatch(protocol['corrected_regex'],p['raw_response'])
        v2_predictions[c]={p['qa_id']:p for p in ps}
        view=scoring_view(v2_predictions[c],'reasoning')
        metrics['guided_metrics']['reasoning'][c]={scope:{name:summarize([q for q in qa if q['format']=='numerical'],view)
            for name,qa in groups(items,trackable).items()} for scope,items in scopes.items()}
        v2_integrity[c]=dict(total=300,missing=0,duplicate=0,sha256=sha(path),
            parse_failures=sum(p['extracted_answer'] is None for p in ps),
            truncated=sum(p['finish_reason']=='length' for p in ps),
            max_tokens=1024,input_token_matches=sum(p['usage']['prompt_tokens']==p['expected_prompt_tokens'] for p in ps))
    metrics['guided_implementation_note']='Reasoning guided results use the uniform technical correction v2; original1800 results are preserved separately. No raw main prediction, parser, hypothesis or tracking setting changed.'
    metrics['guided_v2_protocol_sha256']=sha(protocol_path)
    write(ROOT/'results/stage5_metrics_final.json',metrics)
    statistics=read(ROOT/'results/stage5_hypothesis_tests.json')
    review=read(ROOT/'results/stage5_reasoning_manual_review.json')
    examples=read(ROOT/'results/stage5_reasoning_RD_examples.json')['examples']
    reviewed={p['qa_id']:p for p in review['examples']}
    assert len(reviewed)==len(examples)==10
    for p in examples:assert digest(p['raw_model_output'])==reviewed[p['qa_id']]['raw_output_sha256']
    known_pids=set();server_checks=[]
    baseline=read(ROOT/'logs/stage4_runtime_attempt1.json')['servers']
    runtime_paths=[*sorted((ROOT/'logs').glob('stage5_runtime_attempt*.json')),
                   *sorted((ROOT/'logs').glob('stage5_guided_v2_runtime_attempt*.json'))]
    for path in runtime_paths:
        runtime=read(path)
        for server in runtime['servers']:
            assert server['args']==baseline[server['slot']]['args']
            known_pids.add(server['pid'])
            known_pids.update(map(int,re.findall(r'pid=(\d+)',Path(server['log']).read_text())))
            server_checks.append(dict(runtime=str(path),slot=server['slot'],gpu=server['physical_gpu']['physical_index'],
                uuid=server['physical_gpu']['uuid'],arguments_equal_stage4=True))
    remaining=[pid for pid in known_pids if Path(f'/proc/{pid}').exists()]
    assert not remaining,remaining
    old_integrity=read(ROOT/'results/stage5_integrity.json')
    assert old_integrity['new_predictions']==8392 and old_integrity['reused_predictions']==4196
    violations=sum(r['constraint_violations'] for key,r in old_integrity['records'].items() if key.startswith('reasoning_guided'))
    truncations=sum(r['finish_reasons'].get('length',0) for key,r in old_integrity['records'].items() if key.startswith('reasoning_guided'))
    completed=now();hyp=read(ROOT/'results/stage5_hypotheses_preregistered.json')
    elapsed=(datetime.fromisoformat(completed)-datetime.fromisoformat(hyp['created_at'])).total_seconds()
    jobs=[]
    for path in [*sorted((ROOT/'logs').glob('stage5_job_attempt*.json')),*sorted((ROOT/'logs').glob('stage5_guided_v2_job_attempt*.json'))]:
        j=read(path);jobs.append(dict(path=str(path),status=j['status'],elapsed_s=j['elapsed_s'],started_at=j['started_at']))
    validation=dict(status='PASS',reviewed_at=completed,main_new_requests=5992,official_new_guided=600,
        reasoning_corrected_guided=1800,initial_reasoning_guided_archived=1800,
        physical_new_predictions_total=10192,reused_stage4=4196,final_comparison_matrix=12588,
        additional_archived_implementation_diagnostic=1800,missing=0,duplicates_per_protocol=0,
        original_implementation=dict(constraint_violations=violations,truncated=truncations,records_preserved=True,
            one_completion_token_usage_unavailable=True),corrected_guided=v2_integrity,
        immutable_hypotheses_sha256=sha(ROOT/'results/stage5_hypotheses_preregistered.json'),
        frozen_config_sha256=original_lock['frozen_config_sha256'],guided_correction_protocol_sha256=sha(protocol_path),
        manual_review_complete=True,server_checks=server_checks,remaining_owned_server_or_engine_pids=remaining,
        total_since_preregistration_s=elapsed,jobs=jobs,more_inference_scheduled=False)
    write(ROOT/'results/stage5_final_integrity.json',validation)

    report_path=ROOT/'results/stage5_report.md';report=report_path.read_text()
    history=ROOT/'results/stage5_report_initial_implementation.md'
    if not history.exists():history.write_text(report)
    h6=statistics['hypotheses']['H6']['comparison']
    intro=(f"预登记严格主口径H6成立：简短推理模板A为58/251（23.11%）、B为80/251（31.87%），差{h6['effect_pp']:+.2f}个百分点，p={h6['mcnemar_exact_two_sided_p']:.6g}，95%CI [{h6['ci95_pp'][0]:+.2f}, {h6['ci95_pp'][1]:+.2f}]。净增22题中Count贡献21题；R/D为A31、B30，没有改善。B对打乱D的额外优势为+3.19个百分点，探索性p=.2559，95%CI [−1.20,+8.37]，尚不足以证明真实轨迹的特异收益。\n\n"
        'H7在官方格式下未观察到单调次序；简短推理格式为B30→B-main15→B-events29（均/101），第一步显著下降、第二步显著回升，反驳单调梯度。H8的B-events分别36/101（官方）和29/101（推理），均低于规则51/101；推理严格口径差距显著，官方不劣仍不确定。\n\n'
        '跨模板观察：推理B为31.87%，低于官方B的35.06%；推理A为23.11%，低于官方A的35.46%。H6的模板内优势并不表示相对官方协议获得了更高绝对性能。\n\n'
        '解释边界：预登记10个R/D样例没有可见推理或轨迹引用。H6是模板与严格输出口径的性能差异，不能据此声称模型通过展示推理学会了利用轨迹。严格解析的格式遵循差异也影响H7/H8，见下文的独立事后敏感性诊断。\n\n')
    report=report.replace('## 1. 推理前预登记与运行范围',intro+'## 1. 推理前预登记与运行范围',1)
    report=report.replace('新增8392条、复用4196条，完整矩阵12588条（raw8988、guided3600）。',
        '最终比较矩阵为12588条（raw8988、guided3600），其中8392条新预测、4196条复用。另完整保留原版推理约束实现的1800条诊断输出，因此实际新增计算共10192条。未把实现版本混在同一分母中。')
    report=report.replace('官方仍用原extract。解析失败、截断或规则弃答均保留并计错。',
        '官方仍用原extract。解析失败、没有合法最终行的截断及规则弃答均保留并计错。')
    report=report.replace('推理计数guided按用户确认保留自由推理，用单次structured_outputs.regex约束最终Answer数值；总预算1024，未完成的截断保留失败。官方计数仍用structured_outputs.choice。',
        '推理计数guided按用户确认保留可选自由推理，用单次structured_outputs.regex约束最终Answer数值；总预算1024。最终表使用统一技术修正版v2：允许单行答案，行首Answer:提交为终结字段，随后只能输出四种合法值，并屏蔽约束库未识别的额外EOS。原版1800输出与全部错误均另存；官方计数仍用structured_outputs.choice。')
    # Replace only the numerical auxiliary table, leaving every raw/main score intact.
    begin=report.index('| 模板 | 范围 | 条件 | 严格正确 |')
    end=report.index('\n官方合法率按',begin)
    lines=['| 模板 | 范围 | 条件 | 严格正确 | 最终答案合法比例 | 约束解码正确 | 约束合法比例 |',
           '|---|---|---|---|---:|---|---:|']
    for template in ('official','reasoning'):
        for scope,group,label in [('test','trackable_dimension:event_count','测试可表达81'),('test','dimension:event_count','测试全部242'),
                                  ('full','trackable_dimension:event_count','全集可表达106（含开发）'),('full','dimension:event_count','全集300（含开发）')]:
            for c in CONDITIONS:
                raw=metrics['metrics'][template][c][scope][group];g=metrics['guided_metrics'][template][c][scope][group]
                lines.append(f"| {template} | {label} | {c} | {pct(raw)} | {raw['numerical_legal']}/{raw['numerical_total']} ({100*raw['numerical_legal_ratio']:.2f}%) | {pct(g)} | {g['numerical_legal']}/{g['numerical_total']} ({100*g['numerical_legal_ratio']:.2f}%) |")
    report=report[:begin]+'\n'.join(lines)+'\n'+report[end:]
    sentence='人工引用核查在最终复核后附于本报告。'
    report=report.replace(sentence,'已逐条完成可见输出核查；结论如下。')
    review_table=['','10条输出中8条只有Answer与字母，2条只附上选项陈述；可见推理0/10，显式轨迹引用0/10。这不证明模型的潜在计算没有用轨迹；该排序样例集也不是随机样本。','',
        '| qa_id | 正误 | 完整模型输出 | 轨迹引用核查 |','|---|---|---|---|']
    for q in examples:
        note='仅复述选项，无解释/引用；所写B本身也错' if q['parse_failed'] else '只有最终答案，未显示依据'
        review_table.append(f"| {q['qa_id']} | {'对' if q['correct'] else '错'} | `{q['raw_model_output']}` | {note} |")
    review_table+=['',f'[逐项人工可见输出核查]({ROOT}/results/stage5_reasoning_manual_review.json)。','']
    report=report.replace('## 9. 完整性、长度与耗时','\n'.join(review_table)+'\n## 9. 完整性、长度与耗时',1)
    # Update only reasoning-guided integrity cells to the corrected version.
    for c in CONDITIONS:
        r=old_integrity['records']['reasoning_main_'+c];g=v2_integrity[c]
        pattern=rf'^\| reasoning \| {re.escape(c)} \| [^\n]+$'
        replacement=f"| reasoning | {c} | {r['parse_failures']} | {r['finish_reasons'].get('length',0)} | {g['parse_failures']} | {g['truncated']} | {r['completion_tokens']['p95']} |"
        report=re.sub(pattern,replacement,report,flags=re.M)
    v2_seconds=sum(read(ROOT/'logs'/f'stage5_guided_v2_reasoning_guided_{c}_receipt.json')['elapsed_this_attempt_s'] for c in CONDITIONS)
    report=report.replace('| reasoning/guided | 1800 |', '| reasoning/guided初版（额外归档） | 1800 |')
    report=report.replace('最终完整推理attempt墙钟（含GPU资源等待、模型启动/停止）：',
        f'修正版reasoning/guided六条件墙钟合计：{v2_seconds/60:.2f}分钟。自H6–H8预登记到最终复核总墙钟：{elapsed/3600:.3f}小时。原版末次推理attempt墙钟（仅作分项，含其启动/停止）：')
    report=report.replace('待完成10条可见推理引用的人工复核后停止汇报，不追加调参。',
        '10条可见推理引用复核已完成。全部本任务服务器退出，按要求停止，不追加实验。')
    report+=('\n## 10. 实现错误、修正版本与事后格式诊断\n\n'
        f'原版推理guided共{truncations}/1800截断、1条额外EOS提前结束，不能作为干净的合法数值选择对照。两个实现原因分别为：模型有两个EOS而xgrammar仅识别一个；原regex强制Answer前换行且允许通配前缀吞掉非法Answer值。原1800记录、原错误分数及1条无法恢复的completion-token usage均完整保留，未以重试覆盖。\n\n'
        f'最终修正版在新推理前于{protocol["locked_at"]}独立锁定，[协议]({protocol_path}) SHA256 `{sha(protocol_path)}`。CPU逐项验证单行答案、带自由推理答案可正常结束；Answer:0/1/2.0/9/B前缀立即拒绝，字段未完成时EOS拒绝。六条件300题全部统一重跑，原版和修正版分开报告。此修正不影响任何raw预测或H6–H8判定。\n\n'
        f'[原版指标]({ROOT}/results/stage5_metrics.json)、[原版报告归档]({ROOT}/results/stage5_report_initial_implementation.md)、[最终矩阵指标]({ROOT}/results/stage5_metrics_final.json)。\n\n'
        '独立的事后格式敏感性检查仅把官方extract应用于最终Answer区域，绝不从解释正文找答案，也不替换主表或预登记检验。R/D的B/B-main/B-events严格正确为30/15/29，宽松最终字段诊断为33/24/35，规则仍为51。B-main的严格解析失败37/101，是下降的一部分来源；宽松诊断仍未呈单调（33→24→35）。H8在此辅助口径差距为−15.84pp，p=.0929、CI [−32.67,+0.99]，显示严格显著结论受格式口径影响；它不构成规则不劣证明。\n\n'
        f'该敏感性分析清楚标为事后诊断，原解析规则未改：[数据与配对统计]({ROOT}/results/stage5_posthoc_format_diagnostic.json)。\n\n'
        '资源方面仅把启动检查的额外显存余量从6GiB改为5.5GiB，所有模型/服务参数与阶段四逐项相同；未调整跟踪、过滤或序列化参数。各失败attempt与原始日志保留。\n\n'
        f'最终完整性：[回执]({ROOT}/results/stage5_final_integrity.json)。新增计算10192条、复用4196条；最终主比较矩阵12588条，另有1800条原版约束实现诊断。每个版本内缺失0、重复0，冻结与预登记哈希一致，服务器/EngineCore无遗留。\n')
    for path in sorted((ROOT/'logs').glob('stage5_guided_v2_gpu_memory_attempt*.json')):
        for uid,r in read(path).get('devices',{}).items():
            report+=f'\n修正版计数推理{uid}：本任务NVML峰值{r["own_peak_MiB"]/1024:.2f}GiB，整卡峰值{r["total_peak_MiB"]/1024:.2f}GiB（含共享任务）。\n'
    report_path.write_text(report)
    final_receipt=dict(status='STAGE5_COMPLETE_STOPPED',completed_at=completed,report=str(report_path),
        new_physical_predictions=10192,reused_stage4=4196,comparison_matrix=12588,archived_guided_v1=1800,
        missing=0,duplicates_per_protocol=0,main_hypotheses=statistics['hypotheses'],
        visible_reasoning_review=review['summary'],frozen_config_unchanged=True,remaining_gpu_processes=remaining,
        elapsed_from_registration_s=elapsed,no_more_experiments=True)
    write(ROOT/'results/stage5_receipt.json',final_receipt)
    old_integrity['manual_reasoning_review_pending']=False
    old_integrity['final_report']=str(report_path)
    old_integrity['corrected_guidance_integrity']=str(ROOT/'results/stage5_final_integrity.json')
    write(ROOT/'results/stage5_integrity.json',old_integrity)
    readme_path=ROOT/'README.md';readme=readme_path.read_text()
    line=readme.splitlines()[4]
    readme=readme.replace(line,
        '阶段五补充模板与表示梯度诊断已完成。预登记严格口径H6：推理模板B80/251>A58/251（+8.76pp，p=.00535），其中Count贡献21/22个净增正确；R/D没有B增益。H7非单调（推理B30→主体15→事件29，/101）；H8事件表示仍低于规则51/101。10条预登记样例均未展示推理或轨迹引用。计数约束实现错误及统一修正版单独归档；所有模型服务已退出，冻结v1与主预登记未改，按要求停止。完整报告：[stage5_report.md](/data2/user/toc_phase0/results/stage5_report.md)。',1)
    readme+='\n\n阶段五交付：results/stage5_report.md、stage5_metrics_final.json、stage5_hypothesis_tests.json、stage5_final_integrity.json、stage5_reasoning_RD_examples.md、stage5_reasoning_manual_review.json。原版计数约束结果保留于stage5_metrics.json；最终计数诊断采用事后独立锁定的guided_v2_commit协议，raw主结果和H6–H8不变。\n'
    readme_path.write_text(readme)
    with (ROOT/'research_log.md').open('a') as f:
        f.write('\n## '+completed+' — 阶段五全部完成并停止\n\n'
            '- 严格主口径H6 B80/A58，+8.76pp，p=.00535；Count贡献21/22净增，B与D探索性差异不显著。R/D表示梯度官方37→34→36、推理30→15→29，均非单调；推理H7被反驳，H8事件29低于规则51（p=.01408）。\n'
            '- 格式敏感性仅作事后诊断：R/D宽松最终字段33→24→35，严格差距受格式遵循影响；不改主表或假设判定。预登记10样例全部无可见解释/引用。\n'
            '- 原版guided1800完整保留；终结字段提交语义与额外EOS修正后，六条件全部1800统一重跑。此后注册的辅助修正与原主预登记分开报告。实际新增计算10192条，复用4196，完整最终矩阵12588，另归档原版诊断1800。\n'
            f'- 预登记至最终复核{elapsed/3600:.3f}小时，所有服务器参数逐项等于阶段四，所有已知服务器/EngineCore退出。冻结配置和主预登记哈希复核不变，原始数据/失败输出保留。目标完成，停止。\n')
    print(json.dumps(dict(status=final_receipt['status'],report=str(report_path),elapsed_h=elapsed/3600,
        corrected_guided={c:metrics['guided_metrics']['reasoning'][c]['test']['trackable_dimension:event_count'] for c in CONDITIONS},
        corrected_integrity=v2_integrity),ensure_ascii=False))


if __name__=='__main__':main()
