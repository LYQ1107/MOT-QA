"""Stage 6 protocol, custom tag parser, and saved-message materialization."""
import base64
import json
from functools import lru_cache
import re
from pathlib import Path
from stage5_common import (ROOT,now,read,rows,write,write_rows,immutable,sha,digest,
                          sampling,verify_stage5,final_answer,reasoning_prompt,LEGAL)

SYSTEM=('You are a careful video analyst. Answer the question about the video. '
    'Think briefly and give your final answer on the last line in the requested Answer: format. '
    'When tools are available, you may use them to inspect evidence before answering. '
    'For one call, output <tool_call>{"name":"tool_name","arguments":{...}}</tool_call> '
    'on a single line, without an Answer: line in that turn. Use at most one call per turn and four calls per question. '
    'Tool results are observations from an imperfect tracker, not answers. Compare them with the video. '
    'Do not invent tool results. After receiving a result, continue or give a brief explanation and the final answer.')
DESCRIPTIONS=('Available tools (all use offline frozen 5fps tracks):\n'
    'track(object, t_start=null, t_end=null): representative trajectory summary; optional inclusive time range in seconds.\n'
    'events(object): first appearance, disappearance, reappearance and last observation times and positions.\n'
    'look(object, time): nearest 5fps subject crop expanded by 30% on each side and a full-frame thumbnail; '
    'if not detected, only the full frame.\n'
    'Use the object phrase from the question, options, statements or event descriptions. '
    'Matching is exact after Unicode, case and whitespace normalization; no synonym or fuzzy matching.\n')
NO_TOOLS='Available tools: none. Answer directly using the supplied frames and timestamps.\n'
FINAL_REGEX=read(ROOT/'results/stage5_guided_v2_commit_protocol_locked.json')['corrected_regex']
PREFIX=FINAL_REGEX[:FINAL_REGEX.index('Answer: (2|3|4|5 or more)')]
TOOL_REGEX=PREFIX+r'<tool_call>\{[^\n]*\}</tool_call>'
TOOL_OR_FINAL_REGEX='(?:'+FINAL_REGEX+'|'+TOOL_REGEX+')'
TAG=re.compile(r'<tool_call>(.*?)</tool_call>',re.S)


def parse_call(text):
    matches=TAG.findall(text)
    if not matches:
        return None,('malformed tool call tag' if '<tool_call' in text else None)
    if len(matches)!=1:return None,'only one tool call is allowed per turn'
    try:value=json.loads(matches[0])
    except (ValueError,TypeError):return None,'invalid tool call JSON'
    if not isinstance(value,dict) or set(value)!={'name','arguments'} or not isinstance(value['name'],str):
        return None,'expected exactly name and arguments fields'
    return value,None


def initial_message(item,stamp,condition):
    _,user=reasoning_prompt(item,stamp,'')
    user=user.replace('Question:',(NO_TOOLS if condition=='T-none' else DESCRIPTIONS)+'\nQuestion:',1)
    directory,sample=sampling(item['video_id'])
    # Identical byte content AND order to the Stage5 sampler manifest.
    actual=[directory/name for name in sample['jpeg_files']]
    assert len(actual)==sample['sampled_count'] and all(p.exists() for p in actual)
    images=[dict(type='image_path',path=str(p)) for p in actual]
    return dict(role='user',content=images+[dict(type='text',text=user)])


@lru_cache(maxsize=256)
def encoded(path):
    return base64.b64encode(Path(path).read_bytes()).decode()


def materialize(messages):
    result=[]
    for message in messages:
        if isinstance(message['content'],str):result.append(message);continue
        content=[]
        for block in message['content']:
            if block['type']=='image_path':content.append(dict(type='image_url',image_url=dict(url='data:image/jpeg;base64,'+encoded(block['path']))))
            else:content.append(block)
        result.append(dict(role=message['role'],content=content))
    return result


def tool_message(result):
    return dict(role='user',content=[dict(type='text',text=result['text'])]+
                [dict(type='image_path',path=im['path']) for im in result.get('images',[])])
