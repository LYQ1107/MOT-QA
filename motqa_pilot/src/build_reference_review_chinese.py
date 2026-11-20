"""Add faithful Chinese display text without changing locked review inputs."""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import hashlib
import json
import re
import shutil
import zipfile

ROOT = Path('/home/user/motqa_pilot')
OUT = ROOT / 'results/review'
ENTRY = 'reference_review_zh_v2.html'
BUNDLE = 'reference_review_zh_v2.zip'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    now = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
    selection = OUT / 'reference_review_selection_locked.json'
    config = ROOT / 'results/generation_config_locked.json'
    visibility = ROOT / 'results/visibility_convention.json'
    locked_hashes = {str(p): sha(p) for p in [selection, config, visibility]}
    packet = json.loads(selection.read_text())
    legacy = OUT / 'history/compact_delivery_revision/reference_review_embedded_v1.html'
    payload = json.loads(re.search(
        r'<script id="review-payload" type="application/json">([\s\S]*?)</script>',
        legacy.read_text()).group(1))
    translation_path = ROOT / 'src/reference_review_translations_zh.json'
    translation = json.loads(translation_path.read_text())
    texts = translation['translations']
    assert len(payload['cases']) == len(packet['cases']) == 154
    assert len(texts) == 81
    assert set(texts) == {c['text'] for c in payload['cases']}
    assert all(texts.values())
    assert payload['meta']['selection_sha256'] == sha(selection)
    assert packet['generation_config_sha256'] == sha(config)
    assert [c['review_id'] for c in packet['cases']] == [c['review_id'] for c in payload['cases']]
    views, assets = {}, {}
    for c in packet['cases']:
        views[c['review_id']] = {
            'other_times': [x['time_s'] for x in c['other_target_views']],
            'neighbor_count': len(c['similar_people']),
            'prior': c['prior_observation'],
            'text_zh': texts[c['text']],
            'source_kind_zh': translation['source_labels'][c['source_kind']],
        }
        paths = ([c['full_frame']] + [x['path'] for x in c['other_target_views']]
                 + [x['path'] for x in c['similar_people']])
        for source in paths:
            path = Path(source)
            relative = path.relative_to(OUT)
            assert relative.parts[0] == 'images'
            assets[str(relative)] = path
    payload['views'] = views
    packed = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    template = (ROOT / 'src/reference_review_zh_template.html').read_text()
    document = (template.replace('__GENERATED_AT__', packet['generated_at'])
                .replace('__TRANSLATED_AT__', now)
                .replace('__SELECTION_SHA__', sha(selection))
                .replace('__REVIEW_PAYLOAD__', packed))
    assert len(document.encode()) < 256 * 1024
    assert 'data:image/' not in document
    history = OUT / 'history/chinese_display_revision'
    history.mkdir(parents=True, exist_ok=True)
    primary = OUT / 'reference_review.html'
    if not (history / 'reference_review_compact_en.html').exists():
        shutil.copyfile(primary, history / 'reference_review_compact_en.html')
    delivery_history = OUT / 'history/chinese_download_fix'
    delivery_history.mkdir(parents=True, exist_ok=True)
    for name in ['reference_review.html', 'reference_review_zh.html',
                 'reference_review_browser.zip', 'reference_review_offline.zip',
                 'reference_review_zh.zip', 'chinese_delivery_receipt.json', 'handoff_receipt.json']:
        previous = OUT / name
        if previous.exists() and not (delivery_history / name).exists():
            shutil.copyfile(previous, delivery_history / name)
    page = OUT / ENTRY
    page.write_text(document)
    primary.write_text(document)
    (OUT / 'reference_review_zh.html').write_text(document)
    instructions = OUT / 'OPEN_CHINESE_REVIEW.txt'
    instructions.write_text(
        'MOT-QA Pilot · 中文审阅 v2\n\n'
        '1. 下载 reference_review_zh_v2.zip，选择“全部解压”。\n'
        '2. 进入解压后的 reference_review 文件夹，用 Chrome、Edge 或 Firefox 打开 reference_review_zh_v2.html。\n'
        '   页面顶部应显示“中文审阅 v2”，第一条人物描述以“穿带粉红色抽绳的黑色拉链连帽衫”开头。\n'
        '3. 网页文件与 images 文件夹必须保持同级，不要只从压缩包中单独打开网页。\n'
        '4. 描述优先显示中文；可展开“英文原文（核对用）”。中文保留原文的笼统或可疑细节，由你判断准确性和唯一性。\n'
        '5. 每页5条，点击图片可放大，支持中文/英文搜索。标记“通过 / 不通过 / 不确定”，可填写中文备注。\n'
        '6. 以前已导出的 reference_review_result.json 可用“导入继续”恢复，无须重新审阅已完成项。\n'
        '7. 可随时导出备份。导出始终包含全部154条，不受当前页或筛选影响。完成后上传 reference_review_result.json。\n\n'
        '主区137条，补充区17条；未选择项不算通过。名单、图片、时刻、原描述和通过门槛沿用已锁定版本。\n'
        '本页是指代描述复核。之后的完整推理问答有单独的人工检查流程。\n'
        '全部内容在本地浏览器运行，无需服务器；聊天内网页预览未作为打开方式验证。\n')
    bundle = OUT / BUNDLE
    entries = [ENTRY, 'reference_review_zh.html', 'reference_review.html']
    with zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED) as archive:
        for entry in entries:
            archive.write(page, 'reference_review/' + entry)
        archive.write(instructions, 'reference_review/OPEN_CHINESE_REVIEW.txt')
        for relative, path in sorted(assets.items()):
            archive.write(path, 'reference_review/' + relative)
    with zipfile.ZipFile(bundle) as archive:
        assert archive.testzip() is None
        for entry in entries:
            assert archive.read('reference_review/' + entry) == page.read_bytes()
        for relative, path in assets.items():
            assert hashlib.sha256(archive.read('reference_review/' + relative)).hexdigest() == sha(path)
    aliases = ['reference_review_zh.zip', 'reference_review_browser.zip', 'reference_review_offline.zip']
    for name in aliases:
        shutil.copyfile(bundle, OUT / name)
    assert all(sha(OUT / name) == sha(bundle) for name in aliases)
    assert all(sha(Path(path)) == digest for path, digest in locked_hashes.items())
    receipt = {
        'generated_at': now, 'language': 'zh-CN', 'delivery_version': 'Chinese display v2',
        'html': str(page), 'html_bytes': page.stat().st_size, 'html_sha256': sha(page),
        'zip': str(bundle), 'zip_bytes': bundle.stat().st_size, 'zip_sha256': sha(bundle),
        'zip_aliases': aliases, 'zip_aliases_identical': True, 'html_entries_all_chinese': entries,
        'translation_source': str(translation_path), 'translation_sha256': sha(translation_path),
        'translated_cases': 154, 'unique_source_descriptions': len(texts),
        'packet_id': packet['packet_id'], 'locked_files_sha256': locked_hashes,
        'images': len(assets), 'images_byte_identical': True,
        'canonical_english_metadata_unchanged': True, 'export_schema_unchanged': True,
        'english_originals_collapsed': True, 'translation_policy': translation['policy_zh'],
        'qa_generated': 0, 'new_model_calls': 0, 'new_tracker_runs': 0,
    }
    (OUT / 'chinese_delivery_receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == '__main__':
    main()
