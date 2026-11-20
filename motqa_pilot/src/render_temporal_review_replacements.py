"""Render only the three replacement questions; preserve the accepted17 and original packet."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import zipfile

import render_question_review as renderer
from generate_question_review import ROOT, dump, read_jsonl, sha

OUT=ROOT/'results/question_review_replacements'


def main():
    questions=read_jsonl(ROOT/'data/question_review_temporal_replacements_3.jsonl')
    renderer.OUT=OUT
    media={}
    with ThreadPoolExecutor(max_workers=3) as ex:
        futures=[ex.submit(renderer.render_one,q) for q in questions]
        for f in as_completed(futures):
            m=f.result();media[m['qa_id']]=m
            print('MEDIA_DONE',m['qa_id'],flush=True)
    qhash=sha(ROOT/'data/question_review_temporal_replacements_3.jsonl')
    packet={'schema_version':'motqa_complete_question_review_v1','packet_id':'motqa_temporal_replacement3_'+qhash[:16],
            'questions_sha256':qhash,'generated_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
            'questions':questions,'media':media,'explanations':{q['qa_id']:renderer.explanation(q) for q in questions},
            'title_zh':'MOT-QA · 重现先后补审（3题）',
            'intro_zh':'仅补审原第4、5、17题的三个替换设计，全部改为比较人物A、B重现的先后时刻。之前17题的通过结果保留，不用重复审核。',
            'scope_zh':'本包只有3道待审替换题，编号保留原题序号。按已锁定的各数据集可见性约定判定重现；每题提供源帧和原片／GT核验片段。未计算人物实际路程。约900题整批仍待构建与过滤。',
            'export_filename':'question_review_replacement_result.json'}
    dump(OUT/'media_manifest.json',media)
    template=(ROOT/'src/question_review_template.html').read_text()
    template=template.replace('MOT-QA · 完整推理题中文审阅20题','MOT-QA · 重现先后补审3题').replace('MOT-QA · 完整推理题中文预审（20题）','MOT-QA · 重现先后补审（3题）')
    page=OUT/'打开3题补审.html'
    page.write_text(template.replace('__PAYLOAD__',json.dumps(packet,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')))
    instructions=OUT/'使用说明.txt'
    instructions.write_text('MOT-QA · 3题补审\n\n完整解压ZIP，用系统浏览器打开“打开3题补审.html”，保留media文件夹。\n本包仅包含原第4、5、17题的替换题：比较A、B谁先重新清晰可见。已经通过的17题无需重审。\n每题查看人物参考图、原片/GT核验片段、源帧、答案与依据。标记通过/不通过/不确定，写明备注。\n最后导出 question_review_replacement_result.json 并上传。不要把原20题结果导入此包，题目版本与名单不同。\n\n本批只比较时间先后，不估计人物实际移动距离。MOT17可见性≥0.25的既定约定保持不变，核验依据明确区分重新清晰可见与完全消失。\n')
    bundle=ROOT/'results/motqa_temporal_replacement_review_3_zh_v2.zip'
    with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED) as z:
        z.write(page,'MOTQA_3题重现补审/打开3题补审.html')
        z.write(instructions,'MOTQA_3题重现补审/使用说明.txt')
        for p in sorted((OUT/'media').rglob('*')):
            if p.is_file() and p.suffix in ['.jpg','.mp4']:z.write(p,'MOTQA_3题重现补审/'+str(p.relative_to(OUT)))
    with zipfile.ZipFile(bundle) as z:assert z.testzip() is None
    receipt={'created_at':packet['generated_at'],'status':'WAITING_FOR_USER_REPLACEMENT_REVIEW','packet_id':packet['packet_id'],
             'count':3,'replaces_indices':[4,5,17],'accepted17_unchanged':True,
             'questions_sha256':qhash,'page':str(page),'zip':str(bundle),'zip_bytes':bundle.stat().st_size,'zip_sha256':sha(bundle),
             'video_files':6,'export_filename':packet['export_filename'],'new_model_calls':0,'new_tracker_runs':0,'full900_completed':False}
    dump(OUT/'delivery_receipt.json',receipt)
    print(json.dumps(receipt,ensure_ascii=False))


if __name__=='__main__':main()
