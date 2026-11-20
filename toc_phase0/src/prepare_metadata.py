"""Acquire the stage-one annotations, official source and download manifests."""
import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
LEDGER = ROOT / 'logs/downloads.md'
RECORDS = []


def fetch(url, destination, expected_git=None, expected_sha256=None):
    path = ROOT / destination
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={'User-Agent': 'toc-phase0-research'})
    try:
        with OPENER.open(request, timeout=60) as response:
            data = response.read()
            resolved = response.url
    except Exception as error:
        with LEDGER.open('a') as log:
            log.write(f'| `{destination}` (failed) | {url} | — | {type(error).__name__}: {error} |\n')
        raise
    sha256 = hashlib.sha256(data).hexdigest()
    git_blob = hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()
    if expected_git and git_blob != expected_git:
        raise ValueError(f'Git blob mismatch: {destination}')
    if expected_sha256 and sha256 != expected_sha256:
        raise ValueError(f'SHA256 mismatch: {destination}')
    path.write_bytes(data)
    check = 'Git blob verified' if expected_git else ('Published SHA256 verified' if expected_sha256 else 'Local SHA256 recorded; no independent digest')
    record = dict(path=destination, source=url, resolved_url=resolved, bytes=len(data), sha256=sha256, integrity=check)
    RECORDS.append(record)
    with LEDGER.open('a') as log:
        log.write(f'| `{destination}` | {url} | {len(data)} | {check}; SHA256 `{sha256}` |\n')
    print(json.dumps(dict(path=destination, bytes=len(data), integrity=check)), flush=True)
    return data


def get_json(url, destination):
    return json.loads(fetch(url, destination))


def main():
    dataset = get_json(
        'https://huggingface.co/api/datasets/anonymous-video-benchmark/toc_bench?blobs=true',
        'logs/hf_dataset_info.json',
    )
    revision = dataset['sha']
    files = {item['rfilename']: item for item in dataset['siblings']}
    for name in ['README.md', 'answer_final.json', 'data/test.jsonl']:
        item = files[name]
        lfs = item.get('lfs') or {}
        for endpoint in ['https://hf-mirror.com', 'https://huggingface.co']:
            try:
                fetch(
                    f'{endpoint}/datasets/anonymous-video-benchmark/toc_bench/resolve/{revision}/{name}',
                    f'data/toc_bench/{name}',
                    expected_git=None if lfs else item.get('blobId'),
                    expected_sha256=lfs.get('sha256'),
                )
                break
            except (urllib.error.URLError, TimeoutError):
                if endpoint == 'https://huggingface.co':
                    raise
    video_manifest = [item for item in dataset['siblings'] if item['rfilename'].startswith('videos/')]
    (ROOT / 'data/toc_bench/video_manifest.json').write_text(json.dumps(video_manifest, indent=2) + '\n')

    tree = get_json('https://api.github.com/repos/junzhe-c/toc_bench/git/trees/main?recursive=1', 'logs/github_tree.json')
    commit = get_json('https://api.github.com/repos/junzhe-c/toc_bench/commits/main', 'logs/github_commit.json')['sha']
    for item in tree['tree']:
        if item['type'] == 'blob':
            fetch(f'https://raw.githubusercontent.com/junzhe-c/toc_bench/{commit}/{item["path"]}',
                  f'upstream/toc_bench/{item["path"]}', expected_git=item['sha'])

    for package in ['vllm', 'modelscope', 'transformers', 'supervision']:
        meta = get_json(f'https://pypi.org/pypi/{package}/json', f'logs/pypi_{package}.json')
        print(json.dumps({'package': package, 'latest': meta['info']['version'], 'python': meta['info']['requires_python'],
                          'requirements': meta['info'].get('requires_dist')}), flush=True)

    for name, url in [
        ('qwen_modelscope', 'https://modelscope.cn/api/v1/models/Qwen/Qwen2.5-VL-7B-Instruct/repo/files?Revision=master&Recursive=true'),
        ('dino_hf', 'https://huggingface.co/api/models/IDEA-Research/grounding-dino-base?blobs=true'),
        ('qwen_hf', 'https://huggingface.co/api/models/Qwen/Qwen2.5-VL-7B-Instruct?blobs=true'),
    ]:
        meta = get_json(url, f'logs/{name}_info.json')
        if name == 'qwen_modelscope':
            print(json.dumps({'modelscope_code': meta.get('Code'), 'files': meta.get('Data', {}).get('Files')}), flush=True)
        else:
            print(json.dumps({'model': meta['id'], 'sha': meta['sha'], 'files': meta.get('siblings')}), flush=True)

    pinned = dict(dataset_repo=dataset['id'], dataset_revision=revision, github_repo='junzhe-c/toc_bench',
                  github_commit=commit, video_files=len(video_manifest), video_bytes=sum(x['size'] for x in video_manifest))
    (ROOT / 'logs/pinned_sources.json').write_text(json.dumps(pinned, indent=2) + '\n')
    print(json.dumps(pinned), flush=True)


if __name__ == '__main__':
    try:
        main()
    finally:
        (ROOT / 'logs/metadata_downloads.json').write_text(json.dumps(RECORDS, indent=2) + '\n')
