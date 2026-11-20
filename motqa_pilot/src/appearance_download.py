"""Direct, pinned official ModelScope downloads for the approved Stage 2 supplement."""
import argparse
import concurrent.futures as cf
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = Path('/home/user/motqa_pilot')
SOURCE = ROOT / 'sources/appearance'
MODEL = ROOT / 'models/Qwen3-VL-32B-Instruct'
RESULT = ROOT / 'results/stage2_appearance'
REPO = 'Qwen/Qwen3-VL-32B-Instruct'
PIN = '8d6f46b05db6abe0cb3a5ca8c817929cc0fa2d5a'


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def url(record):
    return f'https://modelscope.cn/models/{REPO}/resolve/{PIN}/' + urllib.parse.quote(record['Path'])


def append_log(body):
    log = ROOT / 'logs/downloads.md'
    archive = SOURCE / 'downloads_log_before_appearance.md'
    if not archive.exists():
        archive.write_bytes(log.read_bytes())
        save(SOURCE / 'downloads_log_append_provenance.json', {
            'at': now(), 'original_bytes': archive.stat().st_size,
            'original_sha256': sha(archive), 'archive_path': str(archive),
            'reason': 'Preserve completed Stage 1 log bytes before required append-only download entries.'})
    with log.open('a') as f:
        f.write('\n' + body + '\n')


def fetch(record):
    dst = MODEL / record['Path']
    dst.parent.mkdir(parents=True, exist_ok=True)
    receipt = SOURCE / 'download_receipts' / (record['Path'].replace('/', '__') + '.json')
    if dst.exists() and dst.stat().st_size == record['Size']:
        if receipt.exists() and json.loads(receipt.read_text())['sha256'] == record['Sha256']:
            return json.loads(receipt.read_text())
        assert sha(dst) == record['Sha256'], str(dst)
    else:
        partial = dst.with_name(dst.name + '.partial')
        start = time.monotonic()
        offset = partial.stat().st_size if partial.exists() else 0
        request = urllib.request.Request(url(record), headers={'Range': f'bytes={offset}-'} if offset else {})
        with opener().open(request, timeout=120) as response:
            if offset and response.status != 206:
                offset = 0
            mode = 'ab' if offset else 'wb'
            print(f'DOWNLOAD {record["Path"]} offset={offset}', flush=True)
            with partial.open(mode) as f:
                for chunk in iter(lambda: response.read(8 << 20), b''):
                    f.write(chunk)
        assert partial.stat().st_size == record['Size'], (str(partial), partial.stat().st_size, record['Size'])
        digest = sha(partial)
        assert digest == record['Sha256'], (str(partial), digest, record['Sha256'])
        partial.rename(dst)
        print(f'VERIFIED {record["Path"]} bytes={record["Size"]} seconds={time.monotonic()-start:.1f}', flush=True)
    entry = {'at': now(), 'repo': REPO, 'revision': PIN, 'url': url(record),
             'path': str(dst), 'bytes': dst.stat().st_size, 'sha256': record['Sha256'],
             'verification': 'publisher manifest SHA256 matched', 'proxy': False}
    save(receipt, entry)
    return entry


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--download', action='store_true')
    args = ap.parse_args()
    for name in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY'):
        os.environ.pop(name, None)
    os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
    SOURCE.mkdir(parents=True, exist_ok=True)
    MODEL.mkdir(parents=True, exist_ok=True)
    manifest_path = SOURCE / 'modelscope_manifest_pinned.json'
    if not manifest_path.exists():
        api = f'https://modelscope.cn/api/v1/models/{REPO}/repo/files?Revision={PIN}&Recursive=true'
        raw = opener().open(api, timeout=60).read()
        manifest_path.write_bytes(raw)
        append_log(f'## Stage 2 appearance model — {now()}\n\nOfficial ModelScope manifest: {api}\n\nRevision `{PIN}`; {len(raw)} bytes; SHA256 `{hashlib.sha256(raw).hexdigest()}`; direct, no proxy.')
    manifest = json.loads(manifest_path.read_text())
    assert manifest['Code'] == 200
    files = [f for f in manifest['Data']['Files'] if f['Type'] == 'blob' and f['Path'] != '.gitattributes']
    if not args.download:
        results = [fetch(f) for f in files if not f['Path'].endswith('.safetensors')]
        large = next(f for f in files if f['Path'].endswith('.safetensors'))
        start = time.monotonic()
        with opener().open(urllib.request.Request(url(large), headers={'Range': 'bytes=0-33554431'}), timeout=120) as response:
            data = response.read(32 << 20)
            status = response.status
        elapsed = time.monotonic() - start
        probe = {'at': now(), 'url': url(large), 'bytes': len(data),
                 'sha256': hashlib.sha256(data).hexdigest(), 'seconds': elapsed,
                 'HTTP_status': status, 'retained': False,
                 'remaining_model_bytes': sum(f['Size'] for f in files if f['Path'].endswith('.safetensors')),
                 'serial_estimated_hours_x1_5': sum(f['Size'] for f in files if f['Path'].endswith('.safetensors')) / (len(data)/elapsed) * 1.5 / 3600}
        save(SOURCE / 'download_speed_probe.json', probe)
        for r in results:
            append_log(f'- `{Path(r["path"]).name}`: {r["url"]}; {r["bytes"]} bytes; SHA256 `{r["sha256"]}`; publisher checksum matched.')
        append_log(f'- Direct transfer speed probe (not a complete checkpoint): {probe["url"]}; {len(data)} bytes; SHA256 `{probe["sha256"]}`; {elapsed:.2f}s; estimated full transfer {probe["serial_estimated_hours_x1_5"]:.2f}h including 1.5× allowance. Probe bytes not retained.')
        print(json.dumps(probe), flush=True)
        return
    probe = json.loads((SOURCE / 'download_speed_probe.json').read_text())
    assert probe['serial_estimated_hours_x1_5'] < 6, 'Estimated >6h; report before proceeding'
    started = time.monotonic()
    with cf.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(fetch, files))
    save(SOURCE / 'download_complete.json', {'completed_at': now(), 'seconds': time.monotonic()-started,
         'repo': REPO, 'revision': PIN, 'files': results, 'bytes': sum(r['bytes'] for r in results),
         'manifest_sha256': sha(manifest_path), 'proxy': False})
    for r in results:
        if r['path'].endswith('.safetensors'):
            append_log(f'- `{Path(r["path"]).name}`: {r["url"]}; {r["bytes"]} bytes; SHA256 `{r["sha256"]}`; publisher checksum matched.')
    print(f'ALL_FILES_VERIFIED {len(results)} in {time.monotonic()-started:.1f}s', flush=True)


if __name__ == '__main__':
    main()
