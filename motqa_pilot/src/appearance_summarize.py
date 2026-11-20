"""Complete ID ledger, explicitly point-bound resources, review HTML and report."""
import argparse
from collections import Counter, defaultdict
import hashlib
import html
import json
import os
from pathlib import Path
import random
import socket
import subprocess
import textwrap
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
from appearance_common import ROOT, RES, DATA, now, sha, read, rows, write, write_rows


def classify(u,g,v,l):
    if not g['check']['valid']:
        return 'unusable_or_invalid_phrase'
    if not u['crop_complete']:
        return 'insufficient_disjoint_crops'
    assert v is not None,u['unit_key']
    if not v['check']['valid']:
        return 'global_parse_failure'
    if not v['check']['passed']:
        return 'global_ambiguous' if v['check']['uncertain_gt_ids'] or len(v['check']['matched_gt_ids'])>1 else 'global_wrong_or_missing_match'
    if not u['anchor']:
        return 'no_anchor_with_future_3s'
    if not u['anchor']['geometric_quality_pass']:
        return 'anchor_quality_failed'
    assert l is not None,u['unit_key']
    if not l['check']['valid']:
        return 'local_parse_failure'
    if not l['check']['passed']:
        return 'local_ambiguous' if l['check']['uncertain_gt_ids'] or len(l['check']['matched_gt_ids'])>1 else 'local_wrong_or_missing_match'
    return 'auto_pass'


def assemble():
    units = rows(RES/'crop_manifest.jsonl')
    assert len(units)==273
    old = [r for r in read(ROOT/'results/stage2/appearance_coverage_by_sequence.json') if r['dataset']=='DanceTrack']
    old_ids = {(r['sequence'],tid) for r in old for tid in r['covered_target_ids']}
    ledger,resources,raw = [],[],[]
    for u in units:
        ident = u['unit_key']
        paths = {p:RES/'raw'/p/f'{ident}.json' for p in ['generate','blind_match','reference_instant_match']}
        g = read(paths['generate'])
        v = read(paths['blind_match']) if paths['blind_match'].exists() else None
        l = read(paths['reference_instant_match']) if paths['reference_instant_match'].exists() else None
        raw += [r for r in (g,v,l) if r is not None]
        status = classify(u,g,v,l)
        r = {'unit_key':ident,'dataset':u['dataset'],'source_split':'val','sequence':u['sequence'],'gt_id':u['gt_id'],
             'phrase':g['check']['phrase'],'generation':g['check'],'global_match':v['check'] if v else None,
             'local_match':l['check'] if l else None,'anchor':u['anchor'],'status':status,'auto_pass':status=='auto_pass',
             'previous_annotation_unique_coverage':(u['sequence'],u['gt_id']) in old_ids,
             'raw_paths':{p:str(path) for p,path in paths.items() if path.exists()},
             'human_review_status':'not yet reviewed; VLM consistency is not a human uniqueness guarantee'}
        ledger.append(r)
        if status=='auto_pass':
            a = u['anchor']
            rid = 'vlm_'+hashlib.sha256((ident+'|'+r['phrase']+'|'+str(a['frame_id_1based'])).encode()).hexdigest()[:16]
            resources.append({'reference_id':rid,'dataset':'DanceTrack','sequence':u['sequence'],'source_split':'val',
                'reference_type':'appearance','text':r['phrase'],'target_ids':[u['gt_id']],
                'frame_start':a['frame_id_1based'],'frame_end':a['frame_id_1based'],'reference_frame':a['frame_id_1based'],
                't_ref_s':a['time_s'],'reference_frames':1,'with_future_3s_frames':1,
                'recommended_binding_text':f'{r["phrase"]} at {a["time_s"]:.3f} s',
                'temporal_validity':'one verified reference instant only; not an interval-wide claim',
                'source':'model_generated_gt_crops_with_heldout_and_local_same_model_validation',
                'model':'Qwen/Qwen3-VL-32B-Instruct','raw_paths':r['raw_paths'],
                'protocol_sha256':sha(RES/'protocol_locked.json'),'prompts_sha256':sha(RES/'prompts_locked.json'),
                'inference_policy_sha256':sha(RES/'inference_policy_locked.json'),
                'status':'MODEL_VALIDATED_CANDIDATE_PENDING_USER_REVIEW',
                'license':'DanceTrack annotations CC BY 4.0; source videos non-commercial research restrictions; model Apache-2.0'})
    assert len(ledger)==len({r['unit_key'] for r in ledger})==273
    newids = {(r['sequence'],r['gt_id']) for r in ledger if r['auto_pass']}
    union = old_ids|newids
    phrase_groups = defaultdict(list)
    for r in ledger:
        if r['phrase']:
            phrase_groups[(r['sequence'],' '.join(r['phrase'].casefold().split()))].append(r)
    duplicates = [{'sequence':seq,'normalized_phrase':phrase,'gt_ids':[r['gt_id'] for r in group],
                   'auto_pass_gt_ids':[r['gt_id'] for r in group if r['auto_pass']]}
                  for (seq,phrase),group in phrase_groups.items() if len(group)>1]
    conflicts = [g for g in duplicates if len(g['auto_pass_gt_ids'])>1]
    write(RES/'duplicate_phrase_audit.json',{'at':now(),'duplicate_groups':duplicates,
         'contradictory_automatic_unique_groups':conflicts,
         'handling':'Report any contradiction; do not silently reinterpret independent matching outputs or repair descriptions.'})
    perseq = []
    for seq in sorted({u['sequence'] for u in units}):
        group = [r for r in ledger if r['sequence']==seq]
        original = sorted(t for s,t in old_ids if s==seq)
        supplemented = sorted(t for s,t in newids if s==seq)
        merged = sorted(t for s,t in union if s==seq)
        perseq.append({'sequence':seq,'GT_IDs':len(group),'old_annotation_unique_IDs':original,
                       'new_model_validated_IDs':supplemented,'mixed_candidate_union_IDs':merged,
                       'still_uncovered_IDs':[r['gt_id'] for r in group if r['gt_id'] not in merged],
                       'statuses':dict(Counter(r['status'] for r in group))})
    words = [len(r['phrase'].split()) for r in ledger if r['phrase']]
    stage_counts = Counter(r['phase'] for r in raw)
    finish = Counter(r['response']['choices'][0].get('finish_reason') for r in raw)
    stage_seconds = defaultdict(list)
    for r in raw:
        stage_seconds[r['phase']].append(r['seconds'])
    summary = {'at':now(),'videos':25,'IDs':273,'generation_outputs':stage_counts['generate'],
        'valid_phrases':sum(r['generation']['valid'] for r in ledger),'statuses':dict(Counter(r['status'] for r in ledger)),
        'global_pass_IDs':sum(bool(r['global_match'] and r['global_match']['passed']) for r in ledger),
        'model_validated_point_references':len(resources),'model_validated_IDs':len(newids),
        'model_validated_videos':len({s for s,t in newids}),'old_annotation_unique_IDs':len(old_ids),
        'old_annotation_unique_videos':len({s for s,t in old_ids}),'overlap_IDs':len(old_ids&newids),
        'newly_covered_IDs':len(newids-old_ids),'mixed_candidate_union_IDs':len(union),
        'mixed_candidate_union_videos':len({s for s,t in union}),'still_uncovered_IDs':273-len(union),
        'warning':'Original annotation uniqueness and new same-model visual validation have different evidence strength; their union is not fully human-verified. Point references are not unique interval counts or independent QA counts.',
        'raw_calls':len(raw),'calls_by_phase':dict(stage_counts),'finish_reasons':dict(finish),
        'duplicate_phrase_groups':len(duplicates),'contradictory_auto_unique_phrase_groups':len(conflicts),
        'tokens':{k:sum(r['response'].get('usage',{}).get(k,0) for r in raw) for k in ['prompt_tokens','completion_tokens','total_tokens']},
        'prompt_tokens_max':max(r['response'].get('usage',{}).get('prompt_tokens',0) for r in raw),
        'request_seconds':{p:{'sum':sum(v),'median':float(np.median(v)),'p95':float(np.percentile(v,95)),'max':max(v)} for p,v in stage_seconds.items()},
        'phrase_words':{'median':float(np.median(words)) if words else 0,'max':max(words) if words else 0},
        'total_retained_raw_images_sha256_verified':all(all(sha(Path(p))==h for p,h in zip(r['image_paths'],r['image_sha256'])) for r in raw)}
    write_rows(RES/'description_ledger.jsonl',ledger)
    write_rows(RES/'reference_resources_supplement.jsonl',resources)
    write(RES/'coverage_by_sequence.json',perseq)
    write(RES/'summary.json',summary)
    return units,ledger,resources,summary


def review(units,ledger):
    path = RES/'visual_review_selection_locked.json'
    if path.exists():
        selection = read(path)['units']
    else:
        rng = random.Random(42)
        selected = []
        for seq in sorted({r['sequence'] for r in ledger}):
            candidates = sorted([r for r in ledger if r['sequence']==seq and r['auto_pass']],key=lambda r:r['unit_key'])
            if not candidates:
                candidates = sorted([r for r in ledger if r['sequence']==seq],key=lambda r:r['unit_key'])
            selected.append(rng.choice(candidates)['unit_key'])
        rejects = sorted([r['unit_key'] for r in ledger if not r['auto_pass'] and r['unit_key'] not in selected])
        selected += rng.sample(rejects,min(5,len(rejects)))
        selection = selected
        write(path,{'locked_at':now(),'seed':42,'selection_method':'one deterministic accepted ID/video if any, otherwise one generated ID; plus up to5 rejected IDs',
                    'units':selected,'not_a_population_error_sample':True})
        (RES/'visual_review_selection_locked.sha256').write_text(f'{sha(path)}  {path}\n')
    output = RES/'visual_review'
    output.mkdir(exist_ok=True)
    unitmap = {u['unit_key']:u for u in units}
    rowmap = {r['unit_key']:r for r in ledger}
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',18)
    cards = []
    for ident in selection:
        u,r = unitmap[ident],rowmap[ident]
        phrase = r['phrase'] or '(no valid phrase)'
        texts = [ident+' | '+r['status'],phrase]
        if r['global_match']:
            texts.append('Global: '+json.dumps(r['global_match'].get('parsed'),ensure_ascii=False))
        if r['local_match']:
            texts.append('Local: '+json.dumps(r['local_match'].get('parsed'),ensure_ascii=False))
        lines = [line for t in texts for line in textwrap.wrap(t,105)]
        paths = [u['target_image']]+u['global_gallery']['images']
        if u['local_gallery']:
            paths += u['local_gallery']['images']
        thumbs = []
        for p in paths:
            with Image.open(p) as src:
                im = src.convert('RGB')
            im.thumbnail((1200,800),Image.Resampling.LANCZOS)
            thumbs.append(im)
        canvas = Image.new('RGB',(1200,len(lines)*25+15+sum(i.height+10 for i in thumbs)),'white')
        d = ImageDraw.Draw(canvas)
        yy = 5
        for line in lines:
            d.text((8,yy),line,fill='black',font=font)
            yy += 25
        for im in thumbs:
            canvas.paste(im,(0,yy)); yy += im.height+10
        canvas.save(output/(ident+'.jpg'),quality=94)
        galleryhtml = ''.join(f'<figure><img loading="lazy" src="{html.escape(os.path.relpath(p,output))}"><figcaption>{html.escape(Path(p).name)}</figcaption></figure>' for p in paths)
        cards.append('<article id="'+ident+'"><h2>'+html.escape(ident+' | '+r['status'])+'</h2><p><strong>'+html.escape(phrase)+'</strong></p><pre>'+html.escape(json.dumps({k:r[k] for k in ['gt_id','global_match','local_match']},ensure_ascii=False,indent=2))+'</pre>'+galleryhtml+'</article>')
    doc = '<!doctype html><html><head><meta charset="utf-8"><title>DanceTrack appearance review</title><style>body{font:16px sans-serif;margin:24px;max-width:1600px}article{border-top:3px solid #777;margin:30px 0;padding-top:15px}img{max-width:100%;height:auto}pre{white-space:pre-wrap}figure{margin:12px 0}</style></head><body><h1>Stage 2 optional appearance review</h1><p>One sample/video plus rejected examples. Model matching is not a human guarantee; original GT is unchanged. No QA has been generated.</p>'+''.join(cards)+'</body></html>'
    (output/'index.html').write_text(doc)
    print(json.dumps({'review_selection':len(selection),'auto_pass_selected':sum(rowmap[k]['auto_pass'] for k in selection),'path':str(output/'index.html')}),flush=True)


def verify_prior():
    checks = []
    archive = ROOT/'sources/appearance/downloads_log_before_appearance.md'
    archived = archive.read_bytes()
    assert (ROOT/'logs/downloads.md').read_bytes().startswith(archived)
    for name in ['results/stage1_snapshot.sha256','results/stage2/snapshot.sha256']:
        for line in (ROOT/name).read_text().splitlines():
            expected,rel = line.split('  ',1)
            p = ROOT/rel
            actual = sha(archive) if rel=='logs/downloads.md' else sha(p)
            assert actual==expected,(name,rel,actual,expected)
            checks.append({'snapshot':name,'path':rel,'matched':True,'historical_downloads_log_uses_preserved_archive':rel=='logs/downloads.md'})
    write(RES/'prior_artifact_integrity.json',{'at':now(),'files_checked':len(checks),'all_passed':True,
        'append_only_downloads_log_prefix_preserved':True,'log_archive':str(archive),
        'note':'Completed snapshots are unchanged. Their historical logs/downloads.md bytes are verified against the saved archive and exact current-log prefix because new authorized downloads require appending to that log.'})


def finalize(ledger,resources,s):
    notes = read(RES/'visual_review_notes.json')
    selection = read(RES/'visual_review_selection_locked.json')['units']
    assert set(selection)=={r['unit_key'] for r in notes['cases']}
    extra = read(RES/'additional_candidate_review_notes.json')
    extra_selection = read(RES/'additional_candidate_review_locked.json')['units']
    assert set(extra_selection)=={r['unit_key'] for r in extra['cases']}
    allnotes = {c['unit_key']:c for c in notes['cases']+extra['cases']}
    assert len(allnotes)==46
    auto_reviews = {r['unit_key']:allnotes[r['unit_key']] for r in ledger if r['auto_pass']}
    assert len(auto_reviews)==25
    clear_keys = {k for k,c in auto_reviews.items() if c['verdict']=='consistent'}
    clear_rows = [r for r in ledger if r['unit_key'] in clear_keys]
    clear_ids = {(r['sequence'],r['gt_id']) for r in clear_rows}
    prior = read(ROOT/'results/stage2/appearance_coverage_by_sequence.json')
    old_ids = {(r['sequence'],tid) for r in prior if r['dataset']=='DanceTrack' for tid in r['covered_target_ids']}
    cleared_resources = [dict(r,status='AGENT_REVIEWED_CANDIDATE_PENDING_USER_REVIEW',
                         agent_review=auto_reviews[f'{r["sequence"]}__id{r["target_ids"][0]:03d}'])
                         for r in resources if (r['sequence'],r['target_ids'][0]) in clear_ids]
    write_rows(RES/'reference_resources_agent_cleared.jsonl',cleared_resources)
    for r in ledger:
        r['agent_visual_review'] = allnotes.get(r['unit_key'])
        r['human_review_status'] = 'USER_NOT_REVIEWED; agent review attached where present'
        r['agent_cleared_candidate'] = r['unit_key'] in clear_keys
    write_rows(RES/'description_ledger.jsonl',ledger)
    review_summary = {'at':now(),'locked_review_cases':30,'posthoc_additional_review_cases':16,'total_agent_review_cases':46,
        'all_25_automatic_candidates_reviewed':True,'automatic_pass_count_unchanged':25,
        'agent_cleared_candidate_IDs':len(clear_ids),'agent_cleared_candidate_videos':len({seq for seq,tid in clear_ids}),
        'auto_pass_needs_review':len(auto_reviews)-len(clear_ids),'agent_cleared_newly_covered_IDs':len(clear_ids-old_ids),
        'old_annotation_plus_agent_cleared_union_IDs':len(clear_ids|old_ids),
        'old_annotation_plus_agent_cleared_union_videos':len({seq for seq,tid in clear_ids|old_ids}),
        'user_human_approval':False,'posthoc_reason':read(RES/'additional_candidate_review_locked.json')['reason'],
        'warning':'The original30 sample remains unchanged. The extra16 are post-hoc. No model inference, prompt/threshold changes, automatic-score changes, or description repairs. Agent-cleared is still a candidate, not a final QA or final human-certified annotation.'}
    write(RES/'review_summary.json',review_summary)
    reviewed_coverage = []
    for seq in sorted({r['sequence'] for r in ledger}):
        original = {tid for video,tid in old_ids if video==seq}
        cleared = {tid for video,tid in clear_ids if video==seq}
        reviewed_coverage.append({'sequence':seq,'old_annotation_unique_IDs':sorted(original),
            'agent_cleared_new_IDs':sorted(cleared),'mixed_source_union_IDs':sorted(original|cleared)})
    write(RES/'coverage_after_agent_review.json',reviewed_coverage)
    job = read(ROOT/'logs/appearance_job.json')
    assert job['status']=='INFERENCE_COMPLETE_STOPPED_BEFORE_STAGE3' and job['server_terminated']
    assert not (ROOT/'data/candidates.jsonl').exists()
    process_snapshot = subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_memory','--format=csv,noheader,nounits'],text=True)
    gpu_snapshot = subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid,memory.used','--format=csv,noheader,nounits'],text=True)
    remaining = []
    for line in process_snapshot.splitlines():
        pid = int(line.split(',')[1].strip())
        try:
            if os.getpgid(pid)==job['server_pid']:
                remaining.append(line)
        except ProcessLookupError:
            pass
    with socket.socket() as sock:
        endpoint_closed = sock.connect_ex(('127.0.0.1',18031))!=0
    write(RES/'gpu_release_check.json',{'at':now(),'server_pid':job['server_pid'],'endpoint_closed':endpoint_closed,
          'own_compute_processes_remaining':remaining,'all_compute_processes':process_snapshot,'GPU_memory_after_cleanup':gpu_snapshot,
          'foreign_processes_terminated':False})
    assert not remaining and endpoint_closed,'Own service did not fully terminate'
    verify_prior()
    runtime = read(ROOT/'logs/appearance_runtime.json')
    memory = read(ROOT/'logs/appearance_gpu_memory.json')
    weights = read(ROOT/'sources/appearance/download_complete.json')
    perseq = read(RES/'coverage_by_sequence.json')
    flagged = [c for c in allnotes.values() if c['verdict'] not in ['consistent','consistent_rejection']]
    auto_flags = [c for c in flagged if next(r['auto_pass'] for r in ledger if r['unit_key']==c['unit_key'])]
    write(RES/'review_flags.json',{'at':now(),'flagged_cases':flagged,'auto_pass_cases_flagged':auto_flags,
         'handling':'Automated results and frozen rules retained. Flagged automatic candidates require human resolution before later QA use; do not silently repair GT or descriptions.'})
    note_counts = Counter(c['verdict'] for c in notes['cases'])
    # User review page for the entire small auto-pass pool; original30 page is preserved.
    unitmap = {u['unit_key']:u for u in rows(RES/'crop_manifest.jsonl')}
    cards = []
    pagebase = RES/'visual_review'
    for r in sorted([r for r in ledger if r['auto_pass']],key=lambda r:(r['unit_key'] in clear_keys,r['unit_key'])):
        k = r['unit_key']; u = unitmap[k]; n = allnotes[k]
        imgs = [u['target_image']]+u['global_gallery']['images']+u['local_gallery']['images']
        cards.append('<article><h2>'+html.escape(k+' | '+n['verdict'])+'</h2><p><strong>'+html.escape(r['phrase'])+'</strong></p><p>'+html.escape(n['observation'])+'</p><p>Local target label: '+html.escape(next(lab for lab,tid in u['local_gallery']['label_to_gt_id'].items() if tid==r['gt_id']))+'</p>'+''.join('<img loading="lazy" style="max-width:100%;display:block;margin:12px 0" src="'+html.escape(os.path.relpath(p,pagebase))+'">' for p in imgs)+'</article>')
    (pagebase/'all_auto_candidates.html').write_text('<!doctype html><meta charset="utf-8"><title>All25 automatic candidates</title><style>body{font:16px sans-serif;margin:24px;max-width:1400px}article{border-top:3px solid #777;margin-top:32px;padding-top:12px}</style><h1>All25 automatic candidates, with agent review</h1><p>Original locked sample30 plus explicitly post-hoc additional16. Automatic scores unchanged. Suspect descriptions appear first. No QA generated; final user review pending.</p>'+''.join(cards))
    report = f'''# 阶段二补充报告：DanceTrack 外观描述

完成时间：{now()}。独立项目：`{ROOT}`。用户已批准原任务 3.4 节的强视觉模型补充方案。本轮已完成并停下，未进入阶段三。

处理 DanceTrack val 全部 **25 个视频、273 个 GT ID**。每个 ID 均有 3 张生成裁剪和 2 张来自不同帧的校验裁剪；GT、原始图像、原有语言描述与阶段二资源保持原样。模型仅生成外观描述和检查匹配，不生成问答或答案，不运行跟踪器、不训练。

## 数量与覆盖

| 指标 | 结果 |
|---|---:|
| 生成输出 / GT ID | {s['generation_outputs']} / 273 |
| 合法且非空的描述 | {s['valid_phrases']} |
| 同视频全部 ID 的盲匹配唯一通过 | {s['global_pass_IDs']} |
| 通过独立裁剪匹配、固定时刻整帧匹配及几何门槛 | **{s['model_validated_IDs']} 个 ID / {s['model_validated_videos']} 个视频** |
| 新增验证时刻 | {len(resources)}；每个 ID 至多一个，均有后续 ≥3 秒 |
| 原有 Refer-Dance 的标注唯一覆盖 | {s['old_annotation_unique_IDs']} / 273 个 ID，{s['old_annotation_unique_videos']} / 25 视频 |
| 相对原覆盖新增的 ID | {s['newly_covered_IDs']} |
| 原标注候选与新模型候选的去重并集 | {s['mixed_candidate_union_IDs']} / 273 个 ID，{s['mixed_candidate_union_videos']} / 25 视频 |
| 并集仍未覆盖 | {s['still_uncovered_IDs']} 个 ID |
| 全部自动候选追加视觉审阅后无明显疑点 | **{len(clear_ids)} 个 ID / {review_summary['agent_cleared_candidate_videos']} 视频** |
| 自动通过但需用户复核后才能采用 | **{len(auto_flags)} 条** |
| 无明显疑点候选相对旧资源新增 ID | {review_summary['agent_cleared_newly_covered_IDs']} |
| 旧标注候选与无明显疑点新候选去重并集 | {review_summary['old_annotation_plus_agent_cleared_union_IDs']} /273 个 ID，{review_summary['old_annotation_plus_agent_cleared_union_videos']} /25 视频 |

两种来源的证据强度不同：旧资源只做过标注层面的唯一性检查，新资源通过了同一视觉模型的独立帧一致性检查；并集不能称为全部人工验证通过。新增记录仅绑定一个具体 `t_ref`，没有外推成连续唯一可见区间，也不能把它们直接当作独立题数。

最终状态分布：`{json.dumps(s['statuses'],ensure_ascii=False)}`。

## 固定方法

每条 GT 轨迹按时间划为五段，交替选出三张生成图、两张校验图；选帧只使用框面积、出画比例和与其他框的重叠代理量。全部 273 个 ID 的五张图互不复用。8 次选帧使用了预先规定的间距/空分段回退，逐条保留在 crop manifest；不存在少图后静默跳过。

生成图和匿名同视频人物图册用于产生 ≤30 词的英文外观短语，禁止位置、动作、时间或 GT 编号。校验图使用独立匿名顺序，要求模型返回全部匹配者和无法排除者；只有恰好匹配目标且无不确定者才通过。随后在预选的一个真实指代时刻，结合整帧和所有 GT-present 人物裁剪再次匹配。该时刻需剩余 ≥3 秒、框在画面内面积比例 ≥0.95、被其他框覆盖比例 ≤0.35、原框宽 ≥16 且高 ≥48 像素。237 个预选时刻满足几何门槛，4 个 ID 没有剩余3秒的校验帧。

这些是同模型视觉一致性检查，不能代替独立人工判断。统一服装、低分辨率、遮挡及相似发型会导致拒绝或误判；未通过记录和原始回答均完整保留。本轮没有根据输出反复改提示词、补生成细节或调整接收阈值。

本轮预先采用了比原任务“指代时刻唯一”更保守的筛选：先要求在整段视频的全部ID图册中唯一，且每ID只检查一个固定时刻。因此上述覆盖是本轮保守流程取得的候选规模，不能解读成每个未通过ID在任何时刻都不可能唯一指认；未做穷尽时刻搜索。

## 抽查

按锁定方法抽查 {len(notes['cases'])} 条：每个视频一条（有自动通过项时从通过项选），另加5条拒绝项。结果 `{json.dumps(dict(note_counts),ensure_ascii=False)}`。其中9条为自动通过项，发现5条的附加外观细节有疑点。由于通过池仅25条，随后明确登记为**事后追加检查**其余16条；原始30条抽样清单没有修改，没有新增模型推理或放宽规则。共审阅46条，覆盖所有25条自动候选。

全部自动候选中，{len(clear_ids)}条未见明显问题，{len(auto_flags)}条需用户复核。疑点包括：粉色裤腰绳被归到连帽上衣、棒球帽说成渔夫帽、黄色帽标说成黄色帽檐、头发/发饰材质或发髻/马尾混称、白色领部或垂发被说成领结、内搭颜色未获图像支持。生成和校验使用同一个模型，确实发生了重复确认错误细节的情况。另有一条被拒绝项的红发匹配疑似选错人，作为可能的假拒绝单列，不擅自改成通过。

自动通过的25条和原始回答保留不变；无明显疑点的{len(clear_ids)}条另存 `reference_resources_agent_cleared.jsonl`，标疑项保留在 `review_flags.json`，后续不得把全部25条直接当作已人工认证资源。这里的人工式观察由智能体完成，最终用户审核仍待完成；原30条是按视频/拒绝情形有意抽取，不能用来估计全273条描述的总体错误率。

原30条页面：`{RES/'visual_review/index.html'}`。全部25条自动候选及标疑理由：`{RES/'visual_review/all_auto_candidates.html'}`。逐条观察：`visual_review_notes.json`、`additional_candidate_review_notes.json`。

## 完整性、模型与资源

官方模型：[{runtime['args'][runtime['args'].index('--served-model-name')+1]}](https://huggingface.co/Qwen/Qwen3-VL-32B-Instruct)，BF16，ModelScope 固定 revision `8d6f46b05db6abe0cb3a5ca8c817929cc0fa2d5a`。下载 {len(weights['files'])} 个运行所需文件（14个权重分片）、{weights['bytes']:,} 字节，逐文件核对官方 SHA256；直连，不使用代理，记录在 `logs/downloads.md`。权重保留在独立项目 models 目录。模型 Apache-2.0 条款见官方模型卡；视频继续遵守 DanceTrack 非商业研究条件。

环境：`{json.dumps(runtime['software'],ensure_ascii=False)}`。服务参数：TP2、BF16、max_model_len32768、max_num_seqs4、image最多4、每图像素65536–2097152、temperature0、seed42、生成512 token/校验768 token。软件代码、提示词、几何阈值、选帧文件均有锁定哈希。生成图册包含目标自身的一份重复视图，推理前在 `inference_policy_locked.json` 明确告知；未在推理后修改。

请求数 {s['raw_calls']}，分阶段 `{json.dumps(s['calls_by_phase'])}`；finish reason `{json.dumps(s['finish_reasons'])}`。输入 token 最大 {s['prompt_tokens_max']}，服务上下文未截断。所有273个ID有唯一生成记录，解析失败/拒绝不从分母移除；条件不适用的后续匹配阶段逐 ID 明确记录。原始回答对应的所有输入图像 SHA256 复核通过。

同视频规范化短语完全重复的组数 {s['duplicate_phrase_groups']}；同一句话被自动判成多个不同唯一目标的矛盾组数 {s['contradictory_auto_unique_phrase_groups']}。详见 `duplicate_phrase_audit.json`，不在事后通过改写描述掩盖冲突。

完整权重下载 {weights['seconds']/60:.2f} 分钟；模型服务启动至推理结束并清理 {job['seconds']/60:.2f} 分钟。逐阶段请求时长分布和 token 总量见 `summary.json`；并发请求时长之和不等于墙钟耗时。两卡分配 `{[(d['physical_index'],d['uuid']) for d in runtime['devices']]}`。显存峰值：`{json.dumps(memory.get('devices',{}))}`（MiB，区分本任务进程与整卡）。本任务服务已终止，显存释放核验见 `gpu_release_check.json`；他人进程未终止。

初次完整下载命令遗漏 `--download`，只重复了配置验证和测速；推理在缺少完整下载回执处停止，未占用 GPU、未生成输出。补上命令后继续，保留失败记录，不改变协议。

首次服务启动在模型加载前失败：vLLM0.16 的设备检查把 `CUDA_VISIBLE_DEVICES` 项转成整数，不接受 GPU UUID。仅把任务环境中的设备列表改为卡号，并保留启动前实际 CUDA UUID 对照；模型架构导入回归通过后重启。没有更改模型、精度、图像、提示词、种子或接收规则。初次回归脚本误用了需要额外参数的公开注册 API，改为调用实际架构检查路径后通过；两次脚本输出均保留。失败服务日志在 `logs/appearance_attempt1/`，修复和代码哈希记录在 `device_mapping_regression.json`、`inference_code_compatibility_revision.json`。

Stage1/Stage2 已锁定文件复核通过；唯一例外是按要求追加的下载日志，其旧字节已归档且与当前日志前缀完全一致。没有改写历史快照来掩盖正常追加。

## 逐视频覆盖

| 视频 | GT ID | 原标注覆盖 | 自动通过 | 自动候选并集 | 审阅无明显疑点 | 审阅后混合并集 |
|---|---:|---:|---:|---:|---:|---:|
'''
    for r in perseq:
        reviewed = next(c for c in reviewed_coverage if c['sequence']==r['sequence'])
        report += f'| {r["sequence"]} | {r["GT_IDs"]} | {len(r["old_annotation_unique_IDs"])} | {len(r["new_model_validated_IDs"])} | {len(r["mixed_candidate_union_IDs"])} | {len(reviewed["agent_cleared_new_IDs"])} | {len(reviewed["mixed_source_union_IDs"])} |\n'
    report += f'''
## 交付与停止点

- 全 ID 台账：`results/stage2_appearance/description_ledger.jsonl`，包含未通过项和全部匹配事实。
- 新增指代候选：`results/stage2_appearance/reference_resources_supplement.jsonl`，与旧文件分开保存。
- 全部25条经智能体视觉审阅后，{len(clear_ids)}条无明显疑点候选与其余标疑项分开：`reference_resources_agent_cleared.jsonl`、`review_flags.json`。
- 协议/模板/代码与图像清单：`protocol_locked.json`、`prompts_locked.json`、`inference_policy_locked.json`、`preinference_snapshot.sha256`。
- 抽查页面和标疑项：`visual_review/index.html`、`visual_review_notes.json`、`review_flags.json`。

本轮完成后停下。阶段三候选题尚未生成；公开跟踪器选定后的训练/调参视频重叠核查仍待后续完成。
'''
    path = ROOT/'results/stage2_appearance_report.md'
    path.write_text(report)
    receipt = {'completed_at':now(),'status':'STAGE2_APPEARANCE_COMPLETE_STOPPED_BEFORE_STAGE3','IDs':273,
        'auto_model_validated_IDs':s['model_validated_IDs'],'newly_covered_IDs':s['newly_covered_IDs'],
        'qa_generated':0,'training':False,'tracker_runs':0,'raw_sources_modified':False,'model_service_stopped':True,
        'visual_review_cases':len(allnotes),'locked_visual_review_cases':len(notes['cases']),
        'posthoc_extra_visual_review_cases':len(extra['cases']),
        'agent_cleared_candidate_IDs':len(clear_ids),'agent_cleared_newly_covered_IDs':review_summary['agent_cleared_newly_covered_IDs'],
        'auto_pass_review_flags':len(auto_flags),'report_sha256':sha(path)}
    write(RES/'receipt.json',receipt)
    artifacts = sorted({p for p in RES.rglob('*') if p.is_file() and p.name!='final_snapshot.sha256'}|{path}|set((ROOT/'src').glob('appearance_*.py')))
    (RES/'final_snapshot.sha256').write_text(''.join(f'{sha(p)}  {p}\n' for p in artifacts))
    with (ROOT/'research_log.md').open('a') as f:
        f.write(f'\n## Stage 2 appearance supplement result — {now()}\n\nAll273 IDs processed; {s["valid_phrases"]} valid phrases, {s["global_pass_IDs"]} held-out global unique, {s["model_validated_IDs"]} fixed-anchor automatic candidates. Original coverage21 IDs; automatic new coverage15, mixed-source auto union36/273. Locked visual sample30 plus explicitly post-hoc16 extra cases reviewed; all25 automatic candidates reviewed, {len(auto_flags)} flagged, {len(clear_ids)} have no obvious agent-identified issue; {review_summary["agent_cleared_newly_covered_IDs"]} newly covered IDs in the latter subset. Keep automatic results and agent-cleared subset separate, no source/GT repair or acceptance tuning. Same-model check repeats accessory/color errors and can falsely reject targets; do not treat it as independent human validation. Own model service terminated; stop before Stage3.\n')
    print(json.dumps(receipt),flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--finalize',action='store_true')
    args = p.parse_args()
    units,ledger,resources,summary = assemble()
    if args.finalize:
        finalize(ledger,resources,summary)
    else:
        review(units,ledger)
        print(json.dumps(summary),flush=True)


if __name__=='__main__':
    main()
