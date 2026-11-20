"""Stage 7: retain the old parser, additionally accept one JSON call at EOS."""
import json
from stage6_common import parse_call


def parse_fixed_call(text):
    call,error=parse_call(text)
    if call is not None:return call,None,False
    marker='<tool_call>'
    if text.count(marker)!=1:return None,error,False
    body=text.split(marker,1)[1].strip()
    try:value,end=json.JSONDecoder().raw_decode(body)
    except (ValueError,TypeError):return None,error,False
    if body[end:].strip() or not isinstance(value,dict) or set(value)!={'name','arguments'}:
        return None,error,False
    if not isinstance(value['name'],str) or not isinstance(value['arguments'],dict):return None,error,False
    return value,None,True


def parse_call_pair(text):
    call,error,_=parse_fixed_call(text)
    return call,error


def cpu_checks():
    body='{"name":"events","arguments":{"object":"cup"}}'
    cases=[('<tool_call>'+body+'</tool_call>',True,False),
           ('<tool_call>'+body,True,True),
           ('I will inspect the events.\n<tool_call>\n'+body+'\n',True,True),
           ('<tool_call>'+body+'\nAnswer: A',False,False),
           ('<tool_call>'+body+' '+body,False,False),
           ('<tool_call>{"name":"events","arguments":',False,False),
           ('Answer: A',False,False)]
    for text,accepted,recovered in cases:
        call,_,recovery=parse_fixed_call(text)
        assert (call is not None)==accepted and recovery==recovered,(text,call,recovery)
    return len(cases)
