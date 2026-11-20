"""Verify the delivered extracted ZIP, pagination, original images and JSON export."""
from pathlib import Path
from datetime import datetime
import base64
import argparse
import json
import os
import re
import signal
import socket
import subprocess
import time
import zipfile

ROOT=Path('/home/user/motqa_pilot')
OUT=ROOT/'results/review/compat_browser_check'


def main():
    global OUT
    parser=argparse.ArgumentParser()
    parser.add_argument('--chinese',action='store_true',help='Check Chinese package and display with a separate browser profile.')
    args=parser.parse_args()
    if args.chinese:
        OUT=ROOT/'results/review/zh_v2_browser_check'
    bundle='reference_review_zh_v2.zip' if args.chinese else 'reference_review_browser.zip'
    entry='reference_review_zh_v2.html' if args.chinese else 'reference_review.html'
    port=28351 if args.chinese else 28349
    OUT.mkdir(exist_ok=True)
    extracted=OUT/'解压后复核 test'
    with zipfile.ZipFile(ROOT/'results/review'/bundle) as archive:
        archive.extractall(extracted)
    page=extracted/'reference_review'/entry
    legacy=(ROOT/'results/review/history/compact_delivery_revision/reference_review_embedded_v1.html').read_text()
    original=json.loads(re.search(r'<script id="review-payload" type="application/json">([\s\S]*?)</script>',legacy).group(1))
    profile=OUT/'firefox_profile'
    downloads=OUT/'exported_TEST_ONLY'
    profile.mkdir(exist_ok=True);downloads.mkdir(exist_ok=True)
    prefs={'marionette.port':port,'marionette.enabled':True,
           'browser.download.folderList':2,'browser.download.dir':str(downloads),
           'browser.helperApps.neverAsk.saveToDisk':'application/json',
           'browser.download.alwaysOpenPanel':False,'network.proxy.type':0,
           'browser.shell.checkDefaultBrowser':False}
    (profile/'user.js').write_text('\n'.join(f'user_pref({json.dumps(k)},{json.dumps(v)});' for k,v in prefs.items())+'\n')
    log=(OUT/'firefox.log').open('a')
    proc=subprocess.Popen(['/usr/lib/firefox/firefox','--headless','--no-remote','--profile',str(profile),'--marionette','about:blank'],
                          stdout=log,stderr=subprocess.STDOUT,
                          env=dict(os.environ,CUDA_VISIBLE_DEVICES='',LIBGL_ALWAYS_SOFTWARE='1'),start_new_session=True)
    conn=None;result={}
    try:
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            try:conn=socket.create_connection(('127.0.0.1',port),timeout=1);break
            except OSError:time.sleep(.25)
        assert conn is not None
        conn.settimeout(45)
        def receive():
            prefix=b''
            while not prefix.endswith(b':'):prefix+=conn.recv(1)
            remaining=int(prefix[:-1]);parts=[]
            while remaining:
                b=conn.recv(remaining);assert b;parts.append(b);remaining-=len(b)
            return json.loads(b''.join(parts))
        result['handshake']=receive();counter=0
        def call(name,params):
            nonlocal counter
            counter+=1;data=json.dumps([0,counter,name,params]).encode();conn.sendall(str(len(data)).encode()+b':'+data)
            r=receive();assert r[0]==1 and r[1]==counter;assert r[2] is None,r[2]
            return r[3]
        def js(code,async_=False):
            r=call('WebDriver:ExecuteAsyncScript' if async_ else 'WebDriver:ExecuteScript',
                   {'script':code,'args':[],'sandbox':None,'newSandbox':False,'line':0,'filename':'compact_review_check'})
            return r.get('value',r) if isinstance(r,dict) else r
        session=call('WebDriver:NewSession',{'capabilities':{'alwaysMatch':{}}})
        result['browser']=session.get('capabilities',{}).get('browserVersion')
        call('WebDriver:SetWindowRect',{'width':1480,'height':1100})
        call('WebDriver:Navigate',{'url':page.as_uri()})
        initial=js('return window.reviewApp.buildResult();')
        assert len(initial['reviews'])==154 and initial['counts']['main']['pending']==137
        assert all(r['verdict'] is None for r in initial['reviews'])
        core=[{k:v for k,v in r.items() if k not in {'verdict','note'}} for r in initial['reviews']]
        assert core==original['cases']
        result['all154_metadata_equal_to_legacy']=True
        if args.chinese:
            assert '中文审阅 v2' in js("return document.querySelector('h1').textContent;")
            result['visible_chinese_v2_version']=True
            translation=json.loads((ROOT/'src/reference_review_translations_zh.json').read_text())['translations']
            displayed=js('return window.reviewApp.packet.views;')
            assert all(displayed[c['review_id']]['text_zh']==translation[c['text']] for c in original['cases'])
            assert js("return document.querySelector('.phrase').textContent;")==translation[original['cases'][0]['text']]
            assert js("return document.querySelector('.english-original p').textContent;")==original['cases'][0]['text']
            assert js("return !document.querySelector('.english-original').open;")
            assert '指代时刻：' in js("return document.querySelector('.stamp').textContent;")
            js("const s=document.getElementById('search');s.value='渔夫帽';s.dispatchEvent(new Event('input'));return true;")
            assert js('return window.reviewApp.filteredCount();')==1
            assert '渔夫帽' in js("return document.querySelector('.phrase').textContent;")
            assert 'bucket hat' in js("return document.querySelector('.english-original p').textContent;")
            js("const s=document.getElementById('search');s.value='';s.dispatchEvent(new Event('input'));return true;")
            result['all154_chinese_translations_present']=True
            result['english_originals_preserved_and_collapsed']=True
            result['chinese_search']=True
        assert js("return document.querySelectorAll('.review-row').length;")==5
        result['five_rows_per_page']=True
        image_status=js("""const done=arguments[arguments.length-1];const imgs=[...document.querySelectorAll('.images img')];Promise.all(imgs.map(im=>new Promise(resolve=>{im.loading='eager';if(im.complete){resolve(im.naturalWidth>0);return;}im.addEventListener('load',()=>resolve(im.naturalWidth>0),{once:true});im.addEventListener('error',()=>resolve(false),{once:true});}))).then(done);""",True)
        assert image_status and all(image_status),image_status
        result['extracted_zip_images_loaded']=len(image_status)
        result['native_first_frame_width']=js("return document.querySelector('.full img').naturalWidth;")
        packet=json.loads((ROOT/'results/review/reference_review_selection_locked.json').read_text())
        assert result['native_first_frame_width']==packet['cases'][0]['width']
        js("const rows=[...document.querySelectorAll('.review-row')];rows[0].querySelector('input[value=pass]').click();rows[1].querySelector('input[value=uncertain]').click();const t=rows[0].querySelector('textarea');t.value='TEST ONLY 分页复核导出';t.dispatchEvent(new Event('input',{bubbles:true}));return true;")
        chosen=js('return window.reviewApp.buildResult();')
        assert chosen['counts']['main']['completed']==2
        js("document.getElementById('next-top').click();return true;")
        assert js("return [...document.querySelectorAll('.review-row')].every(r=>r.id!==window.reviewApp.packet.cases[0].review_id);")
        js("document.getElementById('prev-top').click();return true;")
        assert js("return document.querySelector('.review-row input[value=pass]').checked;")
        assert js("return document.querySelector('.review-row textarea').value;")=='TEST ONLY 分页复核导出'
        result['page_changes_preserve_decisions_and_notes']=True
        js("document.getElementById('dataset-filter').value='MOT17';document.getElementById('dataset-filter').dispatchEvent(new Event('change'));return true;")
        assert js('return window.reviewApp.filteredCount();')==68
        assert js("return document.querySelectorAll('.review-row').length;")==5
        # Export while another dataset is displayed: do not lose off-page answers.
        js("document.getElementById('export-bottom').click();return true;")
        export=downloads/'reference_review_result.json';deadline=time.monotonic()+10
        while not export.exists() and time.monotonic()<deadline:time.sleep(.2)
        assert export.exists()
        exported=json.loads(export.read_text())
        assert exported['reviews']==chosen['reviews'] and len(exported['reviews'])==154
        result['actual_export_includes_all_pages']=True
        call('WebDriver:Navigate',{'url':page.as_uri()})
        assert js('return window.reviewApp.buildResult();')['reviews']==chosen['reviews']
        result['autosave_after_reopen']=True
        # A genuine legacy export must restore in the compact page.
        old_export=json.loads((ROOT/'results/review/browser_check/exported_TEST_ONLY/reference_review_result.json').read_text())
        restored=js('window.reviewApp.importResult('+json.dumps(old_export,ensure_ascii=False)+');return window.reviewApp.buildResult();')
        assert restored['reviews']==old_export['reviews']
        result['legacy_json_import']=True
        for n,expected in [(28,'ALLOW_INDIVIDUALLY_PASSED_ONLY'),(27,'DISABLE_ALL_SPORTSMOT_APPEARANCE')]:
            g=js('const r=window.reviewApp.buildResult();let n=0;for(const c of r.reviews)if(c.group===\'sports_lamot_stratified\')c.verdict=n++<'+str(n)+'?\'pass\':\'fail\';window.reviewApp.importResult(r);return window.reviewApp.buildResult().sports_appearance_gate;')
            assert g['status']==expected and g['passed']==n
        result['sports_70_percent_gate_unchanged']=True
        js("document.getElementById('scope-filter').value='additional';document.getElementById('scope-filter').dispatchEvent(new Event('change'));return true;")
        assert js('return window.reviewApp.filteredCount();')==17
        result['additional17_available']=True
        js("const r=window.reviewApp.buildResult();for(const c of r.reviews){c.verdict=null;c.note='';}window.reviewApp.importResult(r);document.getElementById('scope-filter').value='main';document.getElementById('scope-filter').dispatchEvent(new Event('change'));scrollTo(0,0);return true;")
        assert js('return window.reviewApp.buildResult().counts.main.pending;')==137
        result['test_choices_cleared']=True
        shot=call('WebDriver:TakeScreenshot',{'id':None,'highlights':[],'full':False,'hash':False})
        (OUT/'compact_page_preview.png').write_bytes(base64.b64decode(shot['value'] if isinstance(shot,dict) else shot))
        result['status']='PASSED'
        result['opening_mode']='extracted ZIP via file:// in system Firefox, path includes spaces and Chinese'
        result['tested_html_bytes']=page.stat().st_size
        result['in_app_preview_tested']=False
        call('WebDriver:DeleteSession',{})
    finally:
        if conn:conn.close()
        if proc.poll() is None:
            os.killpg(proc.pid,signal.SIGTERM)
            try:proc.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
        log.close();result['finished_at']=datetime.now().astimezone().isoformat()
        (OUT/'browser_check_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
