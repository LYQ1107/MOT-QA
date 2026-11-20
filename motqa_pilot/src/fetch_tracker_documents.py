"""Archive only official tracker documentation/configuration. Never fetch weights."""
import json
import os
from pathlib import Path
from fetch_sources import fetch

ROOT = Path('/home/user/motqa_pilot')


def main():
    for key in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY'):
        os.environ.pop(key, None)
    (ROOT/'sources/trackers').mkdir(exist_ok=True)
    registry = {}
    tasks = {
        'bytetrack': ('FoundationVision/ByteTrack', ['README.md', 'LICENSE', 'tools/mix_data_ablation.py',
                       'tools/convert_mot17_to_coco.py', 'exps/example/mot/yolox_x_ablation.py']),
        'ocsort': ('noahcao/OC_SORT', ['README.md', 'LICENSE', 'docs/MODEL_ZOO.md', 'docs/GET_STARTED.md',
                                    'trackers/ocsort_tracker/ocsort.py']),
        'mixsort': ('MCG-NJU/MixSort', ['README.md', 'LICENSE', 'exps/example/mot/yolox_x_sportsmot.py',
                                     'tools/convert_sportsmot_to_coco.py',
                                     'MixViT/experiments/mixformer_deit/baseline.yaml']),
        'dance': ('DanceTrack/DanceTrack', ['README.md', 'LICENSE', 'ByteTrack/README.md',
                     'ByteTrack/exps/example/dancetrack/yolox_x.py', 'tools/convert_dance_to_coco.py']),
    }
    for key, (repo, paths) in tasks.items():
        info = json.loads(fetch(f'trackers/{key}_repo.json', f'https://api.github.com/repos/{repo}'))
        commits = json.loads(fetch(f'trackers/{key}_commits.json',
                                   f'https://api.github.com/repos/{repo}/commits?per_page=1'))
        revision = commits[0]['sha']
        registry[key] = {'repository': 'https://github.com/'+repo, 'revision': revision,
                         'default_branch': info['default_branch'], 'files': []}
        for path in paths:
            url = f'https://raw.githubusercontent.com/{repo}/{revision}/{path}'
            name = f'trackers/{key}_' + path.replace('/', '__')
            content = fetch(name, url)
            registry[key]['files'].append({'path': path, 'url': url, 'local': str(ROOT/'sources'/name),
                                           'bytes': len(content)})
    # Metadata only: no resolve/download URLs or model tensors requested.
    fetch('trackers/dancetrack_hf_file_metadata.json',
          'https://huggingface.co/api/datasets/noahcao/dancetrack/revision/main?blobs=true')
    (ROOT/'results/review/tracker_official_sources.json').write_text(
        json.dumps(registry, ensure_ascii=False, indent=2)+'\n')
    print('Official tracker document/configuration download complete; no weights requested.', flush=True)


if __name__ == '__main__':
    main()
