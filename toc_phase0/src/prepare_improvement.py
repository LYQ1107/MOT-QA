"""Register a small development-only search and rescore existing predictions."""
from collections import Counter
import csv
from datetime import datetime, timedelta
import hashlib
import json
import random
import sys

from run_stage3_masa import ROOT, now


def save_new(path, data, readonly=False):
    with path.open('x') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    if readonly:
        path.chmod(0o444)


def main():
    split = json.loads((ROOT/'results/dev_test_split_locked.json').read_text())
    split_lock = json.loads((ROOT/'logs/dev_test_split_lock.json').read_text())
    assert hashlib.sha256((ROOT/'results/dev_test_split_locked.json').read_bytes()).hexdigest()==split_lock['sha256']
    registration=json.loads((ROOT/'results/trackable_subset_preregistered.json').read_text())
    dev=set(split['dev_qa_ids']);dev_videos=set(split['dev_video_ids'])
    plan_path=ROOT/'results/improvement_plan_locked.json'
    if not plan_path.exists():
        started=datetime.fromisoformat(now())
        plan=dict(registered_at=started.isoformat(),deadline=(started+timedelta(hours=24)).isoformat(),
                  maximum_work_hours=24,seed=42,split_sha256=split_lock['sha256'],
                  preregistration_sha256='4a4d1fdbb57158696986a99130d0a4e2ba27a51c73776c813347829d4b9a2593',
                  memory_candidates=[10,25,50],memory_baseline='reuse accepted memo10 raw outputs on development only',
                  filter_trials=[dict(name='none',short_seconds=0,low_confidence=0,top_k=None),
                                 dict(name='short_weak',short_seconds=0.6,low_confidence=0.3,top_k=None),
                                 dict(name='short_weak_top5',short_seconds=0.6,low_confidence=0.3,top_k=5),
                                 dict(name='short_weak_top10',short_seconds=0.6,low_confidence=0.3,top_k=10)],
                  filter_selection='select top5 or top10 satisfying development text P95<=8000 and max<=12000; if neither fits, the single predefined fallback is top3',
                  duration_definition='observed frame count / 5; rank by mean confidence times observed duration, equal to sum(confidence)/5; ties by original ID',
                  event_candidates=['legacy_gap_0.5','public_3fps_min2_confirm2'],
                  public_event_reference=dict(url='https://arxiv.org/html/2605.09904#A1',section='Appendix A, Table 3',
                                              source_tracking_fps=3,minimum_occlusion_frames=2,reappearance_visible_frames=2,
                                              implementation='MASA remains 5fps; project visibility to a 3fps nearest-sample grid (max time offset 1/15s), require two absent samples and two consecutive visible samples; backdate confirmed return to first visible sample',
                                              limitation='box absence/edge position remain proxies; no SAM masks or mask-area thresholds used'),
                  selection_order=['main-four trackable development accuracy with abstentions counted wrong','main-four trackable development coverage'],
                  ties=dict(memory='lower fresh-ID reacquisition proxy, then smaller memory',filter='smaller K',event='public_3fps_min2_confirm2'),
                  optional_b2='deferred; do not change the main serializer or preregistered subset',
                  service_context_candidates=[32768,65536],context_policy='choose a supported context covering complete-input bounds plus generation budget; all four future conditions use the same configuration',
                  test_policy='No new test rule accuracy before immutable frozen_config_v1. The requested historical stage2-vs-stage3 full-subset comparison is written now for reporting and not displayed to the selector.',
                  final_retracking='After freeze, recompute all 689 videos in tracks/v1/raw; never reuse development trial outputs as final raw outputs')
        save_new(plan_path,plan,readonly=True)
    # Fixed development visual sample, using visible predicates/scope only.
    sample_path=ROOT/'results/improvement_dev_visual_selection.json'
    if not sample_path.exists():
        candidates=sorted({r['video_id'] for r in registration['rows'] if r['qa_id'] in dev and r['dimension']=='event_count' and 'fully_hidden' in r['event_types']})
        rng=random.Random(42);selected=rng.sample(candidates,min(6,len(candidates)))
        selected+=sorted({r['video_id'] for r in registration['rows'] if r['qa_id'] in dev and r['dimension']=='reappear_identity'}-set(selected))
        assert set(selected)<=dev_videos
        save_new(sample_path,dict(created_at=now(),seed=42,method='up to six seeded development fully-hidden counting videos plus every development ReID video; no answers or tracker outcomes used',video_ids=sorted(selected)),readonly=True)
    # Existing predictions only. Full historical comparison is saved, not shown.
    sys.path.insert(0,str(ROOT/'upstream/toc_bench'))
    from compute_metrics import is_correct
    qwen={r['qa_id']:r for r in map(json.loads,(ROOT/'results/stage2_predictions.jsonl').read_text().splitlines())}
    rules={r['qa_id']:r for r in map(json.loads,(ROOT/'results/stage3_rule_predictions.jsonl').read_text().splitlines())}
    qa=json.loads((ROOT/'data/toc_bench/answer_final.json').read_text())['items']
    trackable=set(registration['trackable_qa_ids'])
    selected=[r for r in qa if r['qa_id'] in trackable]
    def compare(rows):
        n=len(rows);qc=sum(is_correct(qwen[r['qa_id']]['extracted_answer'],r) for r in rows);rc=sum(is_correct(rules[r['qa_id']]['extracted_answer'],r) for r in rows)
        covered=sum(rules[r['qa_id']]['covered'] for r in rows)
        return dict(total=n,qwen_correct=qc,qwen_accuracy=qc/n if n else None,rule_correct=rc,rule_accuracy=rc/n if n else None,rule_covered=covered,rule_coverage=covered/n if n else None)
    groups={'trackable_all_324':selected,'trackable_main_301':[r for r in selected if r['metadata']['dim']!='reappear_identity']}
    groups.update({'dimension:'+dim:[r for r in selected if r['metadata']['dim']==dim] for dim in sorted({r['metadata']['dim'] for r in selected})})
    rows=[dict(scope=name,**compare(items)) for name,items in groups.items()]
    result=dict(generated_at=now(),new_inference=False,source_predictions=['results/stage2_predictions.jsonl','results/stage3_rule_predictions.jsonl'],
                denominator='same preregistered subset; missing/parse failures/abstentions count wrong',comparison=rows,not_used_for_tuning=True)
    (ROOT/'results/baseline_same_subset_comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    with (ROOT/'results/baseline_same_subset_comparison.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print(json.dumps(dict(plan=str(plan_path),historical_comparison_saved_not_displayed=True,
                         development_dimensions=dict(Counter(r['dimension'] for r in registration['rows'] if r['qa_id'] in dev)),
                         development_trackable=compare([r for r in selected if r['qa_id'] in dev]),
                         visual_sample=json.loads(sample_path.read_text())['video_ids']),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
