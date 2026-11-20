"""Fix delivery size without changing any locked review item or source image."""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import re
import shutil
import zipfile

ROOT=Path('/home/user/motqa_pilot')
OUT=ROOT/'results/review'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    now=datetime.now().astimezone().isoformat()
    selection=OUT/'reference_review_selection_locked.json'
    packet=json.loads(selection.read_text())
    path=OUT/'reference_review.html'
    history=OUT/'history/compact_delivery_revision'
    history.mkdir(parents=True,exist_ok=True)
    legacy=history/'reference_review_embedded_v1.html'
    if not legacy.exists():
        path.rename(legacy)
    old=legacy.read_text()
    payload=json.loads(re.search(r'<script id="review-payload" type="application/json">([\s\S]*?)</script>',old).group(1))
    assert len(payload['cases'])==154
    assert payload['meta']['selection_sha256']==sha(selection)
    assert packet['generation_config_sha256']==sha(ROOT/'results/generation_config_locked.json')
    views={}
    assets={}
    for c in packet['cases']:
        views[c['review_id']]={
            'other_times':[x['time_s'] for x in c['other_target_views']],
            'neighbor_count':len(c['similar_people']),'prior':c['prior_observation'],
        }
        paths=[c['full_frame']]+[x['path'] for x in c['other_target_views']]+[x['path'] for x in c['similar_people']]
        for source in paths:
            p=Path(source);relative=p.relative_to(OUT)
            assert relative.parts[0]=='images'
            assets[str(relative)]=p
    payload['views']=views
    packed=json.dumps(payload,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    template=(ROOT/'src/reference_review_compact_template.html').read_text()
    document=(template.replace('__GENERATED_AT__',packet['generated_at'])
              .replace('__SELECTION_SHA__',sha(selection)).replace('__REVIEW_PAYLOAD__',packed))
    assert len(document.encode())<256*1024
    assert 'data:image/' not in document
    path.write_text(document)
    instructions=OUT/'OPEN_IN_BROWSER.txt'
    instructions.write_text(
        'MOT-QA Pilot 外观复核 · 本地浏览器版本\n\n'
        '1. 下载 reference_review_browser.zip，选择“全部解压”。\n'
        '2. 进入解压后的 reference_review 文件夹，用Chrome、Edge或Firefox打开 reference_review.html。\n'
        '3. reference_review.html 与 images 文件夹必须保持同级；不要只打开压缩包里的单个网页文件。\n'
        '4. 每页5条，可翻页/筛选。图片可点击放大到原分辨率。\n'
        '5. 标记通过/不通过/不确定及备注，可随时导出备份。导出始终包含全部154条，与当前页无关。\n'
        '6. 完成后上传 reference_review_result.json。旧版已导出的JSON可用“导入继续”恢复。\n\n'
        '主区137条+补充17条。全部条目、描述、时刻、图片与审核门槛保持原版；未选择项不算通过。\n'
        '这是本地文件包，不需要启动服务器。聊天内的网页预览不是本次验证的打开方式。\n')
    bundle=OUT/'reference_review_browser.zip'
    with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED) as archive:
        archive.write(path,'reference_review/reference_review.html')
        archive.write(instructions,'reference_review/OPEN_IN_BROWSER.txt')
        for relative,p in sorted(assets.items()):
            archive.write(p,'reference_review/'+relative)
    with zipfile.ZipFile(bundle) as archive:
        assert archive.testzip() is None
        assert archive.read('reference_review/reference_review.html')==path.read_bytes()
        for relative,p in assets.items():
            assert hashlib.sha256(archive.read('reference_review/'+relative)).hexdigest()==sha(p)
    oldzip=OUT/'reference_review_offline.zip'
    if not (history/'reference_review_embedded_v1.zip').exists():
        oldzip.rename(history/'reference_review_embedded_v1.zip')
    shutil.copyfile(bundle,oldzip)
    note={
        'at':now,'reason':'User reported internal visualization error. Prior delivery was a48MiB standalone document; exact in-app error not reproduced. Make a small paginated HTML plus local image files for system browsers.',
        'legacy_html':str(legacy),'legacy_html_bytes':legacy.stat().st_size,'legacy_html_sha256':sha(legacy),
        'html':str(path),'html_bytes':path.stat().st_size,'html_sha256':sha(path),
        'zip':str(bundle),'zip_bytes':bundle.stat().st_size,'zip_sha256':sha(bundle),
        'images':len(assets),'image_bytes_unchanged':True,'page_size':5,
        'selection_sha256':sha(selection),'packet_id':packet['packet_id'],
        'export_case_metadata_unchanged':True,'generation_config_sha256':sha(ROOT/'results/generation_config_locked.json'),
        'qa_generated':0,'new_model_calls':0,'new_tracker_runs':0,
    }
    (OUT/'compact_delivery_receipt.json').write_text(json.dumps(note,ensure_ascii=False,indent=2)+'\n')
    with (ROOT/'research_log.md').open('a') as f:
        f.write(f'\n## Review opening failure: compact offline delivery — {now}\n\n'
                'User could not open original review due to an internal visualization error. Prior Firefox standalone validation did not establish in-app compatibility. '
                'Exact app failure not reproduced; original document48MiB is an avoidable delivery burden. '
                'Archive original HTML/ZIP, preserve locked selection and every image byte, generate <256KiB HTML loading5rows per page plus local images. '
                'Keep packet ID, full154-row export schema and selection hash unchanged; existing exported reviews remain importable. '
                'Validate actual extracted ZIP opening, paging, full-result export and import in a system browser. No QA, model or tracker work.\n')
    print(json.dumps(note,ensure_ascii=False))


if __name__=='__main__':
    main()
