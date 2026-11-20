"""Record source, actual size and checksums of stage-one downloaded artifacts."""
import hashlib
import json
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]


def digest(path, algorithm='sha256'):
    result = hashlib.new(algorithm)
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def record_file(records, path, source, expected_size, expected_sha256=None, expected_git=None, kind='model'):
    size = path.stat().st_size
    actual = digest(path)
    assert size == expected_size, (path, size, expected_size)
    if expected_sha256:
        assert actual == expected_sha256, (path, 'sha256 mismatch')
        integrity = 'Published SHA256 and size verified'
    elif expected_git:
        data = path.read_bytes()
        blob = hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()
        assert blob == expected_git, (path, 'Git blob mismatch')
        integrity = 'Published Git blob and size verified'
    else:
        integrity = 'Size checked; local SHA256 recorded'
    records.append(dict(path=str(path.relative_to(ROOT)), source=source, bytes=size, sha256=actual,
                        integrity=integrity, kind=kind))


def main():
    records = []
    qwen_source = (ROOT / 'logs/qwen_source_used.txt').read_text().strip()
    if qwen_source == 'modelscope':
        meta = json.loads((ROOT / 'logs/qwen_modelscope_info.json').read_text())
        for item in meta['Data']['Files']:
            if item['Type'] == 'blob':
                record_file(records, ROOT / 'models/Qwen2.5-VL-7B-Instruct' / item['Path'],
                            f'https://modelscope.cn/api/v1/models/Qwen/Qwen2.5-VL-7B-Instruct/repo?Revision={item["Revision"]}&FilePath={item["Path"]}',
                            item['Size'], item['Sha256'])
    else:
        meta = json.loads((ROOT / 'logs/qwen_hf_info.json').read_text())
        for item in meta['siblings']:
            lfs = item.get('lfs') or {}
            record_file(records, ROOT / 'models/Qwen2.5-VL-7B-Instruct' / item['rfilename'],
                        f'{qwen_source}/Qwen/Qwen2.5-VL-7B-Instruct/resolve/{meta["sha"]}/{item["rfilename"]}',
                        item['size'], lfs.get('sha256'), None if lfs else item.get('blobId'))
    dino_source = (ROOT / 'logs/dino_source_used.txt').read_text().strip()
    meta = json.loads((ROOT / 'logs/dino_hf_info.json').read_text())
    for item in meta['siblings']:
        if item['rfilename'] in {'.gitattributes', 'pytorch_model.bin'}:
            continue
        lfs = item.get('lfs') or {}
        record_file(records, ROOT / 'models/grounding-dino-base' / item['rfilename'],
                    f'{dino_source}/IDEA-Research/grounding-dino-base/resolve/{meta["sha"]}/{item["rfilename"]}',
                    item['size'], lfs.get('sha256'), None if lfs else item.get('blobId'))

    for path in sorted((ROOT / 'env/conda-meta').glob('*.json')):
        meta = json.loads(path.read_text())
        archive = ROOT / 'cache/conda' / meta['fn']
        record_file(records, archive, meta['url'], meta['size'], meta.get('sha256'), kind='conda')

    report = json.loads((ROOT / 'logs/pip_install_report.json').read_text())
    # pip retains downloaded response bodies in its task-local HTTP cache.
    # Compare each wheel to the digest in pip's installation report.
    cache_by_sha = {}
    for path in (ROOT / 'cache/pip').rglob('*.body'):
        cache_by_sha[digest(path)] = path
    missing = []
    for package in report['install']:
        info = package['download_info']
        expected = info['archive_info']['hashes']['sha256']
        archive = cache_by_sha.get(expected)
        if archive is None:
            missing.append(dict(package=package['metadata']['name'], source=info['url'], sha256=expected))
            continue
        records.append(dict(path=str(archive.relative_to(ROOT)), source=info['url'],
                            filename=unquote(Path(urlparse(info['url']).path).name), bytes=archive.stat().st_size,
                            sha256=expected, integrity='Cached archive SHA256 matches pip report', kind='pip'))
    assert not missing, ('Missing pip cache bodies', missing)
    (ROOT / 'logs/artifact_verification.json').write_text(json.dumps(records, indent=2) + '\n')
    with (ROOT / 'logs/downloads.md').open('a') as log:
        for item in records:
            name = item.get('filename', item['path'])
            log.write(f'| `{name}` | {item["source"]} | {item["bytes"]} | {item["integrity"]}; SHA256 `{item["sha256"]}` |\n')
    totals = {kind: dict(files=sum(item['kind'] == kind for item in records),
                         bytes=sum(item['bytes'] for item in records if item['kind'] == kind))
              for kind in ['model', 'conda', 'pip']}
    (ROOT / 'logs/download_verification_summary.json').write_text(json.dumps(totals, indent=2) + '\n')
    print(json.dumps(totals, indent=2), flush=True)


if __name__ == '__main__':
    main()
