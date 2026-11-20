"""Resume the interrupted DINO artifact with bounded HTTP range requests."""
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
meta = json.loads((ROOT / 'logs/dino_hf_info.json').read_text())
item = next(item for item in meta['siblings'] if item['rfilename'] == 'model.safetensors')
total = item['size']
expected_sha = item['lfs']['sha256']
destination = ROOT / 'models/grounding-dino-base/model.safetensors'
partial = next((destination.parent / '.cache/huggingface/download').glob('*.incomplete'))
url = f'https://huggingface.co/IDEA-Research/grounding-dino-base/resolve/{meta["sha"]}/model.safetensors'
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
chunk_bytes = 32 * 1024 * 1024

with partial.open('ab') as output:
    offset = output.tell()
    while offset < total:
        end = min(total - 1, offset + chunk_bytes - 1)
        request = urllib.request.Request(url, headers={
            'Range': f'bytes={offset}-{end}', 'Accept-Encoding': 'identity',
            'Cache-Control': 'no-cache',
        })
        with opener.open(request, timeout=90) as response:
            assert response.status == 206
            assert response.headers.get('Content-Range') == f'bytes {offset}-{end}/{total}'
            data = response.read()
        assert len(data) == end - offset + 1
        output.write(data)
        output.flush()
        offset = end + 1
        print(json.dumps({'stage': 'dino_range_resume', 'bytes': offset, 'total': total,
                          'percent': round(100 * offset / total, 1)}), flush=True)

sha = hashlib.sha256()
with partial.open('rb') as source:
    for block in iter(lambda: source.read(8 * 1024 * 1024), b''):
        sha.update(block)
assert partial.stat().st_size == total
assert sha.hexdigest() == expected_sha
assert not destination.exists()
partial.rename(destination)
(ROOT / 'logs/dino_source_used.txt').write_text('https://huggingface.co\n')
(ROOT / 'logs/dino_resume_receipt.json').write_text(json.dumps({
    'status': 'DINO_RESUME_COMPLETE_SHA256_VERIFIED', 'source': url, 'bytes': total,
    'sha256': sha.hexdigest(), 'initial_valid_prefix_bytes': 83886080,
    'range_request_bytes': chunk_bytes, 'proxy_used': False,
}, indent=2) + '\n')
print('DINO_RESUME_COMPLETE_SHA256_VERIFIED', flush=True)
