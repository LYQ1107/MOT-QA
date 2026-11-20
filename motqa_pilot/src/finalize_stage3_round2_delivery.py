"""Finish the Stage3 handoff only after raw GT and actual-browser checks pass."""
import hashlib,json,shutil
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import generate_candidates_round2 as g
R=g.ROOT;D=g.RES

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat();summary=json.loads((D/'summary.json').read_text());audit=json.loads((D/'raw_gt_answer_audit.json').read_text());browser=json.loads((D/'browser_check/browser_check_result.json').read_text());cfg=json.loads((R/'results/generation_config_locked.json').read_text());lock=json.loads((R/'results/round2_lock_receipt.json').read_text())
 assert summary['count']==900 and not summary['balance_warnings'] and audit['status']=='PASSED' and audit['verified']==920 and browser['status']=='PASSED'
 assert sha(R/cfg['design_examples']['file'])==cfg['design_examples']['sha256']
 for path,digest in lock['hashes'].items():assert sha(R/path)==digest
 qs=g.rows(R/'data/candidates.jsonl');revised=g.rows(R/'data/precheck_round2_20.jsonl');templates=json.loads((R/'results/templates_locked.json').read_text())['templates']
 assert all(len(v)>=5 and sum(x['paraphrase_split']=='held_out' for x in v) in [1,2] for v in templates.values())
 exclusions={'recorded_at':now,'purpose':'Future training must exclude held-out combinations and test-only paraphrases; no training data constructed.','operation_combinations':[['O6','O1'],['O6','O4'],['O5','O2']],'composition_template_families':['cross_region','cross_exit_count','motion_relation_example_only'],'paraphrase_exclusions':{family:[x['paraphrase_id'] for x in variants if x['paraphrase_split']=='held_out'] for family,variants in templates.items()},'enforcement':'Exclude any split_role=held_out_composition regardless of paraphrase_split; exclude every held_out paraphrase in all other operations.'}
 g.dump(R/'results/training_exclusion_manifest.json',exclusions)
 assets=set()
 for q in qs:
  for rr in q['reference']['persons']:assets.update([rr['image'],rr['zoom_crop']])
  for field in ['query_image','query_zoom_crop']:
   if q.get(field):assets.add(q[field])
  assets.update(q.get('option_images',{}).values())
 assert all(Path(p).exists() for p in assets)
 g.dump(D/'formal_asset_manifest.json',{'count':len(assets),'bytes':sum(Path(p).stat().st_size for p in assets),'files':sorted(assets)})
 report=R/'results/stage3_round2_report.md'
 text=report.read_text();text += '\n题型×数据集分布（允许没有合格候选的单元为0；没有放宽数据集身份限制）：\n\n'
 text += '|题型|DanceTrack|SportsMOT|MOT17|\n|---|---:|---:|---:|\n'
 for op,counts in summary['operation_dataset_counts'].items():text += f'|{op}|{counts.get("DanceTrack",0)}|{counts.get("SportsMOT",0)}|{counts.get("MOT17",0)}|\n'
 text += '\n难度标签分布（均为生成时GT/公开视觉特征的代理统计）：\n\n|标签|min|P25|P50|P75|P95|max|\n|---|---:|---:|---:|---:|---:|---:|\n'
 for key,x in summary['difficulty_quantiles'].items():text+='|'+key+'|'+'|'.join(f'{x[k]:.3f}' for k in ['min','p25','p50','p75','p95','max'])+'|\n'
 text += '\n本轮构造中保留的失败与修复：最初区间题最小7秒上下文被误套到点查询，已补齐合法3/5秒点查询；分数据集取整累积造成O3/O5语义偏斜与O4来源盲基线超限，已按原标准重采样；一个MOT半段起点删失的反事实干扰项已改用经独立GT验证的另一个重叠身份。历史候选、失败日志及诊断结果均留存，未接受放宽配额的诊断解。最终920题答案及已标注的反事实干扰项通过原始GT核验，盲基线检查无超限。\n'
 text += '\n每个模板至少5种英文改写，其中2种标为held_out；有限改写不会证明规则程序无法解析。GT脚本检查是可解性检查，不能据此宣称主动工具调用优于脚本。组合题100道及测试专用改写的未来训练禁用清单见training_exclusion_manifest.json。\n'
 text += '\n交付：[900候选](/home/user/motqa_pilot/data/candidates.jsonl)、[20道对应规则差异](/home/user/motqa_pilot/results/precheck_rule_diff.md)、[正式候选抽查20题中文ZIP](/home/user/motqa_pilot/results/motqa_round2_formal_sample20_zh.zip)。抽查包已实际解压，在Firefox完成20页图片/放大裁剪、原片播放与GT视频、保存、真实20题JSON导出/导入检查，测试选择已清除，浏览器已关闭。旧20道示例无需用户重新审阅。\n'
 report.write_text(text)
 protected=['README.md','results/stage3_operation_blueprint.json'];history=D/'history/before_final_delivery_status'
 for rel in protected:
  dst=history/rel;dst.parent.mkdir(parents=True,exist_ok=True)
  if not dst.exists():shutil.copyfile(R/rel,dst)
 p=R/'results/stage3_operation_blueprint.json';blue=json.loads(p.read_text());blue.update(status='STAGE3_ROUND2_900_CANDIDATES_COMPLETE_WAITING_CONFIRMATION_FOR_FILTERING',updated_at=now,purpose='900 formal candidates generated under round2 rules; old20 preserved as examples, new20 corresponding versions audited separately. Filtering and GT-model check are pending.',actual_candidate_count=900,full_batch_candidate_count=900,design_examples_excluded_from_formal_counts=True,stage3_report=str(report),candidate_file=str(R/'data/candidates.jsonl'),precheck_rule_diff=str(R/'results/precheck_rule_diff.md'),formal_sample20_review=str(D/'formal_review_receipt.json'))
 blue['review_workflow'][1]['status']='20 original design slots passed previously and are examples only.20 corresponding rule-revision versions pass independent GT audit, no user re-review required.900 formal candidates generated; separate reference-stratified random20 package is delivered for inspection.'
 blue['historical_camera_motion_held_indices']=blue.get('camera_motion_held_indices',[]);blue['camera_motion_held_indices']=[]
 if not any(x['operation']=='O8' for x in blue['operations']):blue['operations'].insert(-1,{'operation':'O8','name':'身份核对','subtypes':['numbered_box_match','same_person_yes_no'],'actual_candidates':135,'min_reference_query_separation_s':5,'candidate_boxes_pass_full_geometry':True})
 g.dump(p,blue)
 p=R/'README.md';readme=p.read_text();a=readme.index('Current status:');b=readme.index('\n\n',a);readme=readme[:a]+('Current status:Stage3 round2 has generated900 formal candidates, excluding the20 user-approved design examples. O1/O2/O3/O4/O5/O6/O7/O8/composition counts are60/90/100/105/100/100/110/135/100. All900 answers plus20 corresponding rule-revision examples pass original-GT recomputation, including marked identity-confusion options. The old20 examples remain unchanged. Filtering, final pilot release and Stage5 GT-model checks have not run; stop here for the Stage3 report.')+readme[b:]
 links='\n\n- [当前阶段三报告：900道正式候选](results/stage3_round2_report.md)\n- [900道候选数据](data/candidates.jsonl)\n- [20道对应规则差异：无需重审旧题](results/precheck_rule_diff.md)\n- [正式候选抽查20题中文ZIP](results/motqa_round2_formal_sample20_zh.zip)\n- [阶段五判断标准：推理前已锁定](results/stage5_criteria_locked.json)\n- [阶段三交付与哈希记录](results/stage3_round2/delivery_receipt.json)\n'
 readme=readme[:a]+readme[a:].replace('\n\n',links+'\n',1);p.write_text(readme)
 tracked=['data/candidates.jsonl','data/precheck_round2_20.jsonl','data/question_review_user_passed_20.jsonl','results/generation_config_locked.json','results/templates_locked.json','results/stage5_criteria_locked.json','results/training_exclusion_manifest.json','results/precheck_rule_diff.md','results/stage3_round2_report.md','results/stage3_round2/raw_gt_answer_audit.json','results/stage3_round2/summary.json']
 tracked += [str(x.relative_to(R)) for x in (R/'src').glob('*round2*.py')]
 receipt={'finished_at':now,'status':'STAGE3_COMPLETE_STOP_BEFORE_FILTERING','formal_candidate_count':900,'old20_design_examples_excluded':True,'revised20_examples_excluded':True,'original20_SHA256_unchanged':True,'GT_answers_and_marked_counterfactuals_verified':920,'balance_check':'PASSED','browser_check':'PASSED','assets':len(assets),'report':str(report),'formal_candidates':str(R/'data/candidates.jsonl'),'review_package':str(R/'results/motqa_round2_formal_sample20_zh.zip'),'review_export_filename':'stage3_candidate_review_result.json','hashes':{rel:sha(R/rel) for rel in tracked},'tracker_runs':0,'QA_model_inference_runs':0,'training_runs':0,'filtering_executed':False,'stage5_inference_executed':False,'formal_scale_generated':False,'GPU_service_running':False}
 g.dump(D/'delivery_receipt.json',receipt)
 with (R/'research_log.md').open('a') as f:
  counts={'numeric':sum(q['format'].startswith('numeric') for q in revised),'identity_challenge':sum(q['difficulty']['identity_challenge'] for q in revised),'ordinary_never':sum(q['operation_name']!='O7' and q['semantic_answer']==g.NEVER for q in revised)}
  f.write('\n## 第二轮阶段三交付 — '+now+'\n\n正式候选900，O1–O8/组合为60/90/100/105/100/100/110/135/100；Dance360/Sports405/MOT135，76视频、405主身份，每视频≤20/主身份≤3。旧20题按字节保留且排除统计；对应修订20题统计为'+json.dumps(counts,ensure_ascii=False)+'，规则差异已落盘。身份挑战715/900；数值180/900；二选一150/900；图片选项45/900；外观106，不足29转框标（框434/事件225/位置135）。O7真假55/55；普通Never40/790。原始GT独立重算920题答案、主身份挑战标记、参考裁剪与已标身份反事实干扰项全过；有效选择题干扰项504/720=70%，未降低阈值。语义与字母来源盲基线复检均无超限。实际解压中文抽查ZIP，Firefox20页图片/视频播放/导入导出均通过，测试选择清除。仅运行已授权的公共视觉特征，无跟踪器、问答模型、训练或过滤。最终配置、改写、阶段五标准和未来训练排除项已保存及哈希；停止等待阶段三确认，不提前做阶段四、阶段五或正式规模扩增。\n')
 print(json.dumps({k:v for k,v in receipt.items() if k!='hashes'},ensure_ascii=False))
if __name__=='__main__':main()
