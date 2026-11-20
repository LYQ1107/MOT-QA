"""Record the user's second amendment and lock rules before candidate selection."""
import copy, hashlib, json, shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
R=Path('/home/user/motqa_pilot')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
# Authored paraphrases: each list expresses the same predicates and output target.
T={
'region':[
 'Which region of the image contains person A at {end} s?',
 'At {end} s, is person A in the left, center, or right region of the frame?',
 'Locate person A at {end} s and report the image region containing that person.',
 'What is person A’s left/center/right region at the timestamp {end} s?',
 'Identify the frame region occupied by person A at {end} s.'],
'left_pair':[
 'At {end} s, which person is farther left in the image, A or B?',
 'Who is on the left of the other person at {end} s: A or B?',
 'Compare A and B at {end} s. Which one has the smaller horizontal image coordinate?',
 'Which of A and B occupies the more leftward position at {end} s?',
 'Looking at {end} s, name the leftmost of the two people A and B.'],
'return_time':[
 'After the visibility gap beginning around {gap} s, when does person A first become clearly visible again within {start}–{end} s?',
 'Give A’s first clear return time in {start}–{end} s following the gap that starts near {gap} s.',
 'Within {start}–{end} s, at what time does A first return to clear view after the visibility interruption near {gap} s?',
 'Find A’s first clearly visible frame after the gap around {gap} s, restricted to {start}–{end} s. What is its time?',
 'For the interruption starting near {gap} s, identify A’s earliest clear reappearance during {start}–{end} s.'],
'cross_count':[
 'How many different people cross paths with A during {start}–{end} s? Count each person once.',
 'Count the distinct people whose left-right order with A reverses through an overlap in {start}–{end} s.',
 'During {start}–{end} s, how many unique individuals have a qualifying crossing with A?',
 'Report the number of distinct people A crosses paths with between {start} and {end} s; repeated crossings with one person count once.',
 'Considering {start}–{end} s, what is the deduplicated count of people involved in a crossing with A?'],
'entry_count':[
 'How many distinct track identities first enter from a frame edge during {start}–{end} s? Count each identity once.',
 'Count track identities with their first edge entry in {start}–{end} s, without counting any identity twice.',
 'During {start}–{end} s, how many different track identities make their first appearance at an image edge?',
 'Give the number of distinct identities whose first edge appearance falls between {start} and {end} s.',
 'What is the count of first-time edge-entering track identities in {start}–{end} s?'],
'earlier_return_time':[
 'Comparing A and B in {start}–{end} s, at what time does the earlier of their first clear returns after a visibility gap occur?',
 'Find the first clear return of A and of B during {start}–{end} s after a visibility gap. What is the earlier timestamp?',
 'Which timestamp is earlier when A’s and B’s first clear reappearances in {start}–{end} s are compared? Give that time.',
 'Report the time of the earlier first reappearance of A and B during {start}–{end} s, after their visibility interruptions.',
 'At what time is the earlier first return to clear view among A and B in {start}–{end} s?'],
'earliest_return_person':[
 'Among A, B, and C, who first returns to clear view after a visibility gap during {start}–{end} s?',
 'Which of A, B, and C has the earliest clear reappearance following a visibility interruption in {start}–{end} s?',
 'Compare the first post-gap returns of A, B, and C within {start}–{end} s. Who returns first?',
 'During {start}–{end} s, identify the earliest returning person among A, B, and C after a visibility gap.',
 'Who wins the first-clear-return comparison among A, B, and C for {start}–{end} s?'],
'closest_time':[
 'During {start}–{end} s, in which time segment are A and B closest in image coordinates?',
 'Which segment of {start}–{end} s contains the minimum image-plane separation of A and B?',
 'Compare the image distance between A and B throughout {start}–{end} s. In which segment is its minimum?',
 'Locate the time segment when A and B reach their smallest separation in the image during {start}–{end} s.',
 'Within {start}–{end} s, which segment includes A and B’s closest image positions?'],
'cross_time':[
 'In {start}–{end} s, which time segment contains the first qualifying crossing of A and B?',
 'When A and B first exchange left-right order through an overlap during {start}–{end} s, which segment is it?',
 'Identify the segment of {start}–{end} s containing A and B’s first overlap followed by reversed left-right order.',
 'Which part of {start}–{end} s contains the first crossing event between A and B?',
 'For A and B during {start}–{end} s, report the segment of their earliest qualifying crossing.'],
'return_region':[
 'During {start}–{end} s, in which image region is A at the {ordinal} clear reappearance after a visibility gap?',
 'Where in the left/center/right regions does A make the {ordinal} post-gap return to clear view in {start}–{end} s?',
 'Locate A’s {ordinal} clear reappearance within {start}–{end} s after a visibility interruption. Which region contains A?',
 'At A’s {ordinal} return to clear view following a gap during {start}–{end} s, what is the image region?',
 'Which frame region contains A when the {ordinal} qualifying reappearance occurs in {start}–{end} s?'],
'identity_match':[
 'In the frame at {end} s, four people have numbered boxes 1–4. Which box contains person A from the reference frame?',
 'Match reference person A to one of the four numbered people at {end} s. Give the box number.',
 'Which of boxes 1–4 at {end} s marks the same person as A in the reference image?',
 'Follow person A to {end} s and select the corresponding numbered box among 1–4.',
 'Identify A’s matching person in the numbered-box frame at {end} s. Which number is correct?'],
'identity_same':[
 'Is person B, marked in the frame at {end} s, the same person as reference person A?',
 'Do reference person A and the marked person B at {end} s have the same identity?',
 'Compare A in the reference image with B marked at {end} s. Are they the same individual?',
 'Has reference person A been matched to the same individual in the marked B image at {end} s?',
 'Does the person marked B at {end} s correspond to reference person A?'],
'cross_exit_count':[
 'Among the different people who cross paths with A in {start}–{end} s, how many leave the frame later in that interval? Count each once.',
 'Count distinct people who first cross A and subsequently leave the image, with both events in {start}–{end} s.',
 'During {start}–{end} s, how many unique people satisfy both conditions: a crossing with A, followed by a frame exit?',
 'Select people who cross A in {start}–{end} s, then count those who exit after that crossing but before the interval ends.',
 'What is the deduplicated number of people whose crossing with A precedes their exit, both within {start}–{end} s?'],
'order_region':[
 'Of A and B, who first returns after a visibility gap in {start}–{end} s, and in which image region is that person at {end} s?',
 'Find the earlier first post-gap return among A and B during {start}–{end} s; report that person and their region at {end} s.',
 'Which of A and B reappears first in {start}–{end} s, and where is the earlier returner at the final timestamp?',
 'Compare A’s and B’s first clear returns in {start}–{end} s, then give the earlier person’s left/center/right region at {end} s.',
 'Report the identity and final image region of the earlier first-returning person among A and B in {start}–{end} s.'],
'motion_relation_example_only':[
 'In {start}–{end} s, who has the greater cumulative box-center path in image coordinates, A or B, and is that person left or right of the other at {end} s?',
 'Compare A and B’s cumulative image-coordinate box-center paths for {start}–{end} s; name the farther mover and their final left/right relation.',
 'Which of A and B accumulates more box-center movement in the static-camera image during {start}–{end} s, and where are they relative to the other at the end?',
 'For {start}–{end} s, identify the larger cumulative image-path mover among A and B and state their left/right position at {end} s.',
 'Name the person with the longer cumulative image-coordinate box-center trajectory in {start}–{end} s and their final side relative to the other.']}
def main():
 now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat();p=R/'results/generation_config_locked.json';prev=sha(p)
 hist=R/'results/generation_history/round1';hist.mkdir(parents=True,exist_ok=True)
 if (hist/p.name).exists(): raise RuntimeError('Round2 rules already recorded; do not relock.')
 shutil.copyfile(p,hist/p.name);c=json.loads(p.read_text());c.update(version='stage3_round2_v2',locked_at=now,previous_sha256=prev,current_action='Generate revised20 example versions and approximately900 formal candidates; stop for Stage3 report before filtering.')
 c['design_examples']={'file':str(R/'data/question_review_user_passed_20.jsonl'),'sha256':sha(R/'data/question_review_user_passed_20.jsonl'),'excluded_from_formal_counts':True,'preserve_bytes':True,'revised_versions_for_rule_diff_only':True}
 c['target_identity_reuse']['scope']='Maximum3 questions per primary target identity, across all reference types and operations. Secondary references do not consume this primary quota (latest user instruction).'
 c['max_questions_per_video']=20
 c['hard_margins']={'decisive_event_to_interval_start_min_s':1.,'decisive_event_to_interval_end_min_s':1.,'negative_future_observation_s':2.,'negative_observation_must_be_uncensored':True,'gap_min_s':1.5,'base_gap_definition_s':1.,'comparison_relative_min':.2,'comparison_absolute_width_fraction_min':.05,'comparison_combination':'both relative and absolute gates; applies to geometric distance/path/x-coordinate comparisons, not timestamps','relative_denominator':'absolute runner-up magnitude, bounded below by1e-9','time_partition_interval_min_s':4.,'time_partition_each_bin_min_s':1.,'temporal_order_min_separation_s':1.}
 c['all_reference_geometry']={'same_gates_as_reference_box':True,'reference_types':['box','event','position','appearance'],'departure_event_anchor':'last geometrically acceptable frame in the final visible run before the departure; preserve unique event text/time','zoom_crop_scale':3,'zoom_crop_field':'reference.zoom_crop','zoom_crop_other_boxes':False,'zoom_crop_image_insert':'after_frames','crop_pixels':'tight target bbox crop, native size multiplied by3; other people are not annotated'}
 c['identity_challenge']={'minimum_fraction':.6,'definition':'At least one qualifying crossing or internal occlusion gap strictly longer than1.5s between primary reference and query; no use of answer labels','simple_controls_field':'difficulty.identity_challenge=false'}
 c['O7']={'premise_exists_fraction':.5,'premise_absent_fraction':.5,'ordinary_never_correct_target_fraction':.05,'ordinary_never_as_distractor':True,'semantic_uniformity_exception':'Explicit50/50 premise requirement supersedes generic uniformity of left/center/right/never outcomes; report the unavoidable50% semantic majority baseline, do not conceal it with letter permutation.'}
 c['count_options']={'exact_numeric':True,'multiple_choice':'four adjacent nonnegative integers including the truth and any available identity-confusion answer','N_or_more_allowed_only_at_true_count_ge':8,'primary_policy':'prefer exact integers even at>=8; no3-or-more bucket'}
 c['O8']={'target_fraction':.15,'subtypes':['numbered_box_match','same_person_yes_no'],'min_ref_query_separation_s':5.,'all_candidate_geometry':True,'match_mandatory_overlap_or_crossing_distractor':True,'remaining_candidates':'rank same-frame qualifying people with public visual features','same_person_yes_fraction':.5,'same_person_no_distractor_must_have_overlapped_or_crossed':True}
 c['numeric_answers']={'target_fraction':.2,'operations':['O3','O4','O5'],'formats':{'numeric_time':{'unit':'seconds','absolute_tolerance_s':.5},'numeric_count':{'exact_integer':True}},'binary_question_max_fraction':.25}
 c['optional_crop_options']={'target_fraction':[.05,.10],'optional':True,'candidate_time_separation_from_query_min_s':3.,'no_timestamp_no_box':True,'geometric_gate':True,'shortage_policy':'report below5%; do not relax geometry or invent samples'}
 c['candidate_operation_targets']={'O1':60,'O2':90,'O3':100,'O4':105,'O5':100,'O6':100,'O7':110,'O8':135,'composition':100}
 c['realized_dataset_targets']={'DanceTrack':360,'SportsMOT':405,'MOT17':135};c['dataset_target_rationale']='MOT17 has7 eligible videos, at most140 questions under20/video. Apply previously authorized15% minimum; transfer45 questions to SportsMOT.'
 c['planned_dataset_by_operation']={k:dict(zip(['DanceTrack','SportsMOT','MOT17'],v)) for k,v in {'O1':[24,27,9],'O2':[36,40,14],'O3':[45,45,10],'O4':[42,47,16],'O5':[40,45,15],'O6':[40,45,15],'O7':[44,50,16],'O8':[54,61,20],'composition':[35,45,20]}.items()}
 c['current_prohibitions']=['no tracker execution or tracker weights','no new appearance phrases','no raw data edits','no proxy','no formal-scale generation before Stage5 estimate and user decision','no Stage4 filtering until Stage3 report and confirmation']
 c['stage5_authorization']={'after':'filtered pilot finalization and stage confirmation','conditions':['A','G','G-ph','G-sh','S'],'model':'Qwen2.5-VL-7B-Instruct','frames':32,'timestamps':True,'references_and_3x_crops_after_frames':True,'final_answer_constrained_decoding':True,'parse_failure_counts_incorrect':True,'bootstrap_unit':'video_cluster','bootstrap_repetitions':1000,'seed':42,'paired_test':'exact McNemar'}
 c['templates_file']=str(R/'results/templates_locked.json')
 dump(p,c)
 templates={'version':'round2_v2','locked_at':now,'seed':42,'author':'agent-authored and manually checked for predicate/output equivalence; not an additional user audit','held_out_ids':[3,4],'held_out_use':'test only; forbidden in future training','finite_paraphrases_do_not_guarantee_unparseability':True,'templates':{k:[{'paraphrase_id':i,'paraphrase_split':'held_out' if i in [3,4] else 'shared','text':s,'semantic_review':'checked_same_operation_arguments_and_answer_target'} for i,s in enumerate(v)] for k,v in T.items()}}
 dump(R/'results/templates_locked.json',templates)
 criteria={'locked_at':now,'status':'LOCKED_BEFORE_ANY_STAGE5_INFERENCE','model':'Qwen2.5-VL-7B-Instruct','seed':42,'expand_only_if':{'G_minus_A_pp_min':15.,'G_minus_Gsh_pp_min':10.,'script_S_accuracy_required':1.},'if_G_close_to_A':'Inspect serialization and prompts; do not expand','if_S_below100':'Fix generator before interpreting model results','statistics':{'paired':'exact McNemar','bootstrap':'video cluster resampling with replacement,1000 replicates,seed42'},'power':{'n_paired':'(1.96+0.84)^2*p_disc/delta^2','design_effect':'1+(mean_questions_per_video-1)*rho','candidate_n':'n_paired*design_effect/filter_retention','overall_delta':.05,'per_operation_delta':.10,'composition_min_n':200,'rho':'one-way ANOVA on binary correctness; report raw estimate and design-effect convention'},'no_formal_scale_generation_before_user_decision':True}
 dump(R/'results/stage5_criteria_locked.json',criteria)
 hashes={str(p.relative_to(R)):sha(p) for p in [p,R/'results/templates_locked.json',R/'results/stage5_criteria_locked.json']};dump(R/'results/round2_lock_receipt.json',{'created_at':now,'hashes':hashes,'previous_config_sha256':prev})
 with (R/'research_log.md').open('a') as f:
  f.write('\n## 第二轮硬规则与正式候选生成启动 — '+now+'\n\n用户授权修订规则、新增O8/数值/改写、约900候选和后续GT检查；20个人工通过样例按字节保留且不计正式题库。先读现有GT生成/审核代码，锁定round2规则及阶段五判断标准，再生成20个对应修订版本并逐题记差异，最后生成约900候选和统计/GT核验。MOT17的7视频×20题上限140低于180，采用用户已允许15%=135题，其余45转Sports，目标Dance360/Sports405/MOT135。身份复用按新指令仅计主目标。O7前提真假各半与旧的四选一语义均匀要求有直接冲突，依新要求执行并明报50%多数基线；不靠洗牌掩盖。阶段三后停下，不自动启动过滤或阶段五。公共视觉特征仅用于难度与候选外观排序，不运行跟踪器。\n')
 print(json.dumps(hashes))
if __name__=='__main__': main()
