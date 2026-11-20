"""Construct GT facts and reference resources only. Never construct QA or run models."""
from pathlib import Path
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import csv
import datetime
import hashlib
import io
import json
import math
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/stage2"
DATA = ROOT / "data/stage2"

PROTOCOL = {
    "stage": 2, "seed": 42, "scope": "GT facts and reference resources; no QA or model inference",
    "visibility_threshold_mot17": 0.25, "visibility_status": "PROVISIONAL_PENDING_STAGE2_REVIEW",
    "target_rows": "flag == 1 and class == 1; retain GT ID 0",
    "timestamp": "(original 1-based frame_id - 1) / fps; retain original full-sequence time even in half-val",
    "coordinates": {"unified": "continuous xywh pixel edges, 0-based; no clipping or interpolation",
                    "MOT17": "subtract 1 from source x,y under documented MOT17 1-based coordinate convention",
                    "DanceTrack": "retain released x,y; raw source boxes are retained separately",
                    "SportsMOT": "retain released x,y; raw source boxes are retained separately"},
    "region": {"x_bins": [1/3, 2/3], "ambiguous_margin_width_fraction": 0.05,
               "codes": {"-2": "not visible", "-1": "boundary ambiguous", "0": "left", "1": "center", "2": "right"}},
    "gap": {"strictly_greater_than_s": 1.0, "duration": "number of absent/not-visible frames divided by fps",
            "edge_threshold": 0.02, "edge_test": "signed bbox-to-edge distance / respective width or height < threshold",
            "edge_labels": ["left", "right", "top", "bottom"],
            "internal_gap_evidence": "both last visible and next visible frames; terminal absences reported separately",
            "terminal": "only when remaining invisible frames / fps > 1; right-censored at video end",
            "event_label_meaning": "operational GT-derived edge heuristic specified by the task, not independent semantic occlusion annotations"},
    "entry": "first visible occurrence touches edge; frame-1 entries are left-censored and not used as event references",
    "overlap": {"iou_min": 0.1, "min_consecutive_frames": 3,
                "crossing": "opposite nonzero signs of x_a-x_b immediately before and after an overlap episode; both people must be visible at both evidence frames",
                "unknown_crossing": "missing/censored evidence or tied centers; never convert unknown into a negative"},
    "screen_distance": "sum of center displacement over consecutive visible frames only / image diagonal; gaps not bridged; camera-motion tag retained",
    "appearance": {"group_key": "dataset + sequence + whitespace/casefold-normalized text",
                   "duplicate_policy": "union original per-frame target IDs across all matching description files; retain every provenance path",
                   "unique": "exactly one labeled GT target also visible at t_ref",
                   "units": ["description group", "distinct video/text/target", "contiguous unique interval", "reference frame"],
                   "warning": "annotation uniqueness alone does not verify visual truth or provide independent QA count"},
    "event_reference": {"types": ["enters_frame", "leaves_frame", "becomes_occluded", "reappears"],
                        "same_type_uniqueness_radius_s": 1.0, "comparison": "inclusive +/-1 second over all actors of the same event type",
                        "disappearance_t_ref": "last visible frame; text time is first invisible frame",
                        "eligibility": "all evidence frames within provisional source window; exclude left-censored entries"},
    "position_reference": {"ranks": ["leftmost", "rightmost"], "min_second_place_gap_width_fraction": 0.05,
                           "min_visible_people": 2},
    "future_question_horizon_s": 3.0,
    "reference_text_time_decimals": 3,
    "source_scope": "inventory all 162 public-GT sequences; eligible references only Dance val, Sports val, MOT17 train second half",
    "tracker_overlap_status": "PENDING_PUBLIC_TRACKER_SELECTION_AND_TRAIN_TUNE_AUDIT; continuation authorized without resolution",
    "identity_limits": {"MOT17": "same GT ID does not cover real-person exit/re-entry; do not use unseen-ID absence as a natural-person never-returns label",
                        "DanceTrack": "same ID guaranteed after full occlusion; general out-of-view re-entry identity guarantee unconfirmed",
                        "SportsMOT": "publisher specifies one athlete ID throughout the clip"},
}


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8*1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def ranges(mask):
    mask = np.asarray(mask, bool)
    edges = np.diff(np.r_[False, mask, False].astype(np.int8))
    return list(zip(np.flatnonzero(edges == 1).tolist(), (np.flatnonzero(edges == -1)-1).tolist()))


def groups_from_frames(frames):
    frames = np.asarray(frames, dtype=int)
    split = np.flatnonzero(np.diff(frames) != 1) + 1
    return np.split(frames, split)


def source_window(row):
    n = row["declared_frames"]
    if row["dataset"] in {"DanceTrack", "SportsMOT"} and row["source_split"] == "val":
        return (1, n)
    if row["dataset"] == "MOT17" and row["source_split"] == "train":
        return (n//2+1, n)
    return None


def edge_info(box, width, height):
    x, y, w, h = map(float, box)
    ds = np.array([x/width, (width-x-w)/width, y/height, (height-y-h)/height])
    edges = [name for name, d in zip(PROTOCOL["gap"]["edge_labels"], ds) if d < PROTOCOL["gap"]["edge_threshold"]]
    return dict(touches_edge=bool(edges), edges=edges, closest_edge=PROTOCOL["gap"]["edge_labels"][int(ds.argmin())],
                normalized_distances=ds.tolist())


def process_sequence(row, descriptions, output_base=DATA):
    dataset, sequence = row["dataset"], row["sequence"]
    n, fps, width, height = row["declared_frames"], row["fps"], row["width"], row["height"]
    raw = Path(row["gt_path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == row["gt_sha256"], row["gt_path"]
    gt = np.loadtxt(io.BytesIO(raw), delimiter=",", ndmin=2)
    gt = gt[(gt[:, 6] == 1) & (gt[:, 7] == 1)]
    assert len(gt) == row["target_gt_rows"]
    ids = np.unique(gt[:, 1].astype(np.int32))
    k = len(ids)
    id_to_index = {int(tid): i for i, tid in enumerate(ids)}
    tidx = np.searchsorted(ids, gt[:, 1].astype(np.int32))
    fidx = gt[:, 0].astype(np.int32)-1
    source_boxes = np.full((k, n, 4), np.nan, np.float32)
    source_boxes[tidx, fidx] = gt[:, 2:6]
    boxes = source_boxes.copy()
    if dataset == "MOT17":
        boxes[:, :, :2] -= 1
    present = np.zeros((k, n), bool)
    present[tidx, fidx] = True
    raw_last = np.full((k, n), np.nan, np.float32)
    raw_last[tidx, fidx] = gt[:, 8]
    visibility = np.where(present, raw_last if dataset == "MOT17" else 1., 0.).astype(np.float32)
    visible = present & (visibility >= PROTOCOL["visibility_threshold_mot17"] if dataset == "MOT17" else True)
    centers = boxes[:, :, :2] + boxes[:, :, 2:]/2
    nx = centers[:, :, 0]/width
    regions = np.where(nx < 1/3, 0, np.where(nx < 2/3, 1, 2)).astype(np.int8)
    ambiguous = np.minimum(abs(nx-1/3), abs(nx-2/3)) <= PROTOCOL["region"]["ambiguous_margin_width_fraction"]
    regions[ambiguous] = -1
    regions[~visible] = -2
    target_folder = output_base / "unified" / dataset / row["source_split"]
    target_folder.mkdir(parents=True, exist_ok=True)
    npz_path = target_folder / (sequence + ".npz")
    np.savez_compressed(npz_path, gt_ids=ids, frame_ids=np.arange(1,n+1,dtype=np.int32),
                        timestamps_s=np.arange(n,dtype=np.float64)/fps, boxes_xywh=boxes,
                        boxes_xywh_source=source_boxes, present=present, source_last_column=raw_last,
                        visibility=visibility, visible=visible, region=regions)
    window = source_window(row)
    eligible_frames = np.zeros(n,bool)
    if window:
        eligible_frames[window[0]-1:window[1]] = True
    future = eligible_frames.copy()
    if window:
        future[max(0,window[1]-math.ceil(PROTOCOL["future_question_horizon_s"]*fps)):] = False
    metadata = dict(dataset=dataset, sequence=sequence, source_split=row["source_split"], frames=n, fps=fps,
                    width=width,height=height, source_gt_path=row["gt_path"], source_gt_sha256=row["gt_sha256"],
                    unified_path=str(npz_path), npz_sha256=sha_file(npz_path), gt_ids=ids.tolist(),
                    camera_motion=row["camera_motion"], eligible_source_window_1based=list(window) if window else None,
                    frame_base=1, pixel_origin=0, missing_frame_box="NaN; present=False, visibility=0, visible=False",
                    array_axes="track, frame, optional xywh; gt_ids and frame_ids are explicit axis indices",
                    identity_limitation=PROTOCOL["identity_limits"][dataset])
    events, tracks = [], []
    for ti, tid in enumerate(ids):
        vis = np.flatnonzero(visible[ti])
        spans = ranges(visible[ti])
        displacement = np.linalg.norm(np.diff(centers[ti],axis=0),axis=1)
        consecutive = visible[ti,:-1] & visible[ti,1:]
        distance = float(np.sum(displacement[consecutive])/np.hypot(width,height))
        gaps = np.diff(vis)-1 if len(vis)>1 else np.array([],dtype=int)
        track = dict(dataset=dataset,sequence=sequence,source_split=row["source_split"],gt_id=int(tid),
                     unified_path=str(npz_path),track_axis_index=ti,source_presence_frames=int(present[ti].sum()),
                     visible_frames=len(vis), visible_intervals_1based=[[a+1,b+1] for a,b in spans],
                     first_visible_frame=int(vis[0]+1) if len(vis) else None,last_visible_frame=int(vis[-1]+1) if len(vis) else None,
                     screen_distance_diagonals=distance, camera_motion=row["camera_motion"],
                     max_internal_invisible_s=float(gaps.max()/fps) if len(gaps) else 0.,
                     eligible_source=bool(window), eligible_visible_frames=int((visible[ti]&eligible_frames).sum()))
        tracks.append(track)
        if not len(vis):
            continue

        def add_event(kind, frame_index, evidence_indices, **extra):
            event = dict(dataset=dataset,sequence=sequence,source_split=row["source_split"],gt_id=int(tid),
                         type=kind, frame=frame_index+1,time_s=frame_index/fps,
                         evidence_frames=[int(x+1) for x in evidence_indices],
                         eligible_source=bool(window and all(window[0]-1<=x<window[1] for x in evidence_indices)),
                         camera_motion=row["camera_motion"])
            event.update(extra)
            events.append(event)
            return event

        first = int(vis[0])
        edge = edge_info(boxes[ti,first],width,height)
        if edge["touches_edge"]:
            add_event("enters_frame",first,[first],left_censored=first==0,
                      reference_frame=first+1,position_normalized=(centers[ti,first]/[width,height]).tolist(),edge=edge)
        for left,right in zip(vis[:-1],vis[1:]):
            left,right = int(left),int(right)
            missing = right-left-1
            if missing/fps <= PROTOCOL["gap"]["strictly_greater_than_s"]:
                continue
            edge = edge_info(boxes[ti,left],width,height)
            kind = "leaves_frame" if edge["touches_edge"] else "becomes_occluded"
            e = add_event(kind,left+1,[left,right],reference_frame=left+1,last_visible_frame=left+1,
                          next_visible_frame=right+1,invisible_frames=missing,invisible_duration_s=missing/fps,
                          invisible_frame_range=[left+2,right],right_censored=False,edge=edge,
                          last_position_normalized=(centers[ti,left]/[width,height]).tolist())
            add_event("reappears",right,[left,right],reference_frame=right+1,previous_disappearance_type=kind,
                      invisible_duration_s=missing/fps,position_normalized=(centers[ti,right]/[width,height]).tolist())
        last = int(vis[-1])
        terminal = n-last-1
        if terminal/fps > PROTOCOL["gap"]["strictly_greater_than_s"]:
            edge = edge_info(boxes[ti,last],width,height)
            add_event("leaves_frame" if edge["touches_edge"] else "becomes_occluded",last+1,[last,n-1],
                      reference_frame=last+1,last_visible_frame=last+1,next_visible_frame=None,
                      invisible_frames=terminal,invisible_duration_s=terminal/fps,
                      invisible_frame_range=[last+2,n],right_censored=True,edge=edge,
                      last_position_normalized=(centers[ti,last]/[width,height]).tolist())

    pair_frames = defaultdict(list)
    pair_ious = defaultdict(list)
    for frame in range(n):
        active = np.flatnonzero(visible[:,frame])
        if len(active)<2:
            continue
        b = boxes[active,frame].astype(np.float64)
        lo = np.maximum(b[:,None,:2],b[None,:,:2])
        hi = np.minimum((b[:,:2]+b[:,2:])[:,None,:],(b[:,:2]+b[:,2:])[None,:,:])
        inter = np.prod(np.maximum(0,hi-lo),axis=-1)
        area = b[:,2]*b[:,3]
        iou = inter/(area[:,None]+area[None,:]-inter)
        ia,ib = np.where(np.triu(iou>=PROTOCOL["overlap"]["iou_min"],k=1))
        for a,b in zip(ia,ib):
            key = (int(active[a]),int(active[b]))
            pair_frames[key].append(frame)
            pair_ious[key].append(float(iou[a,b]))
    overlaps = []
    for (a,b), frames in sorted(pair_frames.items()):
        for block in groups_from_frames(frames):
            if len(block)<PROTOCOL["overlap"]["min_consecutive_frames"]:
                continue
            start,end = int(block[0]),int(block[-1])
            pre,post=start-1,end+1
            evidence_ok = pre>=0 and post<n and bool(visible[a,pre] and visible[b,pre] and visible[a,post] and visible[b,post])
            before = float(centers[a,pre,0]-centers[b,pre,0]) if evidence_ok else None
            after = float(centers[a,post,0]-centers[b,post,0]) if evidence_ok else None
            crossing = "unknown" if not evidence_ok or before==0 or after==0 else ("crossed" if before*after<0 else "not_crossed")
            eligible = bool(window and start>=window[0]-1 and end<window[1])
            crossing_eligible = bool(eligible and evidence_ok and pre>=window[0]-1 and post<window[1])
            overlaps.append(dict(dataset=dataset,sequence=sequence,source_split=row["source_split"],gt_ids=[int(ids[a]),int(ids[b])],
                                 frame_start=start+1,frame_end=end+1,frames=len(block),
                                 time_start_s=start/fps,time_end_s=end/fps,crossing_status=crossing,
                                 before_frame=pre+1 if evidence_ok else None,after_frame=post+1 if evidence_ok else None,
                                 x_difference_before=before,x_difference_after=after,
                                 eligible_source=eligible,crossing_eligible_source=crossing_eligible,camera_motion=row["camera_motion"]))

    references, appearance_stats = [], []
    by_text = defaultdict(list)
    for description in descriptions:
        by_text[description["normalized_text"]].append(description)
    for text, members in sorted(by_text.items()):
        labeled = np.zeros((k,n),bool)
        excluded_ids=set()
        for member in members:
            for key, spans in member["per_target_frame_ranges"].items():
                tid=int(key)
                if tid not in id_to_index:
                    excluded_ids.add(tid)
                    continue
                ti=id_to_index[tid]
                for a,b in spans:
                    labeled[ti,a-1:b]=True
        labeled_visible = labeled & visible
        counts = labeled_visible.sum(axis=0)
        positive = counts>0
        unique = counts==1
        unique_scope=unique & eligible_frames
        a_stat=dict(dataset=dataset,sequence=sequence,source_split=row["source_split"],normalized_text=text,
                    text=members[0]["text"],raw_annotation_files=len(members),
                    source_paths=[m["source_path"] for m in members],excluded_non_target_gt_ids=sorted(excluded_ids),
                    all_frames_with_visible_labeled_targets=int(positive.sum()),all_unique_frames=int(unique.sum()),
                    all_ambiguous_frames=int((counts>1).sum()),eligible_frames_with_visible_labeled_targets=int((positive&eligible_frames).sum()),
                    eligible_unique_frames=int(unique_scope.sum()),eligible_ambiguous_frames=int(((counts>1)&eligible_frames).sum()),
                    eligible_unique_with_future_3s_frames=int((unique&future).sum()),eligible_source=bool(window),
                    unique_target_ids_all=ids[np.any(labeled_visible & unique[None,:],axis=1)].tolist(),
                    unique_target_ids_eligible=ids[np.any(labeled_visible & unique_scope[None,:],axis=1)].tolist())
        appearance_stats.append(a_stat)
        for ti,tid in enumerate(ids):
            mask=labeled_visible[ti] & unique_scope
            for a,b in ranges(mask):
                valid_future = np.flatnonzero(mask[a:b+1] & future[a:b+1])+a
                anchor=int(valid_future[len(valid_future)//2]) if len(valid_future) else (a+b)//2
                references.append(dict(ref_type="appearance",dataset=dataset,sequence=sequence,source_split=row["source_split"],
                                       text=members[0]["text"],normalized_text=text,target_ids=[int(tid)],
                                       frame_start=a+1,frame_end=b+1,reference_frame=anchor+1,t_ref_s=anchor/fps,
                                       reference_frames=b-a+1,with_future_3s_frames=len(valid_future),
                                       source_paths=[m["source_path"] for m in members],source_hashes=[m["sha256"] for m in members]))
    for event_type in PROTOCOL["event_reference"]["types"]:
        typed=sorted([e for e in events if e["type"]==event_type],key=lambda x:(x["time_s"],x["gt_id"]))
        times=np.array([e["time_s"] for e in typed])
        for event in typed:
            t=event["time_s"]
            nearby=int(np.searchsorted(times,t+1.,side="right")-np.searchsorted(times,t-1.,side="left"))
            event["same_type_events_within_1s"]=nearby
            event["unique_event_reference"]=nearby==1
            frame=event["reference_frame"]
            if not event["eligible_source"] or event.get("left_censored") or nearby!=1:
                continue
            edge=event.get("edge",{}).get("closest_edge")
            predicate={"enters_frame":f"enters the frame from the {edge}",
                       "leaves_frame":f"leaves the frame near the {edge} edge",
                       "becomes_occluded":"disappears from view", "reappears":"comes back into view"}[event_type]
            references.append(dict(ref_type="event",dataset=dataset,sequence=sequence,source_split=row["source_split"],
                                   text=f"the person who {predicate} at around {t:.3f} s",target_ids=[event["gt_id"]],
                                   reference_frame=frame,t_ref_s=(frame-1)/fps,frame_start=frame,frame_end=frame,
                                   reference_frames=1,with_future_3s_frames=int(future[frame-1]),event=event))

    position_frame_counts={}
    for rank in PROTOCOL["position_reference"]["ranks"]:
        rank_owner=np.full(n,-1,np.int32)
        for frame in np.flatnonzero(eligible_frames):
            active=np.flatnonzero(visible[:,frame])
            if len(active)<2:
                continue
            order=active[np.argsort(centers[active,frame,0],kind="stable")]
            winner,second=(order[0],order[1]) if rank=="leftmost" else (order[-1],order[-2])
            gap=abs(float(centers[winner,frame,0]-centers[second,frame,0]))/width
            if gap>=PROTOCOL["position_reference"]["min_second_place_gap_width_fraction"]:
                rank_owner[frame]=winner
        position_frame_counts[rank]=int((rank_owner>=0).sum())
        for ti,tid in enumerate(ids):
            for a,b in ranges(rank_owner==ti):
                future_fs=np.flatnonzero(future[a:b+1])+a
                anchor=int(future_fs[len(future_fs)//2]) if len(future_fs) else (a+b)//2
                references.append(dict(ref_type="position",dataset=dataset,sequence=sequence,source_split=row["source_split"],
                                       rank=rank,text=f"the {rank} person at {(anchor/fps):.3f} s",target_ids=[int(tid)],
                                       frame_start=a+1,frame_end=b+1,reference_frame=anchor+1,t_ref_s=anchor/fps,
                                       reference_frames=b-a+1,with_future_3s_frames=len(future_fs)))
    for ref in references:
        identity=[ref["dataset"],ref["sequence"],ref["ref_type"],ref["text"],ref["target_ids"],ref["frame_start"],ref["frame_end"]]
        ref["ref_id"]=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:20]
    counts=Counter(e["type"] for e in events)
    eligible_counts=Counter(e["type"] for e in events if e["eligible_source"])
    thresholds=[0.,.1,.25,.5,.75,1.]
    vis_stats=dict(rows=len(gt),track_ids=k,present_frames=int(present.sum()),visible_frames=int(visible.sum()),
                   region_ambiguous_visible_rows=int(((regions==-1)&visible).sum()),
                   source_last_column_quantiles=np.quantile(gt[:,8],[0,.1,.25,.5,.75,.9,1]).tolist(),
                   visible_at_threshold={str(t):int((gt[:,8]>=t).sum()) for t in thresholds} if dataset=="MOT17" else None,
                   true_visibility_available=dataset=="MOT17")
    summary=dict(dataset=dataset,sequence=sequence,source_split=row["source_split"],eligible_source=bool(window),
                 source_window=list(window) if window else None,frames=n,fps=fps,tracks=k,camera_motion=row["camera_motion"],
                 events=dict(counts),eligible_events=dict(eligible_counts),
                 overlap_episodes=len(overlaps),crossings=sum(e["crossing_status"]=="crossed" for e in overlaps),
                 crossing_unknown=sum(e["crossing_status"]=="unknown" for e in overlaps),
                 eligible_overlap_episodes=sum(e["eligible_source"] for e in overlaps),
                 eligible_crossings=sum(e["crossing_status"]=="crossed" and e["crossing_eligible_source"] for e in overlaps),
                 terminal_disappearances=sum(e.get("right_censored",False) for e in events),
                 initial_edge_appearances=sum(e.get("left_censored",False) for e in events),
                 reference_intervals=dict(Counter(r["ref_type"] for r in references)),
                 reference_intervals_with_future_3s=dict(Counter(r["ref_type"] for r in references if r["with_future_3s_frames"])),
                 position_frame_counts=position_frame_counts,visibility=vis_stats)
    return dict(metadata=metadata,tracks=tracks,events=events,overlaps=overlaps,references=references,
                appearance_stats=appearance_stats,summary=summary)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--pilot",action="store_true")
    parser.add_argument("--workers",type=int,default=4)
    args=parser.parse_args()
    started=time.monotonic()
    all_rows=json.loads((ROOT/"results/sequences.json").read_text())
    rows=[r for r in all_rows if r["has_public_gt_file"] and (r["dataset"]!="MOT17" or r["sequence"].endswith("-FRCNN"))]
    motion={(r["dataset"],r["video_key"]):r["camera_motion"] for r in json.loads((ROOT/"results/camera_motion_reviewed.json").read_text())}
    for row in rows:
        row["camera_motion"]=motion[(row["dataset"],row["video_key"])]
    descriptions=defaultdict(list)
    for line in (ROOT/"results/language_descriptions.jsonl").read_text().splitlines():
        d=json.loads(line)
        if d["dataset"] in {"MOT17","SportsMOT","DanceTrack"}:
            descriptions[(d["dataset"],d["sequence"])].append(d)
    out=RESULTS/"pilot" if args.pilot else RESULTS
    out.mkdir(parents=True,exist_ok=True)
    base=DATA/"pilot" if args.pilot else DATA
    if args.pilot:
        rows=[next(r for r in rows if r["dataset"]==d and (r["source_split"]=="val" if d!="MOT17" else True)) for d in ["DanceTrack","SportsMOT","MOT17"]]
    else:
        protocol=dict(PROTOCOL,generated_at=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),workers=args.workers)
        dump(out/"protocol.json",protocol)
        (out/"protocol.sha256").write_text(sha_file(out/"protocol.json")+"  protocol.json\n")
        convention=dict(generated_at=protocol["generated_at"],status="PROVISIONAL_PENDING_STAGE2_REVIEW",threshold=0.25,
                        DanceTrack="GT target box present => visible; last column is constant placeholder 1",
                        SportsMOT="GT target box present => visible; last column is constant placeholder 1",
                        MOT17="flag=1, class=1, visibility>=0.25 => visible; absent rows not visible",
                        interpolation=False,threshold_recommendation="retain requested 0.25; review measured distribution in Stage 2 report before final lock")
        dump(ROOT/"results/visibility_convention.json",convention)
        (ROOT/"results/visibility_convention.sha256").write_text(sha_file(ROOT/"results/visibility_convention.json")+"  visibility_convention.json\n")
    completed=[]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs={pool.submit(process_sequence,row,descriptions[(row["dataset"],row["sequence"])],base):row for row in rows}
        for future in as_completed(jobs):
            result=future.result();completed.append(result);s=result["summary"]
            print(json.dumps(dict(progress=len(completed),total=len(rows),dataset=s["dataset"],sequence=s["sequence"],events=s["events"],overlap=s["overlap_episodes"],crossings=s["crossings"],refs=s["reference_intervals"])),flush=True)
    completed.sort(key=lambda r:(r["summary"]["dataset"],r["summary"]["source_split"],r["summary"]["sequence"]))
    dump(out/"sequence_metadata.json",[r["metadata"] for r in completed])
    dump(out/"sequence_summary.json",[r["summary"] for r in completed])
    for key,filename in [("tracks","track_index.jsonl"),("events","point_events.jsonl"),("overlaps","overlap_events.jsonl"),
                         ("references","reference_resources.jsonl"),("appearance_stats","appearance_diagnostics.jsonl")]:
        target=out/filename
        with target.open("w") as stream:
            for result in completed:
                for record in result[key]:
                    stream.write(json.dumps(record,ensure_ascii=False,allow_nan=False)+"\n")
    dump(out/"compute_receipt.json",dict(status="STAGE2_COMPUTED_REPORT_PENDING",pilot=args.pilot,sequences=len(completed),
         elapsed_s=time.monotonic()-started,completed_at=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
         qa_generated=0,model_inference=False,training=False,tracker_runs=False,gpu_used=False))
    print("STAGE2_COMPUTE_COMPLETE",len(completed),"elapsed_s",time.monotonic()-started,flush=True)


if __name__=="__main__":
    main()
