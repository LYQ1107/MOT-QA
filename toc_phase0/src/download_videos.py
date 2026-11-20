"""Acquire every pinned TOC video and verify the published size and SHA256."""
import concurrent.futures as cf
import hashlib
import json
import os
from pathlib import Path
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / 'data/toc_bench/video_manifest.json').read_text())
PINS = json.loads((ROOT / 'logs/pinned_sources.json').read_text())
REV = PINS['dataset_revision']
REPO = PINS['dataset_repo']
LOCK = threading.Lock()
STOP = threading.Event()
START = time.time()
BLOCK = 16 * 1024 * 1024
for key in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY'):
    os.environ.pop(key, None)


def ledger(message):
    with LOCK, (ROOT / 'logs/downloads.md').open('a') as f:
        f.write(message + '\n')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def source_url(endpoint, name):
    return f'{endpoint}/datasets/{REPO}/resolve/{REV}/{name}'


def choose_endpoint():
    for endpoint in ('https://hf-mirror.com', 'https://huggingface.co'):
        url = source_url(endpoint, MANIFEST[0]['rfilename'])
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            req = urllib.request.Request(url, headers={'Range': 'bytes=0-0', 'Accept-Encoding': 'identity'})
            with opener.open(req, timeout=60) as response:
                assert response.status == 206, response.status
                assert response.read() and response.headers.get('Content-Range') == f'bytes 0-0/{MANIFEST[0]["size"]}'
            ledger(f'| Stage2 video endpoint probe | {url} | 1 | Direct range request succeeded; no proxy |')
            return endpoint
        except Exception as e:
            ledger(f'| Stage2 video endpoint probe FAILED | {url} | — | {type(e).__name__}: {e}; no proxy |')
            print(f'Endpoint failed: {endpoint}: {type(e).__name__}: {e}', flush=True)
    raise RuntimeError('Both direct endpoints failed; stop without proxy')


def acquire(item, endpoint):
    if STOP.is_set():
        return None
    name, size, sha = item['rfilename'], item['size'], item['lfs']['sha256']
    path = ROOT / 'data/toc_bench' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    url = source_url(endpoint, name)
    if path.exists():
        assert path.stat().st_size == size and digest(path) == sha, f'Existing asset mismatch: {name}'
        return dict(path=name, bytes=size, sha256=sha, source=url, status='existing_verified')
    partial = path.with_suffix('.mp4.incomplete')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with partial.open('ab') as output:
        offset = output.tell()
        assert offset <= size, f'Oversized partial: {name}'
        while offset < size:
            if STOP.is_set():
                return None
            end = min(size - 1, offset + BLOCK - 1)
            for attempt in range(3):
                try:
                    req = urllib.request.Request(url, headers={
                        'Range': f'bytes={offset}-{end}', 'Accept-Encoding': 'identity',
                        'Cache-Control': 'no-cache',
                    })
                    with opener.open(req, timeout=90) as response:
                        assert response.status == 206, (name, response.status)
                        assert response.headers.get('Content-Range') == f'bytes {offset}-{end}/{size}'
                        block = response.read()
                    assert len(block) == end - offset + 1, f'Incomplete block for {name}'
                    break
                except Exception as e:
                    ledger(f'| Stage2 video attempt FAILED {attempt+1}/3 | {url} | offset={offset} | {type(e).__name__}: {e}; no proxy |')
                    if attempt == 2:
                        raise
                    time.sleep(2 ** attempt)
            output.write(block)
            output.flush()
            offset = end + 1
    actual_sha = digest(partial)
    assert partial.stat().st_size == size, name
    assert actual_sha == sha, f'SHA256 mismatch: {name}: {actual_sha} != {sha}'
    partial.rename(path)
    ledger(f'| `data/toc_bench/{name}` | {url} | {size} | Published SHA256 verified: `{sha}` |')
    return dict(path=name, bytes=size, sha256=sha, source=url, status='downloaded_verified')


def main():
    assert len(MANIFEST) == 1951
    ledger(f'\n## Stage two videos — pinned revision `{REV}`; no proxy\n')
    endpoint = choose_endpoint()
    records, failures = [], []
    print(f'Downloading 1951 videos, {sum(v["size"] for v in MANIFEST)} bytes from {endpoint}; 8 workers', flush=True)
    with cf.ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(acquire, item, endpoint): item for item in MANIFEST}
        for future in cf.as_completed(futures):
            try:
                record = future.result()
                if record:
                    records.append(record)
                    if len(records) % 25 == 0:
                        elapsed = time.time() - START
                        print(json.dumps({'verified_videos': len(records), 'total': 1951,
                                          'verified_bytes': sum(r['bytes'] for r in records),
                                          'elapsed_s': round(elapsed, 1)}), flush=True)
            except cf.CancelledError:
                pass
            except Exception as e:
                STOP.set()
                failures.append({'path': futures[future]['rfilename'], 'error': f'{type(e).__name__}: {e}'})
                print('DOWNLOAD FAILURE ' + json.dumps(failures[-1]), flush=True)
                for pending in futures:
                    pending.cancel()
    receipt = dict(status='ALL_VIDEOS_VERIFIED' if len(records) == 1951 and not failures else 'DOWNLOAD_FAILED',
                   dataset_revision=REV, endpoint=endpoint, proxy_used=False,
                   expected_count=1951, verified_count=len(records),
                   verified_bytes=sum(r['bytes'] for r in records),
                   elapsed_s=round(time.time() - START, 3),
                   files=sorted(records, key=lambda r: r['path']), failures=failures)
    (ROOT / 'logs/video_download_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({k: v for k, v in receipt.items() if k != 'files'}), flush=True)
    assert receipt['status'] == 'ALL_VIDEOS_VERIFIED', 'Download incomplete: stop and inspect failure receipt'


if __name__ == '__main__':
    main()
