"""Fill original point-query domain and O6 frequency subtype without weaker gates."""
import copy,hashlib,json,math,random,shutil
from collections import defaultdict,Counter
import numpy as np
import generate_candidates_round2 as g
R=g.ROOT;D=g.RES;RNG=random.Random(42)

def all_refs(key):
 m=g.META[key];a=g.scene(key);lo,hi=m['eligible_source_window_1based'];out=[]
 for t in map(int,a['gt_ids']):
  ff=[f for f in range(lo,hi-g.frames(key,3)+1,max(1,g.frames(key,.5))) if g.geom(key,t,f)]
  if len(ff)>5:ff=[ff[i] for i in np.unique(np.linspace(0,len(ff)-1,5).astype(int))]
  for f in ff:out.append(g.make_reference(key,t,f,'box'))
 for x in g.RESOURCES[key]:
  if x['ref_type']=='appearance':continue
  t=int(x['target_ids'][0]);f=x['reference_frame'];kind=x['ref_type']
  if kind=='event':
   ev=x['event']
   if ev.get('invisible_duration_s',2)<1.5:continue
   if ev['type'] in ['leaves_frame','becomes_occluded']:
    f=ev['last_visible_frame']
    while f>=lo and a['visible'][a['axis'][t],f-1] and not g.geom(key,t,f):f-=1
   elif not g.geom(key,t,f):f=next((z for z in range(f,min(hi,f+g.frames(key,2))+1) if g.geom(key,t,z)),f)
  rr=g.make_reference(key,t,f,kind,x)
  if rr:out.append(rr)
 for x in g.APPROVED[key]:
  rr=g.make_reference(key,x['gt_id'],x['reference_frame'],'appearance',x)
  if rr:out.append(rr)
 return [r for r in out if r]

def main():
 original=D/'candidate_pool.jsonl';qs=g.rows(original);hist=D/'history/before_point_frequency_enrichment';hist.mkdir(parents=True,exist_ok=True);shutil.copyfile(original,hist/original.name);extra=[]
 for key,m in g.META.items():
  if not m['eligible_source_window_1based']:continue
  a=g.scene(key);lo,hi=m['eligible_source_window_1based'];rrs=all_refs(key)
  for rr in rrs:
   t=rr['target_id'];rf=rr['frame'];i=a['axis'][t];anchor=max(rf,int(round(rr.get('event_time_s',rr['t_ref_s'])*m['fps']))+1)
   for delay in [3,5,6,9,12]:
    end=anchor+g.frames(key,delay)
    if end>hi:continue
    partner=g.conf_partners(key,t,rf,end);ve=[int(x) for x in a['gt_ids'] if a['visible'][a['axis'][int(x)],end-1]]
    def append(*args,**kwargs):
     q=g.new_fact(key,rr,*args,**kwargs)
     if q:extra.append(q)
    region=int(a['region'][i,end-1])
    if region>=0:
     co=next((u for u,_ in partner.most_common() if int(a['region'][a['axis'][u],end-1])>=0 and int(a['region'][a['axis'][u],end-1])!=region),None)
     append('O1','region',end,end,[rr],g.REG,region,{'region_index':region,'point_query':True},conf={'gt_id':co,'semantic_answer':g.REG[int(a['region'][a['axis'][co],end-1])]} if co is not None else None)
    others=[u for u in ve if u!=t and g.geom(key,u,rf)];others.sort(key=lambda u:-partner[u])
    for u in others[:3]:
     if not a['visible'][i,end-1]:continue
     xx,yy=[float(a['centers'][a['axis'][tt],end-1,0]) for tt in [t,u]]
     r2=g.secondary(key,u,rf)
     if g.geometric_margin(min(xx,yy),max(xx,yy),m['width']):
      ans=0 if xx<yy else 1;append('O2','left_pair',end,end,[rr,r2],['Person A','Person B'],ans,{'point_query':True,'x_centers_px':[xx,yy]},conf={'gt_id':u,'semantic_answer':['Person A','Person B'][1-ans]} if partner[u] else None)
    if rr['type']=='box' and delay>=5 and g.geom(key,t,end):
     good=[u for u in ve if g.geom(key,u,end)];conf=[u for u in good if u!=t and partner[u]]
     if conf:
      u=conf[0]
      for yes in [True,False]:
       marked=t if yes else u
       append('O8','identity_same',end,end,[rr],['No','Yes'],int(yes),{'subtype':'same_person_yes_no','point_query':True,'marked_query_target':marked,'query_marker':g.secondary(key,marked,end),'event_exists':yes},conf={'gt_id':u,'semantic_answer':'No' if yes else 'Yes'})
      if len(good)>=4:append('O8','identity_match',end,end,[rr],['1','2','3','4'],0,{'subtype':'numbered_box_match','point_query':True,'candidate_pool_ids':good,'mandatory_confusion_id':u,'candidate_gt_ids':[t,u]+[z for z in good if z not in [t,u]][:2]},conf={'gt_id':u,'semantic_answer':'2'})
   # Frequency counts use the full qualifying interval and both1s event margins.
   for duration in [6,10,16,24]:
    fs=anchor+g.frames(key,3);end=fs+g.frames(key,duration)
    if end>hi:continue
    es=g.crossing_set(key,t,fs,end)
    if es is None:continue
    byperson=defaultdict(list)
    for e in es:byperson[next(u for u in e['gt_ids'] if u!=t)].append(e)
    candidates=list(byperson)
    # Zero counts are included through currently overlapping distractor people.
    candidates += [u for u,_ in g.conf_partners(key,t,rf,end).most_common() if u not in candidates]
    for u in candidates[:5]:
     r2=g.secondary(key,u,rf)
     if not r2:continue
     count=len(byperson[u]);future=[e for e in g.events_index(key)[3][t] if set(e['gt_ids'])=={t,u} and end<e['after_frame']<=end+g.frames(key,2)]
     if count==0 and (future or end+g.frames(key,2)>hi):continue
     co=None;cv=None
     for other,_ in g.conf_partners(key,t,rf,end).most_common():
      alt=[e for e in g.events_index(key)[3][other] if set(e['gt_ids'])=={other,u} and e['before_frame']>=fs and e['after_frame']<=end]
      if len(alt)!=count and abs(len(alt)-count)<=3:co=other;cv=len(alt);break
     vals=g.count_choices(count,cv);q=g.new_fact(key,rr,'O6','cross_frequency',fs,end,[rr,r2],vals,vals.index(str(count)),{'crossing_frequency':count,'count':count,'pair_ids':[t,u]},decisive=[e['after_frame'] for e in byperson[u]],conf={'gt_id':co,'semantic_answer':str(cv)} if co is not None and str(cv) in vals else None,numeric=count,negative=count==0)
     if q:extra.append(q)
  print('ENRICHED',key,len(extra),flush=True);g.scene.cache_clear();g.geom.cache_clear();g.events_index.cache_clear()
 seen=set();out=[]
 for q in qs+extra:
  e=q['evidence'];d=e['gt_detail'];sig=(q['dataset'],q['sequence'],q['template_id'],q['reference']['type'],tuple(q['reference']['target_ids']),q['reference']['persons'][0]['frame'],e['query_start_frame'] if not d.get('point_query') else None,e['query_end_frame'],q['format'],d.get('ordinal'),d.get('marked_query_target'))
  if sig in seen:continue
  seen.add(sig);q['pool_id']=len(out);out.append(q)
 g.putrows(original,out);g.dump(D/'enrichment_receipt.json',{'before':len(qs),'extra_generated':len(extra),'after_dedup':len(out),'reason':'Point questions use3s/5s reference separation, not an added4s interval; O6 frequency was an original authorized subtype','thresholds_weakened':False,'by_type':dict(Counter(q['operation_name'] for q in out))});print('ENRICHMENT_COMPLETE',len(out),flush=True)
if __name__=='__main__':main()
