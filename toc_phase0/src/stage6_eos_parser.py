"""Proposed exploratory parser only; not used by the registered primary runs.

Accept one complete JSON object ending exactly at EOS after a leading tag.
No closing-tag invention, fuzzy object matching, or answer-based decisions.
"""
import json
from stage6_common import parse_call


def parse_eos_call(text):
    call,error=parse_call(text)
    if call is not None:return call,None,False
    stripped=text.strip();marker='<tool_call>'
    if not stripped.startswith(marker):return None,error,False
    body=stripped[len(marker):].strip()
    try:obj,end=json.JSONDecoder().raw_decode(body)
    except (ValueError,TypeError):return None,error,False
    if body[end:].strip() or not isinstance(obj,dict) or set(obj)!={'name','arguments'} or not isinstance(obj['name'],str) or not isinstance(obj['arguments'],dict):
        return None,error,False
    return obj,None,True


def cpu_checks():
    payload='{"name":"events","arguments":{"object":"cup"}}'
    tests=[('<tool_call>'+payload+'</tool_call>',True,False),
           ('<tool_call>'+payload,True,True),
           ('<tool_call>\n'+payload+'\n',True,True),
           ('<tool_call>'+payload+'\nAnswer: A',False,False),
           ('<tool_call>'+payload+' '+payload,False,False),
           ('<tool_call>{"name":"events","arguments":',False,False)]
    for text,accepted,recovered in tests:
        call,error,got_recovery=parse_eos_call(text)
        assert (call is not None)==accepted and got_recovery==recovered,(text,call,error,got_recovery)
    return len(tests)


if __name__=='__main__':print('Proposed EOS parser CPU checks:',cpu_checks(),'; no model inference or primary modification')
