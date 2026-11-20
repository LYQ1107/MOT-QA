"""Register stage 6 and lock synthetic-only training and development demonstrations."""
from pathlib import Path
import subprocess
from collections import Counter
from stage6_common import *
from stage6_tools import Tools
from stage6_synthetic import generate


def main():
    old=verify_stage5();frozen=read(ROOT/'results/frozen_config_v1.json')
    assert not (ROOT/'results/stage6_hypotheses_preregistered.json').exists()
    h=dict(created_at=now(),before_any_stage6_inference_or_training=True,seed=42,
        frozen_config_sha256=old['frozen_config_sha256'],split_sha256=frozen['split_sha256'],
        trackable_sha256=frozen['preregistration_sha256'],project_root=str(ROOT),
        primary_scope='test trackable251; per-dimension and main-four231 also reported; test all602 supplemental',
        hypotheses=[
            dict(id='H9',statement='Zero-shot tool use T0 exceeds official-format A (89/251,35.46%) on test trackable251.',
                 comparison='T0 minus reused Stage4 official A',criterion='positive delta, exact two-sided McNemar p<.05 and bootstrap lower95% bound>0'),
            dict(id='H10',statement='Five-development-example T1 exceeds zero-shot T0 on test trackable251.',
                 comparison='T1 minus T0',criterion='positive delta, exact two-sided McNemar p<.05 and bootstrap lower95% bound>0'),
            dict(id='H11',statement='After synthetic-only LoRA, B-events reaches at least45/101 on test reappear_or_disappear; frozen rule51/101.',
                 criterion='observed count>=45 is the prespecified empirical endpoint; separately report paired before/after and versus rule with p andCI, without claiming a population lower bound from this count alone')],
        statistics=dict(mcnemar='exact two-sided conditional binomial on discordant correctness, p1 if none',
                        bootstrap='paired question-level percentile95%CI,1000 resamples, numpy default_rng42, sortedqa_id in each group',
                        alpha=.05,multiplicity='raw p reported; Holm-adjust H9/H10 additionally; other dimensions descriptive'),
        parser=dict(source_path=str(ROOT/'src/stage5_common.py'),source_sha256=sha(ROOT/'src/stage5_common.py'),
                    rule='Reuse strict last nonempty Answer: line exactly; no fallback; invalid parses wrong'),
        tool_budget=dict(max_calls=4,total_generation_tokens_per_question=2048,
                         calls_include_invalid_attempts=True,max_assistant_turns=5,temperature=0,seed=42),
        conditional_controls=dict(gate='After all T-none/T0/T1 raw predictions, run only if T0 orT1 has strictly more correct thanT-none on251.',
                                  selection='Choose greater correct count ofT0/T1; tieT0. Lock decision before controls.',
                                  controls=['T-ph: all tool replies placeholder','T-sh: frozen Stage4D assignments projected to requested tools'],
                                  run_scope='test all602 plus separate guided242'),
        training=dict(synthetic_examples=2000,benchmark_labels_used=False,types=dict(RD=800,XOrder=600,Count=600),
                      framework='LlamaFactory0.9.3',rank=8,epochs=2,selection='final second-epoch adapter; no benchmark validation or tuning',
                      evaluation='test trackable251 B-events with original Stage5 reasoning prompt and1024 token limit; compare saved pre-LoRA B-events and frozen rule'),
        look_service_note='Image-count conflict raised before execution: original32 plus at most8look images. Final tool image policy will be separately locked before inference after user clarification.',
        no_tracking_rerun=True,no_frozen_changes=True,stop_after_report=True)
    hlock=immutable(ROOT/'results/stage6_hypotheses_preregistered.json',h)
    side=ROOT/'results/stage6_hypotheses_preregistered.json.sha256';side.write_text(hlock['sha256']+'  stage6_hypotheses_preregistered.json\n');side.chmod(0o444)
    data_dir=ROOT/'data/stage6_synthetic';data_dir.mkdir(parents=True,exist_ok=True)
    train=generate();data_path=data_dir/'train.json'
    data_lock=immutable(data_path,train)
    info={'stage6_synthetic':dict(file_name='train.json',columns=dict(prompt='instruction',query='input',response='output',system='system'))}
    info_lock=immutable(data_dir/'dataset_info.json',info)
    config=dict(model_name_or_path=str(ROOT/'models/Qwen2.5-VL-7B-Instruct'),trust_remote_code=False,
        stage='sft',do_train=True,finetuning_type='lora',lora_rank=8,lora_alpha=16,lora_dropout=0.,lora_target='all',
        freeze_vision_tower=True,freeze_multi_modal_projector=True,dataset='stage6_synthetic',dataset_dir=str(data_dir),
        template='qwen2_vl',cutoff_len=2048,max_samples=2000,overwrite_cache=True,preprocessing_num_workers=4,dataloader_num_workers=2,
        output_dir=str(ROOT/'models/stage6_lora_r8'),logging_steps=10,save_strategy='epoch',save_total_limit=1,
        save_only_model=False,plot_loss=True,overwrite_output_dir=False,report_to='none',
        per_device_train_batch_size=2,gradient_accumulation_steps=8,learning_rate=1.e-4,num_train_epochs=2.,
        lr_scheduler_type='cosine',warmup_ratio=.1,bf16=True,gradient_checkpointing=True,optim='adamw_torch',
        attn_implementation='sdpa',seed=42,data_seed=42,eval_strategy='no',ddp_timeout=1800000)
    # LlamaFactory calls this argument flash_attn, with 'sdpa' as a supported value.
    config['flash_attn']=config.pop('attn_implementation')
    config_lock=immutable(ROOT/'results/stage6_training_config_locked.json',config)
    tools=Tools();visible={q['qa_id']:q for q in rows(ROOT/'results/stage3_visible_inputs.jsonl')}
    split=read(ROOT/'results/dev_test_split_locked.json');dev=set(split['dev_qa_ids'])
    queries={r['qa_id']:r['queries'] for r in read(ROOT/'results/stage3_extracted_queries.json')}
    demo_specs=[
      ('13a41b8c6b50','RD','A','The extinguisher disappears at4.0s away from the edge and reappears at5.2s. This supports full blockage, optionA.'),
      ('13ad81807fa0','RD','B','The cup has several disappearances, each marked away from the edge. Full blockage corresponds to optionB.'),
      ('aa9f2d427438','XOrder','A','The hand first appears at1.6s; the notebook first disappears at6.0s. The hand event is earlier, optionA.'),
      ('1297862b34c8','Count','2','The mug reappears at6.8s and7.4s. These are two returns; its initial appearance is not a return.'),
      ('3afb8d11cee9','Count','5 or more','There are five disappearance entries away from the frame edge, at6.0,11.4,14.2,15.4 and18.0s. This maps to the legal value5 or more.')]
    # Labels are allowed only for these development demonstrations, never synthetic training.
    labels={q['qa_id']:q for q in read(ROOT/'data/toc_bench/answer_final.json')['items'] if q['qa_id'] in dev}
    demos=[]
    for qid,family,answer,explanation in demo_specs:
        assert qid in dev and qid not in set(split['test_qa_ids']) and labels[qid]['correct_answer']==answer
        item=visible[qid];_,question=reasoning_prompt(item,'','')
        messages=[dict(role='user',content='Development demonstration.\n'+question.strip())]
        for obj in queries[qid]:
            call=dict(name='events',arguments=dict(object=obj))
            messages.append(dict(role='assistant',content='<tool_call>'+__import__('json').dumps(call)+'</tool_call>'))
            result=tools.execute(item['video_id'],**call);assert result['legal'] and result['matched']
            messages.append(tool_message(result))
        messages.append(dict(role='assistant',content=explanation+'\nAnswer: '+answer))
        demos.append(dict(qa_id=qid,video_id=item['video_id'],family=family,answer=answer,messages=messages))
    demos_lock=immutable(ROOT/'results/stage6_demonstrations_locked.json',dict(created_at=now(),split='development only',
        selection='TwoR/D and twoCount examples with frozen-rule agreement, plus oneXOrder with directly ordered observed events; chosen without test outcomes.',
        image_policy='Text-only complete demonstrations, actual unchanged offline tool facts; no additional demonstration images',examples=demos))
    manifest=immutable(ROOT/'results/stage6_training_data_locked.json',dict(created_at=now(),hypotheses_sha256=hlock['sha256'],
        examples=2000,families=dict(Counter(r['family'] for r in train)),benchmark_labels_used=False,
        generation_source_sha256=sha(ROOT/'src/stage6_synthetic.py'),train=data_lock,dataset_info=info_lock,config=config_lock,
        source='Deterministic synthetic generator seed42; no benchmark files imported by generator',
        final_adapter='Always second epoch, no benchmark-label checkpoint selection'))
    with (ROOT/'research_log.md').open('a') as stream:
        stream.write('\n## '+now()+' — 阶段六预登记与研究计划\n\n'
            '- 在独立toc_phase0复用v1，禁止重跟踪、重分割或修改可表达清单。先锁H9–H11、纯合成2000条、开发集5完整示范；再并行运行自写多轮工具实验与另一张卡的rank8/2epoch LoRA。\n'
            '- 主范围测试可表达251，工具条件覆盖测试602；每题最多4调用，总生成2048，解析完全复用阶段五。计数另做仅限制最终答案的诊断。对照按预登记观察分数触发，不调参。\n'
            '- 训练仅合成事实与自动答案，无基准标签；最终二轮适配器固定用于带帧B-events评测。保留全部错误、多轮记录、调用统计和资源耗时，完成停止。\n'
            '- look追加图片与原32张服务上限存在技术冲突，已提请一次澄清；工具推理等待最终图片协议，独立CPU/训练准备继续。\n')
    print(__import__('json').dumps(dict(status='REGISTERED_AND_TRAINING_LOCKED',hypotheses=hlock,training_data=manifest,demonstrations=demos_lock),ensure_ascii=False))


if __name__=='__main__':main()
