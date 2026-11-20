"""Audit the repaired interface and preregister H12 before Stage 7 inference."""
from collections import Counter
from stage6_common import *
from stage6_tools import Tools
from stage7_parser import parse_fixed_call,cpu_checks
from stage7_diagnostics import prepare_majority


def main():
    verify_stage5()
    old=read(ROOT/'results/stage6_protocol_locked.json')
    for name,expected in old['source_sha256'].items():assert sha(ROOT/'src'/name)==expected
    for artifact in old['prompts']:assert sha(artifact['path'])==artifact['sha256']
    assert not (ROOT/'results/stage7_protocol_locked.json').exists(),'Already locked; do not replace'
    tools=Tools();records=[];counts=Counter();kinds=Counter()
    for p in rows(ROOT/'results/stage6/main_T1_predictions.jsonl'):
        attempts=[t for t in p['turns'] if '<tool_call' in t['raw_response']][:len(p['tool_calls'])]
        assert len(attempts)==len(p['tool_calls'])
        for turn in attempts:
            call,error,recovered=parse_fixed_call(turn['raw_response'])
            assert call is not None and error is None and recovered
            result=tools.execute(p['video_id'],**call)
            counts.update(attempts=1,recovered=int(recovered),legal_signature=int(result['legal']),exact_object_matched=int(result['matched']))
            kinds[call['name']]+=1
            records.append(dict(qa_id=p['qa_id'],turn=turn['turn'],raw_response_sha256=digest(turn['raw_response']),
                recovered_at_EOS=recovered,parsed_call=call,legal_signature=result['legal'],matched=result['matched']))
    assert counts['attempts']==counts['recovered']==1801
    audit=immutable(ROOT/'results/stage7_parser_offline_audit_locked.json',dict(created_at=now(),before_any_stage7_inference=True,
        source_predictions=str(ROOT/'results/stage6/main_T1_predictions.jsonl'),source_sha256=sha(ROOT/'results/stage6/main_T1_predictions.jsonl'),
        parser_source_sha256=sha(ROOT/'src/stage7_parser.py'),cpu_checks=cpu_checks(),counts=dict(counts),tools=dict(kinds),
        model_requests=0,original_predictions_modified=False,records=records))
    majority=prepare_majority()
    hypotheses=dict(created_at=now(),before_any_stage7_inference=True,project_root=str(ROOT),seed=42,
        hypotheses=[dict(id='H12',statement='With only the complete-JSON-to-EOS parser repair, T1 exceeds reused T-none on test trackable251.',
            criterion='positive accuracy delta, exact two-sided McNemar p<0.05, paired bootstrap95% lower bound>0',
            reference_correct=73,reference_n=251)],
        primary_scope='test trackable251',supplemental_scope='test all602, each dimension and main-four231',
        statistics=dict(mcnemar='exact two-sided conditional binomial on discordant correctness',
            bootstrap='question-level paired percentile95%CI,1000 resamples, numpy default_rng42, sorted qa_id within scope',alpha=.05,
            multiplicity='single primary H12; comparisons against majority and route and per-dimension comparisons reported descriptively'),
        secondary_comparisons=['T1_fixed vs development-majority blind baseline on identical questions',
            'T1_fixed vs frozen-rule/official-A routing baseline on identical questions',
            'T1_fixed vs original Stage6 T1 (interface diagnosis only)'],
        parser_fix='Retain original closed-tag parser. Additionally accept exactly one complete name/arguments JSON object after a single <tool_call> ending at message EOS, allowing any preceding reasoning as for closed tags. No trailing text, partial JSON or multiple objects recovered.',
        unchanged=dict(frozen_config_sha256=sha(ROOT/'results/frozen_config_v1.json'),split_sha256=sha(ROOT/'results/dev_test_split_locked.json'),
            trackable_sha256=sha(ROOT/'results/trackable_subset_preregistered.json'),demonstrations_sha256=sha(ROOT/'results/stage6_demonstrations_locked.json'),
            T1_prompts_sha256=sha(ROOT/'results/stage6/prompts/T1.jsonl'),final_answer_parser_sha256=sha(ROOT/'src/stage5_common.py')),
        conditional_controls=dict(gate='Run T-ph and T-sh iff repaired T1 has strictly more than73 correct on test trackable251; significance not required for this gate.',
            controls='Identical T1 demonstrations and repaired parser; placeholder vs exact Stage4D facts; test all602.',
            decision_lock='Save observed counts and prediction SHA before any control inference.'),
        count_diagnosis='Keep Stage6 corrected final-field-only guidance for242 test counting questions for T1 and triggered controls. It is auxiliary, not used forH12 or the control gate.',
        generation=dict(total_tokens=2048,max_calls=4,max_turns=5,temperature=0,seed=42),
        server=old['server'],same_32_frames_and_timestamps=True,no_new_tracking=True,no_new_training=True,
        information_diagnostics='All label/trajectory associations and recall analyses are post-hoc; no tracking, rule or model parameters selected from them.',
        stop_after_report=True)
    h=immutable(ROOT/'results/stage7_hypotheses_preregistered.json',hypotheses)
    side=ROOT/'results/stage7_hypotheses_preregistered.json.sha256';side.write_text(h['sha256']+'  stage7_hypotheses_preregistered.json\n');side.chmod(0o444)
    sources=['stage7_parser.py','run_stage7.py','stage6_common.py','stage6_tools.py','run_stage6.py','stage6_runtime.py','stage6_final_field_guidance.py']
    protocol=dict(created_at=now(),before_any_stage7_inference=True,hypotheses=h,offline_parser_audit=audit,
        stage6_protocol_sha256=sha(ROOT/'results/stage6_protocol_locked.json'),T1_prompt_path=str(ROOT/'results/stage6/prompts/T1.jsonl'),
        T1_prompt_sha256=hypotheses['unchanged']['T1_prompts_sha256'],demonstrations_sha256=hypotheses['unchanged']['demonstrations_sha256'],
        majority_baselines_sha256=sha(ROOT/'results/stage7_majority_baselines_locked.json'),
        primary_T_none_path=str(ROOT/'results/stage6/main_T-none_predictions.jsonl'),primary_T_none_sha256=sha(ROOT/'results/stage6/main_T-none_predictions.jsonl'),
        stage6_T1_sha256=sha(ROOT/'results/stage6/main_T1_predictions.jsonl'),
        reuse='Invoke unchanged Stage6 infer_tools with only parser and destination/protocol metadata overrides; same tools, messages, sampling, budget and final-answer parser.',
        source_sha256={name:sha(ROOT/'src'/name) for name in sources},
        final_field_guidance_sha256=sha(ROOT/'results/stage6_final_field_guidance_v2_locked.json'),
        allocation='One A800 with enough free memory for unchanged65% server reservation+5.5GiB; prefer fewer processes, then lower utilization; leave all foreign jobs running.')
    plock=immutable(ROOT/'results/stage7_protocol_locked.json',protocol)
    with (ROOT/'research_log.md').open('a') as stream:
        stream.write('\n## '+now()+' — 阶段七计划与H12锁定\n\n先按冻结规则覆盖子集计算R/D边缘列联与Count/X-Order混淆、平衡准确率、kappa、与开发多数类的配对比较，全部标事后诊断；另列不同模型的R/D类别召回。原T1的1801次调用离线完整JSON恢复成功1801次，签名合法1801，短语精确匹配1785。锁H12后只重跑T1及原门槛触发的占位/打乱对照，保持5示范、32原帧、40图上限、2048总生成和4次调用。计数沿用修正版最终字段约束作辅助；不训练、不改轨迹、切分或清单。长任务单阻塞命令等待，完成释放显存并停止。\n')
    print(dict(status='STAGE7_PREREGISTERED',hypotheses=h,protocol=plock,offline_audit_counts=dict(counts)),flush=True)


if __name__=='__main__':main()
