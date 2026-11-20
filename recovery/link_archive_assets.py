#!/usr/bin/env python3
"""Expose large MOT-QA assets from the NAS archive without extracting them locally."""
from pathlib import Path, PurePosixPath
import json

BASE = Path('/data3/liuyeqiang')
RECOVERY = BASE/'TOC_Bench_recovery_20261120'
archive_root = RECOVERY/'motqa_nas_archive/home/user/motqa_pilot'
project = BASE/'motqa_pilot'
manifest = json.loads((BASE/'nas/A800/motqa_pilot_migration_20261113/_control/transfer_manifest.json').read_text())
assert (archive_root/'src/inventory.py').exists(), 'Run mount_assets.sh first'
links = []
for row in manifest['files']:
    rel = PurePosixPath(row['project_relative'])
    if any(part in {'browser_check', 'firefox_profile'} or part.startswith('exported_TEST_ONLY') for part in rel.parts):
        continue
    dest = project/str(rel)
    if dest.exists() or dest.is_symlink():
        continue
    target = archive_root/str(rel)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.symlink_to(target)
    links.append(dict(path=str(dest), target=str(target), bytes=row['bytes']))
(RECOVERY/'motqa_archive_asset_links.json').write_text(json.dumps(dict(archive_root=str(archive_root), links=links), ensure_ascii=False, indent=2)+'\n')
print(f'{len(links)} MOT-QA assets linked to the read-only NAS archive; no asset payload copied')
