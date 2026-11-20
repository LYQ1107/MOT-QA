"""Summarize Stage3 counts, hard checks and the old/new20 rule differences."""
import hashlib,json,math
from collections import Counter,defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import generate_candidates_round2 as g
R=g.ROOT;D=g.RES

def majority(rows,key):
 c=Counter(key(q) for q in rows);return max(c.values(),default=0)/max(1,len(rows))
def outcome(q):
 if q['format'].startswith('numeric'):return str(q['answer'])
 return q['answer']
def semantic(q):
 if q['format']=='numeric_time':return 'time:'+str(q['answer'])
 if q['format']=='numeric_count':return 'count:'+str(q['answer'])
 if q['option_provenance'].get(q['answer'])!='correct':raise RuntimeError('Wrong option provenance')
 if q.get('option_modality')=='image':return 'portrait_slot:'+q['answer']
 if q['template_id'] in ['return_time','closest_time','cross_time']:return 'time_bin:'+str(q['answer_index'])
 if q['operation_name']=='O8':return q['semantic_answer']
 return q['semantic_answer']
def table(head,rows):return '| '+' | '.join(head)+' |\n|'+'|'.join(['---']*len(head))+'|\n'+''.join('| '+' | '.join(str(v).replace('|','/') for v in r)+' |\n' for r in rows)

def main():
 qs=g.rows(R/'data/candidates.jsonl');old=g.rows(R/'data/question_review_user_passed_20.jsonl');new=g.rows(R/'data/precheck_round2_20.jsonl');audit=json.loads((D/'raw_gt_answer_audit.json').read_text());assert audit['status']=='PASSED'
 totals={'count':len(qs),'operations':dict(Counter(q['operation_name'] for q in qs)),'datasets':dict(Counter(q['dataset'] for q in qs)),'references':dict(Counter(q['reference']['type'] for q in qs)),'formats':dict(Counter(q['format'] for q in qs)),'template_families':dict(Counter(q['template_id'] for q in qs)),'O8_subtypes':dict(Counter(q['evidence']['gt_detail']['subtype'] for q in qs if q['operation_name']=='O8')),'O8_same_answers':dict(Counter(q['semantic_answer'] for q in qs if q['template_id']=='identity_same')),'identity_challenge_count':sum(q['difficulty']['identity_challenge'] for q in qs),'simple_control_count':sum(not q['difficulty']['identity_challenge'] for q in qs),'binary_count':sum(q['format']=='multiple_choice' and len(q['options'])==2 for q in qs),'image_option_count':sum(q.get('option_modality')=='image' for q in qs),'held_out_paraphrase_count':sum(q['paraphrase_split']=='held_out' for q in qs),'composition_count':sum(q['split_role']=='held_out_composition' for q in qs),'GT_check':audit['status'],'candidate_SHA256':hashlib.sha256((R/'data/candidates.jsonl').read_bytes()).hexdigest(),'formal_release_completed':False,'filtering_executed':False,'stage5_inference_executed':False}
 vc=Counter((q['dataset'],q['sequence']) for q in qs);pc=Counter((q['dataset'],q['sequence'],q['reference']['primary_target_id']) for q in qs);totals.update(videos_used=len(vc),max_per_video=max(vc.values()),primary_identities=len(pc),max_primary_reuse=max(pc.values()))
 choice=[q for q in qs if q['format']=='multiple_choice'];totals['confusion_option_count']=sum(q['has_confusion_option'] for q in choice);totals['choice_count']=len(choice);totals['confusion_option_fraction']=totals['confusion_option_count']/len(choice)
 ordinary=[q for q in qs if q['operation_name']!='O7'];totals['ordinary_never_correct']=sum(q['semantic_answer']==g.NEVER for q in ordinary);totals['ordinary_never_fraction']=totals['ordinary_never_correct']/len(ordinary);totals['ordinary_never_distractor']=sum(g.NEVER in q['options'].values() and q['semantic_answer']!=g.NEVER for q in ordinary)
 groups=defaultdict(list)
 for q in qs:groups[q['operation_name']].append(q)
 totals['operation_dataset_counts']={op:dict(Counter(q['dataset'] for q in rs)) for op,rs in sorted(groups.items())}
 totals['answer_distributions']={op:{'choice_letters':dict(Counter(q['answer'] for q in rs if q['format']=='multiple_choice')),'semantic_classes':dict(Counter(semantic(q) for q in rs if q['format']=='multiple_choice')),'numeric_count':dict(Counter(str(q['answer']) for q in rs if q['format']=='numeric_count'))} for op,rs in sorted(groups.items())}
 totals['difficulty_quantiles']={}
 for field in ['n_crossings','max_gap_s','density','appearance_similarity']:
  vals=np.array([q['difficulty'][field] for q in qs],float);totals['difficulty_quantiles'][field]=dict(zip(['min','p25','p50','p75','p95','max'],np.quantile(vals,[0,.25,.5,.75,.95,1]).tolist()))
 totals['camera_motion_counts']=dict(Counter(q['difficulty']['camera_motion'] for q in qs))
 blind={};balance_warnings=[]
 for op,rs in sorted(groups.items()):
  cats=[q for q in rs if q['format']=='multiple_choice'];nums=[q for q in rs if q['format'].startswith('numeric')]
  def dsmajor(rows,fun):
   ds=defaultdict(list)
   for q in rows:ds[q['dataset']].append(q)
   return sum(len(v)*majority(v,fun) for v in ds.values())/max(1,len(rows))
  x={'n':len(rs),'multiple_choice_n':len(cats),'numeric_n':len(nums),'majority_answer_letter':majority(cats,outcome),'uniform_random_choice':float(np.mean([1/len(q['options']) for q in cats])) if cats else None,'dataset_only_answer_letter':dsmajor(cats,outcome),'semantic_majority':majority(cats,semantic),'semantic_dataset_only':dsmajor(cats,semantic),'numeric_random_baseline':'not defined for continuous/exact free response; do not equate it with4-choice chance','numeric_modal_exact_answer':majority(nums,outcome) if nums else None}
  blind[op]=x
  if cats and x['dataset_only_answer_letter']-x['majority_answer_letter']>.0500001:balance_warnings.append({'operation':op,'metric':'dataset_only_letter_minus_majority','delta':x['dataset_only_answer_letter']-x['majority_answer_letter']})
  if op!='O7' and cats and x['majority_answer_letter']-x['uniform_random_choice']>.1000001:balance_warnings.append({'operation':op,'metric':'majority_minus_uniform','delta':x['majority_answer_letter']-x['uniform_random_choice']})
  if cats and x['semantic_dataset_only']-x['semantic_majority']>.0500001:balance_warnings.append({'operation':op,'metric':'semantic_dataset_only_minus_majority','delta':x['semantic_dataset_only']-x['semantic_majority']})
  if op!='O7' and cats and x['semantic_majority']-x['uniform_random_choice']>.1000001:balance_warnings.append({'operation':op,'metric':'semantic_majority_minus_uniform','delta':x['semantic_majority']-x['uniform_random_choice']})
 totals['blind_baselines']=blind;totals['balance_warnings']=balance_warnings;g.dump(D/'summary.json',totals)
 if balance_warnings:raise RuntimeError('Rebalance required before Stage3 delivery: '+json.dumps(balance_warnings))
 # Old samples are immutable examples, not formal candidates.
 prior=json.loads((R/'results/generation_history/round1/generation_config_locked.json').read_text())['design_examples'] if False else None
 diff=['# 第二轮规则：20道模板样例逐题差异\n','旧版是用户已通过的17原题＋3时间顺序替换题。旧版按字节保留；下列修订版仅检查新规则，不计入900候选，无需用户重审。\n','各题优先保留原数据集和操作；为通过更严格条件，必要时更换身份、片段或指代。第6/13题互换事件/框标指代，使总体仍为8框标/5事件/4外观/3位置。第13题由最近距离时段改为交错次数；第10题无法保留合法否例时改为正例。\n']
 for a,b in zip(old,new):
  key=b['dataset'],b['sequence'];e=b['evidence'];dd=e['gt_detail'];oldans=a['options'][a['answer']];newans=b['answer'] if b['format'].startswith('numeric') else b['options'][b['answer']]
  changes=[]
  for name,aa,bb in [('视频',a['sequence'],b['sequence']),('主目标',a['reference']['persons'][0]['target_id'],b['reference']['primary_target_id']),('指代方式',a['reference']['type'],b['reference']['type']),('题目格式',a['format'],b['format']),('模板',a['template_id'],b['template_id'])]:
   if aa!=bb:changes.append(f'{name}：{aa} → {bb}')
  changes+=['所有参考图通过统一几何门槛；增加3倍裁剪','决定性事件距区间两端≥1秒；间断如涉及则≥1.5秒','时间分段如涉及则区间≥4秒且每段≥1秒','身份难度：'+str(b['difficulty']['identity_challenge'])]
  diff += [f'\n## 第{a["review_index"]}题\n',f'- 旧ID：{a["qa_id"]}；新ID：{b["qa_id"]}\n',f'- 旧题：{a["question_zh"]}\n',f'- 新题：{b["question_zh"]}\n',f'- 旧答案：{oldans}；新答案：{newans}\n',f'- 新问题区间：{g.sec(key,e["query_start_frame"]):.3f}–{g.sec(key,e["query_end_frame"]):.3f} 秒\n']+[f'- {x}\n' for x in changes]
 diff += ['\n修订版20题：'+json.dumps({'reference':dict(Counter(q['reference']['type'] for q in new)),'numeric':sum(q['format'].startswith('numeric') for q in new),'identity_challenge':sum(q['difficulty']['identity_challenge'] for q in new)},ensure_ascii=False)+'\n']
 (R/'results/precheck_rule_diff.md').write_text('\n'.join(diff))
 feature=json.loads((D/'feature_receipt.json').read_text());solver=json.loads((D/'selection_solver_receipt.json').read_text());now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
 report=['# MOT-QA Pilot 阶段三：第二轮规则与正式候选\n',f'生成时间：{now}。本报告为候选生成阶段；过滤、正式定稿、阶段五模型检查均未运行。\n',f'实际生成 **{len(qs)}道正式候选**，与原20道设计示例分开。另有20个规则修订样例，均不计入候选数量。原始GT独立重算核验候选与修订样例共920题全部通过。\n',table(['题型','候选数'],[(k,v) for k,v in totals['operations'].items()])+ '\n',table(['数据集','候选数'],list(totals['datasets'].items()))+'\n','MOT17仅7视频，每视频20题上限最多140。按上一轮已允许的15%使用135题，其余45题转SportsMOT；未扩展来源。\n',table(['指代方式','数量'],list(totals['references'].items()))+'\n',f'数值格式：{totals["formats"]}；二选一{totals["binary_count"]}/900；人物裁剪图选项{totals["image_option_count"]}/900；测试专用改写{totals["held_out_paraphrase_count"]}题。\n',f'身份挑战{totals["identity_challenge_count"]}/900，简单对照{totals["simple_control_count"]}；每视频最多{totals["max_per_video"]}题、主身份最多{totals["max_primary_reuse"]}题；使用{totals["videos_used"]}个视频。身份难度采用GT交错/内部间断代理，不能据此保证过滤后仍困难。\n',f'选择题身份混淆干扰覆盖{totals["confusion_option_count"]}/{len(choice)}={totals["confusion_option_fraction"]:.2%}；数值题无选项，不纳入该分母。\n',f'O7前提真假各55题；普通题“没有发生”为正确答案{totals["ordinary_never_correct"]}/790={totals["ordinary_never_fraction"]:.2%}，作为干扰项出现{totals["ordinary_never_distractor"]}次。O7真假各半导致该题型语义多数基线天然为50%，按新指令保留并明报。\n','盲基线在候选集上的结果，仅供构造诊断：\n',table(['题型','选择题n','多数字母','均匀随机','仅数据集字母','语义多数','语义仅数据集'],[(op,x['multiple_choice_n'],f'{x["majority_answer_letter"]:.2%}',f'{x["uniform_random_choice"]:.2%}',f'{x["dataset_only_answer_letter"]:.2%}',f'{x["semantic_majority"]:.2%}',f'{x["semantic_dataset_only"]:.2%}') for op,x in blind.items()])+'\n','连续时间自由作答没有可比的有限集合随机基线；整数自由作答报告精确众数比例，不当作四选一随机率。不同子类的语义类别不能直接等同，完整分布保存在summary.json；最终过滤后还需重新平衡。\n',f'公共视觉特征：MobileNetV3-Small（ImageNet-1K），576维全局池化特征与余弦相似度。按[TorchVision官方预处理](https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.mobilenet_v3_small.html)，只用于同帧最近邻排序、裁剪选项排序和appearance_similarity；不是外观唯一性的人工认证。耗时{feature["seconds"]:.1f}秒，GPU显存峰值{feature["peak_GPU_allocated_MiB"]:.1f}MiB；进程结束释放本任务显存。\n','筛选器只做GT约束筛选和配额选择，没有运行过滤VLM。MILP求解记录：'+json.dumps(solver,ensure_ascii=False)+'\n','锁定材料：generation_config_locked.json、templates_locked.json、stage5_criteria_locked.json及round2_lock_receipt.json；旧锁定版本在generation_history保留。\n','阶段五仍按已授权协议：A/G/G-ph/G-sh/S，exact McNemar、视频整群bootstrap1000次(seed42)，先判断G−A≥15pp且G−G-sh≥10pp、S=100%。过滤保留率、p_disc和rho尚未知；正式规模按用户公式在阶段五后计算并汇报，现阶段不提前生成。\n','本阶段完成后停下，等待确认进入原阶段四过滤。修订20样例无需用户重审；正式候选抽查页面另行提供。\n']
 (R/'results/stage3_round2_report.md').write_text('\n'.join(report))
 print(json.dumps({k:v for k,v in totals.items() if k not in ['blind_baselines']},ensure_ascii=False))
if __name__=='__main__':main()
