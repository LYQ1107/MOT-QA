"""Recompute candidate answers from the original released GT; no unified NPZ answers."""
import hashlib,json,math
from collections import Counter,defaultdict
from functools import lru_cache
from pathlib import Path
import numpy as np
from PIL import Image
from audit_question_review_gt import raw,crossings
import generate_candidates_round2 as g
R=g.ROOT;D=g.RES

@lru_cache(maxsize=1000)
def raw_cross(key,t):return sorted(crossings(key,t,1,g.META[key]['frames']),key=lambda e:e[2])
def cross_in(key,t,s,e):return [(u,a,b) for u,a,b in raw_cross(key,t) if a>=s and b<=e]
def edge(key,box):
 x,y,w,h=box;m=g.META[key]
 return min(x/m['width'],(m['width']-x-w)/m['width'],y/m['height'],(m['height']-y-h)/m['height'])<.02
@lru_cache(maxsize=1000)
def raw_gaps(key,t):
 ids,ix,b,v,c=raw(key);m=g.META[key];ff=np.flatnonzero(v[ix[t]]);out=[]
 for left,right in zip(ff[:-1],ff[1:]):
  d=(right-left-1)/m['fps']
  if d>1:out.append({'last':int(left)+1,'first_missing':int(left)+2,'return':int(right)+1,'duration':d,'edge':edge(key,b[ix[t],left])})
 return out

def returns(key,t,s,e):
 return [x for x in raw_gaps(key,t) if s<=x['return']<=e and (key[0]=='SportsMOT' or not x['edge'])]
def region(key,t,f):
 _,ix,b,v,c=raw(key);m=g.META[key];assert v[ix[t],f-1];x=c[ix[t],f-1,0]/m['width'];assert min(abs(x-1/3),abs(x-2/3))>.05
 return int(x>=1/3)+int(x>=2/3)
def geom_raw(key,t,f):
 ids,ix,b,v,c=raw(key);m=g.META[key];i=ix[t];assert v[i,f-1];bb=b[i,f-1];x,y,w,h=bb
 assert w>=16 and h>=48
 inside=max(0,min(x+w,m['width'])-max(x,0))*max(0,min(y+h,m['height'])-max(y,0))/(w*h);assert inside>=.95-1e-8
 others=b[:,f-1];inter=np.maximum(0,np.minimum(bb[:2]+bb[2:],others[:,:2]+others[:,2:])-np.maximum(bb[:2],others[:,:2])).prod(1);inter=np.nan_to_num(inter);inter[i]=0
 assert (inter/(w*h)).max()<=.35+1e-7
 iou=inter/(w*h+others[:,2]*others[:,3]-inter);assert np.nansum(iou>.3)<=1

def recompute(q):
 key=q['dataset'],q['sequence'];m=g.META[key];ids,ix,b,v,c=raw(key);e=q['evidence'];d=e['gt_detail'];s,fin=e['query_start_frame'],e['query_end_frame'];t=q['reference']['primary_target_id'];ts=[r['target_id'] for r in q['reference']['persons']];fam=q['template_id']
 for rr in q['reference']['persons']:
  geom_raw(key,rr['target_id'],rr['frame']);assert s-rr['frame']>=g.frames(key,5 if q['operation_name']=='O8' else 3)
  if rr['type']=='position':
   xx=np.sort(c[:,rr['frame']-1,0][v[:,rr['frame']-1]]);best,runner=(xx[-1],xx[-2]) if 'rightmost' in rr['text'] else (xx[0],xx[1]);assert g.geometric_margin(best,runner,m['width'])
  crop=Image.open(rr['zoom_crop']);native=(math.ceil(b[ix[rr['target_id']],rr['frame']-1,0]+b[ix[rr['target_id']],rr['frame']-1,2])-max(0,math.floor(b[ix[rr['target_id']],rr['frame']-1,0])),math.ceil(b[ix[rr['target_id']],rr['frame']-1,1]+b[ix[rr['target_id']],rr['frame']-1,3])-max(0,math.floor(b[ix[rr['target_id']],rr['frame']-1,1])))
  # Asset cropping clips right/bottom to actual frame dimensions.
  bx=b[ix[rr['target_id']],rr['frame']-1];ww=min(m['width'],math.ceil(bx[0]+bx[2]))-max(0,math.floor(bx[0]));hh=min(m['height'],math.ceil(bx[1]+bx[3]))-max(0,math.floor(bx[1]));assert crop.size==(3*ww,3*hh)
 assert all(s+g.frames(key,1)<=f<=fin-g.frames(key,1) for f in e['decisive_event_frames'])
 if 'time_bin_frames' in d:
  assert (fin-s)/m['fps']>=4 and min((z-a)/m['fps'] for a,z in d['time_bin_frames'])>=1
 if e.get('negative_extension_end_frame'):assert e['negative_extension_end_frame']-fin>=g.frames(key,2) and e['negative_extension_end_frame']<=m['eligible_source_window_1based'][1]
 raw_nc=len(cross_in(key,t,q['reference']['persons'][0]['frame'],fin))
 raw_occ=any(not z['edge'] and z['duration']>1.5 and z['last']>=q['reference']['persons'][0]['frame'] and z['return']<=fin for z in raw_gaps(key,t))
 assert raw_nc==q['difficulty']['n_crossings']
 if not(q['operation_name']=='O4' and key[0]=='MOT17'):assert q['difficulty']['identity_challenge']==bool(raw_nc or raw_occ)
 if fam=='region':expected=g.REG[region(key,t,fin)]
 elif fam=='left_pair':
  x,y=[c[ix[tt],fin-1,0] for tt in ts];assert g.geometric_margin(min(x,y),max(x,y),m['width']);expected='Person A' if x<y else 'Person B'
 elif fam=='return_time':
  gg=d['gap'];match=next(z for z in raw_gaps(key,t) if z['last']==gg['last_visible_frame'] and z['return']==gg['next_visible_frame']);assert match['duration']>=1.5
  re=match['return'];found=s<=re<=fin
  if not found:assert re>fin+g.frames(key,2)
  if q['format']=='numeric_time':expected=g.sec(key,re)
  else:
   k=next((i for i,(a,z) in enumerate(d['time_bin_frames']) if a<=re<=z),3);expected=g.time_values(key,d['time_bin_frames'],True)[k]
 elif fam in ['cross_count','entry_count']:
  if fam=='cross_count':people={u for u,a,z in cross_in(key,t,s,fin)}
  else:
   people=set()
   for tt in ids:
    ff=np.flatnonzero(v[ix[tt]])
    if len(ff) and ff[0]>0 and s<=ff[0]+1<=fin and edge(key,b[ix[tt],ff[0]]):people.add(tt)
  assert people==set(d['counted_gt_ids']);expected=len(people) if q['format']=='numeric_count' else str(len(people))
  if not people:
   assert not cross_in(key,t,s,fin+g.frames(key,2)) if fam=='cross_count' else all(not(fin<f+1<=fin+g.frames(key,2) and edge(key,b[ix[tt],f])) for tt in ids for f in np.flatnonzero(v[ix[tt]])[:1])
 elif fam in ['earlier_return_time','earliest_return_person']:
  rs=[returns(key,tt,s,fin) for tt in ts]
  assert all(z['duration']>=1.5 for rr in rs for z in rr)
  ff=[rr[0]['return'] if rr else None for rr in rs];actual=[f for f in ff if f is not None]
  if fam=='earlier_return_time':assert len(actual)==2;expected=g.sec(key,min(actual))
  else:expected='Person '+chr(65+ff.index(min(actual))) if actual else g.NEVER
 elif fam=='return_region':
  rr=returns(key,t,s,fin);ordinal=d['ordinal'];assert all(z['duration']>=1.5 for z in rr)
  if len(rr)>=ordinal:expected=g.REG[region(key,t,rr[ordinal-1]['return'])]
  else:
   assert len(returns(key,t,s,fin+g.frames(key,2)))<ordinal;expected=g.NEVER
 elif fam=='premise_return_time':
  rr=returns(key,t,s,fin);assert d['ordinal']==1 and all(z['duration']>=2 for z in rr)
  first=rr[0]['return'] if rr else None
  if first is None:assert not returns(key,t,s,fin+g.frames(key,2))
  k=next((i for i,(a,z) in enumerate(d['time_bin_frames']) if first is not None and a<=first<=z),3)
  expected=g.time_values(key,d['time_bin_frames'],True)[k]
 elif fam=='closest_time':
  mins=[];minimum=[];i,j=ix[ts[0]],ix[ts[1]]
  for a,z in d['time_bin_frames']:
   ff=np.arange(a-1,z);ff=ff[v[i,ff]&v[j,ff]];dd=np.linalg.norm(c[i,ff]-c[j,ff],axis=1);kk=int(dd.argmin());mins.append(float(dd[kk]));minimum.append(int(ff[kk]+1))
  winner=int(np.argmin(mins));assert np.allclose(mins,d['quarter_min_distances_px'],atol=1e-2);assert g.geometric_margin(min(mins),sorted(mins)[1],m['width']);expected=g.time_values(key,d['time_bin_frames'])[winner]
 elif fam=='cross_frequency':
  rr=[x for x in cross_in(key,t,s,fin) if x[0]==ts[1]]
  if not rr:assert not [x for x in cross_in(key,t,s,fin+g.frames(key,2)) if x[0]==ts[1]]
  expected=str(len(rr));assert len(rr)==d['crossing_frequency']
 elif fam=='cross_time':
  rr=[x for x in cross_in(key,t,s,fin) if x[0]==ts[1]]
  if rr:first=min(z for u,a,z in rr);k=next(i for i,(a,z) in enumerate(d['time_bin_frames']) if a<=first<=z)
  else:
   assert not [x for x in cross_in(key,t,s,fin+g.frames(key,2)) if x[0]==ts[1]];k=3
  expected=g.time_values(key,d['time_bin_frames'],True)[k]
 elif fam=='cross_region':
  rr=[x for x in cross_in(key,t,s,fin) if x[0]==ts[1]];f=min(z for u,a,z in rr);expected=g.REG[region(key,t,f)]
 elif fam=='cross_exit_count':
  rr=cross_in(key,t,s,fin);people=set()
  for u,a,after in rr:
   ff=np.flatnonzero(v[ix[u]])
   for k,left in enumerate(ff):
    right=ff[k+1] if k+1<len(ff) else m['frames'];duration=(right-left-1)/m['fps']
    if duration>1 and s<=left+1<=fin and after<left+1 and edge(key,b[ix[u],left]):
     assert duration>=1.5;people.add(u)
  assert people==set(d['counted_gt_ids']);expected=str(len(people))
 elif fam=='motion_relation_example_only':
  assert m['camera_motion']=='static';ll=[]
  for tt in ts:
   vv=v[ix[tt],s-1:fin];cc=c[ix[tt],s-1:fin];ll.append(float(np.linalg.norm(np.diff(cc,axis=0),axis=1)[vv[:-1]&vv[1:]].sum()))
  assert g.geometric_margin(max(ll),min(ll),m['width']);win=int(np.argmax(ll));side='left' if c[ix[ts[win]],fin-1,0]<c[ix[ts[1-win]],fin-1,0] else 'right';expected=f'{chr(65+win)} farther; {chr(65+win)} {side}'
 elif fam=='identity_same':
  assert fin-q['reference']['persons'][0]['frame']>=g.frames(key,5);u=d['marked_query_target'];geom_raw(key,u,fin);expected='Yes' if t==u else 'No'
  if t!=u:assert any(t in z['gt_ids'] and u in z['gt_ids'] and q['reference']['persons'][0]['frame']<=z['frame_start'] and z['frame_end']<=fin for z in g.OVERLAPS[key])
 elif fam=='identity_match':
  for u in d['candidate_gt_ids']:geom_raw(key,u,fin)
  expected=str(d['candidate_gt_ids'].index(t)+1)
 elif fam=='first_cross_crop':
  rr=cross_in(key,t,s,fin);first=min(rr,key=lambda z:z[2]);u=first[0];assert u==d['target_option_gt_id'];opts=d['crop_candidates']
  for z in opts:geom_raw(key,z['gt_id'],z['frame']);assert abs(z['frame']-first[2])>=g.frames(key,3)
  expected=q['raw_options'][next(i for i,z in enumerate(opts) if z['gt_id']==u)]
 else:raise ValueError(fam)
 actual=q['answer'] if q['format'].startswith('numeric') else q['options'][q['answer']]
 if isinstance(expected,(int,float)):assert abs(float(actual)-expected)<1e-6,(actual,expected)
 else:assert actual==expected,(actual,expected)
 if q['has_confusion_option']:verify_confusion(q)
 return {'qa_id':q['qa_id'],'raw_GT_recomputed_answer':expected,'status':'PASSED'}

def verify_confusion(q):
 key=q['dataset'],q['sequence'];m=g.META[key];e=q['evidence'];d=e['gt_detail'];co=e['confusion'];t=q['reference']['primary_target_id'];u=co['gt_id'];s,fin=e['query_start_frame'],e['query_end_frame'];fam=q['template_id'];ts=[r['target_id'] for r in q['reference']['persons']];expected=None
 if fam=='region':expected=g.REG[region(key,u,fin)]
 elif fam=='left_pair':expected='Person B' if q['semantic_answer']=='Person A' else 'Person A'
 elif fam=='return_time':
  matches=[z for z in raw_gaps(key,u) if abs(z['first_missing']-d['gap']['frame'])<=g.frames(key,1) and (key[0]=='SportsMOT' or not z['edge'])]
  z=min(matches,key=lambda z:abs(z['first_missing']-d['gap']['frame'])) if matches else None
  f=z['return'] if z else None;k=next((i for i,(a,b) in enumerate(d['time_bin_frames']) if f is not None and a<=f<=b),3);expected=g.time_values(key,d['time_bin_frames'],True)[k]
 elif fam=='cross_count':expected=str(len({a for a,b,c in cross_in(key,u,s,fin)}))
 elif fam=='earliest_return_person':expected='Person B' if q['semantic_answer']=='Person A' else 'Person A'
 elif fam=='return_region':
  rr=returns(key,u,s,fin);expected=g.REG[region(key,u,rr[d['ordinal']-1]['return'])] if len(rr)>=d['ordinal'] else g.NEVER
 elif fam=='premise_return_time':
  rr=returns(key,u,s,fin);first=rr[0]['return'] if rr else None
  k=next((i for i,(a,z) in enumerate(d['time_bin_frames']) if first is not None and a<=first<=z),3)
  expected=g.time_values(key,d['time_bin_frames'],True)[k]
 elif fam in ['cross_time','cross_frequency']:
  rr=[z for z in cross_in(key,u,s,fin) if z[0]==ts[1]]
  if fam=='cross_frequency':expected=str(len(rr))
  else:
   f=min((z[2] for z in rr),default=None);k=next((i for i,(a,b) in enumerate(d['time_bin_frames']) if f is not None and a<=f<=b),3);expected=g.time_values(key,d['time_bin_frames'],True)[k]
 elif fam=='closest_time':
  _,ix,b,v,c=raw(key);mins=[]
  for a,z in d['time_bin_frames']:
   ff=np.arange(a-1,z);ff=ff[v[ix[u],ff]&v[ix[ts[1]],ff]];mins.append(float(np.linalg.norm(c[ix[u],ff]-c[ix[ts[1]],ff],axis=1).min()))
  expected=g.time_values(key,d['time_bin_frames'])[int(np.argmin(mins))]
 elif fam=='cross_region':expected=g.REG[region(key,ts[1],d['first_cross_frame'])]
 elif fam=='identity_same':expected='Yes' if u==d['marked_query_target'] else 'No'
 elif fam=='identity_match':expected=str(d['candidate_gt_ids'].index(u)+1)
 elif fam=='first_cross_crop':
  rr=cross_in(key,u,s,fin);person=min(rr,key=lambda z:z[2])[0];assert person==co['target_option_gt_id'];k=next(i for i,c in enumerate(d['crop_candidates']) if c['gt_id']==person);expected=q['raw_options'][k]
 elif fam=='motion_relation_example_only':expected=co['semantic_answer'] # Example only; formal candidates exclude this subtype.
 else:raise ValueError('Counterfactual not implemented: '+fam)
 assert expected==co['semantic_answer'],('confusion',fam,expected,co['semantic_answer'])
 assert expected!=q['semantic_answer'] and expected in [v for k,v in q['options'].items() if q['option_provenance'][k]=='identity_confusion']

def main():
 allchecks=[];failures=[]
 for rel in ['data/candidates.jsonl','data/precheck_round2_20.jsonl']:
  qs=g.rows(R/rel)
  for q in qs:
   try:allchecks.append(recompute(q))
   except Exception as ex:failures.append({'qa_id':q['qa_id'],'pool_id':q['pool_id'],'template':q['template_id'],'error':repr(ex)})
  print('AUDITED',rel,len(qs),'failures',len(failures),flush=True)
 g.dump(D/'raw_gt_answer_audit.json',{'status':'FAILED' if failures else 'PASSED','verified':len(allchecks),'failures':failures,'method':'Independent re-derivation from original released GT text; exact answer and hard-margin/ref-image checks; no evaluated model','checks':allchecks})
 if failures:raise RuntimeError(f'{len(failures)} raw-GT audit failures; no filtering/inference may start')
 assert len(allchecks)==920
 # Dataset-wide hard quotas on formal candidates; examples never counted.
 qs=g.rows(R/'data/candidates.jsonl');N=len(qs);primary=Counter((q['dataset'],q['sequence'],q['reference']['primary_target_id']) for q in qs);videos=Counter((q['dataset'],q['sequence']) for q in qs)
 assert N==900 and max(primary.values())<=3 and max(videos.values())<=20
 assert sum(q['difficulty']['identity_challenge'] for q in qs)>=.6*N
 assert sum(q['format'].startswith('numeric') for q in qs)==180
 binary=sum(q['format']=='multiple_choice' and len(q['options'])==2 for q in qs);assert binary<=.25*N
 choices=[q for q in qs if q['format']=='multiple_choice'];assert sum(q['has_confusion_option'] for q in choices)>=.7*len(choices)
 o7=[q for q in qs if q['operation_name']=='O7'];assert sum(q['evidence']['gt_detail']['event_exists'] for q in o7)*2==len(o7)
 print('FORMAL_HARD_QUOTAS_PASSED',N,flush=True)
if __name__=='__main__':main()
