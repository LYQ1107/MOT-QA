"""Lock H6-H8, answer-free representations, templates and parser before inference."""
from collections import Counter,defaultdict
from pathlib import Path
import json

from stage5_common import *
from stage5_representations import select,b_main,b_events,suspicious_track,PARAMETERS


def main():
    old_lock=verify_stage4()
    frozen=read(ROOT/'results/frozen_config_v1.json')
    assert PARAMETERS==frozen['rule']['geometry_parameters']
    assert not (ROOT/'logs/stage5_preinference_lock.json').exists()
    assert not (ROOT/'results/stage5_hypotheses_preregistered.json').exists()
    hypotheses=dict(created_at=now(),before_any_stage5_inference=True,seed=42,
        frozen_config_sha256=old_lock['frozen_config_sha256'],split_sha256=frozen['split_sha256'],
        trackable_sha256=frozen['preregistration_sha256'],
        accepted_stage4_conclusion='No detectable benefit of real trajectories B over A in official direct-answer format; B and D have symmetric flips. Rule routing gains about9pp over A on test trackable questions, demonstrating usable track information not used by that model/template.',
        primary_scope='Test trackable251 QA; main-four231 also reported. R/D101 is entirely trackable. Test all602 and full749 supplemental; full includes development used for prior tuning.',
        methods=dict(mcnemar='Exact two-sided conditional binomial test on discordant correctness; p=1 with zero discordances.',
            bootstrap='Question-level paired percentile95%CI,1000 resamples,numpy default_rng(42),sorted qa_id within each subset,as Stage4.',
            alpha=.05,positive='Positive delta, exact two-sided McNemar p<.05 and bootstrap lower bound>0.',
            weak_inequality='For >= hypotheses, report observed ordering separately from inference. Significant positive differences support a transition; significant negative differences contradict it. With no prespecified noninferiority margin, nonsignificance or an observed tie alone does not establish population noninferiority.',
            multiplicity='Unadjusted exact p and CIs reported; additionally Holm-adjust four H7 adjacent comparisons across two templates. No familywise claim for exploratory dimensions.'),
        hypotheses=[
            dict(id='H6',scope='reasoning template, test trackable251',statement='B>A under the brief-reasoning template.',criterion='positive criterion on B-A; strict final-line parser'),
            dict(id='H7',scope='R/D101 test questions, each template separately',statement='B-events >= B-main >= B.',
                comparisons=['B-main minus B','B-events minus B-main'],criterion='Report observed monotonicity (both deltas>=0), each exact p and CI. Statistical support requires positive evidence for both transitions; otherwise distinguish observed ordering from uncertainty. Significant negative transition contradicts monotonicity.'),
            dict(id='H8',scope='R/D101 test questions, each template separately',statement='B-events is not lower than the frozen rule.',
                criterion='Report observed gap to rule. Positive criterion supports at least reaching rule; significant negative delta contradicts it; an overlapping CI remains inconclusive for noninferiority, with no post-hoc margin.')],
        reasoning_parser=dict(rule='Require the final nonempty line to match case-sensitive Answer: <value>. No fallback to earlier lines or reasoning. sp/mcq require exact legal uppercase letter; numerical exact2/3/4/5 or more; ordering exact complete permutation of its labels separated by commas. Parse failure wrong.',
            source_sha256=sha(ROOT/'src/stage5_common.py'),max_tokens=1024),
        numerical_guidance=dict(user_confirmed='Preserve reasoning and constrain only final answer; total1024 tokens.',
            reasoning_backend='structured_outputs.regex',regex=FINAL_NUMBER_REGEX,
            reasoning_semantics='Free reasoning prefix; EOS allowed only after a final newline Answer: with legal number. Token-limit truncations remain failures, not retried or dropped.',
            official_backend='structured_outputs.choice',choices=list(LEGAL)),
        examples='First5 sorted test R/D qa_id answered correctly by reasoning B and first5 wrong, including parse failures. Preserve whole output and evidence; manually describe whether it cites tracks, without inferring private reasoning or editing evidence.',
        no_parameter_updates=True)
    artifacts=[immutable(ROOT/'results/stage5_hypotheses_preregistered.json',hypotheses)]
    Path(str(ROOT/'results/stage5_hypotheses_preregistered.json')+'.sha256').write_text(artifacts[0]['sha256']+'  stage5_hypotheses_preregistered.json\n')
    Path(str(ROOT/'results/stage5_hypotheses_preregistered.json')+'.sha256').chmod(0o444)
    visible=sorted(rows(ROOT/'results/stage3_visible_inputs.jsonl'),key=lambda q:q['qa_id'])
    query_by_id={r['qa_id']:r['queries'] for r in read(ROOT/'results/stage3_extracted_queries.json')}
    source_index=read(ROOT/'results/v1_track_index.json')
    lookup={(r['video_id'],r['query']):r for r in source_index}
    rep_rows=[]; texts={}; descriptive={}
    for i,row in enumerate(sorted(source_index,key=lambda r:(r['video_id'],r['query']))):
        document=read(row['json_path']);selection=select(document)
        text_main=b_main(document,selection);text_events,event_records=b_events(document,selection)
        directory=ROOT/'results/stage5/representations'/f'pair_{i:04d}'
        main_path=directory.with_suffix('.B-main.txt');events_path=directory.with_suffix('.B-events.txt')
        for path,text in [(main_path,text_main),(events_path,text_events)]:
            path.parent.mkdir(parents=True,exist_ok=True);assert not path.exists();path.write_text(text);path.chmod(0o444)
        facts=dict(video_id=row['video_id'],query=row['query'],source_filtered_json=row['json_path'],
            source_sha256=sha(row['json_path']),base_native_id=selection['base_id'],selected_native_ids=selection['native_ids'],
            omitted_native_tracks=selection['omitted'],events=event_records,frozen_config_sha256=old_lock['frozen_config_sha256'])
        facts_path=directory.with_suffix('.facts.json')
        immutable(facts_path,facts)
        rep_rows.append(dict(video_id=row['video_id'],query=row['query'],main_path=str(main_path),main_sha256=sha(main_path),
            events_path=str(events_path),events_sha256=sha(events_path),facts_path=str(facts_path),facts_sha256=sha(facts_path)))
        texts[(row['video_id'],row['query'])]=dict(main=text_main,events=text_events)
        descriptive[(row['video_id'],row['query'])]=[
            dict(native_track_id=track['track_id'],**suspicious_track(track,document)) for track in document['tracks']]
    artifacts.append(immutable(ROOT/'results/stage5_representations_locked.json',dict(created_at=now(),
        deterministic=True,answers_or_metadata_used=False,frozen_config_sha256=old_lock['frozen_config_sha256'],
        rules='Direct frozen representative(document) and timeline(document); no classify/predict call, so unsupported event questions still receive lists.',
        coordinates='Original positions rounded2dec in text; edge predicate evaluated on original coordinates before rounding.',
        omission='Original unfiltered native-track count minus native fragments selected into representative; one omitted-count line.',
        files=rep_rows)))
    from transformers import AutoProcessor
    import numpy as np
    processor=AutoProcessor.from_pretrained(ROOT/'models/Qwen2.5-VL-7B-Instruct',local_files_only=True)
    prior_length={r['qa_id']:r for r in read(ROOT/'results/v1_input_lengths.json')['rows']}
    old_prompts={c:{p['qa_id']:p for p in rows(ROOT/'results/stage4/prompts'/f'{c}.jsonl')} for c in ('A','B','C','D')}
    prompt_rows={template:{c:[] for c in (CONDITIONS if template=='reasoning' else NEW_OFFICIAL)} for template in ('reasoning','official')}
    length_rows=[]
    for item in visible:
        qid=item['qa_id'];video=item['video_id'];_,sample=sampling(video)
        stamp=old_prompts['A'][qid]['user'].split('\n',1)[0]
        evidence={c:old_prompts[c][qid]['evidence'] for c in ('A','B','C','D')}
        new_track_text={c:'\n'.join(texts[(video,q)][key] for q in query_by_id[qid]) for c,key in [('B-main','main'),('B-events','events')]}
        evidence.update({c:TRACKER_PREFACE+new_track_text[c] for c in NEW_OFFICIAL})
        for template,condition_rows in prompt_rows.items():
            for condition in condition_rows:
                if template=='reasoning':system,user=reasoning_prompt(item,stamp,evidence[condition]);budget=1024
                else:
                    system,user=build_prompt(item)
                    user=stamp+'\n'+user.replace('Question:',evidence[condition]+'\nQuestion:',1)
                    budget=get_max_tokens(item['format'])
                track_text=(new_track_text[condition] if condition in NEW_OFFICIAL else old_prompts[condition][qid]['track_text'])
                p=dict(qa_id=qid,video_id=video,format=item['format'],template=template,condition=condition,
                    system=system,user=user,evidence=evidence[condition],track_text=track_text,max_tokens=budget,
                    sampled_frames=sample['sampled_count'],prompt_sha256=digest(dict(system=system,user=user)))
                messages=[dict(role='system',content=system),dict(role='user',content=[dict(type='image') for _ in range(p['sampled_frames'])]+[dict(type='text',text=user)])]
                rendered=processor.apply_chat_template(messages,tokenize=False,add_generation_prompt=True)
                p['expected_prompt_tokens']=len(processor.tokenizer.encode(rendered,add_special_tokens=False))+prior_length[qid]['image_tokens']-p['sampled_frames']
                assert p['expected_prompt_tokens']+budget<=65536
                condition_rows[condition].append(p)
                length_rows.append(dict(qa_id=qid,template=template,condition=condition,input_tokens=p['expected_prompt_tokens'],generation_budget=budget))
    length_stats={}
    for template,by_condition in prompt_rows.items():
        length_stats[template]={}
        for condition,prompts in by_condition.items():
            path=ROOT/'results/stage5/prompts'/template/f'{condition}.jsonl';assert not path.exists()
            write_rows(path,prompts);path.chmod(0o444)
            artifacts.append(dict(path=str(path),sha256=sha(path)))
            values=[p['expected_prompt_tokens'] for p in prompts]
            length_stats[template][condition]=dict(n=len(values),median=float(np.percentile(values,50)),p95=float(np.percentile(values,95)),maximum=max(values))
    artifacts.append(immutable(ROOT/'results/stage5_input_lengths_locked.json',dict(created_at=now(),no_inference=True,
        max_model_len=65536,statistics=length_stats,rows=length_rows)))
    # Geometry diagnostic uses every retained B track; it never feeds any prompt.
    registration=read(ROOT/'results/trackable_subset_preregistered.json')
    dimension={r['qa_id']:r['dimension'] for r in registration['rows']}
    by_dim=defaultdict(set)
    for q in visible:
        for phrase in query_by_id[q['qa_id']]:by_dim[dimension[q['qa_id']]].add((q['video_id'],phrase))
    def aggregate(pairs):
        tracks=[track for pair in pairs for track in descriptive[pair]]
        n=len(tracks);obs=sum(t['observations'] for t in tracks);flag=sum(t['suspicious_observations'] for t in tracks)
        return dict(query_pairs=len(pairs),retained_native_tracks=n,any_suspicious=sum(t['any_suspicious'] for t in tracks),
            majority_suspicious=sum(t['majority_suspicious'] for t in tracks),
            any_ratio=sum(t['any_suspicious'] for t in tracks)/n if n else None,
            majority_ratio=sum(t['majority_suspicious'] for t in tracks)/n if n else None,
            observations=obs,suspicious_observations=flag,observation_ratio=flag/obs if obs else None)
    desc=dict(generated_at=now(),no_tuning=True,scope='All frozen B retained native tracks; per-dimension unique (video,query,native_id); tracks shared by dimensions may occur in more than one row.',
        criterion='An observation is suspicious if |cx-.50|<=.05 AND |cy-.50|<=.05 AND bbox_area/frame_area>=.80. Track proportions reported for any observation and >=50% observations. Geometric proxy, not confirmed false-positive labels.',
        overall=aggregate(set(descriptive)),per_dimension={d:aggregate(pairs) for d,pairs in sorted(by_dim.items())})
    artifacts.append(immutable(ROOT/'results/stage5_full_frame_track_descriptives.json',desc))
    reused=[]
    for mode in ('main','guided'):
        for condition in ('A','B','C','D'):
            path=ROOT/'results/stage4'/f'{mode}_{condition}_predictions.jsonl'
            reused.append(dict(path=str(path),sha256=sha(path),template='official',condition=condition,decoding=mode))
    artifacts.append(immutable(ROOT/'results/stage5_stage4_reuse_locked.json',dict(created_at=now(),files=reused,
        D_assignment_sha256=sha(ROOT/'results/stage4_D_assignments_locked.json'))))
    protocol=read(ROOT/'results/stage4_protocol_locked.json')
    protocol.update(created_at=now(),current_user_authorization='User approved Stage4 main and authorized brief-reasoning and representation gradient diagnostics.',
        conditions=list(CONDITIONS),reasoning_max_tokens=1024,official_max_tokens='64/256 as Stage4',
        numerical_guidance=hypotheses['numerical_guidance'],reasoning_parser=hypotheses['reasoning_parser'],
        new_requests=dict(reasoning_main=4494,official_main=1498,reasoning_guided=1800,official_guided=600,total=8392),
        server_configuration='Exactly Stage4; all model/engine arguments unchanged, numeric CUDA masks chosen at launch.',
        prior_A_route='Frozen rule if covered, otherwise current template A; official uses saved Stage4 A, reasoning uses new reasoning A.',
        run_order='Official new B-main/B-events raw and guided, then reasoning six conditions raw and guided. Each condition is a separate resumable unit; one shared server configuration throughout.',
        final_line_guidance='Single call regex, retaining free-form reasoning and restricting only final Answer value.',
        representation_parameters_updated=False,tracking_rerun=False)
    artifacts.append(immutable(ROOT/'results/stage5_protocol_locked.json',protocol))
    sources={name:sha(ROOT/'src'/name) for name in ('stage5_common.py','stage5_representations.py')}
    immutable(ROOT/'logs/stage5_preinference_lock.json',dict(locked_at=now(),no_stage5_inference_at_lock=True,
        frozen_config_sha256=old_lock['frozen_config_sha256'],source_sha256=sources,artifacts=artifacts))
    with (ROOT/'research_log.md').open('a') as stream:
        stream.write('\n## '+now()+' — 阶段五推理前预登记与表示锁定\n\n'
            '- 已确认项目为独立toc_phase0，冻结v1、分割、可表达清单、阶段四原预测和D分配均保持不变。用户确认只约束推理模板的最终Answer，保留推理，总预算1024。\n'
            '- 计划：H6推理模板B>A；H7两模板R/D表示梯度；H8事件表示对冻结规则。≥同时报告观察排序和统计不确定性，不从未显著差异推导不劣。\n'
            '- 新表示直接复用原representative与timeline函数，unsupported题也输出原始事件；未调用predict或真值/选项映射。锁定899对表示、5992份新提示词及最终行解析。\n'
            '- 新推理8392条（raw5992，guided2400）；官方A/B/C/D复用阶段四。服务参数与阶段四相同，按已授权GPU共享策略启动；逐条件预计小于6小时，实测进度记录于控制器。\n'
            '- 整幅画面几何疑似误检仅统计，不调整、过滤或重跟踪。完成后停止。\n')
    print(json.dumps(dict(status='LOCKED_BEFORE_INFERENCE',hypotheses_sha256=sha(ROOT/'results/stage5_hypotheses_preregistered.json'),
        representation_pairs=len(rep_rows),new_prompts=len(length_rows),new_requests=8392,input_lengths=length_stats,
        suspected_full_frame=desc['overall']),ensure_ascii=False))


if __name__=='__main__':main()
