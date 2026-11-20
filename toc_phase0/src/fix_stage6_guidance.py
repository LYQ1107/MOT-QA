"""Lock an auxiliary grammar correction; preserve all primary results and old diagnostics."""
import os
from pathlib import Path
import re
import shutil
from stage6_common import *


def main():
    import xgrammar as xgr
    from transformers import AutoTokenizer
    tokenizer=AutoTokenizer.from_pretrained(ROOT/'models/Qwen2.5-VL-7B-Instruct',local_files_only=True)
    compiler=xgr.GrammarCompiler(xgr.TokenizerInfo.from_huggingface(tokenizer))
    # A tool-attempt marker commits that turn to the same ordinary custom parser,
    # including malformed/unclosed calls. Do not force its syntax or its EOS.
    # The guarded prefix still prevents an illegal Answer: value from being
    # swallowed into reasoning while waiting for some future tool marker.
    corrected='(?:'+FINAL_REGEX+'|'+PREFIX+r'[ \t]*<tool_call[\s\S]*)'
    compiled=compiler.compile_regex(corrected);old=compiler.compile_regex(TOOL_OR_FINAL_REGEX)
    cases=[('Answer: 2',True),('A reason.\nAnswer: 5 or more',True),('Answer: 0',False),('Answer: 2.0',False),
           ('<tool_call>{"name":"events","arguments":{"object":"cup"}}',True),
           ('<tool_call>\n{"name":"events","arguments":{"object":"cup"}}\n</tool_call>',True),
           ('A reason.\n <tool_call>{"name":"look","arguments":{"object":"cup","time":2}}',True)]
    checks=[]
    for text_,expected in cases:
        matcher=xgr.GrammarMatcher(compiled);valid=True
        for token in tokenizer.encode(text_,add_special_tokens=False):
            if not matcher.accept_token(token):valid=False;break
        accepted=bool(valid and matcher.accept_token(151645))
        assert accepted==expected,(text_,accepted)
        checks.append(dict(text=text_,accepts_primary_eos=accepted))
    primary={}
    for c in ['T-none','T0','T1']:
        path=ROOT/'results/stage6'/f'main_{c}_predictions.jsonl';ps=rows(path);assert len(ps)==602
        primary[c]=dict(path=str(path),sha256=sha(path),questions=602,
            attempted=sum(p['call_attempts'] for p in ps),legal=sum(call['result']['legal'] for p in ps for call in p['tool_calls']))
    lora=ROOT/'results/stage6/main_LoRA-B-events_predictions.jsonl'
    primary['LoRA-B-events']=dict(path=str(lora),sha256=sha(lora),questions=251)
    assert len(rows(lora))==251
    state=read(ROOT/'logs/stage6_job.json')
    # The previous controller and registered server have been stopped deliberately.
    try:os.kill(state['controller_pid'],0)
    except ProcessLookupError:pass
    else:raise RuntimeError('Old controller still present; do not move live output files')
    state.update(status='INTERRUPTED_AUXILIARY_IMPLEMENTATION',interrupted_at=now(),
        interruption_reason='Auxiliary grammar forced closing-tag syntax instead of leaving model errors to the ordinary parser; no primary outcomes changed')
    write(ROOT/'logs/stage6_job_attempt2.json',state);write(ROOT/'logs/stage6_job.json',state)
    archive=ROOT/'results/stage6_guided_initial_implementation';archive.mkdir(parents=True,exist_ok=True)
    archived=[]
    for c in ['T-none','T0','T1']:
        source=ROOT/'results/stage6/predictions/guided'/c
        if source.exists():
            files=sorted(source.glob('*.json'));records=[read(p) for p in files]
            destination=archive/'predictions'/c;destination.parent.mkdir(parents=True,exist_ok=True)
            assert not destination.exists();shutil.move(str(source),str(destination))
            out=archive/f'guided_{c}_predictions.jsonl';write_rows(out,records)
            archived.append(dict(condition=c,completed=len(records),expected=242,partial=len(records)!=242,
                truncated=sum(p['budget_exhausted'] for p in records),output=str(out),sha256=sha(out)))
        aggregate=ROOT/'results/stage6'/f'guided_{c}_predictions.jsonl'
        if aggregate.exists():shutil.move(str(aggregate),str(archive/aggregate.name.replace('_predictions','_original_aggregate')))
        receipt=ROOT/'logs'/f'stage6_guided_{c}_receipt.json'
        if receipt.exists():shutil.move(str(receipt),str(archive/receipt.name))
    value=dict(locked_at=now(),role='Technical correction of auxiliary count diagnosis only; all main predictions andH9-H11 unchanged',
        reason='The ordinary parser can end a malformed/unclosed call and return an error. Original auxiliary grammar disallowed EOS there and imposed single-line closed-tag syntax, generating hallucinated addCriterion and blank-line tails.',
        corrected_tool_or_final_regex=corrected,final_answer_regex_unchanged=FINAL_REGEX,
        semantics='Line-start Answer: commits to a final legal number. Line-start tool-attempt marker commits to a tool turn whose body/EOS are unconstrained; ordinary custom parser alone accepts or rejects it. No invented closing tags.',
        legal_choices=list(LEGAL),bad_words=['<|endoftext|>'],total_generation_tokens=2048,max_calls=4,
        primary_and_training_reused=primary,archived_diagnostics=archived,
        original_diagnostic_records=sum(r['completed'] for r in archived),cpu_checks=checks,
        rerun='All three numerical conditions uniformly242each; later conditional controls use this same corrected grammar',
        unchanged=['all raw primary predictions','H9-H11','frozenv1','split','trackable list','five demonstrations','frames/timestamps','server flags','final-answer parser','seed42','temperature0'],
        implementation_sha256=sha(ROOT/'src/run_stage6.py'))
    lock=immutable(ROOT/'results/stage6_guided_tool_turn_fix_locked.json',value)
    with (ROOT/'research_log.md').open('a') as stream:
        stream.write('\n## '+now()+' — 阶段六辅助计数约束的工具轮修复\n\n'
            '- T1主运行463/602题有工具尝试，共1801次，均缺少闭合标签而被固定解析器拒绝；模型错误保留，不补标签。T0主运行无工具调用。尚未据此改变提示词或任何主流程。\n'
            '- 原辅助grammar额外强制闭合标签且单行JSON，拒绝主循环可处理的错误调用EOS，导致addCriterion/空行长尾。修正为工具轮完全交原解析器，仅Answer轮限制合法值；CPU确认真实未闭合调用可正常EOS，非法Answer0/2.0仍不能EOS。\n'
            '- 停止原辅助计算；原三组共'+str(value['original_diagnostic_records'])+'条（T1部分）完整归档。主1806条、LoRA251条和训练适配器原样复用；三组计数242各统一重跑，控制条件用同一修正版。新协议独立只读锁定，SHA256 '+lock['sha256']+'。\n')
    print(__import__('json').dumps(dict(status='AUXILIARY_FIX_LOCKED',lock=lock,archived=archived,primary=primary),ensure_ascii=False))


if __name__=='__main__':main()
