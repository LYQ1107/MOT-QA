"""Numerical spot-checks against original GT and original description JSONs."""
from pathlib import Path
from collections import Counter,defaultdict
import json
import hashlib
import numpy as np
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
R=ROOT/"results/stage2"


def read_lines(name):
    return [json.loads(x) for x in (R/name).read_text().splitlines()]


def main():
    rng=np.random.default_rng(42)
    metadata=json.loads((R/"sequence_metadata.json").read_text())
    lookup={(m["dataset"],m["sequence"]):m for m in metadata}
    source={}
    annotations={}
    def gt(m):
        key=(m["dataset"],m["sequence"])
        if key not in source:
            a=np.loadtxt(m["source_gt_path"],delimiter=",",ndmin=2)
            a=a[(a[:,6]==1)&(a[:,7]==1)]
            source[key]=a
        return source[key]
    def visible_rows(m,frame):
        a=gt(m)
        return a[(a[:,0]==frame)&((a[:,8]>=.25) if m["dataset"]=="MOT17" else True)]
    refs=read_lines("reference_resources.jsonl")
    assert len({r["ref_id"] for r in refs})==len(refs)
    dimensions=[]
    for m in metadata:
        with np.load(m["unified_path"]) as a:
            assert a["present"].shape==(len(a["gt_ids"]),m["frames"])
            assert int(a["present"].sum())==len(gt(m))
            expected=int((gt(m)[:,8]>=.25).sum()) if m["dataset"]=="MOT17" else len(gt(m))
            assert int(a["visible"].sum())==expected
            assert np.allclose(a["timestamps_s"],(a["frame_ids"]-1)/m["fps"])
            assert hashlib.sha256(Path(m["unified_path"]).read_bytes()).hexdigest()==m["npz_sha256"]
            dimensions.append(dict(dataset=m["dataset"],sequence=m["sequence"],tracks=len(a["gt_ids"]),
                                   presence_rows=int(a["present"].sum()),visible_rows=int(a["visible"].sum())))
    chosen=[]
    for dataset in ["DanceTrack","SportsMOT","MOT17"]:
        for kind in ["appearance","event","position"]:
            candidates=[r for r in refs if r["dataset"]==dataset and r["ref_type"]==kind]
            for i in rng.choice(len(candidates),size=min(10,len(candidates)),replace=False):
                ref=candidates[int(i)];m=lookup[(dataset,ref["sequence"])];frame=ref["reference_frame"]
                original=visible_rows(m,frame);visible_ids=set(original[:,1].astype(int))
                assert ref["target_ids"][0] in visible_ids
                assert abs(ref["t_ref_s"]-(frame-1)/m["fps"])<1e-12
                low,high=m["eligible_source_window_1based"]
                assert low<=ref["frame_start"]<=frame<=ref["frame_end"]<=high
                if kind=="appearance":
                    labels=set()
                    for p in ref["source_paths"]:
                        if p not in annotations:annotations[p]=json.loads(Path(p).read_text())
                        d=annotations[p];mapping=d.get("targets",d.get("label"))
                        labels.update(map(int,mapping.get(str(frame),[])))
                    assert labels & visible_ids == set(ref["target_ids"])
                elif kind=="position":
                    centers=original[:,2]+original[:,4]/2
                    order=np.argsort(centers)
                    w,v=(order[0],order[1]) if ref["rank"]=="leftmost" else (order[-1],order[-2])
                    assert int(original[w,1])==ref["target_ids"][0]
                    assert abs(centers[w]-centers[v])/m["width"]>=.05
                else:
                    e=ref["event"]
                    if e["type"] in ["leaves_frame","becomes_occluded"]:
                        last=e["last_visible_frame"];end=e["next_visible_frame"] or (m["frames"]+1)
                        allgt=gt(m);v=allgt[(allgt[:,1]==e["gt_id"])&((allgt[:,8]>=.25) if dataset=="MOT17" else True)]
                        assert not np.any((v[:,0]>last)&(v[:,0]<end))
                        assert (end-last-1)/m["fps"]>1
                    assert e["same_type_events_within_1s"]==1
                chosen.append(dict(ref_id=ref["ref_id"],dataset=dataset,type=kind,sequence=ref["sequence"],frame=frame,source_check="PASS"))
    overlaps=read_lines("overlap_events.jsonl")
    cross_checks=[]
    for dataset in ["DanceTrack","SportsMOT","MOT17"]:
        candidates=[e for e in overlaps if e["dataset"]==dataset and e["crossing_status"]=="crossed"]
        for i in rng.choice(len(candidates),size=min(10,len(candidates)),replace=False):
            e=candidates[int(i)];m=lookup[(dataset,e["sequence"])];a=gt(m)
            first,second=e["gt_ids"];xs=[]
            for frame in [e["before_frame"],e["after_frame"]]:
                p=a[(a[:,0]==frame)&(a[:,1]==first)][0];q=a[(a[:,0]==frame)&(a[:,1]==second)][0]
                xs.append((p[2]+p[4]/2)-(q[2]+q[4]/2))
            assert xs[0]*xs[1]<0
            assert e["frame_end"]-e["frame_start"]+1>=3
            for frame in range(e["frame_start"],e["frame_end"]+1):
                p=a[(a[:,0]==frame)&(a[:,1]==first)][0,2:6];q=a[(a[:,0]==frame)&(a[:,1]==second)][0,2:6]
                lo=np.maximum(p[:2],q[:2]);hi=np.minimum(p[:2]+p[2:],q[:2]+q[2:]);inter=np.prod(np.maximum(0,hi-lo));iou=inter/(p[2]*p[3]+q[2]*q[3]-inter)
                assert iou>=.1-1e-12
            cross_checks.append(dict(dataset=dataset,sequence=e["sequence"],gt_ids=e["gt_ids"],frames=[e["frame_start"],e["frame_end"]],check="PASS"))
    # Source snapshots remain unchanged. New Stage 2 files are not added to the old snapshot.
    for line in (ROOT/"results/stage1_snapshot.sha256").read_text().splitlines():
        digest,path=line.split("  ",1)
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
    (R/"source_audit.json").write_text(json.dumps(dict(seed=42,sequence_checks=dimensions,
        raw_reference_checks=chosen,raw_crossing_checks=cross_checks,
        stage1_snapshot_unchanged=True,all_passed=True),indent=2)+"\n")
    print("AUDIT_PASS",len(dimensions),"sequence arrays",len(chosen),"raw reference checks",len(cross_checks),"crossing checks")

    # Small, deterministic visual inspection pack. No question or answer is rendered.
    stage1_rows=json.loads((ROOT/"results/sequences.json").read_text())
    paths={(s["dataset"],s["sequence"]):Path(s["path"])/"img1" for s in stage1_rows}
    folder=R/"reference_review";folder.mkdir(exist_ok=True)
    selections=[]
    for dataset in ["DanceTrack","SportsMOT","MOT17"]:
        pool=[r for r in refs if r["dataset"]==dataset and r["ref_type"]=="appearance" and r["with_future_3s_frames"]]
        pool.sort(key=lambda r:((r["frame_end"]-r["frame_start"]+1)/lookup[(dataset,r["sequence"])]["fps"],r["ref_id"]))
        for label,ref in [("short",pool[0]),("long",pool[-1])]:
            m=lookup[(dataset,ref["sequence"])];frame=ref["reference_frame"];image_dir=paths[(dataset,ref["sequence"])]
            image_path=image_dir/f"{frame:08d}.jpg"
            if not image_path.exists():image_path=image_dir/f"{frame:06d}.jpg"
            image=Image.open(image_path).convert("RGB");image.thumbnail((1000,720));scale=image.width/m["width"]
            canvas=Image.new("RGB",(image.width,image.height+90),"white");canvas.paste(image,(0,90));draw=ImageDraw.Draw(canvas)
            draw.text((10,8),f"{dataset} {ref['sequence']} f={frame}  t={ref['t_ref_s']:.2f}s; GT target={ref['target_ids']}",fill="black")
            draw.text((10,30),ref["text"],fill="black")
            draw.text((10,52),f"{label} unique interval: {(ref['frame_end']-ref['frame_start']+1)/m['fps']:.3f}s; red=target, gray=other visible GT",fill="black")
            for row in visible_rows(m,frame):
                x,y,w,h=row[2:6].copy()
                if dataset=="MOT17":x-=1;y-=1
                color="red" if int(row[1]) in ref["target_ids"] else "gray"
                draw.rectangle([int(x*scale),int(y*scale)+90,int((x+w)*scale),int((y+h)*scale)+90],outline=color,width=3 if color=="red" else 1)
                draw.text((int(x*scale)+2,int(y*scale)+92),str(int(row[1])),fill=color)
            dest=folder/f"{dataset}_{label}.jpg";canvas.save(dest,quality=90)
            selections.append(dict(dataset=dataset,kind=label,path=str(dest),reference=ref))
            print("REVIEW",dest)
    (R/"reference_review_selection.json").write_text(json.dumps(selections,indent=2)+"\n")


if __name__=="__main__":
    main()
