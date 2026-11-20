"""Commit the effective auxiliary fix before any replacement diagnosis inference."""
from types import SimpleNamespace as NS
from stage6_common import *
from stage6_final_field_guidance import generate


def main():
    from transformers import AutoTokenizer
    tokenizer=AutoTokenizer.from_pretrained(ROOT/'models/Qwen2.5-VL-7B-Instruct',local_files_only=True)
    # Exact assistant continuation, without inserting a new role/extra prompt.
    messages=[dict(role='system',content='You are a careful video analyst.'),dict(role='user',content='A question')]
    prefix='Two returns are visible.\nAnswer:'
    base=tokenizer.apply_chat_template(messages,tokenize=False,add_generation_prompt=True)
    continuation=tokenizer.apply_chat_template(messages+[dict(role='assistant',content=prefix)],tokenize=False,
                    add_generation_prompt=False,continue_final_message=True)
    assert continuation==base+prefix
    class U:
        def __init__(self,n,p=10):self.completion_tokens=n;self.prompt_tokens=p;self.total_tokens=n+p
        def model_dump(self):return dict(completion_tokens=self.completion_tokens,prompt_tokens=self.prompt_tokens,total_tokens=self.total_tokens)
    class Client:
        def __init__(self,responses):self.responses=iter(responses);self.kwargs=[];self.chat=NS(completions=NS(create=self.create))
        def create(self,**kwargs):
            self.kwargs.append(kwargs);raw,n=next(self.responses)
            return NS(id='cpu-check',usage=U(n),choices=[NS(message=NS(content=raw),finish_reason='stop')])
    # Malformed tool turns are returned unchanged, with no EOS masking/grammar.
    unclosed='<tool_call>{"name":"events","arguments":{"object":"cup"}}'
    client=Client([(unclosed,15)]);r,c=generate(client,messages,2048,'model')
    assert c.message.content==unclosed and len(client.kwargs)==1 and 'structured_outputs' not in client.kwargs[0]['extra_body']
    client=Client([(prefix,20),('2',2)]);r,c=generate(client,messages,2048,'model')
    assert c.message.content==prefix+'2' and r.usage.completion_tokens==22 and client.kwargs[1]['max_tokens']==2028
    assert client.kwargs[1]['extra_body']['continue_final_message'] is True
    value=dict(locked_at=now(),version='final_field_only_v2',role='Auxiliary numerical diagnosis correction only; all primary predictions andH9-H11 preserved',
        reason='Tool turns must retain ordinary decoding/EOS and ordinary parser errors. A union grammar forcing closed tags had constrained tool syntax and caused length tails.',
        method='Generate freely with stop Answer: and include_stop_str_in_output. If an Answer marker is emitted outside a tool-attempt turn, continue the same assistant message under four-value guided choice; no new role prefix. Concatenate actual returned segments.',
        legal_choices=list(LEGAL),temperature=0,seed=42,total_generation_tokens=2048,max_tool_calls=4,
        eos_policy='No special EOS masking or syntax constraints in free/tool stage. Mask extraEOS151643 only during numeric continuation, exactly as Stage5 corrected choice.',
        accounting='All physical response IDs, raw segments, per-request usage/max budget saved. Per-turn usage sums physical requests; per-question completion total<=2048. No budget reset for continuation.',
        parser='Unchanged Stage5 final line parser; no closing-tag recovery; malformed tool calls remain errors.',
        cpu_checks=['Exact Qwen assistant continuation equals original rendered prompt plus raw prefix',
                    'Unclosed real-style call returns unchanged in one unconstrained request',
                    'Reasoning prefix and legal numeric continuation concatenated;20+2tokens,remaining2028'],
        supersedes_unexecuted_grammar_draft_sha256=sha(ROOT/'results/stage6_guided_tool_turn_fix_locked.json'),
        previous_draft_model_requests=0,
        primary_and_training_reused=read(ROOT/'results/stage6_guided_tool_turn_fix_locked.json')['primary_and_training_reused'],
        original_diagnostic_records=read(ROOT/'results/stage6_guided_tool_turn_fix_locked.json')['original_diagnostic_records'],
        implementation_sha256=sha(ROOT/'src/stage6_final_field_guidance.py'),runner_sha256=sha(ROOT/'src/run_stage6.py'),
        run_policy='All3 conditions242 each rerun uniformly; conditional controls use identical v2 method; primary data and training not rerun or changed')
    lock=immutable(ROOT/'results/stage6_final_field_guidance_v2_locked.json',value)
    with (ROOT/'research_log.md').open('a') as f:f.write('\n阶段六有效辅助修正版在任何新推理前锁定：工具轮完全自由解码，遇到Answer:后才对同一assistant的数值续写使用guided choice；总预算仍2048，保存全部物理请求与用量。CPU确认续写渲染完全等于原提示词+前缀、未闭合调用原样返回、20+2token预算不重置。此前工具轮regex草案仅CPU测试、模型请求0。有效协议SHA256 '+lock['sha256']+'。\n')
    print(__import__('json').dumps(dict(status='FINAL_FIELD_ONLY_V2_LOCKED',lock=lock),ensure_ascii=False))


if __name__=='__main__':main()
