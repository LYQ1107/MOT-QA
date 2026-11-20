"""Select formal candidates with explicit quotas and preserve a separate revised20."""
import copy, hashlib, json, math, random
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
from scipy.optimize import Bounds,LinearConstraint,milp
from scipy.sparse import coo_matrix
import generate_candidates_round2 as g
R=g.ROOT;D=g.RES;CFG=g.CFG;RNG=random.Random(42)

def normalize_confusion(q):
 co=q['evidence']['confusion']
 if not co or q['format']!='multiple_choice':return
 family=q['template_id']
 if family=='return_region':
  # A wrong identity's gap crossing the half-video boundary is censored, not a negative event.
  key=q['dataset'],q['sequence'];a=g.scene(key);e=q['evidence'];lo=g.META[key]['eligible_source_window_1based'][0]
  ff=np.flatnonzero(a['visible'][a['axis'][co['gt_id']]])+1
  if any(left<lo and e['query_start_frame']<=right<=e['query_end_frame'] and (right-left-1)/g.META[key]['fps']>1 for left,right in zip(ff[:-1],ff[1:])):
   def no_qualifying_return(u):
    vv=np.flatnonzero(a['visible'][a['axis'][u]])+1
    return not any((right-left-1)/g.META[key]['fps']>1 and e['query_start_frame']<=right<=e['query_end_frame'] for left,right in zip(vv[:-1],vv[1:]))
   replacement=next((u for u,_ in g.conf_partners(key,q['reference']['primary_target_id'],q['reference']['persons'][0]['frame'],e['query_end_frame']).most_common() if no_qualifying_return(u)),None)
   if replacement is not None and q['semantic_answer']!=g.NEVER:
    q['evidence']['confusion']={'gt_id':replacement,'semantic_answer':g.NEVER,'method':'follow_overlapping_person_with_no_qualifying_reappearance'}
   else:q['evidence']['confusion']=None;q['has_confusion_option']=False
   return
 if family in ['left_pair','earliest_return_person','cross_region']:
  co['method']='swap_A_B_roles'
 elif family=='return_time':
  # The counterfactual must follow the question's stated gap, not an unrelated return.
  key=q['dataset'],q['sequence'];d=q['evidence']['gt_detail'];e=q['evidence'];u=co['gt_id'];anchor=d['gap']['frame']
  gg=[z for z in g.events_index(key)[0][u] if abs(z['frame']-anchor)<=g.frames(key,1) and (key[0]=='SportsMOT' or z['type']=='becomes_occluded')]
  first=min(gg,key=lambda z:abs(z['frame']-anchor)) if gg else None
  ret=first.get('next_visible_frame') if first else None
  k=next((i for i,(a,b) in enumerate(d['time_bin_frames']) if ret is not None and a<=ret<=b),3)
  value=g.time_values(key,d['time_bin_frames'],True)[k]
  if value==q['semantic_answer']:q['evidence']['confusion']=None;q['has_confusion_option']=False
  else:co['semantic_answer']=value;co['method']='follow_overlapping_person_at_same_stated_gap'

def hard_eligibility(q):
 key=q['dataset'],q['sequence'];m=g.META[key];a=g.scene(key);e=q['evidence'];dd=e['gt_detail'];fs,fe=e['query_start_frame'],e['query_end_frame'];t=q['reference']['primary_target_id']
 if 'time_bin_frames' in dd and min((b-a)/m['fps'] for a,b in dd['time_bin_frames'])<1:
  return 'displayed_time_bin_below1s'
 for rr in q['reference']['persons']:
  if rr['type']=='position':
   f=rr['frame'];vv=a['visible'][:,f-1];xx=a['centers'][:,f-1,0][vv];xx=np.sort(xx)
   if len(xx)<2:return 'position_has_no_runner_up'
   right='rightmost' in rr['text'];best,runner=(xx[-1],xx[-2]) if right else (xx[0],xx[1])
   if not g.geometric_margin(best,runner,m['width']):return 'position_reference_comparison_margin'
 if q['template_id'] in ['earlier_return_time','earliest_return_person','return_region'] and key[0] in ['MOT17','DanceTrack']:
  for rr in q['reference']['persons']:
   if any(z['type']=='leaves_frame' and (fs<=z['frame']<=fe+g.frames(key,2) or fs<=(z.get('next_visible_frame') or -1)<=fe+g.frames(key,2)) for z in g.events_index(key)[0][rr['target_id']]):
    return 'exit_return_identity_scope'
 crossing_templates=['cross_count','cross_exit_count','cross_time','cross_region','cross_frequency','first_cross_crop']
 if q['template_id'] in crossing_templates:
  relevant={t}
  if q['template_id'] in ['cross_time','cross_region','cross_frequency']:relevant={rr['target_id'] for rr in q['reference']['persons']}
  for z in g.OVERLAPS[key]:
   relates=set(z['gt_ids'])==relevant if q['template_id'] in ['cross_time','cross_region','cross_frequency'] else bool(relevant.intersection(z['gt_ids']))
   if z['crossing_status'] not in ['crossed','not_crossed'] and relates and fs<=z['frame_start']<=fe:
    return 'unknown_crossing_cannot_determine_count_or_absence'
 if dd.get('composition_subtype')=='composition_cross_exit' and dd['count']==0:
  allcross=[z for z in g.events_index(key)[3][t] if z['before_frame']>=fs and z['after_frame']<=fe+g.frames(key,2)]
  for z in allcross:
   u=next(x for x in z['gt_ids'] if x!=t)
   if any(zz['type']=='leaves_frame' and zz['invisible_duration_s']>=1.5 and z['after_frame']<zz['last_visible_frame']<=fe+g.frames(key,2) for zz in g.events_index(key)[0][u]):return 'zero_composition_has_event_within2s_extension'
 if dd.get('composition_subtype')=='composition_cross_exit':
  for u,a,b in [(next(x for x in z['gt_ids'] if x!=t),z['before_frame'],z['after_frame']) for z in g.events_index(key)[3][t] if z['before_frame']>=fs and z['after_frame']<=fe]:
   if any(zz['type']=='leaves_frame' and 1<zz['invisible_duration_s']<1.5 and b<zz['last_visible_frame']<=fe for zz in g.events_index(key)[0][u]):return 'composition_has_near_threshold_exit'
 return None

def add_optional_crop_pool(pool):
 out=[];seen=set();templates=json.loads((R/'results/templates_locked.json').read_text())['templates']['first_cross_crop']
 for q in pool:
  if q['operation_name']!='O6' or q['template_id']!='cross_time' or not q['evidence']['gt_detail']['first_cross_frame']:continue
  key=q['dataset'],q['sequence'];m=g.META[key];a=g.scene(key);t=q['reference']['primary_target_id'];e=q['evidence'];fs,fe=e['query_start_frame'],e['query_end_frame']
  sig=key,t,q['reference']['persons'][0]['frame'],fs,fe
  if sig in seen:continue
  ce=g.crossing_set(key,t,fs,fe)
  if not ce:continue
  ce=sorted(ce,key=lambda x:x['after_frame'])
  # Tied earliest partners make the question ambiguous.
  if len(ce)>1 and ce[1]['after_frame']-ce[0]['after_frame']<g.frames(key,1):continue
  target=next(x for x in ce[0]['gt_ids'] if x!=t)
  query=ce[0]['after_frame'];choices=[]
  for tid in map(int,a['gt_ids']):
   if tid==t:continue
   times=np.flatnonzero(a['visible'][a['axis'][tid]])+1
   times=[int(f) for f in times if abs(f-query)>=g.frames(key,3) and m['eligible_source_window_1based'][0]<=f<=m['eligible_source_window_1based'][1]]
   if not times:continue
   # Uniformly inspect candidate instants in chronological order; no answer-based pixel selection.
   ii=np.unique(np.linspace(0,len(times)-1,min(len(times),15)).astype(int));ff=[times[k] for k in ii if g.geom(key,tid,times[k])]
   if ff:choices.append({'gt_id':tid,'frame':ff[len(ff)//2]})
  if len(choices)<4 or target not in [c['gt_id'] for c in choices]:continue
  f=copy.deepcopy(q);f['reference']['persons']=f['reference']['persons'][:1];f['reference']['target_ids']=[t];f['evidence']['gt_ids']=[t];f['evidence']['role_mapping']={str(t):'A'}
  f['evidence']['gt_detail']={'subtype':'first_cross_crop','target_option_gt_id':target,'first_cross_frame':query,'crop_option_pool':choices}
  f['template_id']='first_cross_crop';f['paraphrase_id']=RNG.randrange(5);f['paraphrase_split']=templates[f['paraphrase_id']]['paraphrase_split'];f['question']=templates[f['paraphrase_id']]['text'].format(start=g.fmt(key,fs),end=g.fmt(key,fe));f['raw_options']=['portrait 1','portrait 2','portrait 3','portrait 4'];f['semantic_answer']=f'person_gt{target}';f['answer_index']=0;f['option_modality']='image';f['evidence']['decisive_event_frames']=[query];f['evidence']['keyframes_1based']=sorted(set(f['evidence']['keyframes_1based']+[query]));f['evidence']['negative_extension_end_frame']=None;f['has_confusion_option']=False;f['evidence']['confusion']=None
  # Include the alternate crossing partner from an overlapping-identity substitution if available.
  for u,_ in g.conf_partners(key,t,f['reference']['persons'][0]['frame'],fe).most_common():
   ue=g.crossing_set(key,u,fs,fe)
   if ue:
    first=min(ue,key=lambda x:x['after_frame']);other=next(x for x in first['gt_ids'] if x!=u)
    if other!=target and other in [c['gt_id'] for c in choices]:f['evidence']['confusion']={'gt_id':u,'target_option_gt_id':other,'semantic_answer':f'person_gt{other}'};f['has_confusion_option']=True;break
  out.append(f);seen.add(sig)
 # The optional candidates are generated separately from the existing numeric/box pool.
 return out

def pick_examples(pool):
 old=g.rows(R/'data/question_review_user_passed_20.jsonl');chosen=[];used=set();reuse=Counter()
 for o in old:
  index=o['review_index'];ds=o['dataset'];kind=o['reference']['type'];op='composition' if len(o['operations'])>1 else o['operations'][0]
  # MOT event anchors cannot support a two-person O6 query under the new full geometry gate.
  # Swap reference modes with Sports example6; preserve overall8/5/4/3 and all dataset/operation counts.
  if index==6:kind='event'
  if index==13:kind='box'
  candidates=[]
  for q in pool:
   if q['pool_id'] in used or q['dataset']!=ds or q['reference']['type']!=kind or q['operation_name']!=op:continue
   if reuse[(ds,q['sequence'],q['reference']['primary_target_id'])]>=3:continue
   if index in [4,5] and q['format']!='numeric_time':continue
   if index in [7,11] and q['format']!='numeric_count':continue
   if index not in [4,5,7,11] and q['format'].startswith('numeric'):continue
   if index==8 and q['template_id']!='motion_relation_example_only':continue
   if index==20 and q['template_id']!='cross_exit_count':continue
   if index in [6,16] and q['template_id']!='closest_time':continue
   if index==9 and not q['evidence']['gt_detail'].get('event_exists',False):continue
   if index==12 and not q['evidence']['gt_detail'].get('event_exists',False):continue
   if index==18 and q['evidence']['gt_detail'].get('event_exists',True):continue
   if index==17 and q['semantic_answer']!=g.NEVER:continue
   priorid=o['reference']['persons'][0]['target_id']
   subtype_change=index==13 and q['template_id']!='closest_time'
   if index==13 and q['semantic_answer']==g.NEVER:subtype_change=2
   no_answer_change=index==10 and q['semantic_answer']!=g.NEVER
   score=(subtype_change,no_answer_change,not q['difficulty']['identity_challenge'],q['sequence']!=o['sequence'],q['reference']['primary_target_id']!=priorid,not q['has_confusion_option'],RNG.random())
   candidates.append((score,q))
  if not candidates:
   raise RuntimeError(f'Cannot regenerate corresponding example {index}/{ds}/{kind}/{op} under hard rules; do not substitute a weaker rule.')
  q=copy.deepcopy(min(candidates,key=lambda z:z[0])[1]);used.add(q['pool_id']);reuse[(ds,q['sequence'],q['reference']['primary_target_id'])]+=1
  q.update(qa_id=f'motqa_precheck_{index:02d}_round2',review_index=index,status='RULE_REVISION_EXAMPLE_NOT_FORMAL',replaces_qa_id=o['qa_id'],exclude_from_formal_statistics=True)
  chosen.append(q)
 if sum(q['difficulty']['identity_challenge'] for q in chosen)<12:
  raise RuntimeError('Revised20 do not satisfy60% identity quota; resample without relaxing.')
 g.putrows(R/'data/precheck_round2_20.jsonl',chosen)
 return chosen,used

class Constraints:
 def __init__(self,n):self.n=n;self.ii=[];self.jj=[];self.vv=[];self.lb=[];self.ub=[];self.names=[]
 def add(self,inds,lo,hi,name,values=None):
  row=len(self.lb);self.ii.extend([row]*len(inds));self.jj.extend(inds);self.vv.extend(values if values is not None else [1.]*len(inds));self.lb.append(lo);self.ub.append(hi);self.names.append(name)
 def matrix(self):return coo_matrix((self.vv,(self.ii,self.jj)),shape=(len(self.lb),self.n)).tocsc()

def classof(q):
 op=q['operation_name'];dd=q['evidence']['gt_detail']
 if q['format']=='numeric_time':return None
 if q['format']=='numeric_count':return str(q['numeric_answer'])
 if q['template_id']=='cross_frequency':return str(dd['crossing_frequency'])
 if op=='O8':return str(q['answer_index']) if dd['subtype']=='same_person_yes_no' else None
 if op in ['O1','O2','O7']:return str(q['answer_index'])
 if op in ['O3','O5','O6']:
  return None if q.get('option_modality')=='image' else str(q['answer_index'])
 return str(dd['count']) if dd.get('count') is not None else str(q['answer_index'])

def select(pool,used):
 pool=[q for q in pool if q['pool_id'] not in used and not q['evidence']['gt_detail'].get('example_only')]
 # Keep pool computation outputs, prune only repeated factual variants to bound optimization.
 groups=defaultdict(list)
 for q in pool:
  d=q['evidence']['gt_detail'];sub=d.get('subtype','')
  groups[(q['dataset'],q['sequence'],q['operation_name'],q['reference']['type'],q['format'],sub,classof(q))].append(q)
 reduced=[]
 for k,qs in groups.items():
  # Candidate pool already favors primary-ID diversity. Seeded sampling preserves it here.
  byid=defaultdict(list)
  for q in qs:byid[q['reference']['primary_target_id']].append(q)
  batch=[]
  while byid:
   for t in list(byid):
    batch.append(byid[t].pop())
    if not byid[t]:del byid[t]
  reduced.extend(batch[:30 if k[3] in ['appearance','event'] else 18])
 pool=reduced;n=len(pool);C=Constraints(n);by=defaultdict(list)
 for i,q in enumerate(pool):
  op=q['operation_name'];ds=q['dataset'];rr=q['reference'];d=q['evidence']['gt_detail'];e=q['evidence']
  for k in [('op',op),('dataset',ds),('video',ds,q['sequence']),('identity',ds,q['sequence'],rr['primary_target_id']),('ref',rr['type'])]:by[k].append(i)
  if q['format'].startswith('numeric'):by['numeric',op].append(i)
  if q['difficulty']['identity_challenge']:by['hard',].append(i)
  if q['has_confusion_option']:by['conf',].append(i)
  if q['format']=='multiple_choice':by['choice',].append(i)
  if op=='O7':by['O7_exists',bool(d['event_exists'])].append(i)
  if op!='O7' and q['semantic_answer']==g.NEVER:by['ordinary_never',].append(i)
  if op=='O8' and d['subtype']=='same_person_yes_no':by['O8_same',].append(i);by['O8_same_answer',q['answer_index']].append(i)
  if q.get('option_modality')=='image':by['image_choice',].append(i)
  k=('duplicate',ds,q['sequence'],op,rr['primary_target_id'],rr['persons'][0]['frame'],e['query_start_frame'],e['query_end_frame'],q['template_id'],d.get('ordinal'),d.get('marked_query_target'))
  by[k].append(i)
 for op,v in CFG['candidate_operation_targets'].items():C.add(by['op',op],v,v,'operation '+op)
 for ds,v in CFG['realized_dataset_targets'].items():C.add(by['dataset',ds],v,v,'dataset '+ds)
 for k,ii in by.items():
  if k[0]=='video':C.add(ii,0,20,str(k))
  elif k[0]=='identity':C.add(ii,0,3,str(k))
  elif k[0]=='duplicate' and len(ii)>1:C.add(ii,0,1,str(k))
 C.add(by['ref','event'],225,225,'event references');C.add(by['ref','position'],135,135,'position references');C.add(by['ref','appearance'],0,135,'appearance maximum; shortages become box')
 for op,v in [('O3',40),('O4',70),('O5',70)]:C.add(by['numeric',op],v,v,'numeric '+op)
 C.add(by['hard',],540,np.inf,'identity challenge>=60%')
 C.add(by['conf',]+by['choice',],0,np.inf,'confusion>=70% of choice questions',values=[1.]*len(by['conf',])+[-.7]*len(by['choice',]))
 C.add(by['O7_exists',True],55,55,'O7 premise true');C.add(by['O7_exists',False],55,55,'O7 premise false')
 C.add(by['ordinary_never',],40,40,'ordinary never correct5% (40/790)')
 C.add(by['O8_same',],60,60,'O8 same person60');C.add(by['O8_same_answer',1],30,30,'O8 same yes30');C.add(by['O8_same_answer',0],30,30,'O8 same no30')
 image_available=len(by['image_choice',]);image_target=45 if image_available>=45 else 0
 C.add(by['image_choice',],image_target,image_target,'optional crop questions')
 # Balance semantic answers, not merely displayed option letters, within family/dataset.
 bal=defaultdict(list)
 for i,q in enumerate(pool):
  cl=classof(q)
  if cl is None:continue
  family=q['template_id'];ds=q['dataset'];fmt=q['format']
  bal[(family,fmt,ds)].append((i,cl))
 for k,vals in bal.items():
  family,fmt,ds=k;classes=sorted(set(cl for _,cl in vals));allii=[i for i,_ in vals]
  if family=='return_region':
   # Half nonexistent; the real-event half is balanced over three regions.
   none=[i for i,c in vals if c=='3'];C.add(none+allii,-1,1,'O7 50/50 '+ds,values=[1.]*len(none)+[-.5]*len(allii))
   positive=[i for i,c in vals if c!='3']
   for cl in ['0','1','2']:
    ii=[i for i,c in vals if c==cl];C.add(ii+positive,-1,1,'O7 positive region '+ds+cl,values=[1.]*len(ii)+[-1/3]*len(positive))
  elif family in ['region','left_pair','cross_region','identity_same']:
   fraction=.5 if family in ['left_pair','identity_same'] else 1/3
   for cl in classes:
    ii=[i for i,c in vals if c==cl];C.add(ii+allii,-1,1,'balanced '+str(k)+cl,values=[1.]*len(ii)+[-fraction]*len(allii))
  else:
   # Four-choice/count families: at most35% (+ integer rounding1) of any semantic class.
   for cl in classes:
    ii=[i for i,c in vals if c==cl];C.add(ii+allii,-np.inf,1,'majority cap '+str(k)+cl,values=[1.]*len(ii)+[-.35]*len(allii))
  # Every observed class is also checked in the report; unavailable categories are not fabricated.
 # Strict pooled semantic caps avoid accumulation of per-dataset integer-rounding allowances.
 pooled=defaultdict(list)
 for i,q in enumerate(pool):
  cl=classof(q)
  if cl is not None:pooled[q['template_id'],q['format']].append((i,cl))
 for (family,fmt),vals in pooled.items():
  if family not in ['return_time','earliest_return_person','cross_count']:continue
  allii=[i for i,_ in vals]
  for cl in sorted(set(c for _,c in vals)):
   ii=[i for i,c in vals if c==cl]
   C.add(ii+allii,-np.inf,0,'strict pooled semantic cap '+family+fmt+cl,values=[1.]*len(ii)+[-.35]*len(allii))
 # Keep the modal semantic class shared across sources for these small subgroups.
 # This prevents a dataset-conditioned blind answer from gaining>5pp merely through rounding.
 for (family,fmt,ds),vals in bal.items():
  if family not in ['return_time','earliest_return_person','cross_count']:continue
  mode='2' if family=='cross_count' else '3'
  modal=[i for i,c in vals if c==mode]
  for cl in sorted(set(c for _,c in vals)):
   if cl==mode:continue
   ii=[i for i,c in vals if c==cl]
   C.add(ii+modal,-np.inf,0,'shared modal class '+family+fmt+ds+cl,values=[1.]*len(ii)+[-1.]*len(modal))
 rng=np.random.default_rng(42);objective=rng.uniform(0,.01,n)+np.array([.15*(not q['has_confusion_option'])+.03*(not q['difficulty']['identity_challenge'])-2.*(q['reference']['type']=='appearance') for q in pool])
 A=C.matrix();g.dump(D/'selection_constraints.json',{'n_variables':n,'n_constraints':len(C.lb),'constraint_names':C.names,'optional_crop_available':image_available,'optional_crop_target':image_target,'planned_operation_dataset_matrix':'soft plan; hard constraints apply only global operation and dataset totals','options':{'time_limit':240,'mip_rel_gap':.05}})
 print('MILP_START',n,len(C.lb),flush=True)
 solution=milp(objective,integrality=np.ones(n),bounds=Bounds(0,1),constraints=LinearConstraint(A,C.lb,C.ub),options={'time_limit':240,'mip_rel_gap':.05})
 receipt={'status':int(solution.status),'message':solution.message,'fun':solution.fun,'mip_gap':getattr(solution,'mip_gap',None)}
 g.dump(D/'selection_solver_receipt.json',receipt)
 if solution.x is None:raise RuntimeError('No quota-feasible selection: '+solution.message)
 ix=np.flatnonzero(solution.x>.5);chosen=[copy.deepcopy(pool[i]) for i in ix]
 residual=A@np.rint(solution.x)
 assert np.all(residual>=np.array(C.lb)-1e-6) and np.all(residual<=np.array(C.ub)+1e-6)
 assert len(chosen)==900
 chosen.sort(key=lambda q:(q['dataset'],q['sequence'],q['operation_name'],q['reference']['primary_target_id'],q['evidence']['query_end_frame']))
 for i,q in enumerate(chosen,1):q.update(qa_id=f'motqa_pilot_r2_{i:04d}',status='STAGE3_CANDIDATE_NOT_FILTERED',exclude_from_formal_statistics=False)
 g.putrows(R/'data/candidates_round2_selected.jsonl',chosen)
 g.dump(D/'selection_summary.json',{'count':len(chosen),'operations':dict(Counter(q['operation_name'] for q in chosen)),'datasets':dict(Counter(q['dataset'] for q in chosen)),'references':dict(Counter(q['reference']['type'] for q in chosen)),'formats':dict(Counter(q['format'] for q in chosen)),'identity_challenge':sum(q['difficulty']['identity_challenge'] for q in chosen),'solver':receipt})
 print('SELECTION_COMPLETE',len(chosen),flush=True)

def main():
 pool=g.rows(D/'candidate_pool.jsonl');print('LOADED_POOL',len(pool),flush=True)
 rejected=Counter();good=[]
 for q in pool:
  normalize_confusion(q)
  reason=hard_eligibility(q)
  if reason:rejected[reason]+=1
  else:good.append(q)
 pool=good;g.dump(D/'preselection_hard_rule_exclusions.json',dict(rejected));print('ELIGIBLE_POOL',len(pool),dict(rejected),flush=True)
 optional=add_optional_crop_pool(pool);print('OPTIONAL_CROP_POOL',len(optional),flush=True)
 for i,q in enumerate(optional,max(q['pool_id'] for q in pool)+1):q['pool_id']=i
 g.putrows(D/'optional_crop_pool.jsonl',optional);pool+=optional
 examples,used=pick_examples(pool);print('REVISED20_COMPLETE',flush=True)
 select(pool,used)
if __name__=='__main__':main()
