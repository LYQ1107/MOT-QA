"""Public visual features, image assets and deterministic final option order."""
import hashlib,json,math,os,random,time
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import torch
from torchvision.models import mobilenet_v3_small,MobileNet_V3_Small_Weights
import generate_candidates_round2 as g
from select_candidates_round2 import normalize_confusion
from render_question_review import source_path
R=g.ROOT;D=g.RES;RNG=random.Random(42)
FONT=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',28)
BOX_COUNTER=Counter()

def coords(q,t,f):
 key=q['dataset'],q['sequence'];b=g.scene(key)['boxes_xywh'][g.scene(key)['axis'][t],f-1];m=g.META[key]
 return tuple([max(0,int(math.floor(b[0]))),max(0,int(math.floor(b[1]))),min(m['width'],int(math.ceil(b[0]+b[2]))),min(m['height'],int(math.ceil(b[1]+b[3])))])

def crop_at(q,t,f,im=None):
 key=q['dataset'],q['sequence'];im=im or Image.open(source_path(key,f)).convert('RGB');b=coords(q,t,f)
 if b[2]<=b[0] or b[3]<=b[1]:raise ValueError(f'Empty crop {key}/{t}/{f}')
 return im.crop(b)

def request_features(questions):
 requests=set();groups=defaultdict(set)
 for q in questions:
  key=q['dataset'],q['sequence'];a=g.scene(key)
  for rr in q['reference']['persons']:
   f=rr['frame']
   for t in map(int,a['gt_ids']):
    if a['visible'][a['axis'][t],f-1]:
     b=coords(q,t,f)
     if b[2]>b[0] and b[3]>b[1]:requests.add((*key,t,f))
  dd=q['evidence']['gt_detail'];end=q['evidence']['query_end_frame']
  if dd.get('subtype')=='numbered_box_match':
   for t in dd['candidate_pool_ids']:requests.add((*key,t,end))
  if q.get('option_modality')=='image':
   for c in dd['crop_option_pool']:requests.add((*key,c['gt_id'],c['frame']))
 for ds,s,t,f in sorted(requests):groups[ds,s,f].add(t)
 return groups

def extract_features(questions):
 start=time.monotonic();torch.manual_seed(42);torch.use_deterministic_algorithms(True);torch.backends.cudnn.benchmark=False;torch.backends.cuda.matmul.allow_tf32=False;torch.set_num_threads(4)
 device='cuda' if torch.cuda.is_available() else 'cpu'
 net=mobilenet_v3_small(weights=None);state=torch.load(R/'models/mobilenet_v3_small/mobilenet_v3_small-047dcff4.pth',map_location='cpu',weights_only=True);net.load_state_dict(state);net.classifier=torch.nn.Identity();net.eval().to(device)
 transform=MobileNet_V3_Small_Weights.IMAGENET1K_V1.transforms();requests=request_features(questions);out={};batch=[];keys=[]
 def flush():
  if not batch:return
  with torch.inference_mode():
   vv=net(torch.stack(batch).to(device));vv=torch.nn.functional.normalize(vv,dim=1).cpu().numpy()
  for k,v in zip(keys,vv):out[k]=v
  batch.clear();keys.clear()
 for (ds,s,f),ids in sorted(requests.items()):
  qq={'dataset':ds,'sequence':s};im=Image.open(source_path((ds,s),f)).convert('RGB')
  for t in sorted(ids):
   batch.append(transform(crop_at(qq,t,f,im)));keys.append((ds,s,t,f))
   if len(batch)>=64:flush()
 flush();arr=np.stack(list(out.values()));g.dump(D/'feature_keys.json',[list(k) for k in out]);np.save(D/'appearance_features.npy',arr)
 receipt={'backbone':'torchvision mobilenet_v3_small IMAGENET1K_V1','torch':torch.__version__,'feature_dim':576,'embedding':'global-average pooled final visual feature, L2 normalized; classifier removed','weights_sha256':'047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f','preprocess':'official pretrained transforms:resize256,center crop224,ImageNet normalization','documentation':'https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.mobilenet_v3_small.html','feature_use':'nearest-neighbor descriptor, not a semantic uniqueness check or specialized ReID model','device':device,'CUDA_VISIBLE_DEVICES':os.environ.get('CUDA_VISIBLE_DEVICES'),'crop_count':len(out),'seconds':time.monotonic()-start,'peak_GPU_allocated_MiB':torch.cuda.max_memory_allocated()/2**20 if device=='cuda' else 0}
 g.dump(D/'feature_receipt.json',receipt);del net
 if device=='cuda':torch.cuda.empty_cache()
 return out

def choose_image_options(q,features):
 ds,s=q['dataset'],q['sequence'];t=q['reference']['primary_target_id'];end=q['evidence']['query_end_frame'];d=q['evidence']['gt_detail']
 if d.get('subtype')=='numbered_box_match':
  emb=features[ds,s,t,end];others=[x for x in d['candidate_pool_ids'] if x!=t];others.sort(key=lambda x:-float(emb@features[ds,s,x,end]));mandatory=d['mandatory_confusion_id'];selected=[mandatory]+[x for x in others if x!=mandatory][:2];RNG.shuffle(selected);slot=BOX_COUNTER[ds]%4;BOX_COUNTER[ds]+=1;selected.insert(slot,t)
  d['candidate_gt_ids']=selected;q['answer_index']=selected.index(t);q['semantic_answer']=str(q['answer_index']+1);q['evidence']['confusion']['semantic_answer']=str(selected.index(mandatory)+1)
 if q.get('option_modality')=='image':
  pool=d['crop_option_pool'];target=d['target_option_gt_id'];actual=next(c for c in pool if c['gt_id']==target);emb=features[ds,s,target,actual['frame']];others=[c for c in pool if c['gt_id']!=target];others.sort(key=lambda c:-float(emb@features[ds,s,c['gt_id'],c['frame']]));co=q['evidence']['confusion'];forced=co.get('target_option_gt_id') if co else None
  selected=[actual]
  if forced is not None:selected.append(next(c for c in others if c['gt_id']==forced))
  selected += [c for c in others if c['gt_id'] not in [x['gt_id'] for x in selected]][:4-len(selected)]
  RNG.shuffle(selected);d['crop_candidates']=selected;q['answer_index']=next(i for i,c in enumerate(selected) if c['gt_id']==target);q['raw_options']=[f'portrait {i+1}' for i in range(4)];q['semantic_answer']=q['raw_options'][q['answer_index']]
  if co:co['semantic_answer']=q['raw_options'][next(i for i,c in enumerate(selected) if c['gt_id']==forced)]

def create_assets(q):
 key=q['dataset'],q['sequence'];a=g.scene(key);m=g.META[key];qid=q['qa_id'];folder=R/'data/ref_frames'/qid;folder.mkdir(parents=True,exist_ok=True)
 zoom={}
 for rr in q['reference']['persons']:
  f=rr['frame'];t=rr['target_id'];im=Image.open(source_path(key,f)).convert('RGB');cr=crop_at(q,t,f,im);cr.resize((cr.width*3,cr.height*3),Image.Resampling.BICUBIC).save(folder/f'{rr["role"]}_zoom3x.jpg',quality=95)
  if rr['type']=='box':
   draw=ImageDraw.Draw(im);b=a['boxes_xywh'][a['axis'][t],f-1];x,y,w,h=map(float,b);draw.rectangle([x,y,x+w,y+h],outline=(255,0,0),width=3)
  im.save(folder/f'{rr["role"]}_reference.jpg',quality=95)
  rr['image']=str(folder/f'{rr["role"]}_reference.jpg');rr['zoom_crop']=str(folder/f'{rr["role"]}_zoom3x.jpg');rr['image_insert']='after_frames';rr['zoom_crop_scale']=3;zoom[rr['role']]=rr['zoom_crop']
 q['reference']['zoom_crop']=zoom['A'];q['reference']['zoom_crops']=zoom
 q['reference']['image']=q['reference']['persons'][0]['image'];q['reference']['image_insert']='after_frames'
 q['reference']['box_xyxy_normalized']=q['reference']['persons'][0]['box_xyxy_normalized']
 q['reference']['text']=q['reference']['persons'][0]['text'];q['reference']['text_zh']=q['reference']['persons'][0]['text_zh']
 q['needs_visual_grounding']=q['difficulty']['needs_visual_grounding']
 d=q['evidence']['gt_detail'];end=q['evidence']['query_end_frame']
 if q['operation_name']=='O8':
  im=Image.open(source_path(key,end)).convert('RGB');draw=ImageDraw.Draw(im)
  ids=d['candidate_gt_ids'] if d['subtype']=='numbered_box_match' else [d['marked_query_target']]
  for n,t in enumerate(ids,1):
   x,y,w,h=map(float,a['boxes_xywh'][a['axis'][t],end-1]);draw.rectangle([x,y,x+w,y+h],outline=(255,0,0),width=3)
   if d['subtype']=='numbered_box_match':
    xx=max(0,int(x));yy=max(0,int(y));draw.rectangle([xx,yy,xx+35,yy+35],fill='white');draw.text((xx+5,yy),str(n),fill='black',font=FONT)
  im.save(folder/'query_marked.jpg',quality=95);q['query_image']=str(folder/'query_marked.jpg');q['query_time_s']=g.sec(key,end);q['query_image_insert']='after_frames'
  if d['subtype']=='same_person_yes_no':
   cr=crop_at(q,d['marked_query_target'],end);cr.resize((cr.width*3,cr.height*3),Image.Resampling.BICUBIC).save(folder/'query_zoom3x.jpg',quality=95);q['query_zoom_crop']=str(folder/'query_zoom3x.jpg')
 if q.get('option_modality')=='image':
  q['option_images_raw']=[]
  for i,c in enumerate(d['crop_candidates']):
   path=folder/f'option_crop_{i+1}.jpg';crop_at(q,c['gt_id'],c['frame']).save(path,quality=95);q['option_images_raw'].append(str(path))

def chinese(q):
 e=q['evidence'];s=g.fmt((q['dataset'],q['sequence']),e['query_start_frame']);f=g.fmt((q['dataset'],q['sequence']),e['query_end_frame']);d=e['gt_detail'];t=q['template_id']
 text={
 'region':f'在 {f} 秒时，人物 A 位于画面的左侧、中间还是右侧？',
 'left_pair':f'在 {f} 秒时，人物 A、B 中谁更靠画面左侧？',
 'return_time':f'人物 A 在 {d.get("gap_time_s",0):.3f} 秒附近开始的可见性间断之后，在 {s}–{f} 秒内首次重新清晰可见的时刻是什么？',
 'cross_count':f'在 {s}–{f} 秒内，有多少个不同的人与 A 交错过？每人只计一次。',
 'entry_count':f'在 {s}–{f} 秒内，有多少个不同的轨迹身份首次从画面边缘进入？每个身份只计一次。',
 'earlier_return_time':f'比较 A、B 在 {s}–{f} 秒内各自第一次在可见性间断后重现的时刻，较早的时刻是多少秒？',
 'earliest_return_person':f'在 {s}–{f} 秒内，A、B、C 中谁最先在可见性间断后重新清晰可见？',
 'closest_time':f'在 {s}–{f} 秒内，A、B 在画面中距离最近的时刻落在哪个时间段？',
 'cross_time':f'在 {s}–{f} 秒内，A、B 第一次发生交错的时刻落在哪个时间段？',
 'cross_frequency':f'在 {s}–{f} 秒内，A、B 一共发生了多少次交错？同一对人物反复交错按多次计。',
 'return_region':f'在 {s}–{f} 秒内，A 第 {d.get("ordinal",1)} 次在可见性间断后重新清晰可见时，位于画面哪个区域？',
 'premise_return_time':f'在 {s}–{f} 秒内，A 第一次在可见性间断后重新清晰可见的时刻落在哪个时间段？如果没有发生，请选择对应选项。',
 'identity_match':f'在 {f} 秒的帧中，四个人分别标了编号框 1–4。哪个框里的人是参考帧中的 A？',
 'identity_same':f'在 {f} 秒帧中标出的人物 B，与参考帧中的人物 A 是同一个人吗？',
 'cross_exit_count':f'在 {s}–{f} 秒内，与 A 交错过的人中，有多少人在交错之后、区间结束之前离开画面？每人只计一次。',
 'cross_region':f'在 {s}–{f} 秒内 A、B 第一次交错之后的第一帧，A 位于画面的哪个区域？',
 'motion_relation_example_only':f'在固定机位视频的 {s}–{f} 秒内，A、B 中谁的框中心在图像坐标中的累计路径更长？在终点，该人在另一人的左侧还是右侧？',
 'first_cross_crop':f'在 {s}–{f} 秒内，第一个与 A 交错的人是谁？从人物裁剪图选项中选择。'}[t]
 if q['format']=='numeric_time':text+=' 请用秒给出数值答案，容差 ±0.5 秒。'
 elif q['format']=='numeric_count':text+=' 请给出精确整数人数。'
 return text

def finalize(qs,features):
 counters=Counter()
 for q in qs:
  key=q['dataset'],q['sequence'];a=g.scene(key);r=q['reference']['persons'][0];t=r['target_id'];f=r['frame'];emb=features[*key,t,f];nn=[(float(emb@v),tid) for (ds,s,tid,ff),v in features.items() if (ds,s)==key and ff==f and tid!=t]
  q['difficulty']['appearance_similarity']=max((v for v,t in nn),default=0.);q['difficulty']['appearance_similarity_status']='computed_public_general_visual_features';q['difficulty']['appearance_similarity_model']='MobileNetV3-Small IMAGENET1K_V1 pooled576';q['difficulty']['nearest_appearance_gt_id']=max(nn)[1] if nn else None
  choose_image_options(q,features);create_assets(q);q['question_zh']=chinese(q)
  if q['format'].startswith('numeric'):
   q['answer']=float(q['numeric_answer']) if q['format']=='numeric_time' else int(q['numeric_answer']);q['options']={};q['options_zh']={};q['option_provenance']={}
  else:
   n=len(q['raw_options']);group=q['operation_name'],q['dataset'],n;slot=counters[group]%n;counters[group]+=1
   order=[i for i in range(n) if i!=q['answer_index']];RNG.shuffle(order);order.insert(slot,q['answer_index'])
   q['options']={chr(65+j):q['raw_options'][i] for j,i in enumerate(order)};q['answer']=chr(65+slot);co=q['evidence']['confusion'];q['option_provenance']={k:'correct' if k==q['answer'] else 'identity_confusion' if co and co.get('semantic_answer')==v else 'other' for k,v in q['options'].items()}
   zh={'left':'左侧','center':'中间','right':'右侧','Person A':'人物 A','Person B':'人物 B','Person C':'人物 C','No':'否','Yes':'是',g.NEVER:'这件事没有发生'};q['options_zh']={k:zh.get(v,v.replace(' s',' 秒')) for k,v in q['options'].items()}
   if q.get('option_modality')=='image':q['option_images']={chr(65+j):q['option_images_raw'][i] for j,i in enumerate(order)}
   # Final provenance is checked after public-feature ranking and option permutation.
   q['has_confusion_option']='identity_confusion' in q['option_provenance'].values()
  if q['operation_name']=='O8':q['evaluation_role']='direct_cross_time_identity_verification'
 return qs

def main():
 start=time.monotonic();formal=g.rows(R/'data/candidates_round2_selected.jsonl');examples=g.rows(R/'data/precheck_round2_20.jsonl');qs=formal+examples
 for q in qs:normalize_confusion(q)
 keysfile=D/'feature_keys.json';arrfile=D/'appearance_features.npy'
 if keysfile.exists() and arrfile.exists():
  keys=[tuple(x) for x in json.loads(keysfile.read_text())];arr=np.load(arrfile);features=dict(zip(keys,arr))
  requests=request_features(qs);needed={(ds,s,t,f) for (ds,s,f),ids in requests.items() for t in ids}
  if not needed.issubset(features):features=extract_features(qs)
 else:features=extract_features(qs)
 formal=finalize(formal,features);examples=finalize(examples,features)
 g.putrows(R/'data/candidates.jsonl',formal);g.putrows(R/'data/precheck_round2_20.jsonl',examples)
 g.dump(D/'asset_receipt.json',{'formal':len(formal),'revised_examples':len(examples),'seconds':time.monotonic()-start,'model_calls':'visual features only; no evaluated VLM, tracker or training','GPU_service_started':False,'GPU_memory_released_on_process_exit':True})
 print('FINALIZED',len(formal),len(examples),flush=True)
if __name__=='__main__':main()
