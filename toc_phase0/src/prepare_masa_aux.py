"""Acquire MASA's documented source dependencies and local BERT assets."""
import json
import sys
import subprocess
import zipfile
from pathlib import Path

from prepare_metadata import fetch, ROOT, RECORDS

repos = [('openai/CLIP', ''), ('siyuanliii/TrackEval', ''), ('SysCV/tet', 'teta'),
         ('scalabel/scalabel', ''), ('TAO-Dataset/tao', ''), ('lvis-dataset/lvis-api', '')]
sources = []
for repo, subdir in repos:
    label = repo.replace('/', '_')
    meta = json.loads((ROOT / f'logs/masa_dep_{label}_commit.json').read_text())
    revision = meta['sha']
    destination = f'cache/masa_source_archives/{label}-{revision}.zip'
    git_source = ROOT / 'upstream/masa_dependencies' / f'{repo.split("/")[-1]}-{revision}'
    if (git_source / '.git').exists():
        actual_revision = subprocess.check_output(['git', '-C', str(git_source), 'rev-parse', 'HEAD'], text=True).strip()
        assert actual_revision == revision
        source = git_source
        destination = None
    else:
        if not (ROOT / destination).is_file():
            fetch(f'https://codeload.github.com/{repo}/zip/{revision}', destination)
        with zipfile.ZipFile(ROOT / destination) as archive:
            directory = archive.namelist()[0].split('/')[0]
            archive.extractall(ROOT / 'upstream/masa_dependencies')
        source = ROOT / 'upstream/masa_dependencies' / directory
    if subdir:
        source /= subdir
    sources.append(dict(repo=repo, commit=revision, archive=destination, install_path=str(source)))
    (ROOT / 'logs/masa_dependency_sources.json').write_text(json.dumps(sources, indent=2) + '\n')
    print(json.dumps({'dependency': repo, 'commit': revision}), flush=True)
(ROOT / 'logs/masa_dependency_sources.json').write_text(json.dumps(sources, indent=2) + '\n')
(ROOT / 'requirements_masa_sources.txt').write_text(''.join(item['install_path'] + '\n' for item in sources))

meta = json.loads((ROOT / 'logs/masa_bert_modelscope_info.json').read_text())
repo = (ROOT / 'logs/masa_bert_modelscope_repo.txt').read_text().strip()
needed = {'config.json', 'model.safetensors', 'tokenizer.json', 'tokenizer_config.json', 'vocab.txt', 'LICENSE'}
for item in meta['Data']['Files']:
    if item['Path'] in needed:
        fetch(f'https://modelscope.cn/api/v1/models/{repo}/repo?Revision={item["Revision"]}&FilePath={item["Path"]}',
              f'models/MASA/bert-base-uncased/{item["Path"]}', expected_sha256=item['Sha256'])
(ROOT / 'logs/masa_aux_downloads.json').write_text(json.dumps(RECORDS, indent=2) + '\n')
print('MASA_AUXILIARY_ASSETS_COMPLETE', flush=True)
