#!/usr/bin/env python3
"""Copy the restored research sources into the MOT-QA Git checkout.

Only regular local files are copied. NAS symlinks and bulk assets are never
followed. Run with --apply after reviewing the selection summary.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import re
import shutil

BASE = Path('/data3/liuyeqiang')
RECOVERY = BASE / 'TOC_Bench_recovery_20261120'
DESTINATION = BASE / 'MOT-QA'
PROJECTS = ('toc_phase0', 'motqa_pilot')
SKIP_DIRECTORIES = {
    '.git', '__pycache__', '.pytest_cache', '.mypy_cache', 'node_modules',
    '.venv', 'env', 'env_masa', 'browser_check', 'firefox_profile',
}
SKIP_SUFFIXES = {
    '.zip', '.tar', '.gz', '.xz', '.bz2', '.7z', '.whl', '.deb', '.sqlite',
    '.pyc', '.pyo', '.so', '.o', '.a', '.npy', '.npz', '.pkl', '.pickle',
    '.pt', '.pth', '.bin', '.safetensors', '.onnx', '.ckpt',
    '.mp4', '.avi', '.mov', '.mkv', '.mp3', '.wav',
    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.ico', '.pdf', '.log',
}
SECRET_RULES = {
    'github_token': re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})'),
    'huggingface_token': re.compile(rb'hf_[A-Za-z0-9]{30,}'),
    'openai_key': re.compile(rb'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{40,}'),
    'private_key': re.compile(rb'-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----'),
    'aws_access_key': re.compile(rb'\bAKIA[A-Z0-9]{16}\b'),
    'credential_in_url': re.compile(rb'https?://[^\s/:@]+:[^\s/@]+@'),
}


def reason_to_skip(project: str, relative: Path, size: int) -> str | None:
    if any(p in SKIP_DIRECTORIES or 'browser_check' in p or p.startswith('exported_TEST_ONLY')
           for p in relative.parts):
        return 'runtime_or_browser_test'
    if relative.name in {'.env', '.netrc', '.git-credentials', 'id_rsa', 'id_ed25519'} \
            or relative.suffix in {'.pem', '.key'}:
        return 'credential_filename'
    if relative.suffix.lower() in SKIP_SUFFIXES:
        return 'bulk_binary_archive_or_runtime_log'
    if project == 'toc_phase0' and relative.parts[0] in {'models', 'data', 'frames_cache', 'tracks'}:
        return 'nas_model_or_dataset'
    if project == 'motqa_pilot':
        if relative.parts[:2] in {('data', 'stage2'), ('data', 'stage2_appearance')}:
            return 'derived_frame_or_track_cache'
        if any(p == 'annotations_v1' for p in relative.parts):
            return 'upstream_annotation_dataset'
        if relative.parts[0] == 'sources' and relative.name.endswith(('_paper.html', '_paper.txt')):
            return 'cached_external_paper'
    if size > 20_000_000:
        return 'larger_than_20MB'
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    selected = []
    excluded = collections.Counter()
    violations = []
    for project in PROJECTS:
        root = BASE / project
        for current, directories, files in os.walk(root, followlinks=False):
            keep = []
            for name in sorted(directories):
                p = Path(current) / name
                if p.is_symlink():
                    excluded[f'{project}:nas_symlink'] += 1
                elif name in SKIP_DIRECTORIES or 'browser_check' in name:
                    excluded[f'{project}:runtime_or_browser_test_directory'] += 1
                else:
                    keep.append(name)
            directories[:] = keep
            for name in sorted(files):
                source = Path(current) / name
                if source.is_symlink():
                    excluded[f'{project}:nas_symlink'] += 1
                    continue
                if not source.is_file():
                    continue
                relative = source.relative_to(root)
                size = source.stat().st_size
                reason = reason_to_skip(project, relative, size)
                if reason:
                    excluded[f'{project}:{reason}'] += 1
                    continue
                data = source.read_bytes()
                for label, pattern in SECRET_RULES.items():
                    for match in pattern.finditer(data):
                        violations.append({
                            'path': f'{project}/{relative.as_posix()}',
                            'line': data[:match.start()].count(b'\n') + 1,
                            'rule': label,
                        })
                selected.append({
                    'path': f'{project}/{relative.as_posix()}',
                    'source': str(source), 'bytes': size,
                    'sha256': hashlib.sha256(data).hexdigest(),
                })
    summary = {
        'selected_files': len(selected),
        'selected_bytes': sum(r['bytes'] for r in selected),
        'projects': {
            p: {'files': sum(r['path'].startswith(p + '/') for r in selected),
                'bytes': sum(r['bytes'] for r in selected if r['path'].startswith(p + '/'))}
            for p in PROJECTS
        },
        'excluded_counts': dict(excluded),
        'secret_pattern_findings': violations,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if violations:
        raise SystemExit('Review secret-pattern findings before publishing; no files copied.')
    if not args.apply:
        return
    if not (DESTINATION / '.git').is_dir():
        raise SystemExit(f'Expected cloned repository at {DESTINATION}')
    for row in selected:
        source, destination = Path(row['source']), DESTINATION / row['path']
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_symlink():
            raise SystemExit(f'Destination must be regular: {destination}')
        if destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest() != row['sha256']:
            raise SystemExit(f'Destination differs; inspect before updating: {destination}')
        shutil.copyfile(source, destination)
        destination.chmod(0o755 if source.stat().st_mode & 0o111 else 0o644)
    metadata = DESTINATION / 'docs'
    metadata.mkdir(exist_ok=True)
    manifest = {
        'date': '2026-11-20',
        'repository': 'https://github.com/LYQ1107/MOT-QA',
        'source_projects': [str(BASE / p) for p in PROJECTS],
        'source_files_unchanged': True,
        'original_conversation_published': False,
        'nas_symlinks_followed': False,
        **summary, 'files': selected,
    }
    (metadata / 'source_manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    source_history = RECOVERY / 'TOC-Bench到MOT-QA_研究历程与方法全景_20261120.txt'
    shutil.copyfile(source_history, metadata / 'research_history_20261120.txt')
    recovery = DESTINATION / 'recovery'
    recovery.mkdir(exist_ok=True)
    for name in [
        'restore_projects.py', 'verify_recovery.py', 'build_archive_index.py',
        'check_motqa_data.py', 'link_archive_assets.py', 'mount_assets.sh',
        'python_a100.sh', 'verification_report.json', 'archive_verification.json',
        'motqa_raw_dataset_check.json', 'COMPLETION.json',
    ]:
        shutil.copyfile(RECOVERY / name, recovery / name)
    tools = DESTINATION / 'tools'
    tools.mkdir(exist_ok=True)
    shutil.copyfile(Path(__file__), tools / Path(__file__).name)
    print('Snapshot prepared; original restored projects and NAS assets were not modified.')


if __name__ == '__main__':
    main()
