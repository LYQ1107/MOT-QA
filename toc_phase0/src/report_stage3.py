"""Assemble the completed stage-three report from saved experimental results."""
import csv
import json
from pathlib import Path

from run_stage3_masa import ROOT,now,write_json

DIMENSIONS=['event_count','reappear_or_disappear','cross_object_order','event_ordering','reappear_identity']


def load(name):return json.loads((ROOT/name).read_text())
def link(name,label=None):return f'[{label or Path(name).name}]({ROOT/name})'
def percent(value):return 'N/A' if value is None else f'{100*value:.2f}%'


def main():
    integrity=load('results/stage3_integrity.json')
    assert integrity['status']=='STAGE3_INTEGRITY_PASSED'
    scope=load('results/stage3_scope_summary.json')
    prereg=load('results/trackable_subset_preregistered.json')
    pilot=load('results/stage3_pilot_receipt.json')
    full=load('results/stage3_full_receipt.json')
    frozen=load('results/stage3_tracker_frozen.json')
    metrics=load('results/stage3_rule_metrics.json')
    diagnostics=load('results/stage3_diagnostics.json')
    review=load('results/stage3_manual_review.json')
    setup=load('logs/masa_setup_receipt.json')
    resampling=load('results/stage3_resampling_receipt.json')
    interruption=load('logs/stage3_full_interruption_attempt1.json')
    lengths=load('results/stage3_evidence_lengths.json')
    drift=load('results/stage3_query_label_drift.json')
    assert review['threshold_calibration_videos']==20 and len(review['detailed_review_videos'])==10
    lines=[
        '# 阶段三：MASA 轨迹与规则基线', '',
        f'完成 **749 题、689 个唯一视频、899 个视频—短语组合** 的 MASA 统一模型跟踪、逐帧 JSON 和原始事实文本。'
        f'四个重点维度726题，另含ReID23题；阶段四未运行。报告生成时间：{now()}。', '',
        f'抽取结果与 `subject_label` 的锚定目标规范化匹配为 **746/749（99.60%）**；'
        f'预登记可表达子集为 **324题**，其中重点四维301题。'
        f'规则覆盖 **{metrics["groups"]["full_749"]["covered"]}/749**，覆盖题准确率 **{percent(metrics["groups"]["full_749"]["accuracy_on_covered"])}**；'
        f'弃答计错后，全集 **109/749（14.55%）**，可表达子集 **109/324（33.64%）**。', '',
        '## 数据范围与目标抽取', '',
        '- 四个重点维度：726题/669视频；含ReID总计749题/689视频。源数据为407个Charades、275个PerceptionTest、7个MOSE视频。',
        '- 按视频合并查询后共899个唯一视频—短语组合：489个视频1短语、190个2短语、10个3短语。每次MASA调用的多个短语用 ` . ` 连接。',
        '- 抽取输入包括question、option_A–D、statement_A/B及events.event_text；排序事件中的it回指问题目标。先保存无metadata的输入投影与全部抽取结果，再读取subject_label做离线评估。未据评估标签修正查询。',
        '- 跨对象187题均提取两个目标。该版本subject_label只记录一个锚定对象，因此本次可独立核对锚定对象召回，不能把它声称为完整双对象精确率。',
        '- 分维度锚定目标规范化匹配：Count298/300、R/D134/134、X-Order186/187、Order105/105、ReID23/23。',
        '- 当前749题的hallucination字段均为空，has_hallucination_distractor也均为False：幻觉变体样本数0，单列结果为N/A。', '',
        '| 未精确匹配qa_id | 从题面抽取 | subject_label（仅评估） |',
        '|---|---|---|',
    ]
    for row in scope['extraction_mismatches']:
        lines.append(f'| {row["qa_id"]} | {"; ".join(row["predicted"])} | {row["subject_label"]} |')
    lines += ['', '前两条分别为题面/metadata颜色冲突与单复数差异，第三条为题面两个目标和metadata对象冲突。均保留题面抽取。',
              '完整输入、抽取、评估分别见 '+link('results/stage3_visible_inputs.jsonl')+'、'+link('results/stage3_extracted_queries.json')+'、'+link('results/stage3_query_evaluation.json')+'。',
              '', '## 事件类型与预登记', '',
              '按全部可见文本中的谓词多标签分类，每种事件在同一题只计一次；同题可进入多行，列和不代表题目总数。', '',
              '| 事件类型 | Count | R/D | X-Order | Order | ReID |',
              '|---|---:|---:|---:|---:|---:|']
    for kind,counts in scope['event_type_dimension_counts'].items():
        lines.append('| '+kind+' | '+' | '.join(str(counts.get(dim,0)) for dim in DIMENSIONS)+' |')
    lines += ['', '其中部分遮挡共299题：Count68、X-Order149、Order82；状态突变126题，均为Count。两类合计425题，不可由当前框/可见区间直接表达，序列化格式保持原约定。', '',
              '| 维度 | 全集题数 | 预登记可表达题数 |', '|---|---:|---:|']
    for dim in DIMENSIONS:
        lines.append(f'| {dim} | {metrics["groups"]["dimension:"+dim]["total"]} | {scope["trackable_per_dimension"][dim]} |')
    lines += ['', f'纳入规则：题面提到的全部事件均可用框的有无、可见区间或位置作代理；任一partly hidden、changes abruptly或other即排除。全遮挡与离开画面仅能通过位置近似区分，不等于有遮挡真值。',
              f'清单生成于 **{prereg["created_at"]}**，阶段四前已只读锁定；完成时确认内容不变。清单为 '+link('results/trackable_subset_preregistered.json')+'，锁定凭据为 '+link('logs/trackable_subset_lock.json')+'。阶段四须分别报告全集及该子集。',
              '', '## MASA 运行与性能', '',
              f'- 官方MASA commit `{setup["official_code_commit"]}`；unified `gdino_masa.pth`，自定义实体模式，FP16、种子42，不使用SAM mask、SAM2、SAM3或ByteTrack。',
              f'- 原视频先重采样为5 fps（ffmpeg fps=5:start_time=0，H.264 CRF18，保持空间分辨率），共{resampling["frames"]:,}帧。派生视频{resampling["bytes"]/1024**3:.2f} GiB，转码墙钟{resampling["elapsed_s"]/60:.2f}分钟；原始视频保留。',
              f'- 完成固定种子选取的20视频视觉抽查后，输出分数阈值固定为 **{frozen["output_score_threshold"]}**，时间为{frozen["frozen_at"]}。'+frozen['threshold_rationale'],
              '- 内部MasaTaoTracker沿用官方默认：init0.1、obj0.01、match0.5、memo10帧、momentum0.8、with_cats=False、max_distance100；fps设为5。memo10帧对应2秒，长遮挡后可能产生新ID。',
              '- 直接使用官方统一推理API。保留每次检测原始置信度，不启用演示脚本中跨轨迹平均分等后处理；输出阈值只用于逐短语文件与文本过滤。',
              '- 本阶段仅运行MASA，未启动vLLM；与vLLM环境的后续交互只通过磁盘JSON。按用户追加授权共享显卡，优先少进程且显存充足的卡，不终止其他任务。',
              f'- 20视频试跑墙钟 **{pilot["elapsed_wall_s"]/60:.2f}分钟**；全量续跑控制器（复用38个已完成视频，含20试跑）墙钟 **{full["elapsed_wall_s"]/3600:.3f}小时**。各视频处理墙钟求和 **{full["summed_video_inference_s"]/3600:.3f}卡时**，等效单进程吞吐{full["frames"]/full["summed_video_inference_s"]:.2f}帧/秒；该时间含CPU解码/预处理及共享资源等待，不等于纯GPU内核用时。',
              f'- 两次完整结束的跟踪控制器墙钟合计 **{(pilot["elapsed_wall_s"]+full["elapsed_wall_s"])/3600:.3f}小时**；无效缓存试跑开销下文另列，转码等并行CPU工作不重复相加，配置与GPU回归等调试时间未计入跟踪墙钟。',
              f'- 首次全量控制终端收到SIGTERM（退出143，来源未确定），无Python异常/OOM日志；最后一条监控时已运行约{interruption["observed_runtime_to_last_monitor_s"]/60:.2f}分钟。38个完整输出（含20试跑）检查通过后复用，未完成视频重算。随后改为独立tmux批作业和持久退出回执，完成后再评分，未跳过样本。含该次中断，跟踪控制器运行墙钟约{(pilot["elapsed_wall_s"]+full["elapsed_wall_s"]+interruption["observed_runtime_to_last_monitor_s"])/3600:.3f}小时；不含图像审查与调试间隔。',
              f'- MASA单进程PyTorch峰值：allocated **{full["max_gpu_allocated_bytes"]/1024**3:.2f} GiB**、reserved **{full["max_gpu_reserved_bytes"]/1024**3:.2f} GiB**；单卡本任务进程由nvidia-smi观测的峰值 **{max(pilot["owned_process_memory_peak_MiB"],full["owned_process_memory_peak_MiB"],interruption["observed_own_memory_peak_MiB"])/1024:.2f} GiB**。共享卡单卡总占用峰值 **{max(pilot["physical_memory_peak_MiB"],full["physical_memory_peak_MiB"],interruption["observed_shared_card_memory_peak_MiB"])/1024:.2f} GiB**，包括其他任务，不归因于MASA。',
              '- 最后一次全量控制器设备：'+', '.join(f'GPU{d["physical_index"]}（{d["uuid"]}）' for d in full['devices'])+'。各阶段成功视频按物理GPU计数：`'+json.dumps(integrity['physical_gpu_video_counts'])+'`。分片按试跑速度估算，未试跑设备使用试跑汇总速度；分配快照和进程级显存记录保存在logs/stage3_*allocation*与*gpu_memory*。',
              f'- 完整性：689视频/899逐短语JSON与文本/749规则预测，无缺失或重复。过滤后{integrity["filtered_observations"]:,}条观测；空轨迹组合{integrity["empty_video_query_pairs"]}/899。轨迹可见间隔按>0.5秒断开，坐标为归一化中心、两位小数，文本不包含推导答案。',
              f'- 原生ID在同一视频中对应多个查询标签：未过滤原始数据为{drift["raw_all_scores"]["ids"]}个ID/{drift["raw_all_scores"]["videos"]}视频；最终≥0.2观测为{drift["score_at_least_0_2"]["ids"]}个ID/{drift["score_at_least_0_2"]["videos"]}视频，原样保留。该统计描述标签变化，缺少逐帧真值验证，不称为真实身份切换率。见 '+link('results/stage3_query_label_drift.json')+'。',
              '- 原始轨迹目录 '+link('tracks/raw','tracks/raw')+'；逐短语文件目录 '+link('tracks/by_query','tracks/by_query')+'；索引 '+link('results/stage3_track_index.json')+'。',
              f'- 使用本地Qwen tokenizer在CPU测量逐题轨迹文本：中位数{lengths["per_question_tokens"]["median"]:,} token、P95 {lengths["per_question_tokens"]["p95"]:,}、最大{lengths["per_question_tokens"]["maximum"]:,}；仅轨迹文本超过阶段二服务32768上下文配置的有{lengths["per_question_tokens"]["over_32768"]}题。这里不包含32张图像、问题、时间戳及证据前言，不能当作完整输入长度。未构造阶段四提示词、未截断文本、未运行vLLM/模型推理。详情见 '+link('results/stage3_evidence_lengths.json')+'。',
              '', '启动失败及修复：第一次在模型构造阶段失败，原因是阶段一构造后导出的配置含MMDetection注入字段；改为从官方原始配置加载、覆盖本地BERT/fps后在构造前留快照，CPU针对性重建通过。自定义实体模式不使用NER，增加环境开关跳过导入时无关NLTK自动下载；未改模型算法。保留失败日志和 '+link('logs/masa_stage3_local_patch.diff')+'。',
              '', '第一批20视频虽通过结构检查，按查询汇总时暴露出官方跨视频文本缓存未失效：换prompt后只刷新token映射，缓存文本特征仍来自首个视频。已判为无效并完整保存在 '+link('tracks/diagnostics/pilot_stale_text_cache','无效试跑诊断目录')+'，不参与后续评分；其墙钟10.65分钟、推理耗时合计14.78 GPU分钟另计。修复是在每个视频开始时清空检测器四个文本缓存属性，保持模型、权重、提示词和算法一致。实际统一模型回归验证相同图像在修复后连续帧检测输出一致，再重跑相同20视频。证据见 '+link('logs/stage3_text_cache_regression.json')+'。',
              '', '## 规则基线', '',
              '规则只读取题面和轨迹，全部749题预测先落盘，再读取正确答案调用官方解析和评分。无法表达、事件未观察到或5fps下时间打平时弃答；弃答在全集准确率分母内计错。计数规则保留0/1，不强行映射为合法答案。',
              '预先记录的规则：置信度总和最大的轨迹为主体，按间隔≤10秒、中心距离≤0.25、面积比≤3拼接非重叠碎片；可见间隔>0.5秒定义间断；边缘阈值0.05区分离框/全遮挡代理；排序容差0.2秒。ReID比较间断前后的原始ID，不合并ID后再回答同一性。', '',
              '| 范围 | 题数 | 覆盖数 | 覆盖率 | 正确数 | 全集准确率 | 覆盖题准确率 |',
              '|---|---:|---:|---:|---:|---:|---:|']
    group_order=['full_749','trackable_324','main_726','main_trackable_301']+['dimension:'+d for d in DIMENSIONS]+['trackable_dimension:'+d for d in DIMENSIONS]
    with (ROOT/'results/stage3_rule_summary.csv').open('w',newline='') as handle:
        writer=csv.writer(handle);writer.writerow(['group','total','covered','coverage','correct','accuracy_all','accuracy_on_covered'])
        for name in group_order:
            row=metrics['groups'][name]
            writer.writerow([name,*[row[k] for k in ('total','covered','coverage','correct','accuracy_all','accuracy_on_covered')]])
            lines.append(f'| {name} | {row["total"]} | {row["covered"]} | {percent(row["coverage"])} | {row["correct"]} | {percent(row["accuracy_all"])} | {percent(row["accuracy_on_covered"])} |')
    num=metrics['numerical']
    lines += ['', f'计数合法集合为{{2,3,4,5 or more}}：规则合法答案 **{num["legal"]}/300（{percent(num["legal_ratio_all"])}）**；在{num["covered"]}道规则已覆盖计数题中，合法比例为 **{percent(num["legal_ratio_covered"])}**。',
              '按事件类型统计覆盖与准确率：', '',
              '| 事件类型（重叠计数） | 总数 | 覆盖 | 正确 | 全集准确率 | 覆盖题准确率 |', '|---|---:|---:|---:|---:|---:|']
    for kind,row in metrics['event_types'].items():
        lines.append(f'| {kind} | {row["total"]} | {row["covered"]} | {row["correct"]} | {percent(row["accuracy_all"])} | {percent(row["accuracy_on_covered"])} |')
    lines += ['', '完整弃答原因：`'+json.dumps(metrics['abstention_reasons'],ensure_ascii=False)+'`。',
              '规则参数与评分见 '+link('results/stage3_rule_protocol.json')+'、'+link('results/stage3_rule_metrics.json')+'；逐题预测见 '+link('results/stage3_rule_predictions.jsonl')+'。',
              '', '## 视觉抽查与遮挡后新ID', '',
              review['selection_explanation'], '',
              '| 视频 | 查询 | 抽查观察 | 可视化 |', '|---|---|---|---|']
    for row in review['detailed_review_videos']:
        lines.append(f'| {row["video_id"]} | {"; ".join(row["queries"])} | {row["observation"]} | [{Path(row["visualization"]).name}]({row["visualization"]}) |')
    lines += ['', review['occlusion_new_id_summary'], '',
              '遮挡前／遮挡中／重现后带框对照：'+ '、'.join(link(f'results/stage3_visualizations/occlusion_cases/occlusion_page{i:02d}.jpg',f'第{i+1}页') for i in range(5))+'。逐事件原始ID、首现帧和候选修正记录见 '+link('results/stage3_occlusion_manual_events.json')+'。', '',
              '视觉审查由本代理依据保存的原画面与带框图完成，比例为小样本目视估计。源画面也出现只跨一个5fps采样帧的完整遮挡；按既定>0.5秒断开规则，这些短缺口可能在文本中被合并。预登记的“可表达”不保证检测成功、身份正确或这种短时事件在序列化后仍可分辨；本阶段保持清单与格式不变。', '',
              '20视频阈值抽查见 '+link('results/stage3_threshold_review_20.json')+'。另一次10视频遮挡审查的逐事件证据与不确定项见 '+link('results/stage3_manual_review.json')+'；抽样清单为 '+link('results/stage3_occlusion_audit_selection.json')+'。自动检测到的时间间断不直接当作物理遮挡，漏检和离开画面单列。',
              '', '## numerical官方提示词原文与阶段四分析约定', '',
              '以下为官方build_prompt的完整numerical文本（图像块在user文本之前，{question}为实际题目）：', '',
              '```text', (ROOT/'results/numerical_official_prompt.txt').read_text().strip(), '```', '',
              '它把2、3、4列为“e.g.”示例，并允许“5 or more”；没有明确将输出限定在四个合法值，也没有明文禁止0/1。官方解析却拒绝0/1。阶段二原始输出严格落入合法集合为8/300（2.67%），官方解析有效为10/300（3.33%，解析会把更大整数归一到5 or more）。',
              '阶段四所有A/B/C/D的主结果保留官方无约束严格准确率；另报合法答案比例，并将全部计数题在四个条件下各做一次约束解码分析。主提示词与简短推理补充模板各自独立运行、分别报告。本阶段只记录 '+link('results/stage4_numerical_analysis_plan.json')+'，未运行任何阶段四推理。',
              '', '## ReID标注与repair_log诊断', '',
              '23题的正确选项语义全部与semantic_ground_truth一致：13题same、10题different；ground_truth_is_real分别为True/False。字段仅用于离线诊断，不进入目标抽取、跟踪、规则或模型提示词。', '',
              '| correct_answer | semantic_ground_truth | ground_truth_is_real | 数量 |', '|---|---|---|---:|']
    for row in diagnostics['reid']['correspondence']:
        lines.append(f'| {row["correct_answer"]} | {row["semantic_ground_truth"]} | {row["ground_truth_is_real"]} | {row["count"]} |')
    repairs=diagnostics['all_repairs']
    lines += ['', '23道ReID均无repair_log。全部100条repair_log记录也无ReID。维度分布：`'+json.dumps(repairs['by_dimension'],ensure_ascii=False)+'`；改动分布：`'+json.dumps(repairs['by_change'],ensure_ascii=False)+'`。主要为选项/陈述置换并同步正确字母，另有一条答案大小写修复。没有证据表明repair_log导致ReID差异。',
              '阶段二预测22题选same、1题选different：按发布标注12/23=52.17%；若仅在诊断中假设23题语义答案全为same，则为22/23=95.65%，四舍五入恰好为论文95.7%。这个反事实在数值上可以解释差值，不能据此证明论文采用了该标注。原始标注未修改，ReID保留为次要维度。',
              '逐题对应、全部100条修复及反事实评分见 '+link('results/stage3_diagnostics.json')+'。',
              '', '## 环境与来源', '',
              '- 独立MASA环境：'+', '.join(f'{k} {setup["versions"][k]}' for k in ('python','torch','torchvision','mmcv','mmengine','mmdet','transformers','numpy'))+'。',
              '- unified权重来自官方README指定的HF仓库 `dereksiyuanli/masa`，固定revision '+setup['weights']['hf_revision']+'；下载使用hf-mirror直连，BERT使用ModelScope，均在阶段一完成。代码、依赖和权重来源/大小/校验保存在 '+link('logs/downloads.md')+'，本阶段没有新增下载。',
              '', '## 结论与阶段门', '', review['quality_conclusion'], '',
              '阶段三所需跟踪、序列化、规则基线、预登记、可视化和诊断均已保存；当前停在阶段三，未进入阶段四。']
    (ROOT/'results/stage3_report.md').write_text('\n'.join(lines)+'\n')
    receipt=dict(status='STAGE3_COMPLETE_STOPPED_BEFORE_STAGE4',completed_at=now(),questions=749,videos=689,query_pairs=899,
                 main_questions=726,trackable_questions=324,main_trackable_questions=301,
                 extraction_exact_matches=746,rule_metrics=metrics['groups'],stage4_started=False,
                 report=str(ROOT/'results/stage3_report.md'),quality_conclusion=review['quality_conclusion'])
    write_json(ROOT/'results/stage3_receipt.json',receipt)
    print(json.dumps(receipt,indent=2,ensure_ascii=False))


if __name__=='__main__':main()
