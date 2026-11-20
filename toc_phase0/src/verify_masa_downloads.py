"""Append MASA acquisition evidence to the already-verified stage-one ledger."""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse, unquote

from verify_downloads import ROOT, digest, record_file

records_path = ROOT / 'logs/artifact_verification.json'
records = json.loads(records_path.read_text())
known = {item['path'] for item in records}
added = []

weight = json.loads((ROOT / 'logs/masa_weight_download_receipt.json').read_text())
assert weight['status'] == 'MASA_UNIFIED_WEIGHT_SHA256_VERIFIED'
path = Path(weight['path'])
assert path.stat().st_size == weight['bytes']
added.append(dict(path=str(path.relative_to(ROOT)), source=weight['source'], bytes=weight['bytes'],
                  sha256=weight['sha256'], integrity='Published SHA256 verified on download completion', kind='model'))
for item in json.loads((ROOT / 'logs/masa_aux_downloads.json').read_text()):
    if item['path'].startswith('models/'):
        assert (ROOT / item['path']).stat().st_size == item['bytes']
        added.append(dict(item, kind='model'))

for meta_path in (ROOT / 'env_masa/conda-meta').glob('*.json'):
    meta = json.loads(meta_path.read_text())
    archive = ROOT / 'cache/conda' / meta['fn']
    if str(archive.relative_to(ROOT)) not in known:
        record_file(added, archive, meta['url'], meta['size'], meta.get('sha256'), kind='conda')

cache_by_sha = {digest(path): path for path in (ROOT / 'cache/pip_masa').rglob('*.body')}
missing = []
for report_path in ['logs/masa_torch_install_report.json', 'logs/masa_core_install_report.json',
                    'logs/masa_sources_install_report.json']:
    report = json.loads((ROOT / report_path).read_text())
    for package in report['install']:
        info = package['download_info']
        if 'archive_info' not in info:
            continue  # Source checkouts are inventoried below by their pinned commit/archive.
        sha = info['archive_info']['hashes']['sha256']
        archive = Path(unquote(urlparse(info['url']).path)) if info['url'].startswith('file:') else cache_by_sha.get(sha)
        if archive is None:
            missing.append(package['metadata']['name'])
            continue
        if info['url'].startswith('file:'):
            assert digest(archive) == sha
        added.append(dict(path=str(archive.relative_to(ROOT)), source=info['url'],
                          bytes=archive.stat().st_size, sha256=sha,
                          integrity='Cached archive SHA256 matches pip report', kind='pip'))
assert not missing, ('Missing MASA pip cache archives', missing)

sources = json.loads((ROOT / 'logs/masa_dependency_sources.json').read_text())
sources.append(dict(repo='siyuanliii/masa', commit='c5472b9c7615f35abdf1188cb1a0c5408fe50d66',
                    archive=None, install_path=str(ROOT / 'upstream/masa')))
for item in sources:
    if item['archive']:
        path = ROOT / item['archive']
        added.append(dict(path=item['archive'], source=f'https://codeload.github.com/{item["repo"]}/zip/{item["commit"]}',
                          bytes=path.stat().st_size, sha256=digest(path),
                          integrity=f'Local archive SHA256 recorded; pinned Git commit {item["commit"]}', kind='source'))
    else:
        path = Path(item['install_path'])
        for pack in (path / '.git/objects/pack').glob('*.pack'):
            added.append(dict(path=str(pack.relative_to(ROOT)), source=f'https://github.com/{item["repo"]}.git',
                              bytes=pack.stat().st_size, sha256=digest(pack),
                              integrity=f'git clone completed; pinned commit {item["commit"]}; pack SHA256 recorded', kind='source'))

new_records = []
for item in added:
    if item['path'] not in known:
        records.append(item)
        new_records.append(item)
        known.add(item['path'])
records_path.write_text(json.dumps(records, indent=2) + '\n')
(ROOT / 'logs/masa_artifact_verification.json').write_text(json.dumps(new_records, indent=2) + '\n')
with (ROOT / 'logs/downloads.md').open('a') as ledger:
    for item in new_records:
        ledger.write(f'| `{item["path"]}` | {item["source"]} | {item["bytes"]} | {item["integrity"]}; SHA256 `{item["sha256"]}` |\n')
totals = {kind: dict(files=sum(item['kind'] == kind for item in records),
                     bytes=sum(item['bytes'] for item in records if item['kind'] == kind))
          for kind in ['model', 'conda', 'pip', 'source']}
(ROOT / 'logs/download_verification_summary.json').write_text(json.dumps(totals, indent=2) + '\n')
print(json.dumps(totals, indent=2))
