"""Correct display precision only; keep all underlying reference frames and facts."""
from pathlib import Path
from collections import Counter,defaultdict
import datetime
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parents[1]
R=ROOT/"results/stage2"


def main():
    refs=[json.loads(x) for x in (R/"revisions/initial_1decimal/reference_resources.jsonl").read_text().splitlines()]
    meta={(m["dataset"],m["sequence"]):m for m in json.loads((R/"sequence_metadata.json").read_text())}
    events=[json.loads(x) for x in (R/"point_events.jsonl").read_text().splitlines()]
    grouped=defaultdict(list)
    for e in events:
        grouped[(e["dataset"],e["sequence"],e["type"])].append(e)
    mapping={}
    for ref in refs:
        old=ref["ref_id"]
        if ref["ref_type"]=="position":
            ref["text"]=f"the {ref['rank']} person at {ref['t_ref_s']:.3f} s"
        elif ref["ref_type"]=="event":
            ref["text"]=re.sub(r"at around [-0-9.]+ s$",f"at around {ref['event']['time_s']:.3f} s",ref["text"])
        identity=[ref["dataset"],ref["sequence"],ref["ref_type"],ref["text"],ref["target_ids"],ref["frame_start"],ref["frame_end"]]
        ref["ref_id"]=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:20]
        mapping[old]=ref["ref_id"]
    timestamp_checks=Counter()
    for ref in refs:
        m=meta[(ref["dataset"],ref["sequence"])]
        if ref["ref_type"]=="position":
            display=float(ref["text"].rsplit(" at ",1)[1].removesuffix(" s"))
            assert round(display*m["fps"])+1==ref["reference_frame"],ref["ref_id"]
            timestamp_checks["position_nearest_frame_matches"]+=1
        elif ref["ref_type"]=="event":
            e=ref["event"];display=float(ref["text"].rsplit("at around ",1)[1].removesuffix(" s"))
            assert round(display*m["fps"])+1==e["frame"]
            same=grouped[(e["dataset"],e["sequence"],e["type"])]
            exact=[x for x in same if abs(x["frame"]-e["frame"])<=m["fps"]]
            shown=[x for x in same if abs(x["time_s"]-display)<=1]
            assert len(exact)==len(shown)==1,ref["ref_id"]
            timestamp_checks["event_frame_and_uniqueness_matches"]+=1
    with (R/"reference_resources.jsonl").open("w") as f:
        for ref in refs:f.write(json.dumps(ref,ensure_ascii=False,allow_nan=False)+"\n")
    protocol=json.loads((R/"protocol.json").read_text())
    protocol["reference_text_time_decimals"]=3
    protocol["display_precision_revision"]=dict(at=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        previous_decimals=1,current_decimals=3,reason="observed 82 wrong position targets, 2 out-of-range timestamps, 2 event-uniqueness changes after 0.1s rounding",
        underlying_reference_frames_and_facts_changed=False)
    (R/"protocol.json").write_text(json.dumps(protocol,indent=2)+"\n")
    digest=hashlib.sha256((R/"protocol.json").read_bytes()).hexdigest()
    (R/"protocol.sha256").write_text(digest+"  protocol.json\n")
    (R/"reference_id_rewrite_map.json").write_text(json.dumps(mapping,indent=2)+"\n")
    audit=json.loads((R/"source_audit.json").read_text())
    for check in audit["raw_reference_checks"]:
        original=check["ref_id"]
        if mapping[original]!=original:check["ref_id_before_time_display_fix"]=original
        check["ref_id"]=mapping[original]
    audit["final_time_display_checks"]=dict(timestamp_checks)
    (R/"source_audit.json").write_text(json.dumps(audit,indent=2)+"\n")
    result=dict(status="PASS",references=len(refs),changed_text_reference_ids=sum(a!=b for a,b in mapping.items()),
                initial_audit="time_display_audit_initial.json",checks=dict(timestamp_checks),
                underlying_reference_frames_and_facts_changed=False,protocol_sha256=digest)
    (R/"time_display_regression.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result))


if __name__=="__main__":
    main()
