"""Open the actual delivered ZIP in Firefox and verify the review workflow."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import base64
import argparse
import json
import os
import signal
import socket
import subprocess
import time
import zipfile

ROOT=Path('/home/user/motqa_pilot');OUT=ROOT/'results/question_review/browser_check'


def main():
    global OUT
    parser=argparse.ArgumentParser()
    parser.add_argument('--replacements',action='store_true')
    args=parser.parse_args()
    n=3 if args.replacements else 20
    if args.replacements:OUT=ROOT/'results/question_review_replacements/browser_check'
    bundle='motqa_temporal_replacement_review_3_zh_v2.zip' if args.replacements else 'motqa_complete_question_review_20_zh_v1.zip'
    entry='MOTQA_3题重现补审/打开3题补审.html' if args.replacements else 'MOTQA_完整题中文审阅20/打开完整题审阅.html'
    export_filename='question_review_replacement_result.json' if args.replacements else 'question_review_result.json'
    port=28357 if args.replacements else 28355
    OUT.mkdir(exist_ok=True);extracted=OUT/'完整题解压 test'
    with zipfile.ZipFile(ROOT/'results'/bundle) as z:z.extractall(extracted)
    page=extracted/entry
    profile=OUT/'firefox_profile';downloads=OUT/'exported_TEST_ONLY'
    profile.mkdir(exist_ok=True);downloads.mkdir(exist_ok=True)
    prefs={'marionette.port':port,'marionette.enabled':True,'browser.download.folderList':2,'browser.download.dir':str(downloads),'browser.helperApps.neverAsk.saveToDisk':'application/json','browser.download.alwaysOpenPanel':False,'network.proxy.type':0,'browser.shell.checkDefaultBrowser':False}
    (profile/'user.js').write_text('\n'.join(f'user_pref({json.dumps(k)},{json.dumps(v)});' for k,v in prefs.items())+'\n')
    log=(OUT/'firefox.log').open('a');proc=subprocess.Popen(['/usr/lib/firefox/firefox','--headless','--no-remote','--profile',str(profile),'--marionette','about:blank'],stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',LIBGL_ALWAYS_SOFTWARE='1'),start_new_session=True)
    conn=None;result={}
    try:
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            try:conn=socket.create_connection(('127.0.0.1',port),timeout=1);break
            except OSError:time.sleep(.2)
        assert conn is not None;conn.settimeout(40)
        def receive():
            p=b''
            while not p.endswith(b':'):p+=conn.recv(1)
            n=int(p[:-1]);parts=[]
            while n:
                b=conn.recv(n);assert b;parts.append(b);n-=len(b)
            return json.loads(b''.join(parts))
        receive();counter=0
        def call(name,params):
            nonlocal counter
            counter+=1;b=json.dumps([0,counter,name,params]).encode();conn.sendall(str(len(b)).encode()+b':'+b);r=receive();assert r[2] is None,r[2];return r[3]
        def js(script,async_=False):
            r=call('WebDriver:ExecuteAsyncScript' if async_ else 'WebDriver:ExecuteScript',{'script':script,'args':[],'sandbox':None,'newSandbox':False,'line':0,'filename':'complete_review_check'})
            return r.get('value',r) if isinstance(r,dict) else r
        session=call('WebDriver:NewSession',{'capabilities':{'alwaysMatch':{}}});result['browser']=session.get('capabilities',{}).get('browserVersion')
        call('WebDriver:SetWindowRect',{'width':1480,'height':1150});call('WebDriver:Navigate',{'url':page.as_uri()})
        initial=js('return window.reviewApp.buildResult();');assert initial['counts']['pending']==n
        assert len(initial['reviews'])==n and initial['counts']['total']==n
        assert ('谁更早' if args.replacements else '谁更靠画面左侧') in js("return document.querySelector('.question').textContent;")
        if args.replacements:assert '3题' in js("return document.querySelector('h1').textContent;")
        assert js("return document.querySelectorAll('.ref').length;")==2
        result['chinese_question_and_multiple_person_references']=True
        images=js("const done=arguments[arguments.length-1];Promise.all([...document.querySelectorAll('article img')].map(im=>new Promise(resolve=>{im.loading='eager';if(im.complete)return resolve(im.naturalWidth>0);im.onload=()=>resolve(im.naturalWidth>0);im.onerror=()=>resolve(false);}))).then(done);",True)
        assert images and all(images);result['images_loaded']=len(images)
        video=js("const done=arguments[arguments.length-1],v=document.querySelector('video');if(v.readyState>=1){done({width:v.videoWidth,duration:v.duration});}else{v.addEventListener('loadedmetadata',()=>done({width:v.videoWidth,duration:v.duration}),{once:true});v.addEventListener('error',()=>done({error:v.error.code}),{once:true});}",True)
        assert video.get('width',0)>0 and video.get('duration',0)>0,video
        result['original_video_metadata_loaded']=video
        playback=js("const done=arguments[arguments.length-1],v=document.querySelector('video');v.currentTime=1;v.play().then(()=>setTimeout(()=>{const t=v.currentTime;v.pause();done({time:t,decoded:v.getVideoPlaybackQuality().totalVideoFrames});},700)).catch(e=>done({error:e.message}));",True)
        assert playback.get('time',0)>1.2 and playback.get('decoded',0)>0,playback
        result['video_playback_and_decoded_frames']=playback
        gtvideo=js("const done=arguments[arguments.length-1],s=document.getElementById('video-version'),v=document.querySelector('video');v.addEventListener('loadedmetadata',()=>done({width:v.videoWidth,duration:v.duration}),{once:true});v.addEventListener('error',()=>done({error:v.error.code}),{once:true});s.value='gt';s.dispatchEvent(new Event('change'));",True)
        assert gtvideo.get('width',0)>0;result['GT_video_metadata_loaded']=gtvideo
        js("document.querySelector('input[value=pass]').click();const t=document.querySelector('textarea');t.value='TEST ONLY 完整题审阅';t.dispatchEvent(new Event('input'));document.getElementById('next').click();return true;")
        assert js("return document.querySelector('article').dataset.id;")==js('return window.reviewApp.packet.questions[1].qa_id;')
        js("document.getElementById('prev').click();return true;")
        assert js("return document.querySelector('input[value=pass]').checked;")
        result['pagination_preserves_decisions']=True
        chosen=js('return window.reviewApp.buildResult();')
        prior=downloads/export_filename
        if prior.exists():prior.rename(downloads/f'previous_TEST_ONLY_{time.time_ns()}.json')
        js("const s=document.getElementById('dataset');s.value='MOT17';s.dispatchEvent(new Event('change'));document.getElementById('export').click();return true;")
        export=downloads/export_filename;deadline=time.monotonic()+8
        while not export.exists() and time.monotonic()<deadline:time.sleep(.1)
        exported=json.loads(export.read_text());assert exported['reviews']==chosen['reviews'] and len(exported['reviews'])==n
        result[f'actual_JSON_export_contains_all{n}']=True
        call('WebDriver:Navigate',{'url':page.as_uri()});assert js('return window.reviewApp.buildResult();')['reviews']==chosen['reviews']
        result['autosave_on_reopen']=True
        js('window.reviewApp.importResult('+json.dumps(exported,ensure_ascii=False)+');return true;')
        assert js('return window.reviewApp.buildResult();')['reviews']==exported['reviews']
        result['JSON_reimport']=True
        js("const r=window.reviewApp.buildResult();for(const q of r.reviews){q.verdict=null;q.note='';}window.reviewApp.importResult(r);document.getElementById('gt-answer').open=true;document.querySelector('.question').scrollIntoView({block:'center'});return true;")
        assert js('return window.reviewApp.buildResult().counts.pending;')==n
        result['test_decisions_cleared']=True
        shot=call('WebDriver:TakeScreenshot',{'id':None,'highlights':[],'full':False,'hash':False})
        (OUT/'完整题中文预览.png').write_bytes(base64.b64decode(shot['value'] if isinstance(shot,dict) else shot))
        result['status']='PASSED';result['opening_mode']='actual ZIP fully extracted, system Firefox, file:// Chinese path'
        call('WebDriver:DeleteSession',{})
    finally:
        if conn:conn.close()
        if proc.poll() is None:
            os.killpg(proc.pid,signal.SIGTERM)
            try:proc.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
        log.close();result['finished_at']=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
        (OUT/'browser_check_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
