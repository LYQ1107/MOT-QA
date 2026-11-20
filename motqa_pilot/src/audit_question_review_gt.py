"""Numerically verify review answers from original GT text, independently of NPZ facts."""
from functools import lru_cache
import math
import numpy as np
from generate_question_review import ROOT, OUT, META, read_jsonl, dump


@lru_cache(maxsize=12)
def raw(key):
    m=META[key];x=np.loadtxt(m['source_gt_path'],delimiter=',',ndmin=2)
    x=x[(x[:,6]==1)&(x[:,7]==1)]
    ids=sorted(set(x[:,1].astype(int)));index={t:i for i,t in enumerate(ids)}
    boxes=np.full((len(ids),m['frames'],4),np.nan)
    visible=np.zeros((len(ids),m['frames']),bool)
    for row in x:
        i=index[int(row[1])];f=int(row[0])-1;b=row[2:6].copy()
        if key[0]=='MOT17':b[:2]-=1
        boxes[i,f]=b;visible[i,f]=key[0]!='MOT17' or row[8]>=.25
    return ids,index,boxes,visible,boxes[...,:2]+boxes[...,2:]/2


def appearances(key,tid):
    ids,ix,b,v,c=raw(key);m=META[key];fs=np.flatnonzero(v[ix[tid]])
    return [int(right)+1 for left,right in zip(fs[:-1],fs[1:]) if (right-left-1)/m['fps']>1]


def crossings(key,tid,start,end):
    ids,ix,b,v,c=raw(key);i=ix[tid];found=[]
    for other in ids:
        if other==tid:continue
        j=ix[other];mask=v[i]&v[j]
        lo=np.maximum(b[i,:,:2],b[j,:,:2]);hi=np.minimum(b[i,:,:2]+b[i,:,2:],b[j,:,:2]+b[j,:,2:])
        inter=np.maximum(hi-lo,0).prod(axis=1);area=b[i,:,2:].prod(axis=1)+b[j,:,2:].prod(axis=1)-inter
        mask &= inter/area>=.1
        edges=np.flatnonzero(np.diff(np.r_[False,mask,False].astype(int)))
        for first,stop in zip(edges[::2],edges[1::2]):
            before,after=first-1,stop
            if stop-first<3 or before<start-1 or after>end-1 or not(v[i,before] and v[j,before] and v[i,after] and v[j,after]):continue
            if (c[i,before,0]-c[j,before,0])*(c[i,after,0]-c[j,after,0])<0:
                found.append((other,before+1,after+1))
    return found


def exits(key,tid):
    ids,ix,b,v,c=raw(key);m=META[key];fs=np.flatnonzero(v[ix[tid]]);out=[]
    for n,left in enumerate(fs):
        right=fs[n+1] if n+1<len(fs) else m['frames']
        if (right-left-1)/m['fps']<=1:continue
        x,y,w,h=b[ix[tid],left]
        if min(x/m['width'],(m['width']-x-w)/m['width'],y/m['height'],(m['height']-y-h)/m['height'])<.02:
            out.append(int(left)+1)
    return out


def main():
    rows=read_jsonl(ROOT/'data/question_review_candidates_20.jsonl');checks=[]
    for q in rows:
        key=(q['dataset'],q['sequence']);m=META[key];ids,ix,b,v,c=raw(key)
        e=q['evidence'];g=e['gt_detail'];start=e['query_start_frame'];end=e['query_end_frame'];ts=e['target_ids'];op=q['operation_name']
        actual=q['options'][q['answer']]
        for r in q['reference']['persons']:
            assert v[ix[r['target_id']],r['frame']-1]
            assert end-r['frame']>=3*m['fps']
        if op=='O1':
            x=c[ix[ts[0]],end-1,0]/m['width'];expected=['left','center','right'][int(x>=1/3)+int(x>=2/3)]
            assert actual==expected and min(abs(x-1/3),abs(x-2/3))>.05
        elif op=='O2':
            expected='Person '+('A' if c[ix[ts[0]],end-1,0]<c[ix[ts[1]],end-1,0] else 'B')
            assert actual==expected
        elif op in ['O5','composition_motion_relation']:
            lengths=[]
            for t in ts:
                visible=v[ix[t],start-1:end];pos=c[ix[t],start-1:end]
                lengths.append(float(np.linalg.norm(np.diff(pos,axis=0),axis=1)[visible[:-1]&visible[1:]].sum()/math.hypot(m['width'],m['height'])))
            assert np.allclose(lengths,g['path_lengths_diagonals'],atol=1e-6)
            winner=int(np.argmax(lengths));role=chr(65+winner)
            if op=='O5':assert actual=='Person '+role
            else:
                other=1-winner;side='left' if c[ix[ts[winner]],end-1,0]<c[ix[ts[other]],end-1,0] else 'right'
                assert actual==f'{role} travels farther; {role} is {side} of '+chr(65+other)
        elif op=='O6':
            i,j=[ix[t] for t in ts];mins=[]
            for ff in np.array_split(np.arange(start-1,end),4):
                ff=ff[v[i,ff]&v[j,ff]];mins.append(np.linalg.norm(c[i,ff]-c[j,ff],axis=1).min()/math.hypot(m['width'],m['height']))
            assert np.allclose(mins,g['quarter_min_distances_diagonals'],atol=1e-6)
            f0,f1=g['time_bin_frames'][int(np.argmin(mins))]
            assert actual==f'{(f0-1)/m["fps"]:.3f}–{(f1-1)/m["fps"]:.3f} s'
        elif op=='O3':
            gap=g['gap'];left=gap['last_visible_frame'];right=gap['next_visible_frame'];i=ix[ts[0]]
            assert v[i,left-1] and v[i,right-1] and not v[i,left:right-1].any()
            assert actual==('Yes' if right<=end else 'No')
        elif op=='O7':
            count=sum(start<=f<=end for f in appearances(key,ts[0]))
            assert count<g['requested_ordinal'] and actual=='This never happens.'
        else:
            cross=crossings(key,ts[0],start,end)
            people={t for t,_,_ in cross}
            if op=='composition_cross_exit':
                people={t for t in people if any(start<=f<=end and any(t==other and after<f for other,_,after in cross) for f in exits(key,t))}
            assert people==set(g['counted_gt_ids'])
            assert actual==str(len(people)) if len(people)<3 else actual=='3 or more'
        checks.append({'qa_id':q['qa_id'],'original_GT_answer_verified':True})
    dump(OUT/'raw_gt_answer_audit.json',{'status':'PASSED','verified_questions':20,'method':'recompute from original released GT text; no use of unified NPZ for answer validation','checks':checks})
    print('ORIGINAL_GT_ANSWERS_VERIFIED',len(checks))


if __name__=='__main__':main()
