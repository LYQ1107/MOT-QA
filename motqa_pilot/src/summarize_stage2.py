"""Report Stage 2 GT/reference resources and stop before question generation."""
from pathlib import Path
from collections import Counter
import csv
import datetime
import hashlib
import json
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'results/stage2'


def load(name):
    return json.loads((R/name).read_text())


def lines(name):
    return [json.loads(x) for x in (R/name).read_text().splitlines()]


def dump(name,value):
    (R/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(headers,rows):
    return '| '+' | '.join(headers)+' |\n|'+'|'.join('---' for _ in headers)+'|\n'+'\n'.join('| '+' | '.join(map(str,row))+' |' for row in rows)+'\n'


def refstats(refs,kind):
    rs=[r for r in refs if r['ref_type']==kind]
    future=[r for r in rs if r['with_future_3s_frames']]
    return dict(intervals=len(rs),future_3s_intervals=len(future),reference_frames=sum(r['reference_frames'] for r in rs),
        future_3s_frames=sum(r['with_future_3s_frames'] for r in rs),videos=len({r['sequence'] for r in rs}),
        cue_id_units=len({(r['sequence'],r.get('normalized_text',r.get('rank',r['text'])),tuple(r['target_ids'])) for r in rs}),
        unique_target_ids=len({(r['sequence'],tid) for r in rs for tid in r['target_ids']}))


def main():
    now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
    summaries=load('sequence_summary.json');metadata=load('sequence_metadata.json')
    meta={(m['dataset'],m['sequence']):m for m in metadata}
    refs=lines('reference_resources.jsonl');apps=lines('appearance_diagnostics.jsonl')
    events=lines('point_events.jsonl');tracks=lines('track_index.jsonl')
    datasets=[]
    for dataset in ['DanceTrack','SportsMOT','MOT17']:
        ss=[s for s in summaries if s['dataset']==dataset];eligible=[s for s in ss if s['eligible_source']]
        rr=[r for r in refs if r['dataset']==dataset];aa=[a for a in apps if a['dataset']==dataset and a['eligible_source']]
        ee=[e for e in events if e['dataset']==dataset];es=[e for e in ee if e['eligible_source']]
        tt=[t for t in tracks if t['dataset']==dataset]
        d=dict(dataset=dataset,sequences=len(ss),eligible_sequences=len(eligible),tracks=sum(s['tracks'] for s in ss),
            eligible_visible_gt_ids=sum(t['eligible_visible_frames']>0 for t in tt),
            rows=sum(s['visibility']['present_frames'] for s in ss),visible_rows=sum(s['visibility']['visible_frames'] for s in ss),
            region_ambiguous_rows=sum(s['visibility']['region_ambiguous_visible_rows'] for s in ss),
            events=dict(Counter(e['type'] for e in ee)),eligible_events=dict(Counter(e['type'] for e in es)),
            initial_edge_entries=sum(e.get('left_censored',False) for e in ee),eligible_initial_edge_entries=sum(e.get('left_censored',False) for e in es),
            terminal_disappearances=sum(e.get('right_censored',False) for e in ee),
            overlap_episodes=sum(s['overlap_episodes'] for s in ss),crossings=sum(s['crossings'] for s in ss),
            crossing_unknown=sum(s['crossing_unknown'] for s in ss),
            eligible_overlap_episodes=sum(s['eligible_overlap_episodes'] for s in eligible),eligible_crossings=sum(s['eligible_crossings'] for s in eligible),
            appearance_groups=len(aa),positive_appearance_groups=sum(a['eligible_frames_with_visible_labeled_targets']>0 for a in aa),
            unique_appearance_groups=sum(a['eligible_unique_frames']>0 for a in aa),
            appearance_positive_frame_pairs=sum(a['eligible_frames_with_visible_labeled_targets'] for a in aa),
            appearance_unique_frame_pairs=sum(a['eligible_unique_frames'] for a in aa),refs={k:refstats(rr,k) for k in ['appearance','event','position']})
        ar=[r for r in rr if r['ref_type']=='appearance']
        lengths=[(r['frame_end']-r['frame_start']+1)/meta[(dataset,r['sequence'])]['fps'] for r in ar]
        d['appearance_interval_seconds_quantiles']=np.quantile(lengths,[0,.25,.5,.75,.95,1]).tolist()
        d['appearance_intervals_under_1s']=sum(x<1 for x in lengths)
        d['screen_distance_quantiles']=np.quantile([t['screen_distance_diagonals'] for t in tt],[0,.25,.5,.75,.95,1]).tolist()
        datasets.append(d)
    dump('dataset_summary.json',datasets)
    values=[]
    for m in metadata:
        if m['dataset']=='MOT17':
            with np.load(m['unified_path']) as a:values.append(a['visibility'][a['present']])
    v=np.concatenate(values)
    distribution=dict(dataset='MOT17',rows=len(v),quantiles=np.quantile(v,[0,.1,.25,.5,.75,.9,1]).tolist(),
        threshold_counts={str(t):int((v>=t).sum()) for t in [0,.1,.25,.5,.75,1]},
        zero_rows=int((v==0).sum()),one_rows=int((v==1).sum()),
        histogram_edges=[0,.1,.25,.5,.75,1.000001],histogram_counts=np.histogram(v,bins=[0,.1,.25,.5,.75,1.000001])[0].tolist())
    dump('visibility_distribution.json',distribution)
    csv_rows=[]
    for s in summaries:
        es=[e for e in events if e['dataset']==s['dataset'] and e['sequence']==s['sequence']]
        csv_rows.append(dict(dataset=s['dataset'],source_split=s['source_split'],sequence=s['sequence'],eligible_source=s['eligible_source'],
            source_window=s['source_window'],tracks=s['tracks'],enters_edge_first_seen=s['events'].get('enters_frame',0),
            frame1_edge_first_seen_censored=sum(e.get('left_censored',False) for e in es),leaves_frame=s['events'].get('leaves_frame',0),
            becomes_occluded=s['events'].get('becomes_occluded',0),reappears=s['events'].get('reappears',0),terminal_disappearances=s['terminal_disappearances'],
            overlap_episodes=s['overlap_episodes'],crossings=s['crossings'],crossing_unknown=s['crossing_unknown'],
            eligible_overlap_episodes=s['eligible_overlap_episodes'],eligible_crossings=s['eligible_crossings'],
            appearance_intervals=s['reference_intervals'].get('appearance',0),event_references=s['reference_intervals'].get('event',0),
            position_intervals=s['reference_intervals'].get('position',0),camera_motion=s['camera_motion']))
    with (R/'sequence_events.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(csv_rows[0]));w.writeheader();w.writerows(csv_rows)
    coverage=[]
    for s in [s for s in summaries if s['eligible_source']]:
        aa=[a for a in apps if a['dataset']==s['dataset'] and a['sequence']==s['sequence']]
        rr=[r for r in refs if r['dataset']==s['dataset'] and r['sequence']==s['sequence'] and r['ref_type']=='appearance']
        tt=[t for t in tracks if t['dataset']==s['dataset'] and t['sequence']==s['sequence'] and t['eligible_visible_frames']]
        have={tid for r in rr for tid in r['target_ids']};need={t['gt_id'] for t in tt}-have
        coverage.append(dict(dataset=s['dataset'],sequence=s['sequence'],source_split=s['source_split'],visible_gt_ids=len(tt),
            description_groups=len(aa),positive_groups=sum(a['eligible_frames_with_visible_labeled_targets']>0 for a in aa),
            unique_groups=sum(a['eligible_unique_frames']>0 for a in aa),unique_intervals=len(rr),
            intervals_with_future_3s=sum(bool(r['with_future_3s_frames']) for r in rr),covered_target_ids=sorted(have),uncovered_target_ids=sorted(need)))
    dump('appearance_coverage_by_sequence.json',coverage)
    with (R/'appearance_coverage_by_sequence.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(coverage[0]));w.writeheader();w.writerows(coverage)
    dance=[c for c in coverage if c['dataset']=='DanceTrack']
    gap=dict(dataset='DanceTrack',source_split='val',videos=25,gt_ids=sum(c['visible_gt_ids'] for c in dance),
        covered_gt_ids=sum(len(c['covered_target_ids']) for c in dance),uncovered_gt_ids=sum(len(c['uncovered_target_ids']) for c in dance),
        videos_with_no_unique_reference=[c['sequence'] for c in dance if not c['unique_intervals']],
        counts_mean='original-label uniqueness, not visually verified appearance accuracy',
        qa_capacity='not established; reference intervals are not independent questions',
        optional_completion=dict(scope='DanceTrack val first: 273 GT IDs, including 252 with no annotation-unique cue',
            method='strong-VLM descriptions from multiple GT crops; same-video uniqueness and visual checks; human GT tracks and answers unchanged',
            user_approval_required=True,approval_source='task_request.txt section 3.4',approved=False,model_calls=0))
    dump('appearance_gaps.json',gap)
    dump('reference_templates.json',dict(time_decimals=3,appearance='Original human text unchanged; t_ref in metadata',
        event={'enters_frame':'the person who enters the frame from the {edge} at around {time:.3f} s',
               'leaves_frame':'the person who leaves the frame near the {edge} edge at around {time:.3f} s',
               'becomes_occluded':'the person who disappears from view at around {time:.3f} s',
               'reappears':'the person who comes back into view at around {time:.3f} s'},
        position='the {leftmost|rightmost} person at {t_ref:.3f} s',qa_templates_created=False))
    selected=load('reference_review_selection.json')
    observations={
        ('DanceTrack','short'):('needs_review','唯一时段仅0.05秒，目标高度重叠，白色T恤难以从该帧核实。'),
        ('DanceTrack','long'):('plausible_but_needs_review','蓝色裤子较能区分；深色外层与浅色内搭的措辞仍需核查。'),
        ('SportsMOT','short'):('needs_review','right-side team player是空间/群体指代，非纯个体外观；唯一时段0.04秒。'),
        ('SportsMOT','long'):('apparent_text_id_mismatch','描述white clothes，原JSON指定ID10，其原始GT框指向绿色上衣运动员。未猜测ID偏移或修正标注。'),
        ('MOT17','short'):('not_visually_unique','泛化的person walking on the street不能从多人画面唯一定位。'),
        ('MOT17','long'):('not_visually_unique','泛化的man walking on the sidewalk不能从多人画面唯一定位。')}
    notes=[]
    for item in selected:
        status,note=observations[(item['dataset'],item['kind'])]
        notes.append(dict(dataset=item['dataset'],selection=item['kind'],status=status,observation=note,image=item['path'],
            ref_id=item['reference']['ref_id'],text=item['reference']['text'],sequence=item['reference']['sequence'],
            frame=item['reference']['reference_frame'],target_ids=item['reference']['target_ids'],reviewer='Codex visual inspection'))
    dump('visual_review_notes.json',dict(selection='shortest and longest interval with future3s per dataset; not random, not an error-rate estimator',
        reviewed_at=now,cases=notes,source_annotations_modified=False,automatic_candidates_removed=False))
    dump('identity_applicability.json',dict(MOT17=dict(physical_person_reentry_after_exit='unsupported by original IDs',
        global_unique_people_across_new_ids='unsupported without additional identity GT',within_original_id_position_relation_interaction='supported subject to valid reference'),
        DanceTrack=dict(fully_occluded_reappearance_same_id='publisher supported',general_out_of_view_reentry_same_id='unconfirmed'),
        SportsMOT=dict(identity='publisher specifies athlete ID throughout clip'),event_labels='task-defined operational edge/gap heuristic'))
    replacements={
        '@@NOW@@':now,'@@PROTOCOL_SHA@@':sha(R/'protocol.json'),'@@VIS_SHA@@':sha(ROOT/'results/visibility_convention.json'),
        '@@COMPUTE_SECONDS@@':f"{load('compute_receipt.json')['elapsed_s']:.2f}",
        '@@DATA_TABLE@@':table(['数据集','序列','有效GT行','可见行','可见比例','区域模糊行'],[[d['dataset'],d['sequences'],f"{d['rows']:,}",f"{d['visible_rows']:,}",f"{d['visible_rows']/d['rows']:.2%}",f"{d['region_ambiguous_rows']:,}"] for d in datasets]),
        '@@VIS_TABLE@@':table(['visibility阈值','保留行','比例'],[[t,f'{c:,}',f"{c/distribution['rows']:.2%}"] for t,c in distribution['threshold_counts'].items()]),
        '@@EVENT_TABLE@@':table(['来源','贴边首现','其中第1帧','离开','遮挡','重现','终端消失','重叠片段','交叉','交叉未知'],[[d['dataset'],d['events'].get('enters_frame',0),d['initial_edge_entries'],d['events'].get('leaves_frame',0),d['events'].get('becomes_occluded',0),d['events'].get('reappears',0),d['terminal_disappearances'],d['overlap_episodes'],d['crossings'],d['crossing_unknown']] for d in datasets]),
        '@@ELIGIBLE_TABLE@@':table(['来源','序列','贴边首现','其中第1帧','离开','遮挡','重现','重叠','交叉'],[[d['dataset'],d['eligible_sequences'],d['eligible_events'].get('enters_frame',0),d['eligible_initial_edge_entries'],d['eligible_events'].get('leaves_frame',0),d['eligible_events'].get('becomes_occluded',0),d['eligible_events'].get('reappears',0),d['eligible_overlap_episodes'],d['eligible_crossings']] for d in datasets]),
        '@@REF_TABLE@@':table(['来源','外观时段','事件指代','位置时段','各类留≥3秒时段'],[[d['dataset'],d['refs']['appearance']['intervals'],d['refs']['event']['intervals'],d['refs']['position']['intervals'],' / '.join(str(d['refs'][k]['future_3s_intervals']) for k in ['appearance','event','position'])] for d in datasets]),
        '@@APP_TABLE@@':table(['来源','全部组','非空组','有唯一时刻组','组通过率','帧通过率','覆盖视频','覆盖GT身份','描述+身份单位'],[[d['dataset'],d['appearance_groups'],d['positive_appearance_groups'],d['unique_appearance_groups'],f"{d['unique_appearance_groups']/d['positive_appearance_groups']:.2%}",f"{d['appearance_unique_frame_pairs']/d['appearance_positive_frame_pairs']:.2%}",f"{d['refs']['appearance']['videos']}/{d['eligible_sequences']}",f"{d['refs']['appearance']['unique_target_ids']}/{d['eligible_visible_gt_ids']}",d['refs']['appearance']['cue_id_units']] for d in datasets]),
        '@@MISSING_VIDEOS@@':', '.join(gap['videos_with_no_unique_reference']),
        '@@IMAGES@@':'\n'.join(f"[{i['dataset']} {i['kind']} 核查图]({i['path']})" for i in selected)}
    report=(ROOT/'src/stage2_report_template.md').read_text()
    for k,v in replacements.items():report=report.replace(k,v)
    assert '@@' not in report
    report_path=ROOT/'results/stage2_report.md';report_path.write_text(report)
    with (ROOT/'research_log.md').open('a') as f:
        f.write(f'\n## Stage 2 result — {now}\n\nUnified162 videos /2518 IDs /1294527 target GT rows;1268058 visible rows at provisional0.25. Eligible references: appearance484 (443 future3s), event352 (312), position2344 (2060). All162 array checks,90 original-source reference checks and30 crossing checks passed. Retain facts and stop.\n\nAppearance hypothesis: label-level uniqueness does not establish visual uniqueness. Dance val resources cover21/273 IDs in7/25 videos, leaving252 IDs and18 videos uncovered. Extreme-duration inspection found generic MOT17 references and a SportsMOT color/ID mismatch. Source GT and descriptions unchanged; no automatic candidate removal or ID repair. Stage2 reports label-based candidates only, not approved QA references. VLM supplementation requires explicit user approval under original3.4 and has not run. Tracker train/tune overlap remains pending public-tracker selection.\n')
    text=(ROOT/'README.md').read_text().replace('Current status: Stage 1 complete; stopped awaiting confirmation.','Current status: Stage 2 complete; stopped for appearance-resource gap review. Stage 3 has not started.')
    text=text.replace('- [Stage 1 report](results/stage1_report.md)','- [Stage 2 report](results/stage2_report.md)\n- [Stage 1 report](results/stage1_report.md)')
    (ROOT/'README.md').write_text(text)
    paths=list((ROOT/'src').glob('*stage2*.py'))+[ROOT/'src/stage2_report_template.md',ROOT/'results/visibility_convention.json',ROOT/'results/visibility_convention.sha256',report_path]
    paths += [p for p in R.rglob('*') if p.is_file() and p.name not in {'receipt.json','snapshot.sha256'}]
    artifacts={str(p.relative_to(ROOT)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(paths)}
    receipt=dict(status='STAGE2_COMPLETE_STOPPED_APPEARANCE_GAP_REVIEW',completed_at=now,project_root=str(ROOT),
        gt_sequences=162,eligible_videos=77,gt_ids=2518,valid_gt_rows=1294527,reference_intervals=3180,
        qa_generated=0,model_calls=0,tracker_runs=0,training=False,gpu_used=False,raw_sources_modified=False,
        visibility_threshold=.25,visibility_status='PROVISIONAL_PENDING_STAGE2_REVIEW',tracker_train_tune_overlap='PENDING_TRACKER_SELECTION_AND_AUDIT',
        user_decision_needed=['confirm visibility convention','authorize optional VLM descriptions or restrict reference resources'],
        artifacts=artifacts,unified_npz_files=[dict(path=m['unified_path'],sha256=m['npz_sha256']) for m in metadata])
    dump('receipt.json',receipt)
    (R/'snapshot.sha256').write_text(''.join(f"{v['sha256']}  {p}\n" for p,v in artifacts.items())+
        ''.join(f"{m['npz_sha256']}  {Path(m['unified_path']).relative_to(ROOT)}\n" for m in metadata)+f"{sha(R/'receipt.json')}  results/stage2/receipt.json\n")
    print(json.dumps({k:v for k,v in receipt.items() if k not in {'artifacts','unified_npz_files'}},ensure_ascii=False))
    print('REPORT',report_path,'artifacts',len(artifacts))


if __name__=='__main__':
    main()
