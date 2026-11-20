"""Stage 5 templates, locked parsing, and artifact validation (no labels)."""
import re
from pathlib import Path

from stage4_common import (ROOT, LEGAL, TRACKER_PREFACE, PLACEHOLDER, now, read, rows,
    write, write_rows, immutable, sha, digest, verify_stage4, sampling, build_prompt,
    get_max_tokens, extract)

CONDITIONS=('A','B','C','D','B-main','B-events')
NEW_OFFICIAL=('B-main','B-events')
FINAL_NUMBER_REGEX=r'[\s\S]*\nAnswer: (2|3|4|5 or more)'
REASONING_SYSTEM='You are a careful video analyst. Answer the question about the video.'
INSTRUCTIONS={
    'mcq_4':'Think briefly, then give your final answer on the last line as "Answer: X", where X is one of A, B, C, D.',
    'sp':'Think briefly, then give your final answer on the last line as "Answer: X", where X is A or B.',
    'numerical':'Think briefly, then give your final answer on the last line as "Answer: N", where N is one of 2, 3, 4, or "5 or more".',
    'ordering':'Think briefly, then give your final answer on the last line as "Answer: " followed by the event labels in chronological order, separated by commas (e.g., "Answer: C, A, B").'}


def reasoning_prompt(item,stamp,evidence):
    assert not any(k in item for k in ('metadata','correct_answer','correct_order'))
    fmt=item['format']
    if fmt.startswith('ordering'):
        options='\n'.join(f'{e["label"]}. {e["event_text"]}' for e in item['events'])
    else:
        letters='ABCD' if fmt=='mcq_4' else 'AB' if fmt=='sp' else ''
        options='\n'.join(f'{letter}. {item.get("option_"+letter) or item.get("statement_"+letter)}' for letter in letters)
    user=stamp+'\n'+evidence
    if evidence and not evidence.endswith('\n'):user+='\n'
    user+='Question: '+item['question']+'\nOptions:\n'+options+'\n\n'+INSTRUCTIONS['ordering' if fmt.startswith('ordering') else fmt]
    return REASONING_SYSTEM,user


def final_answer(raw,fmt):
    """Strict last nonempty line: no fallback into reasoning or earlier answers."""
    lines=(raw or '').strip().splitlines()
    if not lines:return None,None
    match=re.fullmatch(r'\s*Answer:\s*(.*?)\s*',lines[-1])
    if not match:return None,None
    value=match.group(1)
    if fmt in ('sp','mcq_4'):
        allowed='AB' if fmt=='sp' else 'ABCD'
        return (value if value in allowed else None),value
    if fmt=='numerical':return (value if value in LEGAL else None),value
    size=int(fmt.rsplit('_',1)[1])
    if not re.fullmatch(r'[A-D](?:\s*,\s*[A-D])*',value):return None,value
    order=[s.strip() for s in value.split(',')]
    expected=set('ABCD'[:size])
    return (order if len(order)==size and set(order)==expected else None),value


def verify_stage5():
    old=verify_stage4()
    lock=read(ROOT/'logs/stage5_preinference_lock.json')
    assert lock['frozen_config_sha256']==old['frozen_config_sha256']
    for artifact in lock['artifacts']:
        path=Path(artifact['path'])
        assert sha(path)==artifact['sha256'],path
        assert path.stat().st_mode&0o222==0,path
    return lock
