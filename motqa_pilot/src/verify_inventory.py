"""Verify reused release files and add explicit visual-review camera labels."""
from pathlib import Path, PurePosixPath
from collections import defaultdict
import datetime
import hashlib
import json
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main():
    rows = json.loads((ROOT / "results/sequences.json").read_text())
    archives = json.loads((ROOT / "results/local_archive_checksums.json").read_text())
    lookup = {(r["dataset"], r["sequence"]): r for r in rows}
    findings = []
    for archive in archives:
        dataset = archive["dataset"]
        if dataset not in {"DanceTrack", "SportsMOT", "MOT17"}:
            continue
        path = Path(archive["path"])
        images = defaultdict(list)
        metadata = []
        with zipfile.ZipFile(path) if path.suffix == ".zip" else tarfile.open(path, "r:") as release:
            members = release.infolist() if path.suffix == ".zip" else release.getmembers()
            for item in members:
                name = item.filename if path.suffix == ".zip" else item.name
                size = item.file_size if path.suffix == ".zip" else item.size
                parts = PurePosixPath(name).parts
                if len(parts) < 3 or any(p.startswith("._") for p in parts):
                    continue
                if parts[-2] == "img1" and parts[-1].endswith(".jpg"):
                    images[parts[-3]].append((int(parts[-1].split(".")[0]), parts[-1], size))
                elif parts[-1] == "seqinfo.ini" or parts[-2:] == ("gt", "gt.txt"):
                    seq = parts[-2] if parts[-1] == "seqinfo.ini" else parts[-3]
                    data = release.read(item) if path.suffix == ".zip" else release.extractfile(item).read()
                    row = lookup[(dataset, seq)]
                    expected = row["seqinfo_sha256"] if parts[-1] == "seqinfo.ini" else row["gt_sha256"]
                    metadata.append(dict(sequence=seq, member=name, bytes=size, sha256=sha(data), local_match=sha(data) == expected))
        frames = []
        for seq, entries in sorted(images.items()):
            row = lookup[(dataset, seq)]
            manifest = "".join(f"{name}\t{size}\n" for _, name, size in sorted(entries)).encode()
            frames.append(dict(sequence=seq, archive_frames=len(entries), local_frames=row["actual_frames"],
                               archive_image_bytes=sum(r[2] for r in entries),
                               image_name_size_manifest_matches=sha(manifest) == row["image_manifest_sha256"]))
        findings.append(dict(path=str(path), dataset=dataset, metadata=metadata, images=frames,
                             all_metadata_match=all(r["local_match"] for r in metadata),
                             all_image_manifests_match=all(r["image_name_size_manifest_matches"] for r in frames)))
        print("RELEASE_VERIFY", path.name, "metadata",len(metadata),"sequences",len(frames),"match",findings[-1]["all_metadata_match"],findings[-1]["all_image_manifests_match"],flush=True)
    dump(ROOT / "results/archive_local_verification.json", findings)
    assert all(r["all_metadata_match"] and r["all_image_manifests_match"] for r in findings)
    # Compare the three detection variants without multiplying underlying MOT17 videos.
    groups = defaultdict(list)
    for row in rows:
        if row["dataset"] == "MOT17":
            groups[(row["source_split"], row["video_key"])].append(row)
    duplicates = []
    for (split, key), values in sorted(groups.items()):
        signatures = {(r["actual_frames"], r["image_manifest_sha256"],
                       tuple(x["sha256"] for x in r["sample_images"]), r.get("gt_sha256")) for r in values}
        duplicates.append(dict(source_split=split, video_key=key, directories=[r["sequence"] for r in values],
                               identical_frame_manifests_sample_pixels_gt=len(signatures) == 1))
    dump(ROOT / "results/mot17_duplicate_verification.json", duplicates)
    assert all(r["identical_frame_manifests_sample_pixels_gt"] for r in duplicates)
    timestamp = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
    manual = {
        "dancetrack0015": ("static", "medium", "Featureless white studio. Left-wall fixture and room edges stay fixed in six distributed frames; changing dancer scale alone is not camera motion."),
        "dancetrack0044": ("moving", "high", "Blue-screen boundary and stage framing shift with pans/zoom over the clip."),
        "dancetrack0005": ("moving", "high", "Camera moves toward/away from dancers and changes floor/wall perspective and ceiling framing."),
        "dancetrack0034": ("moving", "high", "Stage floor and left wall framing shift, with changes in camera tilt/zoom."),
        "dancetrack0063": ("moving", "high", "Curtain/floor boundary and overhead basketball-board framing shift, consistent with tilt/zoom."),
    }
    motion = json.loads((ROOT / "results/camera_motion.json").read_text())
    review = []
    for row in motion:
        if row["sequence"] in manual:
            label, confidence, reason = manual[row["sequence"]]
            image = ROOT / "results/camera_review" / (row["sequence"] + ".jpg")
            review.append(dict(sequence=row["sequence"], before=row["camera_motion"], after=label,
                               confidence=confidence, rationale=reason, montage=str(image),
                               montage_sha256=sha(image.read_bytes()), reviewed_at=timestamp, reviewer="Codex visual inspection"))
            row.update(camera_motion=label, label_source="agent six-frame visual review", manual_confidence=confidence)
    assert not any(r["camera_motion"] == "unresolved" for r in motion)
    dump(ROOT / "results/camera_manual_review.json", review)
    dump(ROOT / "results/camera_motion_reviewed.json", motion)
    eligibility = dict(generated_at=timestamp, status="PROVISIONAL_PENDING_TRACKER_TRAIN_TUNE_DISCLOSURE",
                       questions_generated=False,
                       DanceTrack=dict(source_split="val", sequences=25),
                       SportsMOT=dict(source_split="val", sequences=45),
                       MOT17=dict(source_split="train", detector_variant="FRCNN", convention="frames floor(N/2)+1 through N inclusive, 1-based", windows=[]))
    for row in rows:
        if row["dataset"] == "MOT17" and row["source_split"] == "train" and row["sequence"].endswith("FRCNN"):
            n = row["declared_frames"]
            eligibility["MOT17"]["windows"].append(dict(sequence=row["sequence"], fps=row["fps"],
                                                     frame_start=n//2+1, frame_end=n, frames=n-n//2))
    dump(ROOT / "results/provisional_source_eligibility.json", eligibility)
    print("VERIFICATION_COMPLETE",flush=True)


if __name__ == "__main__":
    main()
