"""Save the manual review and final resource check without changing predictions."""
from datetime import datetime
import os
from pathlib import Path
from stage6_common import ROOT,read,write,now,sha,verify_stage5


def main():
    verify_stage5()
    integrity=read(ROOT/'results/stage6_integrity.json')
    protocol=read(ROOT/'results/stage6_protocol_locked.json')
    for name,expected in protocol['source_sha256'].items():assert sha(ROOT/'src'/name)==expected
    for key,path in [('hypotheses_sha256','stage6_hypotheses_preregistered.json'),
                     ('protocol_sha256','stage6_protocol_locked.json'),
                     ('frozen_config_sha256','frozen_config_v1.json'),
                     ('split_sha256','dev_test_split_locked.json'),
                     ('trackable_sha256','trackable_subset_preregistered.json')]:
        assert sha(ROOT/'results'/path)==integrity[key],path
    for item in read(ROOT/'results/stage6_final_field_guidance_v2_locked.json')['primary_and_training_reused'].values():
        assert sha(item['path'])==item['sha256']
    sanity=read(ROOT/'results/stage6_lora_loading_sanity.json')
    assert len(sanity['cases'])==3 and all(case['full_text_identical'] for case in sanity['cases'])
    notes={
        'T1':{
            '09ecc5ba1b9b':'给出0.0/1.033秒并解释完全遮挡，但仅收到非法调用反馈，没有工具事实支持这些时间。',
            '0e9e33c81d1d':'给出20.933/21.9秒并选择离开，答案正确；全部4次尝试非法，没有真实工具观察。',
            '128d74ab4e21':'给出13.240/14.160秒并选择离开，答案正确；全部4次尝试非法，没有真实工具观察。',
            '061682ce31ac':'错误地选择离开。4.0/5.2秒与首个开发示范相同，可能受示范影响，无法确定数字的来源；没有真实工具观察。',
            '0893a25082de':'选择离开且错误；26.246秒没有工具事实支持，调用均非法。',
            '093589b84207':'选择离开且错误；29.484/30.585秒没有工具事实支持，调用均非法。'},
        'LoRA-B-events':{
            '0893a25082de':'确实引用事件列表中13.4秒、非贴边的消失，映射到A完全遮挡且答对。',
            '0e9e33c81d1d':'答案A正确，但虚构29.533/30.433秒XML事件及置信度；实际列表只有首次出现0.0秒和最后可见30.4秒。',
            '128d74ab4e21':'答案A正确，但20.8秒实际上是首次出现，列表没有间断；解释不是可靠的消失推理。',
            '061682ce31ac':'虚构19.8秒事件；实际只有5.6秒首次出现、20.2秒最后可见。把away解释为B离开且答错。',
            '093589b84207':'开头引用真实6.0秒非贴边消失，随后重复legal直到1024 token，未输出最终答案。',
            '09ecc5ba1b9b':'7.0秒消失/7.4秒重现及非贴边事实正确，却选择A离开而非B完全遮挡，属于选项映射错误。'}}
    index=read(ROOT/'results/stage6_RD_interactions.json')
    reviewed=[]
    for row in index['records']:
        assert sha(row['record_path'])==row['record_sha256']
        prediction=read(row['record_path'])
        condition=row['condition']
        note=notes.get(condition,{}).get(row['qa_id'],'基本仅给答案，未展示可审核的工具事实引用；最终格式错误照常计错。')
        entry=dict(**row,note=note)
        if condition=='T1':
            entry.update(tool_attempts=len(prediction['tool_calls']),
                         tool_responses_are_only_errors=all(t.get('parse_error') and not t['result']['legal'] for t in prediction['tool_calls']))
        reviewed.append(entry)
    write(ROOT/'results/stage6_RD_manual_review.json',dict(created_at=now(),posthoc=True,
        selection=index['selection'],number_reviewed=len(reviewed),
        scope='All 24 previously selected examples, without replacing any examples or predictions.',
        conclusions='Correct labels do not guarantee faithful reasoning. No T1 example received real tool facts; LoRA examples mix grounded reasoning, invented events, option errors and repetition.',records=reviewed))
    runtimes=[]
    for pattern in ['stage6_runtime_*_attempt*.json','stage6_lora_sanity_hf_runtime.json']:
        for path in sorted((ROOT/'logs').glob(pattern)):
            d=read(path);runtimes.append(dict(path=str(path),pid=d['pid']))
    remaining=[]
    for runtime in runtimes:
        try:os.kill(runtime['pid'],0);remaining.append(runtime)
        except ProcessLookupError:pass
    assert not remaining,remaining
    import pynvml
    groups={runtime['pid'] for runtime in runtimes}
    owned=[];snapshots=[]
    pynvml.nvmlInit()
    try:
        for index in range(pynvml.nvmlDeviceGetCount()):
            handle=pynvml.nvmlDeviceGetHandleByIndex(index)
            uid=pynvml.nvmlDeviceGetUUID(handle)
            if isinstance(uid,bytes):uid=uid.decode()
            processes=pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
            for process in processes:
                try:group=os.getpgid(process.pid)
                except ProcessLookupError:continue
                if group in groups:owned.append(dict(pid=process.pid,gpu_uuid=uid,group=group))
            snapshots.append(dict(gpu_index=index,gpu_uuid=uid,total_used_MiB=round(pynvml.nvmlDeviceGetMemoryInfo(handle).used/1024**2,3),
                                  process_count=len(processes)))
    finally:pynvml.nvmlShutdown()
    assert not owned,owned
    completed=now()
    resource_check=dict(checked_at=completed,remaining_task_owned_pids=remaining,remaining_task_owned_gpu_processes=owned,
        runtimes=runtimes,all_gpu_memory_snapshot=snapshots,foreign_processes_untouched=True)
    write(ROOT/'results/stage6_final_resource_check.json',resource_check)
    integrity.update(final_review_at=completed,final_resource_check=str(ROOT/'results/stage6_final_resource_check.json'),
        loading_sanity=str(ROOT/'results/stage6_lora_loading_sanity.json'),manual_review=str(ROOT/'results/stage6_RD_manual_review.json'),
        posthoc_diagnostics=str(ROOT/'results/stage6_posthoc_diagnostics.json'),remaining_task_owned_gpu_processes=owned)
    write(ROOT/'results/stage6_integrity.json',integrity)
    receipt=read(ROOT/'results/stage6_receipt.json')
    receipt.update(final_review_at=completed,loading_sanity_passed=True,all_task_gpu_memory_released=True,
        total_elapsed_through_review_s=(datetime.fromisoformat(completed)-datetime.fromisoformat(read(ROOT/'results/stage6_hypotheses_preregistered.json')['created_at'])).total_seconds(),
        primary_predictions_unchanged=True,optional_EOS_exploration_run=False)
    write(ROOT/'results/stage6_receipt.json',receipt)
    log=ROOT/'research_log.md'
    text=log.read_text()
    marker='### 阶段六最终复核（2026-11-04）'
    if marker not in text:
        with log.open('a') as stream:
            stream.write('\n\n'+marker+'\n\nT0没有尝试调用；T1的1801次尝试均因闭合标签缺失而非法，未传入真实工具事实，未触发T-ph/T-sh。H9反向显著，H10无显著增益。合成LoRA训练35.67分钟，R/D29→40/101，未达45；全251题83→83。两个合成样例与一个开发视频的HF/PEFT、vLLM适配器输出逐字一致，未发现加载差异，不重训、不改参数。人工复核保留24例，LoRA正确样例也出现虚构事件和选项映射问题。事后按开发多数语义固定选完全遮挡，测试68/101，高于路由63/101；该诊断不修改主假设或分割。2783条正式预测完整唯一，旧514条辅助记录独立保留。最终本任务CPU/GPU服务均已退出，冻结v1和全部主预测哈希不变，EOS容错仅离线原型未推理，停止。\n')
    print(dict(status='STAGE6_COMPLETE_STOPPED',reviewed_examples=len(reviewed),loading_sanity='PASS',
               remaining_task_owned_gpu_processes=owned,total_elapsed_through_review_s=receipt['total_elapsed_through_review_s']),flush=True)


if __name__=='__main__':main()
