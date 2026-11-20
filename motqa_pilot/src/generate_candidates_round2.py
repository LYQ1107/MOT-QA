"""Deterministic GT-only candidate pool under the user's second-round rules.

No evaluated VLM or tracker is run. Choice order is assigned after selection.
"""
import argparse, copy, hashlib, json, math, random, time
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
import numpy as np
from generate_question_review import ROOT, META, EVENTS, OVERLAPS, scene, good_box, make_ref, path_length

RES=ROOT/'results/stage3_round2'; RES.mkdir(parents=True,exist_ok=True)
CFG=json.loads((ROOT/'results/generation_config_locked.json').read_text())
TEMPLATES=json.loads((ROOT/'results/templates_locked.json').read_text())['templates']
RNG=random.Random(42)
REG=['left','center','right']; REGZH=['左侧','中间','右侧']; NEVER='This never happens.'

def dump(p,x): p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def rows(p): return [json.loads(s) for s in p.read_text().splitlines() if s]
def putrows(p,a): p.parent.mkdir(parents=True,exist_ok=True);p.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in a))
def sec(key,f): return (int(f)-1)/META[key]['fps']
def fmt(key,f): return f'{sec(key,f):.3f}'
def frames(key,s): return int(math.ceil(s*META[key]['fps']-1e-8))

def geometric_margin(x,y,w):
 gap=abs(float(x)-float(y));return gap>=.05*w and gap>=.2*max(abs(float(y)),1e-9)

@lru_cache(maxsize=300000)
def geom(key,t,f):
 m=META[key]
 return bool(m['eligible_source_window_1based'][0]<=f<=m['eligible_source_window_1based'][1] and good_box(key,t,f))

@lru_cache(maxsize=10)
def events_index(key):
 gap=defaultdict(list);ret=defaultdict(list);entry=[];cross=defaultdict(list);overlap=defaultdict(list)
 for e in EVENTS[key]:
  if e['type'] in ['becomes_occluded','leaves_frame']:
   gap[e['gt_id']].append(e)
  elif e['type']=='reappears':ret[e['gt_id']].append(e)
  elif e['type']=='enters_frame':entry.append(e)
 for e in OVERLAPS[key]:
  for t in e['gt_ids']:overlap[t].append(e)
  if e['crossing_status']=='crossed' and e['crossing_eligible_source']:
   for t in e['gt_ids']:cross[t].append(e)
 for d in [gap,ret,cross,overlap]:
  for t in d:d[t].sort(key=lambda e:e.get('frame') or e.get('after_frame') or e.get('frame_start') or 0)
 return gap,ret,entry,cross,overlap

def relevant_returns(key,t,s,e,allow_edge=False):
 gaps,ret,_,_,_=events_index(key);out=[]
 for x in ret[t]:
  if not s<=x['frame']<=e:continue
  g=next((g for g in gaps[t] if g.get('next_visible_frame')==x['frame']),None)
  if g is None:continue
  # Preserve conservative publisher identity scope for Dance/MOT.
  if key[0] in ['DanceTrack','MOT17'] and g['type']!='becomes_occluded':continue
  out.append((x,g))
 return out

def event_margin(key,fs,fe,event_frames):
 n=frames(key,1)
 return all(fs+n<=int(f)<=fe-n for f in event_frames)

def valid_returns(key,t,fs,fe):
 rr=relevant_returns(key,t,fs,fe)
 if any(g['invisible_duration_s']<1.5 or not event_margin(key,fs,fe,[e['frame']]) for e,g in rr):return None
 return rr

def crossing_set(key,t,fs,fe):
 _,_,_,cross,_=events_index(key)
 es=[e for e in cross[t] if e['before_frame']>=fs and e['after_frame']<=fe]
 if not event_margin(key,fs,fe,[e['after_frame'] for e in es]):return None
 return es

def conf_partners(key,t,rf,fe):
 *_,overlap=events_index(key);cc=Counter()
 for e in overlap[t]:
  if rf<=e['frame_start'] and e['frame_end']<=fe:
   cc[next(x for x in e['gt_ids'] if x!=t)]+=e['frames']
 return cc

def make_reference(key,t,f,kind,resource=None):
 if not geom(key,t,f):return None
 rr=make_ref(key,t,f,kind,resource)
 if rr:
  rr['geometric_gate_pass']=True
  rr['anchor_frame']=f
  if kind=='event':rr['event_time_s']=resource['event']['time_s']
 return rr

def reference_pool(key):
 m=META[key];a=scene(key);lo,hi=m['eligible_source_window_1based'];fps=m['fps'];pool=[]
 for x in RESOURCES[key]:
  if x['ref_type']=='appearance':continue
  t=int(x['target_ids'][0]);kind=x['ref_type'];f=x['reference_frame'];resource=copy.deepcopy(x)
  if kind=='event':
   ev=x['event']
   if ev.get('invisible_duration_s',2)<1.5:continue
   if ev['type'] in ['leaves_frame','becomes_occluded']:
    # Last fully usable view in the same final contiguous visible run.
    f=ev['last_visible_frame']
    while f>=lo and a['visible'][a['axis'][t],f-1] and not geom(key,t,f):f-=1
   elif not geom(key,t,f):
    limit=min(hi,f+frames(key,2));f=next((z for z in range(f,limit+1) if geom(key,t,z)),f)
  elif not geom(key,t,f):
   # Position descriptions name the exact displayed instant; do not silently move anchors.
   continue
  rr=make_reference(key,t,f,kind,resource)
  if rr and hi-max(f,int(round(rr.get('event_time_s',rr['t_ref_s'])*fps))+1)>=frames(key,5):pool.append(rr)
 for x in APPROVED[key]:
  rr=make_reference(key,int(x['gt_id']),int(x['reference_frame']),'appearance',x)
  if rr:pool.append(rr)
 # Native GT-based box references: regular anchors plus anchors before hard events.
 anchors=defaultdict(set)
 for t in a['gt_ids']:
  t=int(t);i=a['axis'][t]
  for f in range(lo,hi-frames(key,7),max(1,frames(key,3))):
   if a['visible'][i,f-1]:anchors[t].add(f)
 for e in OVERLAPS[key]:
  if e['before_frame'] is not None:
   for t in e['gt_ids']:
    for dt in [4,7]:anchors[t].add(e['before_frame']-frames(key,dt))
 for e in EVENTS[key]:
  if e['type'] in ['becomes_occluded','leaves_frame']:
   for dt in [5,8,12]:anchors[e['gt_id']].add(e['frame']-frames(key,dt))
 for t,fs in anchors.items():
  usable=[f for f in sorted(fs) if lo<=f<=hi-frames(key,7) and geom(key,t,f)]
  if len(usable)>25:usable=sorted(RNG.sample(usable,25))
  for f in usable:pool.append(make_reference(key,t,f,'box'))
 dedup={ (r['target_id'],r['frame'],r['type'],r.get('source_reference_id')):r for r in pool if r }
 out=list(dedup.values());RNG.shuffle(out);return out

def new_fact(key,ref,op,template,fs,fe,persons,values,answer,detail,decisive=None,conf=None,format='multiple_choice',numeric=None,negative=False):
 m=META[key];t=ref['target_id'];a=scene(key);high=m['eligible_source_window_1based'][1]
 anchors=[max(r['frame'],int(round(r.get('event_time_s',r['t_ref_s'])*m['fps']))+1) for r in persons]
 minsep=5 if op=='O8' else 3
 if fs<max(anchors)+frames(key,minsep) or fe>high or fe<fs:return None
 decisive=decisive or []
 if not event_margin(key,fs,fe,decisive):return None
 if negative and fe+frames(key,2)>high:return None
 _,_,_,cross,_=events_index(key)
 nc=sum(ref['frame']<=e['before_frame'] and e['after_frame']<=fe for e in cross[t])
 gaps=events_index(key)[0][t]
 occ=[e for e in gaps if e['type']=='becomes_occluded' and e['invisible_duration_s']>1.5 and e['last_visible_frame']>=ref['frame'] and e.get('next_visible_frame') and e['next_visible_frame']<=fe]
 vv=a['visible'][a['axis'][t],ref['frame']-1:fe]
 z=np.flatnonzero(np.diff(np.r_[False,~vv,False].astype(np.int8)))
 mg=float(max((z[1::2]-z[::2])/m['fps'],default=0))
 context=dict(start=fmt(key,fs),end=fmt(key,fe),gap=f'{detail.get("gap_time_s",0):.3f}',ordinal=['','first','second','third'][min(detail.get('ordinal',1),3)])
 variant=RNG.randrange(5);wording=TEMPLATES[template][variant]
 question=wording['text'].format(**context)
 if format=='numeric_time':question+=' Answer with a timestamp in seconds.'
 if format=='numeric_count':question+=' Answer with the exact integer count.'
 rr=copy.deepcopy(persons)
 for role,r in zip('ABCDEF',rr):r['role']=role
 ids=[r['target_id'] for r in rr]
 hard=bool(nc or occ)
 f={'dataset':key[0],'sequence':key[1],'source_split':m['source_split'],'fps':m['fps'],'video_duration_s':m['frames']/m['fps'],
  'question':question,'template_id':template,'paraphrase_id':variant,'paraphrase_split':wording['paraphrase_split'],
  'format':format,'raw_options':values,'semantic_answer':str(numeric) if format.startswith('numeric') else values[answer],
  'answer_index':answer,'numeric_answer':numeric,'answer_tolerance':.5 if format=='numeric_time' else 0,
  'operation_name':op,'operations':{'composition_cross_exit':['O6','O4'],'composition_cross_region':['O6','O1'],'composition_motion':['O5','O2']}.get(detail.get('composition_subtype'),[op]),
  'split_role':'held_out_composition' if op=='composition' else 'regular',
  'reference':{'type':ref['type'],'persons':rr,'target_ids':ids,'primary_target_id':t,'t_ref_s':ref['t_ref_s']},
  'evidence':{'gt_ids':ids,'primary_target_id':t,'source_window_1based':m['eligible_source_window_1based'],
   'query_start_frame':fs,'query_end_frame':fe,'time_spans_s':[[sec(key,fs),sec(key,fe)]],
   'keyframes_1based':sorted(set([r['frame'] for r in rr]+[fs,fe]+decisive)),
   'decisive_event_frames':decisive,'negative_extension_end_frame':fe+frames(key,2) if negative else None,
   'role_mapping':{str(t):c for t,c in zip(ids,'ABCDEF')},'gt_detail':detail,'confusion':conf},
  'has_confusion_option':bool(conf) and format=='multiple_choice',
  'difficulty':{'n_crossings':int(nc),'max_gap_s':mg,'density':float(a['visible'][:,ref['frame']-1:fe].sum(0).mean()),
   'appearance_similarity':None,'identity_challenge':hard,'identity_challenge_evidence':{'crossing_count':int(nc),'internal_gaps_gt1_5s':len(occ)},
   'needs_visual_grounding':ref['type']!='position','camera_motion':m['camera_motion']},
  'identity_risk':False,'license_registry':'logs/licenses.md','source_gt_sha256':m['source_gt_sha256'],'unified_gt_sha256':m['npz_sha256']}
 if op=='O4' and key[0]=='MOT17':f['identity_scope']='within_id';f['difficulty']['identity_challenge']=False
 return f

def numbered_bins(key,fs,fe,n=4):
 edges=np.linspace(fs,fe+1,n+1).astype(int)
 if sec(key,fe)-sec(key,fs)<4 or min(np.diff(edges))/META[key]['fps']<1:return None
 return [[int(edges[k]),int(edges[k+1]-1)] for k in range(n)]

def time_values(key,bins,never=False):
 v=[f'{fmt(key,s)}–{fmt(key,e)} s' for s,e in bins]
 return v+([NEVER] if never else [])

def count_choices(n,conf=None):
 low=max(0,n-1)
 if conf is not None:
  low=max(0,min(n,conf)-1)
  if max(n,conf)>low+3:conf=None;low=max(0,n-1)
 return [str(x) for x in range(low,low+4)]

def secondary(key,t,f):return make_reference(key,t,f,'box')

def facts_for_ref(key,ref):
 m=META[key];a=scene(key);t=ref['target_id'];rf=ref['frame'];i=a['axis'][t];lo,hi=m['eligible_source_window_1based'];fps=m['fps']
 gap,ret,entries,cross,ov=events_index(key)
 start=max(rf,int(round(ref.get('event_time_s',ref['t_ref_s'])*fps))+1)+frames(key,3)
 if start+frames(key,4)>hi:return []
 windows=[]
 for d in [6,10,16,24]:
  end=start+frames(key,d)
  if end<=hi:windows.append((start,end))
 # Align intervals with events, always leaving >=1s margins.
 for e in gap[t]:
  if e['invisible_duration_s']<1.5 or not e.get('next_visible_frame'):continue
  s=e['frame']-frames(key,2)
  for end in [e['next_visible_frame']+frames(key,2),e['next_visible_frame']-frames(key,3)]:
   if s>=start and end-s>=frames(key,4) and end<=hi:windows.append((s,end))
 for e in cross[t][:]:
  if e['before_frame']>=start+frames(key,2):
   s=e['before_frame']-frames(key,2);e2=min(hi,e['after_frame']+frames(key,6))
   if e2-s>=frames(key,4):windows.append((s,e2))
 RNG.shuffle(windows);windows=list(dict.fromkeys(windows))[:9]
 result=[]
 def add(*args,**kwargs):
  f=new_fact(key,ref,*args,**kwargs)
  if f:result.append(f)
 def atregion(x,f):return int(a['region'][a['axis'][x],f-1])
 for fs,fe in windows:
  partner=conf_partners(key,t,rf,fe)
  ve=[int(x) for x in a['gt_ids'] if a['visible'][a['axis'][int(x)],fe-1]]
  pointstart=max(start,fe-frames(key,4))
  rg=atregion(t,fe)
  if rg>=0:
   co=next((x for x,_ in partner.most_common() if atregion(x,fe)>=0 and atregion(x,fe)!=rg),None)
   add('O1','region',pointstart,fe,[ref],REG,rg,{'region_index':rg,'point_query':True},conf={'gt_id':co,'semantic_answer':REG[atregion(co,fe)]} if co is not None else None)
  others=[x for x in ve if x!=t and geom(key,x,rf)]
  others.sort(key=lambda x:-partner[x])
  for other in others[:5]:
   j=a['axis'][other];r2=secondary(key,other,rf)
   if r2 is None:continue
   x1,x2=[float(a['centers'][k,fe-1,0]) for k in [i,j]]
   if a['visible'][i,fe-1] and geometric_margin(min(x1,x2),max(x1,x2),m['width']):
    ans=0 if x1<x2 else 1
    add('O2','left_pair',pointstart,fe,[ref,r2],['Person A','Person B'],ans,{'point_query':True,'x_centers_px':[x1,x2],'relative_margin':abs(x1-x2)/max(x1,x2),'absolute_margin_width':abs(x1-x2)/m['width']},conf={'gt_id':other,'semantic_answer':['Person A','Person B'][1-ans]} if partner[other] else None)
   bins=numbered_bins(key,fs,fe)
   if bins:
    mins=[];minframes=[]
    for s,e in bins:
     ff=np.arange(s-1,e);vv=a['visible'][i,ff]&a['visible'][j,ff]
     if not vv.any():break
     ff=ff[vv];dd=np.linalg.norm(a['centers'][i,ff]-a['centers'][j,ff],axis=1);k=int(dd.argmin())
     mins.append(float(dd[k]));minframes.append(int(ff[k]+1))
    if len(mins)==4:
     ix=int(np.argmin(mins));best=mins[ix];runner=sorted(mins)[1]
     if geometric_margin(best,runner,m['width']) and event_margin(key,fs,fe,[minframes[ix]]):
      conf=None
      for u,_ in partner.most_common():
       if u==other:continue
       ui=a['axis'][u];mm=[]
       for s,e in bins:
        ff=np.arange(s-1,e);vv=a['visible'][ui,ff]&a['visible'][j,ff]
        if not vv.any():break
        dd=np.linalg.norm(a['centers'][ui,ff[vv]]-a['centers'][j,ff[vv]],axis=1);mm.append(float(dd.min()))
       if len(mm)==4 and int(np.argmin(mm))!=ix:
        conf={'gt_id':u,'semantic_answer':time_values(key,bins)[int(np.argmin(mm))]};break
      add('O6','closest_time',fs,fe,[ref,r2],time_values(key,bins),ix,{'time_bin_frames':bins,'quarter_min_distances_px':mins,'closest_frame':minframes[ix],'relative_margin':(runner-best)/max(runner,1e-9),'absolute_margin_width':(runner-best)/m['width']},decisive=[minframes[ix]],conf=conf)
   # Crossing time, including an ordinary nonexistent event outcome.
   bins3=numbered_bins(key,fs,fe,3)
   es=[e for e in cross[t] if set(e['gt_ids'])=={t,other} and e['before_frame']>=fs and e['after_frame']<=fe]
   if bins3 and (not es or event_margin(key,fs,fe,[es[0]['after_frame']])):
    future=[e for e in cross[t] if set(e['gt_ids'])=={t,other} and fe<e['after_frame']<=fe+frames(key,2)]
    if es or (not future and fe+frames(key,2)<=hi):
     ans=next((k for k,(s,e) in enumerate(bins3) if s<=es[0]['after_frame']<=e),3) if es else 3
     conf=None
     for u,_ in partner.most_common():
      ue=[e for e in cross[u] if set(e['gt_ids'])=={u,other} and e['before_frame']>=fs and e['after_frame']<=fe]
      ua=next((k for k,(s,e) in enumerate(bins3) if s<=ue[0]['after_frame']<=e),3) if ue else 3
      if ua!=ans:conf={'gt_id':u,'semantic_answer':time_values(key,bins3,True)[ua]};break
     add('O6','cross_time',fs,fe,[ref,r2],time_values(key,bins3,True),ans,{'time_bin_frames':bins3,'first_cross_frame':es[0]['after_frame'] if es else None},decisive=[es[0]['after_frame']] if es else [],conf=conf,negative=not es)
   # Composition: first crossing -> region of A (not an ordinary template).
   if es and event_margin(key,fs,fe,[es[0]['after_frame']]):
    e=es[0];rg2=atregion(t,e['after_frame'])
    if rg2>=0:
     add('composition','cross_region',fs,fe,[ref,r2],REG,rg2,{'composition_subtype':'composition_cross_region','first_cross_frame':e['after_frame'],'region_index':rg2},decisive=[e['after_frame']],conf={'gt_id':other,'semantic_answer':REG[atregion(other,e['after_frame'])]} if atregion(other,e['after_frame'])>=0 and atregion(other,e['after_frame'])!=rg2 else None)
   if m['camera_motion']=='static' and a['visible'][i,fe-1]:
    lengths=[path_length(a,x,fs,fe,1) for x in [t,other]]
    if geometric_margin(max(lengths),min(lengths),m['width']) and geometric_margin(min(x1,x2),max(x1,x2),m['width']):
     winner=int(np.argmax(lengths));left=x1<x2 if winner==0 else x2<x1;ans=2*winner+(0 if left else 1)
     add('composition','motion_relation_example_only',fs,fe,[ref,r2],['A farther; A left','A farther; A right','B farther; B left','B farther; B right'],ans,{'composition_subtype':'composition_motion','example_only':True,'path_lengths_px':lengths,'x_centers_px':[x1,x2]},conf={'gt_id':other,'semantic_answer':['A farther; A left','A farther; A right','B farther; B left','B farther; B right'][2*(1-winner)+(0 if left else 1)]} if partner[other] else None)
  # Count distinct crossing partners, or conservative MOT first-entry identities.
  if key[0]=='MOT17':
   es=[e for e in entries if fs<=e['frame']<=fe]
   exits=[e for gs in gap.values() for e in gs if e['type']=='leaves_frame' and fs<=e['frame']<=fe]
   # Exclude windows with exit/return ambiguity, as frozen previously.
   count_ok=not exits and event_margin(key,fs,fe,[e['frame'] for e in es])
   counted={e['gt_id'] for e in es};fam='entry_count';ef=[e['frame'] for e in es]
   future=[e for e in entries if fe<e['frame']<=fe+frames(key,2)]
  else:
   es=crossing_set(key,t,fs,fe);count_ok=es is not None;counted={next(x for x in e['gt_ids'] if x!=t) for e in es or []};fam='cross_count';ef=[e['after_frame'] for e in es or []]
   future=[e for e in cross[t] if fe<e['after_frame']<=fe+frames(key,2)]
  if count_ok and (counted or (not future and fe+frames(key,2)<=hi)):
   n=len(counted);cv=None;co=None
   if key[0]!='MOT17':
    for u,_ in partner.most_common():
     ue=crossing_set(key,u,fs,fe)
     if ue is not None:
      un=len({next(x for x in e['gt_ids'] if x!=u) for e in ue})
      if un!=n and abs(un-n)<=3:cv=un;co=u;break
   vals=count_choices(n,cv);detail={'count':n,'counted_gt_ids':sorted(counted),'count_kind':'first_edge_entry' if key[0]=='MOT17' else 'unique_crossing_people'}
   conf={'gt_id':co,'semantic_answer':str(cv)} if cv is not None and str(cv) in vals else None
   for form in ['multiple_choice','numeric_count']:
    add('O4',fam,fs,fe,[ref],vals,vals.index(str(n)),detail,decisive=ef,conf=conf,format=form,numeric=n,negative=n==0)
   if key[0]!='MOT17' and es:
    selected=set();exitfs=[];allcross=defaultdict(list)
    for e in es:allcross[next(x for x in e['gt_ids'] if x!=t)].append(e)
    bad=False
    for u in counted:
     exits=[g for g in gap[u] if g['type']=='leaves_frame' and g['invisible_duration_s']>=1.5 and fs<=g['last_visible_frame']<=fe and any(e['after_frame']<g['last_visible_frame'] for e in allcross[u])]
     if not event_margin(key,fs,fe,[g['last_visible_frame'] for g in exits]):bad=True
     if exits:selected.add(u);exitfs += [g['last_visible_frame'] for g in exits]
    if not bad:
     nn=len(selected);vals2=count_choices(nn)
     add('composition','cross_exit_count',fs,fe,[ref],vals2,vals2.index(str(nn)),{'composition_subtype':'composition_cross_exit','count':nn,'counted_gt_ids':sorted(selected),'crossed_gt_ids':sorted(counted)},decisive=ef+exitfs,negative=nn==0)
  # O3: question anchored to a particular visibility gap.
  for g in gap[t]:
   if g['invisible_duration_s']<1.5 or not g.get('next_visible_frame'):continue
   if key[0] in ['MOT17','DanceTrack'] and g['type']!='becomes_occluded':continue
   if not event_margin(key,fs,fe,[g['frame']]):continue
   rf2=g['next_visible_frame'];positive=fs<=rf2<=fe
   if positive and not event_margin(key,fs,fe,[rf2]):continue
   if not positive and (rf2<=fe+frames(key,2) or fe+frames(key,2)>hi):continue
   bins=numbered_bins(key,fs,fe,3)
   if not bins:continue
   ix=next((j for j,(s,e) in enumerate(bins) if s<=rf2<=e),3)
   detail={'gap_time_s':g['time_s'],'gap':g,'return_frame':rf2 if positive else None,'time_bin_frames':bins,'event_exists':positive}
   conf=None
   for u,_ in partner.most_common():
    ur=relevant_returns(key,u,fs,fe);ui=next((j for j,(s,e) in enumerate(bins) if ur and s<=ur[0][0]['frame']<=e),3)
    if ui!=ix:conf={'gt_id':u,'semantic_answer':time_values(key,bins,True)[ui]};break
   add('O3','return_time',fs,fe,[ref],time_values(key,bins,True),ix,detail,decisive=[g['frame']]+([rf2] if positive else []),conf=conf,negative=not positive)
   if positive:add('O3','return_time',fs,fe,[ref],[],0,detail,decisive=[g['frame'],rf2],format='numeric_time',numeric=sec(key,rf2))
  rr=valid_returns(key,t,fs,fe)
  if rr is None:continue
  # O7: both real and nonexistent presupposed returns.
  for ordinal in [1,2]:
   exists=len(rr)>=ordinal
   if exists:
    ev,g=rr[ordinal-1];rg3=atregion(t,ev['frame'])
    if rg3<0:continue
    ix=rg3;dec=[ev['frame']]
   else:
    future=relevant_returns(key,t,fe+1,min(hi,fe+frames(key,2)))
    if fe+frames(key,2)>hi or len(rr)+len(future)>=ordinal:continue
    ix=3;dec=[]
   conf=None
   for u,_ in partner.most_common():
    ur=relevant_returns(key,u,fs,fe);ui=atregion(u,ur[ordinal-1][0]['frame']) if len(ur)>=ordinal else 3
    if ui>=0 and ui!=ix:conf={'gt_id':u,'semantic_answer':(REG+[NEVER])[ui]};break
   add('O7','return_region',fs,fe,[ref],REG+[NEVER],ix,{'ordinal':ordinal,'event_exists':exists,'reappearance_frames':[e['frame'] for e,g in rr]},decisive=dec,conf=conf,negative=not exists)
  # O5: two first returns -> exact earlier timestamp.
  if rr:
   for u,_ in partner.most_common():
    if u==t or not geom(key,u,rf):continue
    ur=valid_returns(key,u,fs,fe)
    if not ur or abs(rr[0][0]['frame']-ur[0][0]['frame'])<frames(key,1):continue
    r2=secondary(key,u,rf)
    if r2:
     earlier=min(rr[0][0]['frame'],ur[0][0]['frame'])
     add('O5','earlier_return_time',fs,fe,[ref,r2],[],0,{'first_return_frames':{'A':rr[0][0]['frame'],'B':ur[0][0]['frame']}},decisive=[rr[0][0]['frame'],ur[0][0]['frame']],format='numeric_time',numeric=sec(key,earlier));break
  # O5 MC: choose among three people, including a never-return outcome.
  candidates=[u for u in a['gt_ids'] if int(u)!=t and geom(key,int(u),rf)]
  candidates=sorted(map(int,candidates),key=lambda u:-partner[u])[:6]
  if len(candidates)>=2:
   u,v=candidates[:2];ur=valid_returns(key,u,fs,fe);vr=valid_returns(key,v,fs,fe)
   if ur is not None and vr is not None:
    rrall=[rr,ur,vr];rs=[z[0][0]['frame'] if z else None for z in rrall];ts=[x for x in rs if x is not None]
    marginok=len(ts)<2 or sorted(ts)[1]-min(ts)>=frames(key,1)
    future=any(relevant_returns(key,x,fe+1,min(hi,fe+frames(key,2))) for x in [t,u,v])
    if marginok and (ts or (not future and fe+frames(key,2)<=hi)):
     ix=rs.index(min(ts)) if ts else 3;vals=['Person A','Person B','Person C',NEVER]
     conf={'gt_id':u,'semantic_answer':vals[1 if ix==0 else 0]} if partner[u] and ix in [0,1] else None
     add('O5','earliest_return_person',fs,fe,[ref,secondary(key,u,rf),secondary(key,v,rf)],vals,ix,{'first_return_frames':rs},decisive=ts,conf=conf,negative=not ts)
  # O8 only box reference, query>=5s, genuine interaction distractor.
  if ref['type']=='box' and fe-rf>=frames(key,5) and geom(key,t,fe):
   good=[x for x in ve if geom(key,x,fe)];confids=[x for x in good if x!=t and partner[x]]
   if confids:
    u=confids[0]
    for yes in [True,False]:
     b=t if yes else u;rb=secondary(key,b,fe)
     # new_fact handles the primary ref, not the query marker as a second prior ref.
     add('O8','identity_same',fe-frames(key,1),fe,[ref],['No','Yes'],int(yes),{'subtype':'same_person_yes_no','marked_query_target':b,'query_marker':rb,'event_exists':yes},conf={'gt_id':u,'semantic_answer':'No' if yes else 'Yes'})
    if len(good)>=4:
     add('O8','identity_match',fe-frames(key,1),fe,[ref],['1','2','3','4'],0,{'subtype':'numbered_box_match','candidate_pool_ids':good,'mandatory_confusion_id':u,'candidate_gt_ids':[t,u]+[x for x in good if x not in [t,u]][:2]},conf={'gt_id':u,'semantic_answer':'2'})
 return result

RESOURCES=defaultdict(list);APPROVED=defaultdict(list)
for x in rows(ROOT/'results/stage2/reference_resources.jsonl'):RESOURCES[(x['dataset'],x['sequence'])].append(x)
for x in rows(ROOT/'results/review/appearance_reference_pool_user_verified.jsonl'):APPROVED[(x['dataset'],x['sequence'])].append(x)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--only',default='');args=ap.parse_args();allrows=[];counts=[]
 keys=[key for key,m in META.items() if m['eligible_source_window_1based'] and (not args.only or key[1]==args.only)]
 for key in keys:
  file=RES/'pool_by_video'/f'{key[0]}__{key[1]}.jsonl';file.parent.mkdir(parents=True,exist_ok=True)
  if file.exists():
   result=rows(file);allrows.extend(result);continue
  refs=reference_pool(key)
  # Keep type/identity diversity; box anchors should not swamp reviewed appearance anchors.
  bytype=defaultdict(list)
  for rr in refs:bytype[rr['type']].append(rr)
  selected=[]
  for kind,lim in [('appearance',100),('event',70),('position',90),('box',180)]:
   rs=bytype[kind]
   if len(rs)>lim:rs=RNG.sample(rs,lim)
   selected.extend(rs)
  result=[]
  for rr in selected:result.extend(facts_for_ref(key,rr))
  unique={}
  for q in result:
   # Different paraphrases of the same factual query do not create more questions.
   sig=(q['template_id'],q['format'],q['reference']['type'],tuple(q['reference']['target_ids']),q['reference']['persons'][0]['frame'],q['evidence']['query_start_frame'],q['evidence']['query_end_frame'],q['semantic_answer'],q['evidence']['gt_detail'].get('ordinal'))
   unique.setdefault(sig,q)
  result=list(unique.values());rng=random.Random(42+int(hashlib.sha256(str(key).encode()).hexdigest()[:8],16));rng.shuffle(result)
  # Limit identical stratum dominance without removing primary identity diversity.
  groups=defaultdict(list)
  for q in result:groups[(q['operation_name'],q['format'],q['reference']['type'],q['semantic_answer'] if q['operation_name'] in ['O1','O2','O7'] else str(q['evidence']['gt_detail'].get('subtype','')))].append(q)
  kept=[]
  for g,qs in groups.items():
   byid=defaultdict(list)
   for q in qs:byid[q['reference']['primary_target_id']].append(q)
   ordered=[]
   while byid:
    for t in list(byid):
     ordered.append(byid[t].pop())
     if not byid[t]:del byid[t]
   cap=50 if g[2]=='appearance' else 35 if g[2]=='event' else 20
   kept.extend(ordered[:cap])
  result=kept
  putrows(file,result);allrows.extend(result)
  info={'video':key,'refs':dict(Counter(r['type'] for r in refs)),'pool_n':len(result),'types':dict(Counter(q['operation_name'] for q in result))};counts.append(info)
  print(json.dumps(info),flush=True)
  dump(RES/'pool_progress.json',counts)
  scene.cache_clear();geom.cache_clear();events_index.cache_clear()
 for i,q in enumerate(allrows):q['pool_id']=i
 putrows(RES/'candidate_pool.jsonl',allrows)
 dump(RES/'pool_summary.json',{'count':len(allrows),'operations':dict(Counter(q['operation_name'] for q in allrows)),'reference_types':dict(Counter(q['reference']['type'] for q in allrows))})
 print('POOL_COMPLETE',len(allrows),flush=True)
if __name__=='__main__':main()
