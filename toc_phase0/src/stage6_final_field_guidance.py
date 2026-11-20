"""Free reasoning/tools until Answer:, then constrained numeric continuation.

Tool turns use the ordinary model EOS and are never grammar-constrained.
Every physical response and token usage is retained; the2048 budget is shared.
"""
from copy import deepcopy
from types import SimpleNamespace
from stage6_common import LEGAL


class Usage:
    def __init__(self,requests):
        self.prompt_tokens=sum(r['usage']['prompt_tokens'] for r in requests)
        self.completion_tokens=sum(r['usage']['completion_tokens'] for r in requests)
        self.total_tokens=sum(r['usage']['total_tokens'] for r in requests)
        self.requests=len(requests)
    def model_dump(self):
        return dict(prompt_tokens=self.prompt_tokens,completion_tokens=self.completion_tokens,total_tokens=self.total_tokens,
                    request_count=self.requests,aggregation='sum_of_physical_request_usage')


def request(client,kwargs,phase):
    response=client.chat.completions.create(**kwargs);choice=response.choices[0]
    assert isinstance(choice.message.content,str)
    assert response.usage.prompt_tokens+kwargs['max_tokens']<=65536
    assert response.usage.completion_tokens<=kwargs['max_tokens']
    detail=dict(phase=phase,response_id=response.id,raw_response=choice.message.content,usage=response.usage.model_dump(),
                finish_reason=choice.finish_reason,max_tokens=kwargs['max_tokens'],stop_reason=getattr(choice,'stop_reason',None))
    return response,choice,detail


def generate(client,materialized_messages,remaining,model):
    first_kwargs=dict(model=model,messages=materialized_messages,temperature=0.,seed=42,max_tokens=remaining,
                      stop=['Answer:'],extra_body=dict(include_stop_str_in_output=True))
    first,choice,detail=request(client,first_kwargs,'free_reasoning_or_tool_until_Answer_marker')
    details=[detail];raw=choice.message.content
    left=remaining-first.usage.completion_tokens
    # A tagged attempt belongs to the ordinary parser, even if malformed. Never
    # complete its markup or constrain its EOS to manufacture a successful call.
    if '<tool_call' not in raw and raw.endswith('Answer:') and left>0:
        continuation=deepcopy(materialized_messages)+[dict(role='assistant',content=raw)]
        kwargs=dict(model=model,messages=continuation,temperature=0.,seed=42,max_tokens=left,
                    extra_body=dict(structured_outputs=dict(choice=list(LEGAL)),bad_words=['<|endoftext|>'],
                                    continue_final_message=True,add_generation_prompt=False))
        second,choice,detail=request(client,kwargs,'constrained_final_number_continuation')
        details.append(detail)
        if choice.finish_reason!='length':assert choice.message.content in LEGAL,detail
        raw+=choice.message.content
    usage=Usage(details);assert usage.completion_tokens<=remaining
    combined_choice=SimpleNamespace(message=SimpleNamespace(content=raw),finish_reason=choice.finish_reason,
                                    stop_reason=getattr(choice,'stop_reason',None))
    combined_response=SimpleNamespace(id=first.id,usage=usage,physical_requests=details)
    return combined_response,combined_choice
