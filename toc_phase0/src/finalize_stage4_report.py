"""CPU-only review of Stage 4 diagnostics and final report; no new inference."""
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import re

from stage4_common import ROOT, CONDITIONS, now, read, rows, write, sha, verify_stage4
from stage4_scores import inputs


def main():
    lock=verify_stage4()
    scopes,trackable=inputs()
    visible=rows(ROOT/'results/stage3_visible_inputs.jsonl')
    originals={q['qa_id']:q for q in read(ROOT/'data/toc_bench/answer_final.json')['items']}
    assert all(all(q[k]==originals[q['qa_id']][k] for k in q) for q in visible)
    old_prompts={p['qa_id']:p for p in rows(ROOT/'results/stage2_prompt_texts.jsonl')}
    a_prompts=rows(ROOT/'results/stage4/prompts/A.jsonl')
    for p in a_prompts:
        assert p['system']==old_prompts[p['qa_id']]['system']
        assert p['user'].split('\n',1)[1]==old_prompts[p['qa_id']]['user']
    main_predictions={c:{p['qa_id']:p for p in rows(ROOT/'results/stage4'/f'main_{c}_predictions.jsonl')} for c in CONDITIONS}
    guided={c:{p['qa_id']:p for p in rows(ROOT/'results/stage4'/f'guided_{c}_predictions.jsonl')} for c in CONDITIONS}
    stats=read(ROOT/'results/stage4_paired_statistics.json')
    hypotheses=read(ROOT/'results/stage4_hypotheses_preregistered.json')
    for h in stats['hypotheses']:
        registered=next(q for q in hypotheses['hypotheses'] if q['id']==h['id'])
        h['scope']=registered['scope']
        h['statement']=registered['statement']
    write(ROOT/'results/stage4_paired_statistics.json',stats)
    distributions={}
    for scope in ('test','full'):
        distributions[scope]={}
        for group,qa in [('all_count',[q for q in scopes[scope] if q['format']=='numerical']),
                         ('trackable_count',[q for q in scopes[scope] if q['format']=='numerical' and q['qa_id'] in trackable])]:
            distributions[scope][group]=dict(total=len(qa),truth=dict(Counter(str(q['correct_answer']) for q in qa)),
                main={c:dict(Counter(main_predictions[c][q['qa_id']]['raw_response'].strip() for q in qa)) for c in CONDITIONS},
                guided={c:dict(Counter(guided[c][q['qa_id']]['raw_response'].strip() for q in qa)) for c in CONDITIONS})
    d=read(ROOT/'results/stage4_D_assignments_locked.json')
    lookup={(r['video_id'],r['query']):r for r in d['assignments']}
    queries={r['qa_id']:r['queries'] for r in read(ROOT/'results/stage3_extracted_queries.json')}
    d_scopes={}
    for scope in ('full','test'):
        d_scopes[scope]={}
        for group,qa in [('all',scopes[scope]),('trackable',[q for q in scopes[scope] if q['qa_id'] in trackable])]:
            counts=Counter()
            for q in qa:
                assignments=[lookup[(q['video_id'],phrase)] for phrase in queries[q['qa_id']]]
                counts['questions']+=1
                counts['all_blocks_unchanged']+=all(not a['text_changed_from_B'] for a in assignments)
                counts['any_block_unchanged']+=any(not a['text_changed_from_B'] for a in assignments)
                counts['any_temporal_permutation_fallback']+=any(a['donor_video_id'] is None for a in assignments)
                counts['only_different_video_donors']+=all(a['donor_video_id'] is not None for a in assignments)
            d_scopes[scope][group]=dict(counts)
    old={p['qa_id']:p for p in rows(ROOT/'results/stage2_predictions.jsonl')}
    numeric_ids={q['qa_id'] for q in scopes['full'] if q['format']=='numerical'}
    protocol_diagnostic=dict(visible_fields_equal_original_benchmark=len(visible),
        A_after_removing_only_timestamps_equals_saved_stage2_prompt=len(a_prompts),
        image_cache='Both runners use frames_cache/official32; Stage4 locked all JPEG hashes before inference.',
        allowed_differences='Added common timestamps; server max_model_len32768 to65536 and memory budget. Other official sampling, prompts, parser, generation settings remain unchanged.',
        no_factor_isolation='No new ablation was run, so the Stage2-to-A change cannot be attributed uniquely to timestamps.',
        stage2_count_raw_distribution=dict(Counter(old[qid]['raw_response'] for qid in numeric_ids)),
        A_count_raw_distribution=dict(Counter(main_predictions['A'][qid]['raw_response'] for qid in numeric_ids)))
    runtime=read(ROOT/'logs/stage4_runtime_attempt1.json')
    assert lock['locked_at']<runtime['started_at']
    pids={server['pid'] for server in runtime['servers']}
    for server in runtime['servers']:
        pids.update(map(int,re.findall(r'pid=(\d+)',Path(server['log']).read_text())))
    remaining=[pid for pid in pids if Path(f'/proc/{pid}').exists()]
    assert not remaining,remaining
    errors=ROOT/'logs/stage4_request_errors.jsonl'
    assert not errors.exists() or not errors.read_text().strip()
    reviewed=now()
    result=dict(reviewed_at=reviewed,no_new_inference=True,count_distributions=distributions,
        D_control_question_counts=d_scopes,stage2_vs_A_protocol_check=protocol_diagnostic,
        preregistration_before_server_start=True,preinference_lock_at=lock['locked_at'],server_start_recorded_at=runtime['started_at'],
        raw_timestamp_semantics='Per-prediction started_at was recorded when building the completed response record, not at request dispatch. latency_s uses monotonic request timing. Server runtime timestamp provides an earlier pre-request bound for preregistration audit.',
        known_server_and_engine_pids=sorted(pids),remaining_owned_server_or_engine_pids=remaining,
        http_or_inference_errors=0,supplemental_template_started=False)
    write(ROOT/'results/stage4_review_diagnostics.json',result)
    integrity=read(ROOT/'results/stage4_integrity.json')
    integrity['first_prediction_recorded_at']=integrity.pop('first_inference_started_at')
    integrity['prediction_timestamp_semantics']=result['raw_timestamp_semantics']
    integrity['server_start_recorded_at']=runtime['started_at']
    integrity['preinference_lock_at']=lock['locked_at']
    integrity['known_server_and_engine_pids']=sorted(pids)
    integrity['remaining_owned_server_and_engine_pids']=remaining
    integrity['reviewed_at']=reviewed
    write(ROOT/'results/stage4_integrity.json',integrity)
    path=ROOT/'results/stage4_main_report.md'
    report=path.read_text()
    interpretation=(
        '当前冻结轨迹与官方直接答复格式下，未观察到真实轨迹B带来的净收益。主要四维可表达子集也只有A 77/231、B 78/231（+0.43个百分点）。R/D的B为37/101，低于A的39/101和冻结规则的51/101；新A回退路由为63/101。轨迹中可供规则利用的信息，尚未通过本次文本融合转化为大模型收益。\n\n'
        '测试全部602题上B比A高2.49个百分点，但McNemar p=0.2449、95%CI [−1.50, +6.31]，且D分数更高；这不改变预登记主子集的结论。计数的严格涨分应结合合法输出率与约束解码解释：测试全部242道计数题B严格83题正确、A 54题，约束后B 97题、A 102题。\n\n'
        'H5中B虽显著高于25%随机水平，却未显著高于A。测试可表达计数81题里，guided B有72条回答“2”，guided A有73条；恒答“2”即32/81（39.51%），接近B的33/81（40.74%）。因此高于25%本身不能作为使用轨迹信息的证据。\n\n')
    marker='## 1. 推理前完成与锁定'
    report=report.replace(marker,interpretation+marker,1)
    report=report.replace('## 4. 预登记假设检验\n\n',
        '## 4. 预登记假设检验\n\n'
        'H1：测试可表达R/D上B>A；H2：主子集C与A无明显差异；H3：主子集D不高于A；H4：测试可表达X-Order上B同时高于A和规则；H5：测试可表达Count的约束解码B同时高于A和25%随机水平。H4只有B高于规则这一部分达标，H5只有高于25%这一部分达标，均未满足完整假设。\n\n',1)
    scope_labels=dict(H1='R/D, B−A',H2='主子集, C−A',H3='主子集, D−A',H4='X-Order',H5='Count guided, B−A')
    for hid,label in scope_labels.items():
        old_label={'H1':'B_minus_A','H2':'C_minus_A','H3':'D_minus_A','H5':'guided_B_minus_A'}.get(hid)
        if old_label:
            pattern=rf'(\| {hid} \| [^|]+ \| ){old_label}'
            report=re.sub(pattern,lambda m:m.group(1)+label,report)
    report=report.replace('B_minus_A, n=30','X-Order, B−A, n=30').replace('B_minus_rule, n=30','X-Order, B−规则, n=30')
    report=report.replace('该部分不是有效的错误时间对照，削弱D对照的纯度。',
        '该部分不是有效的错误时间对照，削弱D对照的纯度。测试可表达251题中，5题的D全部轨迹块与B相同，6题至少有一块相同；128题全部采用异视频供体，123题至少使用一次自身时间块置换。置换可能保留部分区间数量信息，不能保证每题均得到无信息证据。')
    report=report.replace('749题×4主条件 + 300题×4独立guided = 4196条唯一预测；无缺失、无重复。',
        '749题×4主条件 + 300题×4独立guided = 4196条唯一预测；无缺失、无重复。当前749题均实际采样32帧。')
    report=report.replace('若有失败恢复，原错误、有效预测和各attempt日志全部保留，最终回执的本次时间不包含旧attempt。',
        '本次为单一推理attempt，无HTTP或推理错误；未重跑已提交预测。主四条件用时47.67分钟，guided四条件20.19分钟，含启动/停止的总推理墙钟68.67分钟。')
    report=report.replace('设备、UUID、共享前显存及服务器参数见',
        '使用物理GPU4与GPU6（GPU6有其他任务共享）。设备、UUID、共享前显存及服务器参数见')
    addition=(
        '\n## 9. 额外离线诊断与最终复核\n\n'
        '新A相较阶段二已有明显变化：同一749题的阶段二为166/749（22.16%），新A为239/749（31.91%）；其中计数从2/300升至68/300。已逐题验证749份可见输入字段与原标注相同，A移除新增时间戳后与阶段二保存的system/user全文完全相同；两阶段使用同一官方JPEG缓存目录，阶段四启动前另锁定逐JPEG哈希。\n\n'
        '这是用户要求重新运行A的意义所在：阶段二分数不能替代当前A。新增时间戳及共同服务上下文等变化没有被单独消融，本轮不将该差异唯一归因于时间戳，也不运行额外推理解释它。\n\n'
        '推理前总锁定时间 '+lock['locked_at']+'，服务器启动记录 '+runtime['started_at']+'；前者早于模型服务启动。原预测记录中的started_at实际为响应记录构建时刻，latency_s使用请求的单调时钟耗时；完整性回执已明确该语义，原预测未改写。\n\n'
        f'最终复核时间：{reviewed}。服务器及EngineCore PID均已退出；GPU4回到约空闲，GPU6仅保留原共享进程。'
        f'详细计数输出分布、D对照覆盖及协议核对见 [离线诊断]({ROOT}/results/stage4_review_diagnostics.json)。\n\n'
        '实际保存40条差异样例（39条测试、1条明确标注的开发补充）。Order的B对/A错全集仅3条；ReID的B对/A错为0条、B错/A对为2条，因此这些方向无法提供5条。所有符合项均按预登记选择规则保留，未改变样例标准或补造。\n')
    report+=addition
    path.write_text(report)
    receipt=read(ROOT/'results/stage4_main_receipt.json')
    receipt.update(review_completed_at=reviewed,examples_saved=40,known_gpu_processes_remaining=remaining,
        elapsed_until_review_from_D_registration_s=(datetime.fromisoformat(reviewed)-datetime.fromisoformat(d['created_at'])).total_seconds())
    write(ROOT/'results/stage4_main_receipt.json',receipt)
    readme_path=ROOT/'README.md';readme=readme_path.read_text()
    old_status=readme.split('\n')[4]
    new_status=('阶段四官方格式主实验已完成：749题×A/B/C/D全部重跑，300道计数题×四条件另做guided choice，共4196条唯一预测、无缺失。'
        '测试可表达251题A 89/251（35.46%）、B 88/251（35.06%），B−A −0.40个百分点（p=1，95%CI −5.98至+4.79）；'
        '新A回退路由112/251（44.62%）。H1/H4/H5未获支持，H2与无差异相容但非等效证明，H3仍不确定。'
        '完整主表、计数诊断和检验见 [stage4_main_report.md](/data2/user/toc_phase0/results/stage4_main_report.md)，'
        '原始输出与样例见 results/stage4 和 results/stage4_AB_examples.md。冻结v1及所有预登记保持不变；补充简短推理模板未运行，已按要求停止。')
    readme=readme.replace(old_status,new_status,1)
    readme=readme.replace('未来四条件共同冻结max_model_len=65536，实测32768也可容纳。','阶段四四条件共同使用max_model_len=65536，实测32768也可容纳。')
    readme=readme.replace('本轮使用GPU2/4，完成后本任务worker均已退出。','冻结重跟踪使用GPU2/4，阶段四推理使用GPU4/6，均已退出本任务GPU进程。')
    readme+='\n\n阶段四可复核入口：`src/prepare_stage4.py`生成且锁定假设、D、图像和提示词（已经锁定，不要重跑覆盖）；`src/run_stage4_inference.py`读取锁定输入并支持已提交单元恢复；`src/analyze_stage4.py`离线评分；`src/finalize_stage4_report.py`离线协议核对与报告复核。当前实验已完成，无需再启动推理。\n'
    readme_path.write_text(readme)
    with (ROOT/'research_log.md').open('a') as stream:
        stream.write('\n## '+reviewed+' — 阶段四主报告离线复核\n\n'
            '- 官方直接答复证据融合未提升主子集：B88/A89；主要四维B78/A77也无明显净收益。R/D规则51>A39>B37，A回退路由63，轨迹信号仍可由显式规则利用。\n'
            '- 全测试计数严格B83>A54，但guided B97<A102；主计数81题guided B33/A30不显著（p=.5078），B72条回答2，恒答2即32题正确。未将严格格式提升作为轨迹增益证据。\n'
            '- 旧阶段二与新A的749份可见字段、去时间戳提示词逐项一致；记录新A计数涨幅及共同协议变化，未追加推理做因素归因。\n'
            '- D主子集5题全部块与B相同，6题至少一块相同，局限如实披露。差异样例40条，稀缺方向不足数明确。\n'
            '- 原始预测started_at字段为响应记录构建时刻，补充说明时间语义；preregistration早于服务器启动已用runtime独立验证，原始预测不改写。\n'
            '- 服务器及EngineCore均退出，冻结与锁定哈希不变。只做CPU汇报复核；补充模板未运行，停止等待用户。\n')
    print(json.dumps(dict(status='REVIEWED_STOPPED',reviewed_at=reviewed,report=str(path),
        examples=40,remaining_gpu_processes=remaining,hypotheses_sha256=sha(ROOT/'results/stage4_hypotheses_preregistered.json'),
        D_sha256=sha(ROOT/'results/stage4_D_assignments_locked.json')),ensure_ascii=False))


if __name__=='__main__':
    main()
