"""Finish Stage 7 after actual interactions have been read and annotated."""
from datetime import datetime
from stage6_common import ROOT,read,write,now,sha,verify_stage5


def main():
    verify_stage5()
    receipt=read(ROOT/'results/stage7_receipt.json')
    integrity=read(ROOT/'results/stage7_integrity.json')
    index=read(ROOT/'results/stage7_RD_interactions.json')
    manual=read(ROOT/'results/stage7_RD_manual_review.json')
    expected={(r['condition'],r['qa_id']):r for r in index['records']}
    reviewed={(r['condition'],r['qa_id']):r for r in manual['records']}
    assert set(expected)==set(reviewed) and len(reviewed)==len(manual['records'])
    for key,row in expected.items():
        assert sha(row['record_path'])==row['record_sha256']
        assert reviewed[key]['note'].strip() and reviewed[key]['facts_consistency'].strip()
    for preserved in read(ROOT/'results/stage6_final_field_guidance_v2_locked.json')['primary_and_training_reused'].values():
        assert sha(preserved['path'])==preserved['sha256']
    training=read(ROOT/'results/stage6_training_receipt.json')
    assert sha(ROOT/'models/stage6_lora_r8/adapter_model.safetensors')==training['adapter_sha256']
    assert not read(ROOT/'results/stage7_final_resource_check.json')['remaining_task_owned_gpu_processes']
    metrics=read(ROOT/'results/stage7_metrics.json');h=receipt['hypothesis']
    tools=read(ROOT/'results/stage7_tool_usage.json')['statistics']['main']
    report=ROOT/'results/stage7_report.md'
    text=report.read_text()
    marker='## 人工核验：最终答案是否与实际工具事实一致'
    if marker in text:text=text.split(marker,1)[0].rstrip()+'\n'
    lines=['',marker,'',
        '复核全部固定选择的样例，核查的是模型真实收到的工具返回；正确标签和事实一致性分别记录。占位符或no-tracks没有相关事件事实时记为无法核验，不把猜对视为工具证据支持。打乱轨迹的事实一致性相对打乱后的实际返回判断，不能等同于视频真值正确。','',
        f'[人工阅读记录]({ROOT}/results/stage7_RD_manual_review.json)；[完整对话]({ROOT}/results/stage7_RD_interactions.md)。','',
        '| 条件 | qa_id | 严格答案 | 与工具事实一致性 | 具体核查 |','|---|---|---|---|---|']
    for row in index['records']:
        note=reviewed[row['condition'],row['qa_id']]
        cells=[row['condition'],row['qa_id'],('正确' if row['correct'] else '错误')+f"（{row['prediction']} / 真值{row['truth']}）",
            note['facts_consistency'],note['note'].replace('|','/').replace('\n',' ')]
        lines.append('| '+' | '.join(cells)+' |')
    if manual.get('summary'):lines += ['',manual['summary']]
    completed=now()
    registered=read(ROOT/'results/stage7_hypotheses_preregistered.json')['created_at']
    wall=(datetime.fromisoformat(completed)-datetime.fromisoformat(registered)).total_seconds()
    lines += ['',f'最终复核完成时间：{completed}；从H12预登记至交付共{wall/3600:.3f}小时。冻结配置、既有预测和LoRA适配器均未修改。本任务服务已释放显存，阶段七到此停止，不开始新的数据构建或训练。']
    report.write_text(text+'\n'.join(lines)+'\n')
    integrity.update(final_review_at=completed,manual_review_records=len(reviewed),manual_review_sha256=sha(ROOT/'results/stage7_RD_manual_review.json'),
                     stage6_adapter_unchanged=True,all_stage6_primary_predictions_unchanged=True,report_sha256=sha(report))
    write(ROOT/'results/stage7_integrity.json',integrity)
    receipt.update(status='STAGE7_COMPLETE_STOPPED',final_review_at=completed,manual_review_records=len(reviewed),total_elapsed_through_review_s=wall,
                   report_sha256=sha(report),no_new_training_or_data_building=True)
    write(ROOT/'results/stage7_receipt.json',receipt)
    baseline=metrics['metrics']['Majority blind']['trackable'];t1=metrics['metrics']['T1']['trackable']
    control_text=''
    if 'T-ph' in metrics['metrics']:
        control_text=f"同子集占位{metrics['metrics']['T-ph']['trackable']['correct']}/251、打乱{metrics['metrics']['T-sh']['trackable']['correct']}/251，真实轨迹无可检出的特异优势。"
    introduction=(f"阶段七已完成并停止。冻结v1、切分、可表达清单及5示范不变。接口增加完整JSON到EOS的恢复后，测试可表达T1为{t1['correct']}/251，T-none73/251，开发多数类盲基线{baseline['correct']}/251，路由112/251；H12={h['conclusion']}，p={h['mcnemar_exact_two_sided_p']:.6g}。"+control_text+f"轨迹事后诊断中R/D边缘与标签Fisher p=.2589、规则与盲基线均51/75；Count18/81低于盲基线32/81；X-Order仅覆盖9题，7/9对5/9的配对p=.5，尚无可靠超出类别先验的证据。全部交互和人工事实核查已保存，本任务GPU进程已退出。完整报告：[stage7_report.md]({ROOT}/results/stage7_report.md)。阶段六历史报告：[stage6_report.md]({ROOT}/results/stage6_report.md)。")
    readme=ROOT/'README.md';paragraphs=readme.read_text().split('\n\n')
    assert paragraphs[2].startswith(('阶段六','阶段七'))
    paragraphs[2]=introduction;readme.write_text('\n\n'.join(paragraphs))
    log=ROOT/'research_log.md';marker='阶段七最终结果与停止'
    if marker not in log.read_text():
        with log.open('a') as stream:
            stream.write('\n## '+completed+' — '+marker+'\n\n')
            stream.write(f"H12 {h['conclusion']}：修复T1={t1['correct']}/251 vsT-none73，差值{h['effect_pp']:+.2f}pp，exact p={h['mcnemar_exact_two_sided_p']:.6g}，95%CI{h['ci95_pp']}；开发多数盲基线{baseline['correct']}/251、路由112/251。")
            stream.write('冻结规则信息量诊断：R/D与多数类同51/75，BA.5441、kappa.1071、Fisher p.2589；Count规则18对盲基线32/81，BA.2398、kappa.0789、p.0161；X-Order7对5/9、BA.75、kappa.5263、p.5，开发覆盖0，不外推信息不存在。\n')
            for c,v in tools.items():
                u=v['all'];stream.write(f"{c}：合法执行{u['legal_calls']}/{u['attempts']}，物体未匹配{u['object_unmatched']}/{u['legal_calls']}，look题{u['questions_with_look']}/602。\n")
            stream.write(f"{len(reviewed)}条固定样例全部人工核验，错误/不一致照实报告；正式预测{integrity['new_predictions']}条，缺失0重复0，先前主预测与适配器SHA不变。无新训练/跟踪/数据构建，全部任务GPU服务已退出，停止。\n")
    print(dict(status=receipt['status'],H12=h['conclusion'],repaired_T1_correct=t1['correct'],blind_baseline_correct=baseline['correct'],
               reviewed=len(reviewed),new_predictions=integrity['new_predictions'],total_hours=wall/3600),flush=True)


if __name__=='__main__':main()
