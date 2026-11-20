"""Pure synthetic event reasoning data. Does not read benchmark data or labels."""
import random
from collections import Counter


def generate(seed=42,n=2000):
    rng=random.Random(seed);result=[]
    colors=['red','blue','green','white','black','yellow','orange','purple']
    things=['cup','box','bag','bottle','book','chair','shoe','plate','cabinet','toy','towel','hat']
    def name():return rng.choice(colors)+' '+rng.choice(things)
    def at():return rng.randint(1,45)/5
    def loc(edge=False):
        if edge:
            side=rng.choice(['left','right','top','bottom']);x=rng.randint(15,85)/100;y=rng.randint(15,85)/100
            if side=='left':x=rng.randint(1,4)/100
            elif side=='right':x=rng.randint(96,99)/100
            elif side=='top':y=rng.randint(1,4)/100
            else:y=rng.randint(96,99)/100
            return x,y,'yes ('+side+')'
        return rng.randint(10,90)/100,rng.randint(10,90)/100,'no'
    def sequence(obj,k,edges=None,start=None):
        time=at() if start is None else start;x,y,_=loc();lines=[f'first appears at {time:.1f}s at ({x:.2f}, {y:.2f})'];events=[('first',time,False)]
        for j in range(k):
            time+=rng.randint(4,25)/5;edge=edges[j] if edges is not None else False;x,y,flag=loc(edge)
            lines.append(f'disappears at {time:.1f}s; last position ({x:.2f}, {y:.2f}); within 0.05 of frame edge: {flag}')
            events.append(('disappears',time,edge));time+=rng.randint(3,30)/5;x,y,_=loc()
            lines.append(f'reappears at {time:.1f}s at ({x:.2f}, {y:.2f})');events.append(('reappears',time,False))
        time+=rng.randint(5,20)/5;x,y,_=loc();lines.append(f'last seen at {time:.1f}s at ({x:.2f}, {y:.2f})')
        return f'[Tracking events] query="{obj}"  video_length={time+.2:.1f}s  tracker_fps=5\n'+'\n'.join(lines)+'\n',events
    for i in range(n):
        obj=name();family='RD' if i<800 else 'XOrder' if i<1400 else 'Count'
        if family=='RD':
            edge=bool(i%2);text,ev=sequence(obj,1,[edge]);before=ev[1][1];after=ev[2][1]
            opts=[f'{obj} was fully blocked before coming back',f'{obj} left the frame before coming back'];rng.shuffle(opts)
            target=f'{obj} left the frame before coming back' if edge else f'{obj} was fully blocked before coming back'
            answer='AB'[opts.index(target)]
            question=f'Before {obj} comes back into view, was it fully blocked or did it leave the frame?'
            options='A. '+opts[0]+'\nB. '+opts[1]
            explanation=f'The disappearance at {before:.1f}s is '+('within 0.05 of an edge, indicating departure from the frame' if edge else 'away from every edge, indicating full blockage')+f', followed by reappearance at {after:.1f}s. This matches option {answer}.'
            instruction='Think briefly, then give your final answer on the last line as "Answer: X", where X is A or B.'
        elif family=='XOrder':
            other=name()
            while other==obj:other=name()
            text1,ev1=sequence(obj,rng.randint(1,2));text2,ev2=sequence(other,rng.randint(1,2))
            kinds={'first':'enters the frame','disappears':'gets fully hidden','reappears':'comes back into view'}
            typ1=rng.choice(list(kinds));typ2=rng.choice(list(kinds))
            t1=next(t for kind,t,edge in ev1 if kind==typ1);t2=next(t for kind,t,edge in ev2 if kind==typ2)
            if abs(t1-t2)<.1:
                text2,ev2=sequence(other,1,start=t1+2.)
                t2=next(t for kind,t,edge in ev2 if kind==typ2)
            a=f'{obj} {kinds[typ1]} before {other} {kinds[typ2]}'
            b=f'{other} {kinds[typ2]} before {obj} {kinds[typ1]}'
            opts=[a,b];rng.shuffle(opts);answer='AB'[opts.index(a if t1<t2 else b)]
            text=text1+'\n'+text2;question='Which event happens first in the video?';options='A. '+opts[0]+'\nB. '+opts[1]
            explanation=f'The specified event for {obj} is at {t1:.1f}s, and the specified event for {other} is at {t2:.1f}s. Comparing these times gives option {answer}.'
            instruction='Think briefly, then give your final answer on the last line as "Answer: X", where X is A or B.'
        else:
            bucket=(i-1400)%4;k=[2,3,4,rng.randint(5,7)][bucket];task=rng.choice(['returns','hidden','disappears'])
            edges=[False]*k
            if task=='hidden':
                edges += [True]*rng.randint(0,2);rng.shuffle(edges)
            text,ev=sequence(obj,len(edges),edges)
            phrase={'returns':'come back into view','hidden':'get fully hidden','disappears':'completely disappear'}[task]
            question=f'How many times does the {obj} {phrase} in the video?';options=''
            answer=str(k) if k<5 else '5 or more'
            times=[t for kind,t,edge in ev if (kind=='reappears' if task=='returns' else kind=='disappears' and (not edge if task=='hidden' else True))]
            assert len(times)==k
            explanation='The relevant '+('reappearances' if task=='returns' else 'disappearances away from edges' if task=='hidden' else 'disappearances')+' are at '+', '.join(f'{t:.1f}s' for t in times)+f'. There are {k}, so the legal answer is {answer}.'
            instruction='Think briefly, then give your final answer on the last line as "Answer: N", where N is one of 2, 3, 4, or "5 or more".'
        result.append(dict(id=f'synthetic_{i:04d}',family=family,instruction=text+'\nQuestion: '+question+'\nOptions:\n'+options+'\n\n'+instruction,input='',output=explanation+'\nAnswer: '+answer,system='You are a careful video analyst. Answer the question about the video.'))
    rng.shuffle(result)
    assert len(result)==2000 and Counter(r['family'] for r in result)=={'RD':800,'XOrder':600,'Count':600}
    return result
