#!/usr/bin/env python3
"""Build a local read-only archive index from TAR headers read on the NAS host."""
from pathlib import Path
import json
import stat
from ratarmountcore.SQLiteIndex import SQLiteIndex

ROOT = Path(__file__).resolve().parent
ARCHIVE = Path('/data3/liuyeqiang/nas/A800/motqa_pilot_migration_20261113/motqa_pilot_code_results.tar')
members = [json.loads(line) for line in (ROOT/'motqa_tar_members.jsonl').read_text().splitlines()]
manifest = json.loads((ARCHIVE.parent/'_control/transfer_manifest.json').read_text())
lookup = {m['name'].lstrip('./'): m for m in members}
assert len(members) == manifest['total_files'] == 28112
for item in manifest['files']:
    assert lookup[item['relative_path']]['size'] == item['bytes'], item['relative_path']

index = SQLiteIndex(indexFilePath=str(ROOT/'motqa_archive.remote-index.sqlite'), archiveFilePath=str(ARCHIVE), backendName='SQLiteIndexedTar')
index.open_writable()
records = []
for m in members:
    path, name = SQLiteIndex.normpath(m['name']).rsplit('/', 1)
    kind = b'5' if stat.S_ISDIR(m['mode']) else b'2' if stat.S_ISLNK(m['mode']) else b'0'
    records.append((path, name, m['offset'], m['offset_data'], m['size'], m['mtime'], m['mode'], kind, m['linkname'], m['uid'], m['gid'], False, m['sparse'], False, 0))
index.set_file_infos(records)
index.finalize()
index.store_metadata('{}', str(ARCHIVE))
index.store_metadata_key_value('isGnuIncremental', '0')
index.close()
print(f'Indexed {len(members)} archive members; all names and sizes match the backup manifest')
