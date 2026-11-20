"""Inventory the public QA release and video manifest without fetching videos."""
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path

from load_bench import ROOT, load_bench


def csv_counts(path, header, rows):
    with path.open('w', newline='') as output:
        writer = csv.writer(output)
        writer.writerow(header)
        writer.writerows(rows)


def main():
    items = load_bench()
    projection = [json.loads(line) for line in (ROOT / 'data/toc_bench/data/test.jsonl').read_text().splitlines()]
    videos = json.loads((ROOT / 'data/toc_bench/video_manifest.json').read_text())
    by_id = {item['qa_id']: item for item in projection}
    assert len(items) == len(by_id) == len(projection) == 2323
    assert len({item['qa_id'] for item in items}) == len(items)
    differences = {}
    for item in items:
        projected = by_id[item['qa_id']]
        differing = [key for key in item if projected.get(key) != item[key]]
        if differing:
            differences[item['qa_id']] = differing
    assert not differences, differences
    paths = {video['rfilename'] for video in videos}
    missing = sorted({item['video_path'] for item in projection} - paths)
    assert not missing, missing

    dims = Counter(item['metadata']['dim'] for item in items)
    formats = Counter(item['format'] for item in items)
    matrix = Counter((item['metadata']['dim'], item['format']) for item in items)
    top_fields = Counter(key for item in items for key in item)
    metadata_fields = Counter(key for item in items for key in item['metadata'])
    keys = Counter()

    def inspect(value, prefix=''):
        if isinstance(value, dict):
            for key, child in value.items():
                path = f'{prefix}.{key}' if prefix else key
                keys[path] += 1
                inspect(child, path)
        elif isinstance(value, list):
            for child in value:
                inspect(child, prefix + '[]')

    for item in items:
        inspect(item)
    sources = defaultdict(lambda: dict(qa_count=0, video_count=0, bytes=0))

    def source(video_id):
        return 'perception_test' if video_id.startswith('perception_test_') else video_id.split('_', 1)[0]

    for item in items:
        sources[source(item['video_id'])]['qa_count'] += 1
    for video in videos:
        bucket = sources[source(Path(video['rfilename']).stem)]
        bucket['video_count'] += 1
        bucket['bytes'] += video['size']
    trajectory_keys = {key: count for key, count in keys.items()
                       if any(token in key.lower() for token in ('bbox', 'box', 'track', 'trajectory', 'timestamp', 'frame'))}
    examples = [next(item for item in projection if item['format'] == fmt)
                for fmt in ['mcq_4', 'numerical', 'ordering_3']]
    result = dict(qa_count=len(items), unique_videos=len({item['video_id'] for item in items}),
                  canonical_and_jsonl_fields_equal=True, missing_video_paths=missing,
                  dimensions=dict(dims), formats=dict(formats),
                  five_tracking_dimensions_total=sum(dims[dim] for dim in [
                      'event_count', 'reappear_identity', 'reappear_or_disappear',
                      'cross_object_order', 'event_ordering']),
                  top_level_fields=dict(top_fields), metadata_fields=dict(metadata_fields),
                  trajectory_related_field_names=trajectory_keys,
                  all_item_field_paths=dict(keys), source_counts=dict(sources),
                  video_files=len(videos), video_bytes=sum(video['size'] for video in videos),
                  hallucination_variants=dict(Counter(str(item['metadata'].get('hallucination')) for item in items)))
    output = ROOT / 'results'
    (output / 'benchmark_inventory.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    (output / 'qa_examples.json').write_text(json.dumps(examples, indent=2, ensure_ascii=False) + '\n')
    csv_counts(output / 'dimension_counts.csv', ['dimension', 'count'], sorted(dims.items()))
    csv_counts(output / 'format_counts.csv', ['format', 'count'], sorted(formats.items()))
    format_names = sorted(formats)
    csv_counts(output / 'dimension_format_counts.csv', ['dimension', *format_names, 'total'],
               [[dim, *[matrix[dim, fmt] for fmt in format_names], dims[dim]] for dim in sorted(dims)])
    print(json.dumps({key: result[key] for key in ['qa_count', 'unique_videos', 'dimensions', 'formats',
                      'trajectory_related_field_names', 'source_counts', 'video_bytes']}, indent=2))


if __name__ == '__main__':
    main()
