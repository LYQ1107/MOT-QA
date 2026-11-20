"""Download the pinned official MASA unified checkpoint without a proxy."""
import hashlib
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
meta = json.loads((ROOT / 'logs/masa_hf_info.json').read_text())
item = next(item for item in meta['siblings'] if item['rfilename'] == 'gdino_masa.pth')
destination = ROOT / 'models/MASA/gdino_masa.pth'
destination.parent.mkdir(parents=True, exist_ok=True)
partial = destination.with_suffix('.pth.incomplete')
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
endpoints = [os.environ.get('HF_ENDPOINT', 'https://hf-mirror.com'), 'https://huggingface.co']
selected_url = None
for endpoint in endpoints:
    url = f'{endpoint}/dereksiyuanli/masa/resolve/{meta["sha"]}/gdino_masa.pth'
    try:
        with partial.open('ab') as output:
            offset = output.tell()
            while offset < item['size']:
                end = min(item['size'] - 1, offset + 32 * 1024 * 1024 - 1)
                request = urllib.request.Request(url, headers={
                    'Range': f'bytes={offset}-{end}', 'Accept-Encoding': 'identity', 'Cache-Control': 'no-cache',
                })
                with opener.open(request, timeout=90) as response:
                    assert response.status == 206
                    assert response.headers.get('Content-Range') == f'bytes {offset}-{end}/{item["size"]}'
                    data = response.read()
                assert len(data) == end - offset + 1
                output.write(data)
                output.flush()
                offset = end + 1
                print(json.dumps({'asset': 'gdino_masa.pth', 'bytes': offset, 'total': item['size'],
                                  'percent': round(100 * offset / item['size'], 1)}), flush=True)
        selected_url = url
        break
    except (urllib.error.URLError, TimeoutError) as error:
        with (ROOT / 'logs/downloads.md').open('a') as log:
            log.write(f'| MASA unified endpoint attempt (failed) | {url} | — | {type(error).__name__}: {error} |\n')
        print(f'Direct endpoint failed: {endpoint}: {error}', flush=True)
        if endpoint == endpoints[-1]:
            raise

sha = hashlib.sha256()
with partial.open('rb') as source:
    for block in iter(lambda: source.read(8 * 1024 * 1024), b''):
        sha.update(block)
assert partial.stat().st_size == item['size']
assert sha.hexdigest() == item['lfs']['sha256']
assert not destination.exists()
partial.rename(destination)
receipt = dict(status='MASA_UNIFIED_WEIGHT_SHA256_VERIFIED', path=str(destination), source=selected_url,
               bytes=item['size'], sha256=sha.hexdigest(), hf_revision=meta['sha'], proxy_used=False)
(ROOT / 'logs/masa_weight_download_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
with (ROOT / 'logs/downloads.md').open('a') as log:
    log.write(f'| `models/MASA/gdino_masa.pth` | {selected_url} | {item["size"]} | Published SHA256 verified: `{sha.hexdigest()}` |\n')
print('MASA_UNIFIED_WEIGHT_SHA256_VERIFIED', flush=True)
