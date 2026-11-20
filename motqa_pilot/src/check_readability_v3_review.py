"""Open the delivered ZIP in a real offline browser and check review/export."""
import base64
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time
import zipfile

import readability_v3 as v


def main():
    rec = json.loads((v.D/'review_receipt.json').read_text())
    out = v.D/'browser_check'
    extract = out/'中文解压 test'
    extract.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(rec['zip']) as z:
        z.extractall(extract)
    page = extract/'MOTQA_修订补审12题/打开中文补审12题.html'
    profile, download = out/'firefox_profile', out/'exported_TEST_ONLY'
    profile.mkdir(exist_ok=True)
    download.mkdir(exist_ok=True)
    port = 28366
    prefs = {'marionette.port': port, 'marionette.enabled': True,
             'browser.download.folderList': 2, 'browser.download.dir': str(download),
             'browser.helperApps.neverAsk.saveToDisk': 'application/json',
             'browser.download.alwaysOpenPanel': False, 'network.proxy.type': 0,
             'browser.shell.checkDefaultBrowser': False}
    (profile/'user.js').write_text('\n'.join(f'user_pref({json.dumps(k)},{json.dumps(x)});' for k,x in prefs.items())+'\n')
    log = (out/'firefox.log').open('a')
    proc = subprocess.Popen(['/usr/lib/firefox/firefox', '--headless', '--no-remote',
        '--profile', str(profile), '--marionette', 'about:blank'], stdout=log,
        stderr=subprocess.STDOUT, start_new_session=True,
        env=dict(os.environ, CUDA_VISIBLE_DEVICES='', LIBGL_ALWAYS_SOFTWARE='1'))
    conn = None
    result = {}
    try:
        deadline = time.monotonic()+20
        while time.monotonic() < deadline:
            try:
                conn = socket.create_connection(('127.0.0.1', port), timeout=1)
                break
            except OSError:
                time.sleep(.2)
        assert conn
        conn.settimeout(50)
        def receive():
            prefix = b''
            while not prefix.endswith(b':'):
                prefix += conn.recv(1)
            data = b''
            size = int(prefix[:-1])
            while len(data) < size:
                data += conn.recv(size-len(data))
            return json.loads(data)
        receive()
        count = 0
        def call(name, args):
            nonlocal count
            count += 1
            b = json.dumps([0, count, name, args]).encode()
            conn.sendall(str(len(b)).encode()+b':'+b)
            x = receive()
            assert x[2] is None, x[2]
            return x[3]
        def js(code, asynchronous=False):
            x = call('WebDriver:ExecuteAsyncScript' if asynchronous else 'WebDriver:ExecuteScript',
                {'script': code, 'args': [], 'sandbox': None, 'newSandbox': False,
                 'line': 0, 'filename': 'readability_v3_delivery_check'})
            return x.get('value', x) if isinstance(x, dict) else x
        session = call('WebDriver:NewSession', {'capabilities': {'alwaysMatch': {}}})
        result['browser_version'] = session.get('capabilities', {}).get('browserVersion')
        call('WebDriver:SetWindowRect', {'width': 1480, 'height': 1160})
        call('WebDriver:Navigate', {'url': page.as_uri()})
        js('localStorage.removeItem('+json.dumps(rec['packet_id'])+');return true;')
        call('WebDriver:Navigate', {'url': page.as_uri()})
        assert '中文版' in js("return document.querySelector('h1').textContent;")
        syntax = js("try{new Function(document.querySelector('script').textContent);return 'ok'}catch(e){return e.name+': '+e.message}")
        assert syntax == 'ok', syntax
        images = 0
        for i in range(rec['count']):
            if i:
                js('window.step(1);return true;')
            progress = js("return document.getElementById('progress').textContent;")
            assert f'第 {i+1}/{rec["count"]}' in progress, (i, progress)
            assert js("return /[\u4e00-\u9fff]/.test(document.querySelectorAll('#body h2')[2].textContent);")
            loaded = js("const done=arguments[arguments.length-1];Promise.all([...document.querySelectorAll('#body img')].map(im=>new Promise(resolve=>{if(im.complete)return resolve(im.naturalWidth>0);im.onload=()=>resolve(im.naturalWidth>0);im.onerror=()=>resolve(false)}))).then(done);", True)
            assert loaded and all(loaded)
            images += len(loaded)
            assert js("return [...document.querySelectorAll('#body img')].filter(x=>x.src.includes('/input32_')).length;") == 32
        js('window.step(-11);return true;')
        playback = js("const done=arguments[arguments.length-1],v=document.querySelector('video');const play=()=>{v.currentTime=1;v.play().then(()=>setTimeout(()=>{v.pause();done({time:v.currentTime,decoded:v.getVideoPlaybackQuality().totalVideoFrames,width:v.videoWidth})},700)).catch(e=>done({error:e.message}))};if(v.readyState>=1)play();else v.addEventListener('loadedmetadata',play,{once:true});", True)
        assert playback.get('time', 0) > 1.2 and playback.get('decoded', 0) > 0
        gt = js("const done=arguments[arguments.length-1],v=document.querySelector('video'),s=document.getElementById('version');v.addEventListener('loadedmetadata',()=>done(v.videoWidth),{once:true});s.value='gt_clip';s.dispatchEvent(new Event('change'));", True)
        assert gt > 0
        js("document.querySelector('input[value=pass]').click();const t=document.getElementById('notes');t.value='TEST ONLY';t.dispatchEvent(new Event('input'));window.step(1);window.step(-1);return true;")
        assert js("return document.querySelector('input[value=pass]').checked;")
        output = download/rec['export_filename']
        if output.exists():
            output.rename(download/f'prior_TEST_ONLY_{time.time_ns()}.json')
        js('window.exportJSON();return true;')
        deadline = time.monotonic()+8
        while not output.exists() and time.monotonic() < deadline:
            time.sleep(.1)
        exported = json.loads(output.read_text())
        assert exported['packet_id'] == rec['packet_id']
        assert len(exported['reviews']) == 12 and exported['reviews'][0]['verdict'] == 'pass'
        call('WebDriver:Navigate', {'url': page.as_uri()})
        assert js("return document.querySelector('input[value=pass]').checked;")
        js('localStorage.removeItem('+json.dumps(rec['packet_id'])+');return true;')
        call('WebDriver:Navigate', {'url': page.as_uri()})
        code = "const done=arguments[arguments.length-1],input=document.getElementById('import'),dt=new DataTransfer();dt.items.add(new File(["+json.dumps(json.dumps(exported, ensure_ascii=False))+"],'review.json',{type:'application/json'}));input.files=dt.files;input.dispatchEvent(new Event('change'));setTimeout(()=>done(document.querySelector('input[value=pass]').checked),400);"
        assert js(code, True)
        js('localStorage.removeItem('+json.dumps(rec['packet_id'])+');return true;')
        call('WebDriver:Navigate', {'url': page.as_uri()})
        assert '已标记 0/12' in js("return document.getElementById('progress').textContent;")
        shot = call('WebDriver:TakeScreenshot', {'id': None, 'highlights': [], 'full': False, 'hash': False})
        (out/'中文补审预览.png').write_bytes(base64.b64decode(shot['value'] if isinstance(shot, dict) else shot))
        result.update(status='PASSED', actual_delivered_ZIP_extracted=True, all12_pages=True,
            images_loaded=images, actual32_frames_each=True, Chinese_question_display=True,
            raw_video_playback=playback, GT_video_loaded=True, actual_JSON_export12=True,
            save_reload_and_import=True, test_choices_cleared=True)
        call('WebDriver:DeleteSession', {})
    finally:
        if conn:
            conn.close()
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
        log.close()
        result['finished_at'] = v.now()
        g_path = out/'browser_check_result.json'
        g_path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
