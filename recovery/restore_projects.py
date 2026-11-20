#!/usr/bin/env python3
"""Restore project code and modest research artifacts; keep bulk assets on NAS."""
from pathlib import Path, PurePosixPath
import csv
import hashlib
import json
import os
import shutil
import sys
import tarfile

HOME_ROOT = Path('/data3/liuyeqiang')
NAS = HOME_ROOT / 'nas/A800'
RECOVERY = HOME_ROOT / 'TOC_Bench_recovery_20261120'
TOC_SOURCE = NAS / 'data2/user/toc_phase0'
TOC = HOME_ROOT / 'toc_phase0'
MOTQA = HOME_ROOT / 'motqa_pilot'
records = []
links = []


def save_bytes(destination, content, source, expected=None, mode=0o644):
    digest = hashlib.sha256(content).hexdigest()
    if expected is not None and digest != expected:
        raise RuntimeError(f'Backup digest mismatch: {source}')
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.is_symlink() or hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
            raise RuntimeError(f'Existing destination differs: {destination}')
    else:
        destination.write_bytes(content)
        destination.chmod(mode & 0o777)
    if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
        raise RuntimeError(f'Local digest mismatch: {destination}')
    records.append(dict(source=str(source), destination=str(destination), bytes=len(content), sha256=digest,
                        backup_manifest_verified=expected is not None))


def copy_file(source, destination, expected=None):
    save_bytes(destination, source.read_bytes(), source, expected, source.stat().st_mode)


def link(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink():
        if destination.readlink() != source:
            raise RuntimeError(f'Existing symlink differs: {destination}')
    elif destination.exists():
        raise RuntimeError(f'Existing destination is not a symlink: {destination}')
    else:
        destination.symlink_to(source, target_is_directory=source.is_dir())
    links.append(dict(path=str(destination), target=str(source), exists=destination.exists()))


def copy_code_tree(source, destination):
    excluded = {'.git', '__pycache__', 'node_modules', '.pytest_cache', 'build', 'dist'}
    binary = {'.pth', '.pt', '.bin', '.safetensors', '.so', '.mp4', '.jpg', '.jpeg', '.png', '.gif', '.webp', '.zip', '.whl', '.pdf'}
    for parent, dirs, files in os.walk(source, followlinks=False):
        dirs[:] = sorted(x for x in dirs if x not in excluded)
        for name in sorted(files):
            p = Path(parent) / name
            if p.suffix.lower() in binary or p.stat().st_size > 20_000_000:
                continue
            if p.is_symlink():
                raise RuntimeError(f'Unexpected source code symlink: {p}')
            copy_file(p, destination / p.relative_to(source))


def restore_toc():
    print('Restoring TOC source and upstream code', flush=True)
    for name in ['src', 'upstream']:
        copy_code_tree(TOC_SOURCE / name, TOC / name)
    for p in sorted(TOC_SOURCE.iterdir()):
        if p.is_file() and not p.is_symlink():
            copy_file(p, TOC / p.name)
    for name in ['results', 'logs']:
        (TOC / name).mkdir(exist_ok=True)
        for p in sorted((TOC_SOURCE / name).iterdir()):
            destination = TOC / name / p.name
            if p.is_dir() or p.stat().st_size > 20_000_000:
                link(p, destination)
            elif p.is_file():
                copy_file(p, destination)
    for name in ['data', 'tracks', 'frames_cache']:
        link(TOC_SOURCE / name, TOC / name)
    (TOC / 'models').mkdir(exist_ok=True)
    for p in sorted((TOC_SOURCE / 'models').iterdir()):
        if p.name != 'stage6_lora_r8':
            link(p, TOC / 'models' / p.name)
            continue
        for q in sorted(p.iterdir()):
            dest = TOC / 'models' / p.name / q.name
            if q.is_symlink():
                old = str(q.readlink())
                if old.startswith('/data2/user/nas/A800/'):
                    target = NAS / old.removeprefix('/data2/user/nas/A800/')
                else:
                    raise RuntimeError(f'Unmapped model symlink: {q} -> {old}')
                link(target, dest)
            elif q.is_dir():
                # Resume optimizer/checkpoints stay on NAS; main adapter is repaired above.
                link(q, dest)
            elif q.suffix in {'.safetensors', '.bin', '.pth', '.pt'}:
                link(q, dest)
            else:
                copy_file(q, dest)
    print('TOC restored', flush=True)


def select_motqa(row):
    rel = PurePosixPath(row['project_relative'])
    if any(x in {'browser_check', 'firefox_profile', 'node_modules', '__pycache__', '.git'} or x.startswith('exported_TEST_ONLY') for x in rel.parts):
        return False
    if len(rel.parts) == 1 or rel.parts[0] == 'src':
        return True
    if str(rel) == 'results/motqa_readability_v3_review12_zh.zip':
        return True
    return row['bytes'] <= 20_000_000 and rel.suffix.lower() in {'.json', '.jsonl', '.csv', '.txt', '.md', '.html', '.yaml', '.yml', '.py', '.toml', '.sh', '.lock', '.ini'} and rel.parts[0] in {'data', 'results', 'sources', 'logs'}


def restore_motqa():
    control = NAS / 'motqa_pilot_migration_20261113/_control'
    manifest = json.loads((control / 'transfer_manifest.json').read_text())
    selected = {r['relative_path']: r for r in manifest['files'] if select_motqa(r)}
    print(f'MOT-QA selection: {len(selected)} files, {sum(r["bytes"] for r in selected.values())} bytes', flush=True)
    archive = NAS / 'motqa_pilot_migration_20261113/motqa_pilot_code_results.tar'
    found = set()
    # Read TAR headers on the NAS host once, then use offsets here. This avoids
    # thousands of round trips for headers of media files we are not copying.
    index = {r['name'].removeprefix('./').removeprefix('/'): r for r in
             (json.loads(line) for line in (RECOVERY/'motqa_tar_members.jsonl').read_text().splitlines())}
    with archive.open('rb') as raw:
        for key, row in sorted(selected.items(), key=lambda x: index[x[0]]['offset_data']):
            member = index[key]
            if member['size'] != row['bytes'] or member['sparse']:
                raise RuntimeError(f'Unexpected archive member: {key}')
            rel = PurePosixPath(row['project_relative'])
            if '..' in rel.parts or rel.is_absolute():
                raise RuntimeError(f'Invalid member path: {rel}')
            destination = MOTQA / str(rel)
            if destination.is_file() and not destination.is_symlink() and hashlib.sha256(destination.read_bytes()).hexdigest() == row['sha256']:
                content = destination.read_bytes()
            else:
                raw.seek(member['offset_data'])
                content = raw.read(member['size'])
            save_bytes(destination, content, str(archive) + '::' + key, row['sha256'], member['mode'])
            found.add(key)
            if len(found) % 1000 == 0:
                print(f'MOT-QA verified {len(found)}/{len(selected)}', flush=True)
    missing = sorted(selected.keys() - found)
    if missing:
        raise RuntimeError(f'Archive missing selected members: {missing[:10]}')
    (RECOVERY / 'motqa_selected_backup_manifest.json').write_text(json.dumps(list(selected.values()), ensure_ascii=False, indent=2)+'\n')
    for name in ['ALL_FILES_VERIFIED.json', 'execution_manifest.json']:
        copy_file(control / name, RECOVERY / ('motqa_' + name))
    deferred = [r for r in manifest['files'] if r['relative_path'] not in selected]
    (RECOVERY / 'motqa_assets_retained_in_nas_archive.json').write_text(json.dumps(dict(archive=str(archive), files=deferred, excluded_base_models=manifest['excluded']), ensure_ascii=False, indent=2)+'\n')
    print('MOT-QA restored, all selected files match the backup manifest', flush=True)


def main():
    if '--toc-already-restored' in sys.argv:
        # The initial pass completed TOC and validated each copied file before
        # the archive transfer strategy changed. Rebuild its local receipt.
        for parent, dirs, files in os.walk(TOC, followlinks=False):
            for name in dirs + files:
                p = Path(parent)/name
                if p.is_symlink():
                    links.append(dict(path=str(p), target=str(p.readlink()), exists=p.exists()))
            for name in files:
                p = Path(parent)/name
                if p.is_symlink():
                    continue
                content = p.read_bytes()
                records.append(dict(source=str(TOC_SOURCE/p.relative_to(TOC)), destination=str(p), bytes=len(content), sha256=hashlib.sha256(content).hexdigest(), backup_manifest_verified=False,
                                    verification='Local hash re-recorded; initial TOC source copy already completed and verified'))
        print('Reused completed TOC restoration', flush=True)
    else:
        restore_toc()
    restore_motqa()
    value = dict(status='FILES_RESTORED', local_files=len(records), local_bytes=sum(x['bytes'] for x in records), files=records, nas_links=links)
    (RECOVERY / 'restore_manifest.json').write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k:v for k,v in value.items() if k not in {'files','nas_links'}}), flush=True)


if __name__ == '__main__':
    main()
