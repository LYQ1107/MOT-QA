"""Offline Chinese review of20 actual formal candidates, with new answer modalities."""
import concurrent.futures,copy,hashlib,html,json,random,shutil,zipfile
from pathlib import Path
import generate_candidates_round2 as g
import render_question_review as renderer
R=g.ROOT;OUT=g.RES/'review';OUT.mkdir(parents=True,exist_ok=True);renderer.OUT=OUT

def main():
 qs=g.rows(R/'data/candidates.jsonl');rng=random.Random(42);picked=[]
 for kind,n in [('box',8),('event',5),('appearance',4),('position',3)]:
  a=[q for q in qs if q['reference']['type']==kind];picked+=rng.sample(a,n)
 # Reference-stratified random sample is independent of answers and model outcomes.
 picked.sort(key=lambda q:q['qa_id']);picked=copy.deepcopy(picked)
 for q in picked:
  roles=q['evidence']['role_mapping'];extra=q['evidence']['gt_detail'].get('counted_gt_ids',[])
  extra+=q['evidence']['gt_detail'].get('candidate_gt_ids',[])
  if q['evidence']['gt_detail'].get('marked_query_target') is not None:extra=extra+[q['evidence']['gt_detail']['marked_query_target']]
  for tid in extra:
   if str(tid) not in roles:roles[str(tid)]=chr(65+len(roles))
 g.putrows(g.RES/'formal_sample20.jsonl',picked)
 media={}
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
  jobs={ex.submit(renderer.render_one,q):q for q in picked}
  for fut in concurrent.futures.as_completed(jobs):
   q=jobs[fut];media[q['qa_id']]=fut.result();print('RENDERED',q['qa_id'],flush=True)
 payload=[]
 for q in picked:
  d=copy.deepcopy(q);asset=OUT/'media'/q['qa_id'];rr=media[q['qa_id']]
  for person in d['reference']['persons']:
   for field in ['image','zoom_crop']:
    src=Path(person[field]);dst=asset/src.name
    if src.resolve()!=dst.resolve():shutil.copyfile(src,dst)
    person[field]=str(dst.relative_to(OUT))
  for field in ['query_image','query_zoom_crop']:
   if d.get(field):
    src=Path(d[field]);dst=asset/src.name;shutil.copyfile(src,dst);d[field]=str(dst.relative_to(OUT))
  if d.get('option_images'):
   for k,src in list(d['option_images'].items()):
    src=Path(src);dst=asset/src.name;shutil.copyfile(src,dst);d['option_images'][k]=str(dst.relative_to(OUT))
  d['media']=rr;payload.append(d)
 packet={'packet_id':'motqa_round2_formal20_'+hashlib.sha256(json.dumps([q['qa_id'] for q in picked]).encode()).hexdigest()[:16],'count':20,'questions':payload}
 page=HTML.replace('__PACKET__',json.dumps(packet,ensure_ascii=False).replace('</','<\\/'))
 (OUT/'打开正式候选抽查20题.html').write_text(page)
 (OUT/'使用说明.txt').write_text('完整解压本文件夹，用Chrome、Edge或Firefox打开“打开正式候选抽查20题.html”。这是900道候选中的真实随机样本；与旧20道模板及规则修订版本不同。中文问题优先，含原片/GT片、参考图与3倍裁剪、O8查询图或人物裁剪选项。可导出stage3_candidate_review_result.json。过滤尚未运行，最终题目仍需过滤与10%人工抽检。\n')
 zip_path=R/'results/motqa_round2_formal_sample20_zh.zip'
 with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED,compresslevel=3) as z:
  for p in sorted(OUT.rglob('*')):
   if p.is_file() and p.suffix not in ['.log']:z.write(p,'MOTQA_正式候选抽查20题/'+str(p.relative_to(OUT)))
 g.dump(g.RES/'formal_review_receipt.json',{'packet_id':packet['packet_id'],'sample_n':20,'strata':{'box':8,'event':5,'appearance':4,'position':3},'seed':42,'sampling':'without replacement within reference type; no model outcomes or answer labels used','page':str(OUT/'打开正式候选抽查20题.html'),'zip':str(zip_path),'zip_bytes':zip_path.stat().st_size,'zip_sha256':hashlib.sha256(zip_path.read_bytes()).hexdigest(),'export_filename':'stage3_candidate_review_result.json'})
 print('REVIEW_COMPLETE',zip_path,flush=True)

HTML='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>MOT-QA 第二轮 · 正式候选抽查20题</title><style>body{font:17px/1.6 system-ui;color:#193748;background:#eef4f6;margin:0}main{max-width:1200px;margin:auto;padding:22px}section,header{background:white;border:1px solid #ccdce5;border-radius:10px;padding:20px;margin-bottom:16px}h1{font-size:25px}h2{font-size:21px}button,select,textarea{font:inherit;padding:8px;margin:4px;border:1px solid #9bb6c5;border-radius:5px;background:white}button{cursor:pointer}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}img{max-width:100%;max-height:430px;object-fit:contain}video{width:100%;max-height:650px;background:#10232b}.choice{border:1px solid #c9d9e3;padding:10px;margin:8px 0}.minor{color:#5a7180;font-size:14px}pre{white-space:pre-wrap;overflow-wrap:anywhere}textarea{box-sizing:border-box;width:95%}</style><main><header><h1>MOT-QA 第二轮 · 正式候选抽查20题</h1><p>这20题从已生成的900道正式候选中按指代方式随机抽取。旧20道已通过设计样例及其修订版不在此包中。过滤尚未运行。</p><div id="progress"></div><button onclick="step(-1)">上一题</button><button onclick="step(1)">下一题</button><button onclick="exportJSON()">导出20题结果</button><button onclick="document.getElementById('import').click()">导入继续</button><input type=file id=import accept="application/json" hidden></header><section id="body"></section></main><script>const packet=__PACKET__;let i=0;const K=packet.packet_id;let state=JSON.parse(localStorage.getItem(K)||'{}');const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));function save(){localStorage.setItem(K,JSON.stringify(state));}function render(){const q=packet.questions[i],s=state[q.qa_id]||{};document.getElementById('progress').textContent=`第 ${i+1}/20 题；已标记 ${Object.values(state).filter(x=>x.verdict).length}/20`;const refs=q.reference.persons.map(r=>`<div><b>人物 ${r.role}</b><p>${esc(r.text_zh)}（${r.t_ref_s.toFixed(3)}秒）</p><img src="${esc(r.image)}"><details><summary>3倍目标裁剪图</summary><img src="${esc(r.zoom_crop)}"></details></div>`).join('');let options=Object.entries(q.options).map(([k,v])=>`<div class=choice>${k}：${esc(q.options_zh[k]||v)}${q.option_images?`<br><img src="${esc(q.option_images[k])}">`:''}</div>`).join('');if(q.format.startsWith('numeric'))options=`<p>数值作答：${q.format==='numeric_time'?'时间（秒），容差±0.5秒':'精确整数人数'}。</p>`;const ans=q.format.startsWith('numeric')?q.answer:q.answer+'：'+(q.options_zh[q.answer]||q.options[q.answer]);document.getElementById('body').innerHTML=`<h2>${esc(q.qa_id)} · ${esc(q.operation_name)} · ${esc(q.dataset)} / ${esc(q.sequence)}</h2><div class=grid>${refs}</div><h2>${esc(q.question_zh)}</h2><details><summary>英文原文及测试改写标记</summary><p>${esc(q.question)}</p><p>${esc(q.paraphrase_split)}</p></details>${q.query_image?`<h3>查询帧（${q.query_time_s.toFixed(3)}秒）</h3><img src="${esc(q.query_image)}">`:''}${options}<h3>跨时间片段</h3><select id=version><option value=raw_clip>原片</option><option value=gt_clip>GT核验片段</option></select><video id=video controls preload=metadata src="${esc(q.media.raw_clip)}"></video><p class=minor>片段对应原视频 ${q.media.clip_start_s.toFixed(3)}–${q.media.clip_end_s.toFixed(3)}秒；GT字母框仅供核验，不是正式模型输入。</p><details><summary>展开GT答案与事实核验</summary><p><b>${esc(ans)}</b></p><pre>${esc(JSON.stringify(q.evidence.gt_detail,null,2))}</pre><div class=grid>${q.media.frames.map(f=>`<div><p>${f.time_s.toFixed(3)}秒</p><img src="${esc(f.image)}"></div>`).join('')}</div></details><p>身份挑战代理：${q.difficulty.identity_challenge?'是':'简单对照'}；相机：${esc(q.difficulty.camera_motion)}</p><div>${[['pass','通过'],['fail','不通过'],['uncertain','不确定']].map(([v,t])=>`<label><input type=radio name=verdict value=${v} ${s.verdict===v?'checked':''}>${t}</label>`).join('　')}</div><textarea id=notes placeholder="备注">${esc(s.notes||'')}</textarea>`;document.getElementById('version').onchange=e=>{document.getElementById('video').src=q.media[e.target.value]};document.querySelectorAll('[name=verdict]').forEach(x=>x.onchange=e=>{state[q.qa_id]={...(state[q.qa_id]||{}),verdict:e.target.value};save();document.getElementById('progress').textContent=`第 ${i+1}/20 题；已标记 ${Object.values(state).filter(x=>x.verdict).length}/20`});document.getElementById('notes').oninput=e=>{state[q.qa_id]={...(state[q.qa_id]||{}),notes:e.target.value};save()};}function step(d){i=Math.max(0,Math.min(19,i+d));render();window.scrollTo(0,0)}function exportJSON(){let out={packet_id:packet.packet_id,exported_at:new Date().toISOString(),total:20,reviews:packet.questions.map(q=>({qa_id:q.qa_id,verdict:state[q.qa_id]?.verdict||null,notes:state[q.qa_id]?.notes||''}))};let a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(out,null,2)],{type:'application/json'}));a.download='stage3_candidate_review_result.json';a.click();URL.revokeObjectURL(a.href)}document.getElementById('import').onchange=async e=>{let v=JSON.parse(await e.target.files[0].text());if(v.packet_id!==packet.packet_id)throw Error('题包不匹配');state=Object.fromEntries(v.reviews.map(x=>[x.qa_id,{verdict:x.verdict,notes:x.notes}]));save();render()};render();</script></html>'''
if __name__=='__main__':main()
