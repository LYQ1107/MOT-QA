"""Exercise actual offline review/JSON export in an isolated headless Firefox."""
from pathlib import Path
from datetime import datetime
import base64
import json
import os
import signal
import socket
import subprocess
import time

ROOT=Path('/home/user/motqa_pilot')
OUT=ROOT/'results/review/browser_check'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    profile=OUT/'firefox_profile'
    profile.mkdir(exist_ok=True)
    downloads=OUT/'exported_TEST_ONLY'
    downloads.mkdir(exist_ok=True)
    prefs={'marionette.port':28347,'marionette.enabled':True,
           'browser.download.folderList':2,'browser.download.dir':str(downloads),
           'browser.helperApps.neverAsk.saveToDisk':'application/json',
           'browser.download.alwaysOpenPanel':False,'browser.startup.homepage':'about:blank',
           'network.proxy.type':0,'browser.shell.checkDefaultBrowser':False}
    (profile/'user.js').write_text('\n'.join('user_pref('+json.dumps(k)+','+json.dumps(v)+');' for k,v in prefs.items())+'\n')
    env=dict(os.environ,CUDA_VISIBLE_DEVICES='',LIBGL_ALWAYS_SOFTWARE='1')
    log=(OUT/'firefox.log').open('a')
    proc=subprocess.Popen(['/usr/lib/firefox/firefox','--headless','--no-remote','--profile',str(profile),'--marionette','about:blank'],
                          stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
    s=None
    results={}
    try:
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            try:
                s=socket.create_connection(('127.0.0.1',28347),timeout=1)
                break
            except OSError:
                time.sleep(.25)
        assert s is not None,'Firefox Marionette failed to start; inspect firefox.log'
        s.settimeout(45)

        def read_packet():
            prefix=b''
            while not prefix.endswith(b':'):
                prefix+=s.recv(1)
            remaining=int(prefix[:-1]);parts=[]
            while remaining:
                part=s.recv(remaining)
                assert part,'Firefox connection closed'
                parts.append(part);remaining-=len(part)
            return json.loads(b''.join(parts))

        results['handshake']=read_packet()
        counter=0

        def call(name,params):
            nonlocal counter
            counter+=1
            data=json.dumps([0,counter,name,params]).encode()
            s.sendall(str(len(data)).encode()+b':'+data)
            reply=read_packet()
            assert reply[0]==1 and reply[1]==counter,reply[:2]
            assert reply[2] is None,reply[2]
            return reply[3]

        def js(script):
            r=call('WebDriver:ExecuteScript',{'script':script,'args':[], 'newSandbox':False,'sandbox':None,'line':0,'filename':'review_browser_check'})
            return r.get('value',r)

        session=call('WebDriver:NewSession',{'capabilities':{'alwaysMatch':{'acceptInsecureCerts':False}}})
        results['browser']=session.get('capabilities',{}).get('browserVersion')
        call('WebDriver:SetWindowRect',{'width':1480,'height':1100})
        page=(ROOT/'results/review/reference_review.html').as_uri()
        call('WebDriver:Navigate',{'url':page})
        initial=js('return window.reviewApp.buildResult();')
        assert len(initial['reviews'])==154 and initial['counts']['main']['pending']==137
        assert initial['counts']['additional']['pending']==17
        assert all(r['verdict'] is None for r in initial['reviews'])
        results['initial_all_pending']=True
        results['offline_images']=js("return [...document.querySelectorAll('.images img')].every(x=>x.src.startsWith('data:image/jpeg;base64,'));")
        assert results['offline_images']
        js("const rows=[...document.querySelectorAll('.review-row')];rows[0].querySelector('input[value=pass]').click();rows[1].querySelector('input[value=uncertain]').click();const t=rows[0].querySelector('textarea');t.value='TEST ONLY 浏览器导出核验';t.dispatchEvent(new Event('input',{bubbles:true}));return true;")
        chosen=js('return window.reviewApp.buildResult();')
        assert chosen['counts']['main']['completed']==2
        assert chosen['reviews'][0]['verdict']=='pass' and chosen['reviews'][1]['verdict']=='uncertain'
        assert chosen['reviews'][0]['note']=='TEST ONLY 浏览器导出核验'
        js("document.getElementById('export-bottom').click();return true;")
        export=downloads/'reference_review_result.json'
        deadline=time.monotonic()+10
        while not export.exists() and time.monotonic()<deadline:
            time.sleep(.2)
        assert export.exists(),'Actual browser download did not complete'
        exported=json.loads(export.read_text())
        assert exported['reviews']==chosen['reviews']
        results['actual_download_export']=True
        call('WebDriver:Navigate',{'url':page})
        restored=js('return window.reviewApp.buildResult();')
        assert restored['reviews']==chosen['reviews']
        results['autosave_reload']=True
        gate=js("const r=window.reviewApp.buildResult();let n=0;for(const c of r.reviews)if(c.group==='sports_lamot_stratified')c.verdict=n++<28?'pass':'fail';window.reviewApp.importResult(r);return window.reviewApp.buildResult().sports_appearance_gate;")
        assert gate['status']=='ALLOW_INDIVIDUALLY_PASSED_ONLY' and gate['passed']==28
        gate=js("const r=window.reviewApp.buildResult();let n=0;for(const c of r.reviews)if(c.group==='sports_lamot_stratified')c.verdict=n++<27?'pass':'fail';window.reviewApp.importResult(r);return window.reviewApp.buildResult().sports_appearance_gate;")
        assert gate['status']=='DISABLE_ALL_SPORTSMOT_APPEARANCE' and gate['passed']==27
        results['sports_70_percent_gate']=True
        # Restore only the actual exported two-case test state, then exercise import.
        literal=json.dumps(exported,ensure_ascii=False)
        imported=js('window.reviewApp.importResult('+literal+');return window.reviewApp.buildResult();')
        assert imported['reviews']==exported['reviews']
        results['json_import_round_trip']=True
        shown=js("document.getElementById('dataset-filter').value='MOT17';document.getElementById('dataset-filter').dispatchEvent(new Event('change'));return [...document.querySelectorAll('.review-row')].filter(r=>!r.hidden).length;")
        assert shown==68
        results['dataset_filter']=True
        js("document.getElementById('dataset-filter').value='';document.getElementById('dataset-filter').dispatchEvent(new Event('change'));const r=window.reviewApp.buildResult();for(const c of r.reviews){c.verdict=null;c.note='';}window.reviewApp.importResult(r);scrollTo(0,0);return true;")
        assert js('return window.reviewApp.buildResult().counts.main.pending;')==137
        results['test_choices_cleared']=True
        results['main_complete']=False
        shot=call('WebDriver:TakeScreenshot',{'id':None,'highlights':[],'full':False,'hash':False})
        data=shot['value'] if isinstance(shot,dict) else shot
        (OUT/'review_page_preview.png').write_bytes(base64.b64decode(data))
        results['screenshot']=str(OUT/'review_page_preview.png')
        results['status']='PASSED'
        results['note']='Isolated test profile only. Two-choice exported fixture is TEST ONLY, not user review input. All test choices cleared afterward.'
        call('WebDriver:DeleteSession',{})
    finally:
        if s is not None:
            s.close()
        if proc.poll() is None:
            os.killpg(proc.pid,signal.SIGTERM)
            try:proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid,signal.SIGKILL);proc.wait()
        log.close()
        results['finished_at']=datetime.now().astimezone().isoformat()
        (OUT/'browser_check_result.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(results,ensure_ascii=False))


if __name__=='__main__':
    main()
