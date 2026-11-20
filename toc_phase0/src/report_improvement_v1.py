"""Report the completed, frozen single-round study; never select parameters."""
from datetime import datetime
import hashlib
import json

from run_stage3_masa import ROOT,now,write_json


def read(path):return json.loads((ROOT/path).read_text())
def pct(value):return 'N/A' if value is None else f'{100*value:.2f}%'
def link(path,label=None):return f'[{label or path}]({ROOT/path})'


def main():
    frozen=read('results/frozen_config_v1.json');lock=read('logs/frozen_config_v1_lock.json')
    assert hashlib.sha256((ROOT/'results/frozen_config_v1.json').read_bytes()).hexdigest()==lock['sha256']
    metrics=read('results/v1_rule_metrics.json')['metrics'];integrity=read('results/v1_integrity.json')
    assert integrity['status']=='PASS'
    lengths=read('results/v1_input_lengths.json');assert lengths['text_limits_met']
    memory=read('results/improvement/dev/memory_selection.json');fil=read('results/improvement/dev/filter_selection.json')
    event=read('results/improvement/dev/event_selection.json');plan=read('results/improvement_plan_locked.json')
    split=read('results/dev_test_split_locked.json');hist=read('results/baseline_same_subset_comparison.json')
    comparisons=read('results/v1_baseline_comparison.json')['rows']
    dev_job=read('logs/improvement_dev_job.json');final_job=read('logs/improvement_final_job.json')
    reproduction=read('results/v1_dev_reproduction.json')
    for job in (dev_job,final_job):assert job['status']=='COMPLETE'
    manual=read('results/improvement_dev_memory_manual_review.json')
    test=metrics['test']['groups'];full=metrics['full']['groups']
    test_main_comparison=next(r for r in comparisons if r['scope']=='test' and r['group']=='main_trackable')
    main_delta=100*(test_main_comparison['frozen_rule_correct']-test_main_comparison['original_rule_correct'])/test_main_comparison['total']
    report=['# TOC-Bench 阶段三：限时改进一轮与冻结报告','',f'生成时间：{now()}。阶段四推理尚未运行。','',
      f'本轮已冻结 memo={frozen["tracking"]["memo_tracklet_frames"]}、过滤 `{frozen["filter"]["name"]}`、事件规则 `{frozen["rule"]["event_mode"]}`，并在冻结后重新跟踪全部689个视频。测试集规则在可表达子集上的严格准确率为 **{test["trackable"]["correct"]}/{test["trackable"]["total"]}（{pct(test["trackable"]["accuracy_all"])}）**；主要四维可表达子集为 **{test["main_trackable"]["correct"]}/{test["main_trackable"]["total"]}（{pct(test["main_trackable"]["accuracy_all"])}）**。弃答、非法数值与解析失败全部计错。','',
      f'本轮开发集主要可表达题从29/70增至30/70；测试集相同口径从{test_main_comparison["original_rule_correct"]}/{test_main_comparison["total"]}变为{test_main_comparison["frozen_rule_correct"]}/{test_main_comparison["total"]}（{main_delta:+.2f}个百分点）。测试准确率未提高，主要产出是压缩预算达标和配置冻结。测试主要可表达子集的阶段二Qwen为{test_main_comparison["stage2_qwen_correct"]}/{test_main_comparison["total"]}（{pct(test_main_comparison["stage2_qwen_correct"]/test_main_comparison["total"])}），低于冻结规则的{pct(test["main_trackable"]["accuracy_all"])}；该比较尚不能替代阶段四的四条件实验。保持按开发集选出的配置。','',
      '## 1. 视频切分与使用边界','',
      f'切分最先完成：seed42，排序后按 Python random.Random(42) 打乱689个视频，前138个为开发集，其余551个为测试集；对应147/602题，同视频无交叉。开发集可表达73题，其中主要四维70题；测试集可表达251题，其中主要四维231题。','',
      f'- {link("results/dev_test_split_locked.json","只读切分文件")}；生成时间 `{split.get("created_at",split.get("generated_at",split.get("locked_at","见文件")))}`。',
      f'- SHA256：`{frozen["split_sha256"]}`。',
      f'- 原预登记324题清单及规则保持不变：SHA256 `{frozen["preregistration_sha256"]}`。',
      '- 原阶段三报告在切分前已包含全集结果；本轮所有新参数选择仅使用开发集，测试集新规则准确率在冻结后才计算。全集结果包含参与调参的开发集，作为附带结果。',
      f'- {link("results/improvement_plan_locked.json","单轮计划")}登记于 `{plan["registered_at"]}`，截止 `{plan["deadline"]}`；不扩展搜索网格。','',
      '## 2. 已有预测的同子集比较（无需新推理）','',
      '以下为原阶段二Qwen预测与原阶段三规则预测，均在同一预登记子集计分；阶段二提示词尚未加入阶段四统一时间戳，因此这些Qwen分数不是未来条件A。','',
      '| 可表达子集 | 题数 | 阶段二 Qwen | 原规则 | 原规则覆盖率 |','|---|---:|---:|---:|---:|']
    for row in hist['comparison']:
        report.append(f'| {row["scope"]} | {row["total"]} | {row["qwen_correct"]}/{row["total"]} ({pct(row["qwen_accuracy"])}) | {row["rule_correct"]}/{row["total"]} ({pct(row["rule_accuracy"])}) | {pct(row["rule_coverage"])} |')
    report+=['',f'明细：{link("results/baseline_same_subset_comparison.csv")}。','',
      '## 3. 开发集逐项比较','',
      '所有选择的第一指标为主要四维可表达70题上的准确率（弃答计错），第二指标为覆盖率。记忆长度同分时使用固定窗口的“新ID或无法匹配”代理，再同分取较小记忆；过滤同分取较小K；事件协议同分取公开3fps定义。原版规则147题预测已逐项复核，与已接受输出完全一致。','',
      '### 3.1 MASA 身份记忆','',
      '| memo帧数（5fps） | 主要可表达正确/70 | 覆盖/70 | 开发全集正确/147 | 固定窗口新ID | 前后ID不同 | 无法判定 | 每查询轨迹均数 | 跨查询标签的原生ID数 |',
      '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for row in memory['candidates']:
        p=row['proxy'];m=row['primary']
        report.append(f'| {row["memory"]} ({row["memory"]/5:g}s) | {m["correct"]} ({pct(m["accuracy_all"])}) | {m["covered"]} | {row["all"]["correct"]} | {p["fresh_ids"]}/{p["judgeable"]} ({pct(p["fresh_id_ratio"])}) | {p["different_ids"]}/{p["judgeable"]} ({pct(p["different_ids"]/p["judgeable"])}) | {p["unjudgeable"]}/81 | {p["mean_tracks_per_query"]:.2f} | {p["multi_query_label_native_ids_at_0_2"]} |')
    report+=['',f'选择 memo={memory["selected_memory"]}。81个窗口在读取25/50结果前固定，仅来自开发集原10帧轨迹的几何重现候选；它们不是完整遮挡真值。新生ID从23降至19，但前后ID不同从29增至31，变化更多转向已有ID；不能据此宣称身份质量全面提高。无法匹配不会被算作身份保持。跨查询标签变化也不等同于真实ID切换率。','',
      '### 3.2 短弱轨迹过滤和 top-K 压缩','',
      '先删除“观测时长<0.6秒且平均置信度<0.3”的轨迹，再按平均置信度×观测时长降序排列；观测时长=观测帧数/5，同分按原生ID。无类别特例，不参考答案决定单题过滤。分别比较只删短弱轨迹、top5、top10；所有保留轨迹的全部原始区间仍保留。','',
      '| 过滤方案（固定所选memo、原事件协议） | 主要可表达正确/70 | 覆盖/70 | 开发全集正确/147 | 轨迹文本P95 | 最大token | 满足长度目标 |',
      '|---|---:|---:|---:|---:|---:|---|']
    original=read(f'results/improvement/dev/memo{memory["selected_memory"]}_original/metrics.json')
    original_lengths=read(f'results/improvement/dev/memo{memory["selected_memory"]}_original/lengths.json')
    om=original['groups']['main_trackable'];ol=original_lengths['groups']['dev']['track_text_tokens']
    report.append(f'| none | {om["correct"]} | {om["covered"]} | {original["groups"]["all"]["correct"]} | {ol["p95"]:.1f} | {ol["maximum"]} | {original_lengths["text_limits_met"]} |')
    for row in fil['candidates']:
        text=row.get('text');primary=row['primary']
        p95=f'{text["p95"]:.1f}' if text else '未用于长度选择'
        report.append(f'| {row["filter"]["name"]} | {primary["correct"]} | {primary["covered"]} | {row["all"]["correct"]} | {p95} | {text["maximum"] if text else "—"} | {row.get("text_limits_met","—")} |')
    report+=['',f'选择 `{fil["selected_filter"]["name"]}`。被省略轨迹仅用一行数量说明；保留逐帧原始JSON，压缩文本不写推导答案。','',
      '### 3.3 事件定义','',
      '[论文附录A表3](https://arxiv.org/html/2605.09904#A1)公开的时间尺度为3fps、最短完全遮挡2帧、重现需连续2个可见帧确认。候选实现保持MASA5fps，将可见性投影到3fps最近采样点，时间偏差至多1/15秒；两个缺失样本构成间断，两个连续可见样本确认重现并回溯到第一个可见样本。框缺失和边界位置仍是代理，部分遮挡/状态变化不据此判定。','',
      '| 事件协议（固定所选memo、过滤） | 主要可表达正确/70 | 覆盖/70 | 开发全集正确/147 |',
      '|---|---:|---:|---:|']
    for row in event['candidates']:
        report.append(f'| {row["event_mode"]} | {row["primary"]["correct"]} ({pct(row["primary"]["accuracy_all"])}) | {row["primary"]["covered"]} | {row["all"]["correct"]} |')
    report+=['',f'选择 `{event["selected_event"]}`。几何合并阈值、边界阈值0.05、顺序容差0.2秒均保持原协议。3个时间阈值边界 sanity case 已通过。','',
      '开发集可表达题的原版与最终所选方案：','',
      '| 维度 | 题数 | 原版正确/覆盖 | 所选方案正确/覆盖 |','|---|---:|---:|---:|']
    dev_original=read('results/improvement/dev/memo10_original/metrics.json')['groups']
    dev_selected=read('results/improvement/dev/'+frozen['dev_selected_label']+'/metrics.json')['groups']
    for dim in ('event_count','reappear_or_disappear','cross_object_order','event_ordering','reappear_identity'):
        a=dev_original['trackable_dimension:'+dim];b=dev_selected['trackable_dimension:'+dim]
        report.append(f'| {dim} | {a["total"]} | {a["correct"]}/{a["covered"]} | {b["correct"]}/{b["covered"]} |')
    before_numeric=read('results/improvement/dev/memo10_original/metrics.json')['numerical']
    after_numeric=read('results/improvement/dev/'+frozen['dev_selected_label']+'/metrics.json')['numerical']
    report+=['',f'开发集Count合法输出由{before_numeric["legal"]}/{before_numeric["covered"]}（覆盖题口径{pct(before_numeric["legal_ratio_covered"])}）变为{after_numeric["legal"]}/{after_numeric["covered"]}（{pct(after_numeric["legal_ratio_covered"])}）；按全部58道Count题计为{before_numeric["legal"]}/58→{after_numeric["legal"]}/58。0/1继续原样保留并按官方协议记错。']
    report+=['',
      '## 4. 开发集视觉检查与重新分配ID','',
      '本轮先看源视频再看新跟踪ID：9个开发视频、18张总览，加6个局部时间窗的12张5fps密集图和2张原尺寸复核图。源画面确认2个完整遮挡后返回窗口，涉及1只蓝杯和2枚白蛋。3个候选实体中，蓝杯和右侧蛋可匹配遮挡前后框，左侧蛋在注册的遮挡前帧无法匹配，单列为无法判定。其余部分遮挡、多实例歧义、旋转或终末遮挡不进入物理重现比例。','',
      f'人工逐项结果：{link("results/improvement_dev_memory_manual_review.json")}；带框对比图：{link("results/improvement_dev_memory_visual_comparison.json")}。','']
    report += [f'![蓝杯：三种记忆均恢复ID0，遮挡时有塑料瓶误检]({ROOT}/results/improvement/dev_memory_visuals/dev_blue_cup_arm.jpg)','',
               f'![鸡蛋：可辨的右侧蛋保持ID，另一枚蛋不计入匹配分母]({ROOT}/results/improvement/dev_memory_visuals/dev_eggs_forearm.jpg)','']
    for row in manual['summary']:
        report.append(f'- memo{row["memory"]}：可判定实体对 {row["judgeable"]}/{row["candidates"]}，新建ID {row["fresh_ids"]}/{row["judgeable"]}（{pct(row["fresh_id_ratio"])}），不同ID {row["different_ids"]}；另{row["unjudgeable"]}个实体无法对应，未算作身份保持。')
    report+=['', '该物理样本很小，两个窗口均短于原2秒记忆，不能单独说明长遮挡收益，也不能作为总体遮挡恢复率。固定81窗口代理提供更大但带检测选择偏差的开发集比较。蓝杯遮挡时存在将塑料瓶误检为蓝杯的框；鸡蛋样例另一枚蛋缺少可辨的遮挡前对应框，未将它的新ID算入已匹配实例的分母。','',
      '## 5. 一次性冻结与全部视频重新跟踪','',
      f'冻结于 `{frozen["frozen_at"]}`。{link("results/frozen_config_v1.json","冻结配置v1")}及其哈希回执均只读；SHA256：`{lock["sha256"]}`。',
      f'配置：MASA-GroundingDINO unified、5fps、FP16、score≥0.2、seed42、memo={frozen["tracking"]["memo_tracklet_frames"]}；文本以 ` . ` 分隔；不开SAM mask，不使用SAM2/SAM3；每视频重置跟踪状态及全部检测器文本缓存。',
      f'过滤：`{json.dumps(frozen["filter"],ensure_ascii=False)}`；序列化保留原生ID、均值置信度、全部可见区间、首次/末次位置、间断和一行省略数。事件规则为 `{frozen["rule"]["event_mode"]}`。',
      '冻结后689个视频均在 `tracks/v1/raw` 重新计算，未复用开发消融结果；899个查询均保存未过滤JSON、过滤JSON和证据文本。全部749题先提交唯一规则预测，再读取答案评分。',
      f'冻结配置全量复跑的开发题预测与所选开发试验一致：{reproduction["matching_predictions"]}/{reproduction["development_questions"]}；差异题清单保存在 {link("results/v1_dev_reproduction.json")}，不据此重新调参。',
      f'完整性：{integrity["videos"]}视频、{integrity["query_pairs"]}组合、{integrity["frames"]}帧；保留{integrity["retained_tracks"]}条轨迹，省略{integrity["omitted_tracks"]}条（短弱{integrity["short_weak_removed"]}、排序{integrity["rank_omitted"]}）。原始轨迹完整保留。','',
      f'- 开发记忆实验：{dev_job["elapsed_s"]/3600:.3f}小时墙钟，276个单元；两卡共享方式运行。',
      f'- 全量物理GPU：{", ".join(str(d["physical_index"]) for d in final_job["selected_devices"])}；UUID、启动前进程数及剩余显存见 {link("logs/improvement_final_job.json")}。',
      f'- 冻结后全量跟踪：{final_job["elapsed_s"]/3600:.3f}小时墙钟，逐视频处理时长合计{sum(r["inference_s"] for r in final_job["records"])/3600:.3f}卡小时（含共享等待与CPU环节）。',
      f'- 全量单worker显存：PyTorch allocated峰值{max(r["peak_gpu_allocated_bytes"] for r in final_job["records"])/2**30:.2f}GiB；NVML观测本任务进程峰值{final_job["owned_process_peak_MiB"]/1024:.2f}GiB；共享卡总占用峰值{final_job["shared_card_peak_MiB"]/1024:.2f}GiB，后者包含其他任务。',
      f'- {link("results/v1_integrity.json","完整性回执")}；{link("results/v1_track_index.json","轨迹索引")}。',
      f'- {link("logs/improvement_v1_validation.json","收尾核验")}：锁定文件与冻结代码哈希一致，本任务GPU worker均已退出。','',
      '## 6. 冻结后规则结果（测试集为主）','',
      '| 范围 | 题数 | 覆盖 | 覆盖率 | 严格正确 | 全分母准确率 | 覆盖题准确率 |','|---|---:|---:|---:|---:|---:|---:|']
    for scope,title in [('test','测试'),('full','全集（开发参与调参）')]:
        for name in ('all','main','trackable','main_trackable'):
            r=metrics[scope]['groups'][name]
            report.append(f'| {title}/{name} | {r["total"]} | {r["covered"]} | {pct(r["coverage"])} | {r["correct"]} | {pct(r["accuracy_all"])} | {pct(r["accuracy_on_covered"])} |')
    for scope,title in [('test','测试集'),('full','全集（附带）')]:
        report+=['',f'### {title}分维度','', '| 维度 | 全部题：覆盖/题数 | 全部题准确率 | 可表达：覆盖/题数 | 可表达准确率 | 可表达覆盖题准确率 |','|---|---:|---:|---:|---:|---:|']
        for dim in ('event_count','reappear_or_disappear','cross_object_order','event_ordering','reappear_identity'):
            a=metrics[scope]['groups']['dimension:'+dim];b=metrics[scope]['groups']['trackable_dimension:'+dim]
            report.append(f'| {dim} | {a["covered"]}/{a["total"]} | {pct(a["accuracy_all"])} | {b["covered"]}/{b["total"]} | {pct(b["accuracy_all"])} | {pct(b["accuracy_on_covered"])} |')
        n=metrics[scope]['numerical']
        report+=['',f'数值规则合法答案比例：{n["legal"]}/{n["total"]}（{pct(n["legal_ratio_all"])}）；在覆盖题中为{n["legal"]}/{n["covered"]}（{pct(n["legal_ratio_covered"])}）。不将0/1静默改写为合法答案。']
    report+=['','## 7. 同一子集的 Qwen 与冻结规则对照','',
             '下表全部使用同一组题作为分母。Qwen来自阶段二已有预测；条件A将在阶段四统一格式下重新运行。','',
             '| 范围/子集 | 题数 | 阶段二Qwen | 原规则 | 冻结规则 | 冻结规则覆盖率 |',
             '|---|---:|---:|---:|---:|---:|']
    for row in comparisons:
        if row['scope']=='dev' or row['group'] not in ('all','main','trackable','main_trackable') and not row['group'].startswith('trackable_dimension:'):continue
        n=row['total']
        report.append(f'| {row["scope"]}/{row["group"]} | {n} | {row["stage2_qwen_correct"]}/{n} ({pct(row["stage2_qwen_correct"]/n)}) | {pct(row["original_rule_correct"]/n)} | {row["frozen_rule_correct"]}/{n} ({pct(row["frozen_rule_correct"]/n)}) | {pct(row["frozen_rule_covered"]/n)} |')
    report+=['',f'全维度与开发集明细见 {link("results/v1_baseline_comparison.csv")}。','',
             '## 8. 压缩文本及完整输入长度','',
             '使用本地Qwen tokenizer和实际图像处理器核算。8种开发帧形状已同时校验实际像素网格、展开图像占位符后的输入长度。全部视频均使用官方缓存JPEG的实际尺寸和采样索引/FPS时间戳。A/B/C按官方格式加时间戳及相应证据精确计数；D尚不分配打乱对象，以每查询最大轨迹文本加边界余量计算保守上界。无模型推理。','',
             '| 范围 | 轨迹文本中位/P95/最大 | B完整输入中位/P95/最大 | A完整输入最大 | C完整输入最大 | D完整输入上界最大 |',
             '|---|---:|---:|---:|---:|---:|']
    for name in ('dev','test','all'):
        group=lengths['groups'][name];t=group['track_text_tokens'];b=group['complete_input_tokens']['B']
        report.append(f'| {name} | {t["median"]:g}/{t["p95"]:g}/{t["maximum"]} | {b["median"]:g}/{b["p95"]:g}/{b["maximum"]} | {group["complete_input_tokens"]["A"]["maximum"]} | {group["complete_input_tokens"]["C"]["maximum"]} | {group["complete_input_tokens"]["D_upper_bound"]["maximum"]} |')
    maximum=lengths['groups']['all']['input_plus_supplement_reserve']['maximum']
    query_lengths=lengths['query_text_tokens']
    report+=['',f'899个唯一视频—查询文本的中位/P95/最大为{query_lengths["median"]:g}/{query_lengths["p95"]:g}/{query_lengths["maximum"]} token。',
             f'全集每题合并轨迹文本达到P95≤8000、最大≤12000的目标。冻结的未来共同服务配置为 `max_model_len=65536`，A/B/C/D全部一致；包括D上界和1024生成余量的最大输入需求为{maximum} token，低于65536及模型支持的128000。主实验仍使用普通题64、排序题256 token；1024仅用于补充模板容量预留。',
             f'按当前实测长度，最小可容纳的候选上下文为{lengths["minimum_fitting_context"]}；v1按冻结时的保守预算统一预留65536。本阶段只做CPU长度核算，尚未启动该vLLM服务配置。',
             f'明细：{link("results/v1_input_lengths.json")}。','',
             '## 9. 保留的问题与下一阶段边界','',
             '- 本轮停止调参并保持冻结配置。部分遮挡/状态突变仍无法由主序列化直接表达；B2面积比变体列为待办，不替代B、不修改预登记子集。',
             '- 本轮主要四维测试准确率下降，ReID新增正确题也未改变该结论。几何代理、少量物理样例、类别无关关联的标签变化均有局限；对大模型使用轨迹后的收益仍需阶段四验证。',
             '- 阶段四待用户确认后运行：官方格式主实验A/B/C/D均重跑并加相同时间戳；主报测试集，附带全集及固定可表达子集；计数题额外报合法比例及四条件独立约束解码诊断；简短推理模板四条件另跑、分开报告。',
             f'- 不将subject_label、semantic_ground_truth、ground_truth_is_real等metadata送入任何模型提示词。ReID保持次要分析；既有ReID及数值官方提示词诊断见 {link("results/stage3_report.md","原阶段三报告")}。','']
    path=ROOT/'results/stage3_improvement_report.md';path.write_text('\n'.join(report))
    receipt=dict(status='STAGE3_SINGLE_ROUND_COMPLETE_AWAITING_STAGE4_CONFIRMATION',completed_at=now(),
                 report=str(path),frozen_config_sha256=lock['sha256'],test=test['all'],test_trackable=test['trackable'],
                 test_main_trackable=test['main_trackable'],test_main_trackable_change_percentage_points=main_delta,
                 text_limits_met=True,stage4_inference_run=False,preregistration_unchanged=True,
                 total_wall_hours=(datetime.fromisoformat(now())-datetime.fromisoformat(plan['registered_at'])).total_seconds()/3600)
    write_json(ROOT/'results/stage3_improvement_receipt.json',receipt)
    print(json.dumps(receipt,ensure_ascii=False))


if __name__=='__main__':main()
