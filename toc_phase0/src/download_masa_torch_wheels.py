"""Resume the official cu118 wheels via a tested direct university mirror."""
import hashlib
import http.client
import json
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request

from prepare_metadata import ROOT, fetch

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
receipts = []
for package, version in [('torch', '2.1.2'), ('torchvision', '0.16.2'), ('torchaudio', '2.1.2')]:
    filename = f'{package}-{version}+cu118-cp311-cp311-linux_x86_64.whl'
    encoded = filename.replace('+', '%2B')
    index = f'https://download.pytorch.org/whl/cu118/{package}/'
    if package == 'torch':
        info = json.loads((ROOT / 'logs/masa_torch_wheel_origin.json').read_text())
    else:
        html = fetch(index, f'logs/masa_{package}_official_wheel_index.html').decode()
        link = next(link for link in re.findall(r'href=[\"\']([^\"\']+)', html) if encoded in link)
        original = urllib.parse.urljoin(index, link)
        info = dict(url=urllib.parse.urldefrag(original)[0],
                    sha256=urllib.parse.parse_qs(urllib.parse.urlsplit(original).fragment)['sha256'][0])
    destination = ROOT / 'cache/masa_wheels' / filename
    partial = destination.with_suffix('.whl.incomplete')
    initial_prefix = partial.stat().st_size if partial.exists() else 0
    urls = [f'https://mirror.sjtu.edu.cn/pytorch-wheels/cu118/{encoded}', info['url']]
    for url in urls:
        try:
            with opener.open(urllib.request.Request(url, headers={'Range': 'bytes=0-0', 'Accept-Encoding': 'identity'}), timeout=40) as response:
                assert response.status == 206
                total = int(response.headers['Content-Range'].split('/')[-1])
            with partial.open('ab') as output:
                offset = output.tell()
                while offset < total:
                    end = min(total - 1, offset + 32 * 1024 * 1024 - 1)
                    request = urllib.request.Request(url, headers={'Range': f'bytes={offset}-{end}', 'Accept-Encoding': 'identity', 'Cache-Control': 'no-cache'})
                    with opener.open(request, timeout=90) as response:
                        assert response.status == 206
                        assert response.headers['Content-Range'] == f'bytes {offset}-{end}/{total}'
                        data = response.read()
                    assert len(data) == end - offset + 1
                    output.write(data)
                    output.flush()
                    offset = end + 1
                    print(json.dumps({'wheel': package, 'bytes': offset, 'total': total, 'percent': round(100 * offset / total, 1)}), flush=True)
            selected = url
            break
        except (urllib.error.URLError, TimeoutError, http.client.IncompleteRead) as error:
            print(f'Direct wheel endpoint failed: {url}: {error}', flush=True)
            if url == urls[-1]:
                raise
    sha = hashlib.sha256()
    with partial.open('rb') as source:
        for block in iter(lambda: source.read(8 * 1024 * 1024), b''):
            sha.update(block)
    assert sha.hexdigest() == info['sha256']
    assert not destination.exists()
    partial.rename(destination)
    record = dict(path=str(destination), source=selected, official_url=info['url'], bytes=total,
                  sha256=sha.hexdigest(), integrity='Official PyTorch index SHA256 verified',
                  initial_valid_prefix_bytes=initial_prefix, initial_prefix_source=info['url'] if initial_prefix else None)
    receipts.append(record)
    (ROOT / 'logs/masa_torch_wheel_downloads.json').write_text(json.dumps(receipts, indent=2) + '\n')
    with (ROOT / 'logs/downloads.md').open('a') as ledger:
        ledger.write(f'| `{filename}` | {selected} (official index: {index}; prefix source: {record["initial_prefix_source"]}) | {total} | Official published SHA256 verified: `{sha.hexdigest()}` |\n')
    print(f'{filename}: OFFICIAL_SHA256_VERIFIED', flush=True)
