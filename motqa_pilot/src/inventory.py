"""Read-only Stage 1 inventory of local MOT datasets and official expressions."""
from pathlib import Path
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import configparser
import datetime
import hashlib
import io
import json
import os
import re
import time
import zipfile
import numpy as np
import cv2

ROOT = Path(__file__).resolve().parents[1]
DATASETS = {
    "DanceTrack": Path("/data2/user/LocateMOT/data/DanceTrack"),
    "SportsMOT": Path("/data2/user/LocateMOT_FullDataV2_spill/datasets/SportsMOT"),
    "MOT17": Path("/data2/user/LocateMOT/data/MOT17/MOT17"),
}
LAMOT_ARCHIVE = Path("/data2/user/TTA-RMOT-assets/flexhook/lamot_20261101/lamot_github/LaMOT-main.zip")
LAMOT = ROOT / "sources/LaMOT-5300242c06381c8d5ad36865dd88f4b62c2482bc/annotations_v1"
REFER = Path("/data2/user/TTA-RMOT-assets/flexhook/refer-dance-official/Refer-Dance")
ARCHIVES = [
    ("DanceTrack", Path("/data2/user/LocateMOT/data/downloads/DanceTrack") / name)
    for name in ("train1.zip", "train2.zip", "val.zip")
] + [
    ("SportsMOT", Path("/data2/user/LocateMOT_FullDataV2_spill/downloads/SportsMOT") / name)
    for name in ("train.tar", "val.tar")
] + [("MOT17", Path("/data2/user/LocateMOT/data/downloads/MOT17.zip")), ("LaMOT", LAMOT_ARCHIVE)]

CONFIG = {
    "stage": 1, "seed": 42, "scope": "inventory only; no questions, tracker, training or model inference",
    "raw_data_read_only": True,
    "mot17_canonical_detector": "FRCNN", "mot17_duplicate_video_key": "MOT17-NN",
    "description_normalization": "Unicode casefold, trim and collapse whitespace; no semantic rewriting",
    "description_dedup_keys": ["normalized text globally", "dataset + sequence + normalized text"],
    "description_target_definition": "union of original GT IDs across nonempty annotated frames; also report frame-wise mean",
    "camera": {
        "method": "GT-masked background Shi-Tomasi + forward/backward LK + partial affine RANSAC",
        "pairs_per_sequence": 12, "pair_interval_s": 0.2, "resize_width": 640,
        "gt_mask_padding_px_resized": 5, "max_corners": 800, "quality_level": 0.01,
        "min_feature_distance_px": 7, "forward_backward_error_px": 1.5,
        "min_tracks": 20, "min_ransac_inlier_fraction": 0.5,
        "ransac_reprojection_px": 2.0, "min_valid_pairs": 4,
        "motion_unit": "affine grid displacement / image diagonal / elapsed seconds",
        "moving_if_median_at_least": 0.005, "moving_if_p90_at_least": 0.015,
        "mot17_final_labels": "official paper Table 9; estimator retained for comparison",
        "unknown_policy": "record unresolved and inspect a montage; never silently force a bin",
    },
    "image_verification": "count all frame names; sizes for every image; dimensions and SHA256 first/middle/last; motion frames decoded",
    "checksum_scope": "complete archive SHA256; every GT/seqinfo/expression SHA256; image-tree manifest hashes paths+sizes, not pixels",
}


def now():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha_file(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(16 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical(dataset, name):
    return re.sub(r"-(DPM|FRCNN|SDP)$", "", name) if dataset == "MOT17" else name


def frame_ranges(frames):
    values = sorted(set(map(int, frames)))
    result = []
    for value in values:
        if not result or value != result[-1][1] + 1:
            result.append([value, value])
        else:
            result[-1][1] = value
    return result


def read_sequence(dataset, split, path):
    cfg = configparser.ConfigParser()
    ini_bytes = (path / "seqinfo.ini").read_bytes()
    cfg.read_string(ini_bytes.decode())
    s = cfg["Sequence"]
    length = int(s["seqLength"])
    row = dict(dataset=dataset, source_split=split, sequence=path.name,
               video_key=canonical(dataset, path.name), path=str(path), resolved_path=str(path.resolve()),
               fps=float(s["frameRate"]), width=int(s["imWidth"]), height=int(s["imHeight"]),
               declared_frames=length, duration_s=length / float(s["frameRate"]),
               seqinfo_sha256=sha_bytes(ini_bytes))
    image_dir = path / s["imDir"]
    frames = sorted((int(e.name.split(".")[0]), Path(e.path), e.stat().st_size)
                    for e in os.scandir(image_dir) if e.is_file() and e.name.lower().endswith((".jpg", ".png")) and not e.name.startswith("._"))
    row["actual_frames"] = len(frames)
    row["image_bytes"] = sum(x[2] for x in frames)
    row["frame_id_min_max"] = [frames[0][0], frames[-1][0]]
    existing = {x[0] for x in frames}
    row["missing_frame_ranges"] = frame_ranges(set(range(1, length + 1)) - existing)
    row["extra_frame_ranges"] = frame_ranges(existing - set(range(1, length + 1)))
    row["image_manifest_sha256"] = sha_bytes("".join(f"{f.name}\t{size}\n" for _, f, size in frames).encode())
    row["sample_images"] = []
    for index in sorted({0, len(frames) // 2, len(frames) - 1}):
        fid, f, size = frames[index]
        data = f.read_bytes()
        im = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        row["sample_images"].append(dict(frame=fid, path=str(f), bytes=size, sha256=sha_bytes(data),
                                        decoded=im is not None, width=None if im is None else im.shape[1],
                                        height=None if im is None else im.shape[0]))
    gt_path = path / "gt/gt.txt"
    row["has_public_gt_file"] = gt_path.exists()
    gt = None
    if gt_path.exists():
        raw = gt_path.read_bytes()
        gt = np.loadtxt(io.BytesIO(raw), delimiter=",", ndmin=2)
        targets = (gt[:, 6] == 1) & (gt[:, 7] == 1)
        pairs = gt[:, :2].astype(np.int64)
        row.update(gt_path=str(gt_path), gt_bytes=len(raw), gt_sha256=sha_bytes(raw),
                   gt_columns=gt.shape[1], gt_rows=len(gt), all_gt_ids=len(set(gt[:, 1].astype(int))),
                   target_gt_rows=int(targets.sum()), target_gt_ids=len(set(gt[targets, 1].astype(int))),
                   flag_counts=dict(Counter(map(str, gt[:, 6]))), class_counts=dict(Counter(map(str, gt[:, 7]))),
                   last_column_min_max=[float(gt[:, 8].min()), float(gt[:, 8].max())],
                   last_column_quantiles=np.quantile(gt[:, 8], [0, .25, .5, .75, 1]).tolist(),
                   last_column_distinct_values=len(np.unique(gt[:, 8])),
                   target_visibility_zero_rows=int(((gt[:, 8] == 0) & targets).sum()),
                   duplicate_frame_id_rows=len(pairs) - len(np.unique(pairs, axis=0)),
                   gt_frame_min_max=[int(gt[:, 0].min()), int(gt[:, 0].max())])
    return row, gt, dict((fid, path) for fid, path, _ in frames)


def camera_motion(row, gt, frames):
    p = CONFIG["camera"]
    cv2.setRNGSeed(42)
    n = row["declared_frames"]
    step = max(1, round(row["fps"] * p["pair_interval_s"]))
    starts = np.unique(np.linspace(1, n - step, p["pairs_per_sequence"]).astype(int))
    boxes = defaultdict(list)
    if gt is not None:
        for r in gt:
            boxes[int(r[0])].append(r[2:6])
    pairs = []
    for a in starts:
        b = int(a + step)
        a = int(a)
        record = dict(frame_a=a, frame_b=b)
        if a not in frames or b not in frames:
            record["failure"] = "missing frame"
            pairs.append(record)
            continue
        images, masks = [], []
        for fid in (a, b):
            im = cv2.imread(str(frames[fid]), cv2.IMREAD_GRAYSCALE)
            if im is None:
                break
            scale = min(1, p["resize_width"] / im.shape[1])
            im = cv2.resize(im, (round(im.shape[1] * scale), round(im.shape[0] * scale)), interpolation=cv2.INTER_AREA)
            mask = np.full(im.shape, 255, np.uint8)
            for x, y, w, h in boxes[fid]:
                pad = p["gt_mask_padding_px_resized"]
                x1, y1 = max(0, int(x * scale) - pad), max(0, int(y * scale) - pad)
                x2, y2 = min(im.shape[1], int((x + w) * scale) + pad), min(im.shape[0], int((y + h) * scale) + pad)
                mask[y1:y2, x1:x2] = 0
            images.append(im)
            masks.append(mask)
        if len(images) < 2:
            record["failure"] = "decode failure"
            pairs.append(record)
            continue
        h, w = images[0].shape
        points = cv2.goodFeaturesToTrack(images[0], maxCorners=p["max_corners"], qualityLevel=p["quality_level"],
                                         minDistance=p["min_feature_distance_px"], mask=masks[0])
        record["background_fraction"] = float((masks[0] > 0).mean())
        if points is None or len(points) < p["min_tracks"]:
            record["failure"] = "too few background corners"
            pairs.append(record)
            continue
        end, status, _ = cv2.calcOpticalFlowPyrLK(images[0], images[1], points, None, winSize=(21, 21), maxLevel=3)
        back, status_b, _ = cv2.calcOpticalFlowPyrLK(images[1], images[0], end, None, winSize=(21, 21), maxLevel=3)
        xy = np.rint(end[:, 0]).astype(int)
        valid = status.ravel().astype(bool) & status_b.ravel().astype(bool)
        valid &= np.linalg.norm(back[:, 0] - points[:, 0], axis=1) < p["forward_backward_error_px"]
        inside = (xy[:, 0] >= 0) & (xy[:, 0] < w) & (xy[:, 1] >= 0) & (xy[:, 1] < h)
        valid &= inside
        valid[inside] &= masks[1][xy[inside, 1], xy[inside, 0]] > 0
        record["valid_background_tracks"] = int(valid.sum())
        if valid.sum() < p["min_tracks"]:
            record["failure"] = "too few reliable background tracks"
            pairs.append(record)
            continue
        affine, inliers = cv2.estimateAffinePartial2D(points[valid, 0], end[valid, 0], method=cv2.RANSAC,
                                                     ransacReprojThreshold=p["ransac_reprojection_px"], maxIters=2000,
                                                     confidence=.99, refineIters=10)
        if affine is None or float(inliers.mean()) < p["min_ransac_inlier_fraction"]:
            record["failure"] = "inconsistent global transform"
            pairs.append(record)
            continue
        grid = np.array([[x * w, y * h] for x in [.1, .3, .5, .7, .9] for y in [.1, .5, .9]])
        moved = np.column_stack([grid, np.ones(len(grid))]) @ affine.T
        speed = np.median(np.linalg.norm(moved - grid, axis=1)) / np.hypot(w, h) / ((b - a) / row["fps"])
        record.update(speed_diagonals_per_second=float(speed), inlier_fraction=float(inliers.mean()), affine=affine.tolist())
        pairs.append(record)
    speeds = [r["speed_diagonals_per_second"] for r in pairs if "speed_diagonals_per_second" in r]
    median = float(np.median(speeds)) if speeds else None
    p90 = float(np.quantile(speeds, .9)) if speeds else None
    label = "unresolved" if len(speeds) < p["min_valid_pairs"] else ("moving" if median >= p["moving_if_median_at_least"] or p90 >= p["moving_if_p90_at_least"] else "static")
    official = None
    if row["dataset"] == "MOT17":
        official = "static" if row["video_key"] in {"MOT17-01", "MOT17-02", "MOT17-03", "MOT17-04", "MOT17-08", "MOT17-09"} else "moving"
    return dict(dataset=row["dataset"], source_split=row["source_split"], sequence=row["sequence"], video_key=row["video_key"],
                valid_pairs=len(speeds), median_speed=median, p90_speed=p90, automatic_label=label,
                camera_motion=official or label, label_source="official Table 9" if official else "background affine estimate", pairs=pairs)


def normalize(text):
    return " ".join(text.casefold().split())


def expression_record(resource, path, data, dataset, sequence, language_split, local_split):
    mapping = data["targets"] if resource == "LaMOT" else data["label"]
    language = data["language"] if resource == "LaMOT" else data["sentence"]
    per_id = defaultdict(list)
    nonempty = []
    counts = []
    for frame, ids in mapping.items():
        ids = sorted(set(map(int, ids)))
        counts.append(len(ids))
        if ids:
            nonempty.append(int(frame))
        for tid in ids:
            per_id[tid].append(int(frame))
    return dict(resource=resource, dataset=dataset, sequence=sequence, video_key=canonical(dataset, sequence),
                language_split=language_split, source_split=local_split,
                source_path=str(path), sha256=sha_file(path), text=language, normalized_text=normalize(language),
                target_ids=sorted(per_id), n_unique_targets=len(per_id), annotated_frame_keys=len(mapping),
                nonempty_frames=len(nonempty), nonempty_frame_ranges=frame_ranges(nonempty),
                mean_targets_per_annotated_frame=float(np.mean(counts)) if counts else 0.,
                mean_targets_per_positive_frame=float(np.mean([n for n in counts if n])) if nonempty else 0.,
                per_target_frame_ranges={str(tid): frame_ranges(fs) for tid, fs in sorted(per_id.items())})


def languages(sequence_rows, gt_data):
    split_lookup = {(r["dataset"], r["video_key"]): r["source_split"] for r in sequence_rows}
    output = []
    with (ROOT / "results/language_descriptions.jsonl").open("w") as stream:
        for resource, files in [("LaMOT", sorted(LAMOT.rglob("*.json"))),
                                ("Refer-Dance", sorted((REFER / "expression").glob("*/*.json")))]:
            for path in files:
                data = json.loads(path.read_text())
                if resource == "LaMOT":
                    rel = path.relative_to(LAMOT)
                    language_split, dataset = rel.parts[:2]
                    if dataset == "TAO":
                        dataset = "TAO/" + rel.parts[2]
                    sequence = path.stem.rsplit("_", 1)[0]
                else:
                    dataset, sequence, language_split = "DanceTrack", path.parent.name, None
                key = (dataset, canonical(dataset, sequence))
                rec = expression_record(resource, path, data, dataset, sequence, language_split, split_lookup.get(key))
                if key in gt_data:
                    gt = gt_data[key]
                    pairs = set(map(tuple, gt[:, :2].astype(np.int64)))
                    # Count original, unmodified frame/ID references, never remap IDs.
                    mapping = data["targets"] if resource == "LaMOT" else data["label"]
                    refs = [(int(frame), int(tid)) for frame, ids in mapping.items() for tid in set(ids)]
                    rec["gt_references"] = len(refs)
                    rec["gt_reference_matches"] = sum(pair in pairs for pair in refs)
                    rec["unmatched_target_ids"] = sorted(set(rec["target_ids"]) - set(gt[:, 1].astype(int)))
                    rec["invalid_frame_id_examples"] = [list(pair) for pair in refs if pair not in pairs][:5]
                stream.write(json.dumps(rec, ensure_ascii=False) + "\n")
                output.append(rec)
    groups = defaultdict(list)
    for rec in output:
        groups[(rec["resource"], rec["dataset"], rec["language_split"], rec["source_split"])].append(rec)
    summaries = []
    for (resource, dataset, langsplit, split), records in sorted(groups.items(), key=lambda x: str(x[0])):
        positive = [r for r in records if r["n_unique_targets"]]
        summaries.append(dict(resource=resource, dataset=dataset, language_split=langsplit, source_split=split,
                              sequences=len({r["sequence"] for r in records}), descriptions=len(records),
                              unique_texts=len({r["normalized_text"] for r in records}),
                              unique_sequence_texts=len({(r["sequence"], r["normalized_text"]) for r in records}),
                              positive_descriptions=len(positive), empty_descriptions=len(records)-len(positive),
                              unique_positive_texts=len({r["normalized_text"] for r in positive}),
                              mean_unique_targets_all=float(np.mean([r["n_unique_targets"] for r in records])),
                              mean_unique_targets_positive=float(np.mean([r["n_unique_targets"] for r in positive])) if positive else 0.,
                              single_target_descriptions=sum(r["n_unique_targets"] == 1 for r in records),
                              target_count_histogram=dict(Counter(str(r["n_unique_targets"]) for r in records)),
                              gt_references=sum(r.get("gt_references", 0) for r in records),
                              gt_reference_matches=sum(r.get("gt_reference_matches", 0) for r in records)))
    dump(ROOT / "results/language_summary.json", summaries)
    print("LANGUAGE", len(output), "records; grouped summary", json.dumps(summaries, ensure_ascii=False), flush=True)


def main():
    cv2.setNumThreads(1)
    started = time.monotonic()
    CONFIG["generated_at"] = now()
    protocol = ROOT / "results/stage1_inventory_protocol.json"
    dump(protocol, CONFIG)
    (ROOT / "results/stage1_inventory_protocol.sha256").write_text(sha_file(protocol) + "  stage1_inventory_protocol.json\n")
    rows, gt_data, frame_data = [], {}, {}
    for dataset, root in DATASETS.items():
        for split in ("train", "val", "test"):
            if not (root / split).exists():
                continue
            paths = sorted(p for p in (root / split).iterdir() if p.is_dir() and (p / "seqinfo.ini").exists())
            for path in paths:
                row, gt, frames = read_sequence(dataset, split, path)
                rows.append(row)
                key = (dataset, row["video_key"])
                if dataset != "MOT17" or path.name.endswith("-FRCNN"):
                    if gt is not None:
                        gt_data[key] = gt
                    frame_data[key] = frames
                print("SEQUENCE", dataset, split, path.name, row["actual_frames"], "frames", flush=True)
    dump(ROOT / "results/sequences.json", rows)
    canonical_rows = [r for r in rows if r["dataset"] != "MOT17" or r["sequence"].endswith("-FRCNN")]
    groups = defaultdict(list)
    for row in canonical_rows:
        groups[(row["dataset"], row["source_split"])].append(row)
    stats = []
    for (dataset, split), values in sorted(groups.items()):
        stats.append(dict(dataset=dataset, split=split, unique_sequences=len(values),
                          sequence_directories=sum(r["dataset"] == dataset and r["source_split"] == split for r in rows),
                          frames=sum(r["actual_frames"] for r in values), declared_frames=sum(r["declared_frames"] for r in values),
                          fps=dict(Counter(str(r["fps"]) for r in values)),
                          resolutions=dict(Counter(f"{r['width']}x{r['height']}" for r in values)),
                          gt_sequences=sum(r["has_public_gt_file"] for r in values),
                          gt_rows=sum(r.get("gt_rows", 0) for r in values),
                          target_gt_rows=sum(r.get("target_gt_rows", 0) for r in values),
                          target_gt_ids=sum(r.get("target_gt_ids", 0) for r in values),
                          image_bytes=sum(r["image_bytes"] for r in values)))
    dump(ROOT / "results/split_summary.json", stats)
    print("SPLITS", json.dumps(stats), flush=True)
    languages(rows, gt_data)
    motion = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(camera_motion, r, gt_data.get((r["dataset"], r["video_key"])),
                               frame_data[(r["dataset"], r["video_key"])]): r for r in canonical_rows}
        for future in as_completed(futures):
            item = future.result()
            motion.append(item)
            print("CAMERA", item["dataset"], item["sequence"], item["camera_motion"], item["valid_pairs"], flush=True)
    motion.sort(key=lambda r: (r["dataset"], r["source_split"], r["sequence"]))
    dump(ROOT / "results/camera_motion.json", motion)
    archives = []
    for dataset, path in ARCHIVES:
        record = dict(dataset=dataset, path=str(path), bytes=path.stat().st_size, sha256=sha_file(path))
        archives.append(record)
        print("ARCHIVE", json.dumps(record), flush=True)
    # The Refer-Dance release was already unpacked: hash every annotation file, not frame copies.
    refer_files = sorted((REFER / "expression").glob("*/*.json")) + [REFER / "labels.json", REFER / "seqmap.txt"]
    refer_entries = [dict(path=str(p.relative_to(REFER)), bytes=p.stat().st_size, sha256=sha_file(p)) for p in refer_files]
    dump(ROOT / "results/refer_annotation_manifest.json", refer_entries)
    archives.append(dict(dataset="Refer-Dance", path=str(REFER), bytes=sum(r["bytes"] for r in refer_entries),
                         annotation_files=len(refer_entries), annotation_manifest_sha256=sha_file(ROOT / "results/refer_annotation_manifest.json")))
    dump(ROOT / "results/local_archive_checksums.json", archives)
    anomalies = [r for r in rows if r["actual_frames"] != r["declared_frames"] or r["missing_frame_ranges"] or r["extra_frame_ranges"]
                 or r.get("duplicate_frame_id_rows", 0) or any(not s["decoded"] or s["width"] != r["width"] or s["height"] != r["height"] for s in r["sample_images"])]
    dump(ROOT / "results/inventory_anomalies.json", anomalies)
    dump(ROOT / "results/stage1_inventory_receipt.json", dict(completed_at=now(), elapsed_seconds=time.monotonic()-started,
         status="INVENTORY_COMPUTED_REPORT_PENDING", sequence_directories=len(rows), unique_videos=len(canonical_rows),
         unresolved_cameras=sum(r["camera_motion"] == "unresolved" for r in motion), anomalies=len(anomalies),
         gpu_used=False, raw_files_modified=False))
    print("INVENTORY_COMPLETE", len(canonical_rows), "videos; anomalies",len(anomalies), "elapsed_s",time.monotonic()-started, flush=True)


if __name__ == "__main__":
    main()
