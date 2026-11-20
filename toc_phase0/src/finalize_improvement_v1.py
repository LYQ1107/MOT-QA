"""Serialize fresh frozen outputs, commit all predictions, then score fixed scopes."""
import csv
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import sys

from improvement_events import identity_segments,timeline_public
from improvement_facts import filter_document,serialize_compressed
from rule_prediction import predict
from run_stage3_masa import ROOT,now,write_json
from track_facts import query_document

sys.path.insert(0,str(ROOT/'upstream/toc_bench'))
from answer_extractor import extract
from compute_metrics import is_correct


def summary(items,predictions):
    n=len(items);covered=sum(predictions[q['qa_id']]['covered'] for q in items)
    correct=sum(is_correct(predictions[q['qa_id']]['extracted_answer'],q) for q in items)
    return dict(total=n,covered=covered,correct=correct,coverage=covered/n if n else None,
                accuracy_all=correct/n if n else None,accuracy_on_covered=correct/covered if covered else None)


def groups(items,trackable):
    result=dict(all=items,main=[q for q in items if q['metadata']['dim']!='reappear_identity'],
                trackable=[q for q in items if q['qa_id'] in trackable],
                main_trackable=[q for q in items if q['qa_id'] in trackable and q['metadata']['dim']!='reappear_identity'])
    for dim in sorted({q['metadata']['dim'] for q in items}):
        result['dimension:'+dim]=[q for q in items if q['metadata']['dim']==dim]
        result['trackable_dimension:'+dim]=[q for q in result['dimension:'+dim] if q['qa_id'] in trackable]
    return result


def main():
    frozen_path=ROOT/'results/frozen_config_v1.json'
    frozen=json.loads(frozen_path.read_text());freeze_lock=json.loads((ROOT/'logs/frozen_config_v1_lock.json').read_text())
    frozen_sha=hashlib.sha256(frozen_path.read_bytes()).hexdigest()
    assert frozen_sha==freeze_lock['sha256'] and frozen_path.stat().st_mode&0o222==0
    split_path=ROOT/'results/dev_test_split_locked.json';split=json.loads(split_path.read_text())
    assert hashlib.sha256(split_path.read_bytes()).hexdigest()==frozen['split_sha256']
    registration_path=ROOT/'results/trackable_subset_preregistered.json'
    assert hashlib.sha256(registration_path.read_bytes()).hexdigest()==frozen['preregistration_sha256']
    registration=json.loads(registration_path.read_text());trackable=set(registration['trackable_qa_ids'])
    assert len(trackable)==324
    job=json.loads((ROOT/'logs/improvement_final_job.json').read_text())
    assert job['status']=='COMPLETE' and job['expected_units']==job['completed_units']==689
    assert job['frozen_config_sha256']==frozen_sha
    tasks=json.loads((ROOT/'results/stage3_tracking_tasks.json').read_text())
    visible=[json.loads(s) for s in (ROOT/'results/stage3_visible_inputs.jsonl').read_text().splitlines()]
    extracted=json.loads((ROOT/'results/stage3_extracted_queries.json').read_text())
    assert len(visible)==len({q['qa_id'] for q in visible})==749 and len(tasks)==689
    index=[];counts=dict(videos=0,query_pairs=0,frames=0,retained_tracks=0,omitted_tracks=0,
                         short_weak_removed=0,rank_omitted=0,retained_observations=0,empty_retained_queries=0)
    for task in tasks:
        raw=json.loads((ROOT/'tracks/v1/raw'/(task['video_id']+'.json')).read_text())
        assert raw['complete'] and raw['video_id']==task['video_id'] and raw['queries']==task['queries']
        assert raw['frozen_config_sha256']==frozen_sha and raw['study_mode']=='final'
        assert raw['memo_tracklet_frames']==frozen['tracking']['memo_tracklet_frames']
        assert raw['tracker_parameters']==frozen['tracking']['native_tracker']
        assert raw['fps']==5 and len(raw['frames'])==raw['frame_count']
        assert raw['unified'] and not raw['sam_mask'] and not raw['sam2_or_sam3_used']
        assert all(f['frame_id']==i and abs(f['timestamp_seconds']-i/5)<1e-8 for i,f in enumerate(raw['frames']))
        counts['videos']+=1;counts['frames']+=raw['frame_count']
        for query_index,query in enumerate(raw['queries']):
            unfiltered=query_document(raw,query_index,frozen['tracking']['score_threshold'])
            unfiltered_path=ROOT/'tracks/v1/unfiltered_by_query'/task['video_id']/f'query_{query_index:02d}.json'
            write_json(unfiltered_path,unfiltered)
            document=filter_document(unfiltered,frozen['filter'])
            document['frozen_config_sha256']=frozen_sha
            path=ROOT/'tracks/v1/by_query'/task['video_id']/f'query_{query_index:02d}.json'
            write_json(path,document);text_path=path.with_suffix('.txt');text_path.write_text(serialize_compressed(document))
            index.append(dict(video_id=task['video_id'],query=query,json_path=str(path),unfiltered_json_path=str(unfiltered_path),text_path=str(text_path),frozen_config_sha256=frozen_sha))
            counts['query_pairs']+=1
            counts['retained_tracks']+=len(document['tracks']);counts['omitted_tracks']+=document['total_omitted']
            counts['short_weak_removed']+=document['short_weak_removed'];counts['rank_omitted']+=document['rank_omitted']
            counts['retained_observations']+=sum(len(t['observations']) for t in document['tracks'])
            counts['empty_retained_queries']+=not document['tracks']
    assert counts['videos']==689 and counts['query_pairs']==899 and counts['frames']==101359,counts
    write_json(ROOT/'results/v1_track_index.json',index)
    index_by_video={}
    for row in index:index_by_video.setdefault(row['video_id'],[]).append(row)
    @lru_cache(maxsize=4)
    def documents(video):
        return {row['query']:json.loads(Path(row['json_path']).read_text()) for row in index_by_video[video]}
    predictions=[]
    for item in visible:
        docs=documents(item['video_id'])
        result=(predict(item,docs) if frozen['rule']['event_mode']=='legacy_gap_0.5' else
                predict(item,docs,timeline_fn=timeline_public,identity_segments_fn=identity_segments))
        answer=result.pop('answer');raw=None if answer is None else ', '.join(answer) if isinstance(answer,list) else str(answer)
        predictions.append(dict(qa_id=item['qa_id'],raw_response=raw,format=item['format'],
                                extracted_answer=extract(raw,item['format']) if raw is not None else None,
                                frozen_config_sha256=frozen_sha,error=None,**result))
    assert len(predictions)==len({p['qa_id'] for p in predictions})==749
    prediction_path=ROOT/'results/v1_rule_predictions.jsonl'
    prediction_path.write_text(''.join(json.dumps(p,ensure_ascii=False)+'\n' for p in predictions))
    predictions_saved_at=now()
    prototype_path=ROOT/'results/improvement/dev'/frozen['dev_selected_label']/'predictions.jsonl'
    prototype={p['qa_id']:p for p in map(json.loads,prototype_path.read_text().splitlines())}
    fields=('raw_response','extracted_answer','covered','reason')
    mismatches=[p['qa_id'] for p in predictions if p['qa_id'] in prototype and any(p[k]!=prototype[p['qa_id']][k] for k in fields)]
    write_json(ROOT/'results/v1_dev_reproduction.json',dict(checked_at=now(),development_questions=len(prototype),
               matching_predictions=len(prototype)-len(mismatches),mismatch_qa_ids=mismatches,
               parameters_changed=False,test_scores_used=False))
    # No correct answers or other construction metadata are used above this line.
    all_qa=json.loads((ROOT/'data/toc_bench/answer_final.json').read_text())['items']
    ids={q['qa_id'] for q in visible};qa=[q for q in all_qa if q['qa_id'] in ids]
    by_id={p['qa_id']:p for p in predictions}
    scopes={'full':qa,'dev':[q for q in qa if q['qa_id'] in set(split['dev_qa_ids'])],
            'test':[q for q in qa if q['qa_id'] in set(split['test_qa_ids'])]}
    assert len(scopes['dev'])==147 and len(scopes['test'])==602
    metrics={};comparison=[];legal={'2','3','4','5 or more'}
    qwen={p['qa_id']:p for p in map(json.loads,(ROOT/'results/stage2_predictions.jsonl').read_text().splitlines())}
    old={p['qa_id']:p for p in map(json.loads,(ROOT/'results/stage3_rule_predictions.jsonl').read_text().splitlines())}
    for scope,items in scopes.items():
        numeric=[q for q in items if q['format']=='numerical']
        covered=sum(by_id[q['qa_id']]['covered'] for q in numeric)
        nlegal=sum(by_id[q['qa_id']]['raw_response'] in legal for q in numeric)
        group_rows=groups(items,trackable)
        metrics[scope]=dict(groups={name:summary(rows,by_id) for name,rows in group_rows.items()},
                           numerical=dict(total=len(numeric),covered=covered,legal=nlegal,
                                          legal_ratio_all=nlegal/len(numeric),legal_ratio_covered=nlegal/covered if covered else None))
        for name,rows in group_rows.items():
            if not rows:continue
            n=len(rows)
            comparison.append(dict(scope=scope,group=name,total=n,
                  stage2_qwen_correct=sum(is_correct(qwen[q['qa_id']]['extracted_answer'],q) for q in rows),
                  original_rule_correct=sum(is_correct(old[q['qa_id']]['extracted_answer'],q) for q in rows),
                  frozen_rule_correct=sum(is_correct(by_id[q['qa_id']]['extracted_answer'],q) for q in rows),
                  frozen_rule_covered=sum(by_id[q['qa_id']]['covered'] for q in rows)))
    result=dict(generated_at=now(),prediction_commit_at=predictions_saved_at,frozen_at=frozen['frozen_at'],
                frozen_config_sha256=frozen_sha,split_sha256=frozen['split_sha256'],
                denominators='all questions in each fixed scope; abstentions, illegal answers, and parse failures count wrong',
                primary_scope='test',full_scope_note='Development videos participated in parameter selection; full scores are supplemental.',
                no_vllm_inference=True,metrics=metrics)
    write_json(ROOT/'results/v1_rule_metrics.json',result)
    write_json(ROOT/'results/v1_baseline_comparison.json',dict(generated_at=now(),new_vlm_inference=False,
                stage2_caveat='Historical official prompt without stage-four timestamps; not the future condition A.',rows=comparison))
    with (ROOT/'results/v1_baseline_comparison.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(comparison[0]));writer.writeheader();writer.writerows(comparison)
    write_json(ROOT/'results/v1_integrity.json',dict(status='PASS',checked_at=now(),frozen_config_sha256=frozen_sha,
                split_sha256=frozen['split_sha256'],preregistration_sha256=frozen['preregistration_sha256'],
                all_predictions_unique=True,unfiltered_raw_json_preserved=True,**counts))
    print(json.dumps(dict(status='COMPLETE',counts=counts,test=metrics['test']['groups']['all'],
                          test_trackable=metrics['test']['groups']['trackable']),ensure_ascii=False))


if __name__=='__main__':main()
