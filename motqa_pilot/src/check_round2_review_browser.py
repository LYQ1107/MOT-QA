"""Check actual extracted ZIP, videos, all20 image pages and JSON export/import."""
import base64,json,os,signal,socket,subprocess,time,zipfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
R=Path('/home/user/motqa_pilot');D=R/'results/stage3_round2';OUT=D/'browser_check';OUT.mkdir(parents=True,exist_ok=True)
def main():
 rec=json.loads((D/'formal_review_receipt.json').read_text());extract=OUT/'中文解压 test';extract.mkdir(exist_ok=True)
 with zipfile.ZipFile(rec['zip']) as z:z.extractall(extract)
 page=extract/'MOTQA_正式候选抽查20题/打开正式候选抽查20题.html';profile=OUT/'firefox_profile';download=OUT/'exported_TEST_ONLY';profile.mkdir(exist_ok=True);download.mkdir(exist_ok=True);port=28365
 prefs={'marionette.port':port,'marionette.enabled':True,'browser.download.folderList':2,'browser.download.dir':str(download),'browser.helperApps.neverAsk.saveToDisk':'application/json','browser.download.alwaysOpenPanel':False,'network.proxy.type':0,'browser.shell.checkDefaultBrowser':False}
 (profile/'user.js').write_text('\n'.join(f'user_pref({json.dumps(k)},{json.dumps(v)});' for k,v in prefs.items())+'\n')
 log=(OUT/'firefox.log').open('a');proc=subprocess.Popen(['/usr/lib/firefox/firefox','--headless','--no-remote','--profile',str(profile),'--marionette','about:blank'],stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',LIBGL_ALWAYS_SOFTWARE='1'),start_new_session=True)
 conn=None;result={}
 try:
  deadline=time.monotonic()+20
  while time.monotonic()<deadline:
   try:conn=socket.create_connection(('127.0.0.1',port),timeout=1);break
   except OSError:time.sleep(.2)
  assert conn;conn.settimeout(50)
  def receive():
   pre=b''
   while not pre.endswith(b':'):pre+=conn.recv(1)
   size=int(pre[:-1]);b=b''
   while len(b)<size:b+=conn.recv(size-len(b))
   return json.loads(b)
  receive();counter=0
  def call(name,params):
   nonlocal counter
   counter+=1;b=json.dumps([0,counter,name,params]).encode();conn.sendall(str(len(b)).encode()+b':'+b);v=receive();assert v[2] is None,v[2];return v[3]
  def js(code,async_=False):
   v=call('WebDriver:ExecuteAsyncScript' if async_ else 'WebDriver:ExecuteScript',{'script':code,'args':[],'sandbox':None,'newSandbox':False,'line':0,'filename':'round2_review_browser_check'});return v.get('value',v) if isinstance(v,dict) else v
  sess=call('WebDriver:NewSession',{'capabilities':{'alwaysMatch':{}}});result['browser']=sess.get('capabilities',{}).get('browserVersion');call('WebDriver:SetWindowRect',{'width':1480,'height':1100});call('WebDriver:Navigate',{'url':page.as_uri()})
  js('localStorage.removeItem('+json.dumps(rec['packet_id'])+');return true;');call('WebDriver:Navigate',{'url':page.as_uri()})
  assert '正式候选抽查20题' in js("return document.querySelector('h1').textContent;")
  images=0;zoom=0
  for i in range(20):
   if i:js('window.step(1);return true;')
   assert f'第 {i+1}/20' in js("return document.getElementById('progress').textContent;")
   ok=js("const done=arguments[arguments.length-1];Promise.all([...document.querySelectorAll('#body img')].map(im=>new Promise(resolve=>{if(im.complete)return resolve(im.naturalWidth>0);im.onload=()=>resolve(im.naturalWidth>0);im.onerror=()=>resolve(false)}))).then(done);",True)
   assert ok and all(ok);images+=len(ok);zoom+=js("return [...document.querySelectorAll('img')].filter(im=>im.src.includes('zoom3x')).length;")
  js('window.step(-19);return true;')
  playback=js("const done=arguments[arguments.length-1],v=document.querySelector('video');const play=()=>{v.currentTime=1;v.play().then(()=>setTimeout(()=>{v.pause();done({time:v.currentTime,decoded:v.getVideoPlaybackQuality().totalVideoFrames,width:v.videoWidth})},700)).catch(e=>done({error:e.message}))};if(v.readyState>=1)play();else v.addEventListener('loadedmetadata',play,{once:true});",True)
  assert playback.get('time',0)>1.2 and playback.get('decoded',0)>0
  gt=js("const done=arguments[arguments.length-1],v=document.querySelector('video'),s=document.getElementById('version');v.addEventListener('loadedmetadata',()=>done(v.videoWidth),{once:true});s.value='gt_clip';s.dispatchEvent(new Event('change'));",True);assert gt>0
  js("document.querySelector('input[value=pass]').click();let t=document.getElementById('notes');t.value='TEST ONLY';t.dispatchEvent(new Event('input'));window.step(1);window.step(-1);return true;");assert js("return document.querySelector('input[value=pass]').checked;")
  output=download/rec['export_filename']
  if output.exists():output.rename(download/f'prior_TEST_ONLY_{time.time_ns()}.json')
  js('window.exportJSON();return true;');deadline=time.monotonic()+8
  while not output.exists() and time.monotonic()<deadline:time.sleep(.1)
  exported=json.loads(output.read_text());assert len(exported['reviews'])==20 and exported['reviews'][0]['verdict']=='pass'
  call('WebDriver:Navigate',{'url':page.as_uri()});assert js("return document.querySelector('input[value=pass]').checked;")
  js('localStorage.removeItem('+json.dumps(rec['packet_id'])+');return true;');call('WebDriver:Navigate',{'url':page.as_uri()});assert not js("return document.querySelector('input[value=pass]').checked;")
  code="const done=arguments[arguments.length-1],input=document.getElementById('import'),dt=new DataTransfer();dt.items.add(new File(["+json.dumps(json.dumps(exported,ensure_ascii=False))+"],'review.json',{type:'application/json'}));input.files=dt.files;input.dispatchEvent(new Event('change'));setTimeout(()=>done(document.querySelector('input[value=pass]').checked),400);"
  assert js(code,True)
  js('localStorage.removeItem('+json.dumps(rec['packet_id'])+');return true;');call('WebDriver:Navigate',{'url':page.as_uri()});assert '已标记 0/20' in js("return document.getElementById('progress').textContent;")
  shot=call('WebDriver:TakeScreenshot',{'id':None,'highlights':[],'full':False,'hash':False});(OUT/'正式候选中文预览.png').write_bytes(base64.b64decode(shot['value'] if isinstance(shot,dict) else shot))
  result.update(status='PASSED',actual_extracted_ZIP=True,all20_pages=True,images_loaded=images,zoom_images_loaded=zoom,video_playback=playback,GT_video_loaded=True,actual_JSON_export20=True,save_reload_and_import=True,test_choices_cleared=True);call('WebDriver:DeleteSession',{})
 finally:
  if conn:conn.close()
  if proc.poll() is None:
   os.killpg(proc.pid,signal.SIGTERM)
   try:proc.wait(timeout=10)
   except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
  log.close();result['finished_at']=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat();(OUT/'browser_check_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
