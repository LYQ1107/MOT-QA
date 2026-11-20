"""Deterministic disjoint GT crops and anonymous galleries for DanceTrack val."""
import concurrent.futures as cf
import hashlib
import json
import math
from pathlib import Path
import random
import shutil
import time
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
from appearance_common import ROOT, RES, DATA, MODEL, PYTHON, MODEL_NAME, SYSTEM, GENERATE, MATCH, LOCAL, now, sha, write, read, write_rows, key

FONT = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 19)

CONFIG = {
    'stage': '2 optional appearance supplementation', 'seed': 42,
    'scope': 'All 273 GT IDs in 25 DanceTrack val videos; descriptions and validation only, no QA generation, tracker or training.',
    'raw_data': 'read only; original GT and language annotations unchanged',
    'authorization': 'User explicitly agreed to strong-VLM GT-crop appearance supplementation after Stage 2 gap report.',
    'model': {'name': MODEL_NAME, 'modelscope_revision': '8d6f46b05db6abe0cb3a5ca8c817929cc0fa2d5a',
              'local_path': str(MODEL), 'dtype': 'bfloat16', 'tensor_parallel_size': 2,
              'reason': 'Official dense 32B vision-language model, separate from evaluated Qwen2.5-VL-7B and eventual Qwen3-VL-8B filter.'},
    'crops': {'five_temporal_bins': 'span first..last GT-visible frames; best unused quality frame in each bin; generation bins 0,2,4, held-out bins 1,3',
              'quality': 'sqrt(box area / max area for this ID) * in-frame box-area fraction * (1 - maximum intersection / target box area)',
              'min_spacing_s': 0.5,
              'fallback': 'relax spacing if bin has no unused spaced candidate; then choose unused global best if bin empty; record relaxation. Never reuse a frame between generation and validation.',
              'padding_fraction_each_side': 0.05, 'output_jpeg_quality': 95,
              'native_crop': 'clipped only when reading pixels; no change to GT boxes; preserve aspect ratio, resize only for gallery',
              'gallery': {'crop_size_px': [144, 256], 'generation_crops_per_person': 3,
                          'held_out_crops_per_person': 2, 'columns': 4, 'persons_per_page': 12,
                          'labels': 'P01 etc assigned using seed42+stable stage/video/frame key; raw GT ID never included in model images/text'}},
    'anchor': {'selection': 'best-quality held-out frame with >=3 seconds remaining; ties earlier frame',
               'in_frame_area_fraction_min': 0.95, 'max_other_box_cover_fraction': 0.35,
               'min_native_box_height_px': 48, 'min_native_box_width_px': 16,
               'references_per_id_max': 1, 'full_frame_long_edge_px': 1280,
               'meaning': 'one verified timepoint only; do not extrapolate to a contiguous unique interval'},
    'generation': {'temperature': 0, 'seed': 42, 'max_tokens': 512, 'one_attempt_per_id': True,
                   'phrase_max_words': 30, 'no_scene_location_action_time_GT_label_in_phrase': True},
    'validation': {'same_model': True, 'independent_held_out_frames': True,
                   'independent_anonymous_permutations': True, 'temperature': 0, 'seed': 42, 'max_tokens': 768,
                   'global': 'phrase matches exactly target ID and no uncertain IDs among all same-video GT identities',
                   'local': 'at preselected anchor, full-frame plus every GT-present crop matches exactly target and no uncertain IDs',
                   'accept': 'both global and local pass, valid phrase, anchor geometric quality thresholds pass',
                   'parse_failure': 'retain raw output and reject; no content-directed retries or label repairs',
                   'limitation': 'same-model held-out visual consistency is not independent human verification; indistinguishable/unclear people may be rejected'},
    'service': {'max_model_len': 32768, 'gpu_memory_utilization': 0.80, 'max_num_seqs': 4,
                'max_num_batched_tokens': 16384, 'enforce_eager': True, 'max_images': 4,
                'mm_processor_kwargs': {'max_pixels': 2097152, 'min_pixels': 65536},
                'per_endpoint_concurrency': 3, 'max_estimated_operation_hours': 6},
    'visual_review': {'selection': 'one deterministic accepted ID per video if any; otherwise one generated ID; plus 5 seed42 rejected cases if available',
                      'purpose': 'agent checks facts and ambiguity, not a population error-rate estimate; final user review is still needed'},
    'stop': 'Stop and report after optional Stage 2 supplementation; Stage 3 remains unstarted.'
}


def seed_for(*parts):
    return 42 ^ int.from_bytes(hashlib.sha256('|'.join(map(str, parts)).encode()).digest()[:8], 'big')


def labels_for(tids, *parts):
    ids = sorted(map(int, tids))
    random.Random(seed_for(*parts)).shuffle(ids)
    return {f'P{i+1:02d}': tid for i, tid in enumerate(ids)}


def native_crop(frame, box):
    x, y, w, h = map(float, box)
    return frame.crop((max(0, math.floor(x-.05*w)), max(0, math.floor(y-.05*h)),
                       min(frame.width, math.ceil(x+1.05*w)), min(frame.height, math.ceil(y+1.05*h))))


def panel(paths, label='', cell=(144,256)):
    out = Image.new('RGB', (cell[0]*len(paths), cell[1]+30), (238,238,238))
    draw = ImageDraw.Draw(out)
    draw.text((5,3), label, font=FONT, fill=(0,0,0))
    for i, p in enumerate(paths):
        with Image.open(p) as source:
            tile = ImageOps.contain(source.convert('RGB'), cell, Image.Resampling.LANCZOS)
        out.paste(tile, (i*cell[0]+(cell[0]-tile.width)//2, 30+(cell[1]-tile.height)//2))
    return out


def gallery(label_to_id, crops, outbase, view):
    records = list(label_to_id.items())
    pages = []
    for page_start in range(0,len(records),12):
        chunk = records[page_start:page_start+12]
        tiles = [panel(crops[tid], label) for label,tid in chunk]
        tw, th = max(t.width for t in tiles), max(t.height for t in tiles)
        cols = min(4,len(tiles))
        im = Image.new('RGB', (cols*tw, math.ceil(len(tiles)/cols)*th), 'white')
        for i,tile in enumerate(tiles):
            im.paste(tile, ((i%cols)*tw,(i//cols)*th))
        path = outbase / f'{view}_page{len(pages):02d}.jpg'
        im.save(path, quality=95)
        pages.append(str(path))
    return pages


def process(meta):
    seq, fps = meta['sequence'], meta['fps']
    directory = DATA / seq
    directory.mkdir(parents=True, exist_ok=True)
    a = np.load(meta['unified_path'])
    ids, boxes, present = a['gt_ids'], a['boxes_xywh'], a['visible']
    width, height = meta['width'], meta['height']
    seqdir = Path(meta['source_gt_path']).parent.parent
    paths = sorted((seqdir/'img1').glob('*.jpg'))
    assert len(paths) == meta['frames']
    records, cropmap = [], {}
    for ti, tid0 in enumerate(ids):
        tid = int(tid0)
        vis = np.flatnonzero(present[ti])
        b = boxes[ti,vis].astype(np.float64)
        area = b[:,2]*b[:,3]
        inarea = (np.minimum(b[:,0]+b[:,2], width)-np.maximum(b[:,0],0)).clip(0) * (np.minimum(b[:,1]+b[:,3],height)-np.maximum(b[:,1],0)).clip(0)
        inclip = inarea/area
        cover = np.zeros(len(vis))
        for oi in range(len(ids)):
            if oi == ti:
                continue
            ob = boxes[oi,vis]
            iw = (np.minimum(b[:,0]+b[:,2],ob[:,0]+ob[:,2])-np.maximum(b[:,0],ob[:,0])).clip(0)
            ih = (np.minimum(b[:,1]+b[:,3],ob[:,1]+ob[:,3])-np.maximum(b[:,1],ob[:,1])).clip(0)
            frac = np.nan_to_num(iw*ih/area, nan=0.0)
            cover = np.maximum(cover, frac)
        quality = np.sqrt(area/area.max()) * inclip * (1-cover)
        bins = np.minimum(4, ((vis-vis[0])*5/(vis[-1]-vis[0]+1)).astype(int))
        selected = []
        for bi in range(5):
            unused = np.array([i for i in range(len(vis)) if i not in [s['visible_index'] for s in selected]], dtype=int)
            if not len(unused):
                break
            inbin = unused[bins[unused] == bi]
            spaced = np.array([i for i in inbin if all(abs(int(vis[i])-s['frame_index_0based']) >= .5*fps for s in selected)], dtype=int)
            pool, fallback = (spaced, 'none') if len(spaced) else ((inbin,'spacing_relaxed') if len(inbin) else (unused,'empty_bin_global_unused'))
            chosen = int(pool[np.lexsort((vis[pool], -quality[pool]))[0]])
            f = int(vis[chosen])
            role = 'generation' if bi in (0,2,4) else 'validation'
            p = directory / f'id{tid:03d}_{role}_{bi}_f{f+1:06d}.jpg'
            with Image.open(paths[f]) as frame:
                crop = native_crop(frame.convert('RGB'), boxes[ti,f])
                crop.save(p, quality=95)
            selected.append({'bin':bi,'role':role,'visible_index':chosen,'frame_index_0based':f,'frame_id_1based':f+1,
                'time_s':f/fps,'box_xywh':boxes[ti,f].tolist(),'quality':float(quality[chosen]),
                'in_frame_fraction':float(inclip[chosen]),'max_other_box_cover_fraction':float(cover[chosen]),
                'path':str(p),'sha256':sha(p),'source_frame_path':str(paths[f]),'source_frame_sha256':sha(paths[f]),'fallback':fallback})
        generation = [s for s in selected if s['role']=='generation']
        validation = [s for s in selected if s['role']=='validation']
        assert not set(s['frame_id_1based'] for s in generation) & set(s['frame_id_1based'] for s in validation)
        target = directory / f'id{tid:03d}_target.jpg'
        panel([s['path'] for s in generation], 'Target views').save(target,quality=95)
        candidates = [s for s in validation if s['time_s'] <= (meta['frames']-1)/fps-3]
        anchor = sorted(candidates,key=lambda s:(-s['quality'],s['frame_id_1based']))[0] if candidates else None
        if anchor:
            anchor = dict(anchor)
            anchor['geometric_quality_pass'] = bool(anchor['in_frame_fraction'] >= .95 and anchor['max_other_box_cover_fraction'] <= .35 and anchor['box_xywh'][2]>=16 and anchor['box_xywh'][3]>=48)
        record = {'unit_key':key(seq,tid),'dataset':'DanceTrack','source_split':'val','sequence':seq,'gt_id':tid,
                  'crop_records':selected,'generation_paths':[s['path'] for s in generation],
                  'validation_paths':[s['path'] for s in validation],'target_image':str(target),
                  'anchor':anchor,'visible_frame_count':len(vis),'crop_complete':len(generation)==3 and len(validation)==2,
                  'local_gallery':None,'global_gallery':None,'generation_gallery':None}
        records.append(record)
        cropmap[tid] = record
    genlabels = labels_for(ids,'generation',seq)
    vallabels = labels_for(ids,'heldout',seq)
    genpages = gallery(genlabels,{tid:cropmap[tid]['generation_paths'] for tid in map(int,ids)},directory,'generation_gallery')
    valpages = gallery(vallabels,{tid:cropmap[tid]['validation_paths'] for tid in map(int,ids)},directory,'heldout_gallery')
    for record in records:
        record['generation_gallery'] = {'images':genpages,'label_to_gt_id':genlabels}
        record['global_gallery'] = {'images':valpages,'label_to_gt_id':vallabels}
        anchor = record['anchor']
        if not anchor:
            continue
        f = anchor['frame_index_0based']
        local_ids = ids[present[:,f]]
        local_labels = labels_for(local_ids,'local',seq,record['gt_id'],f)
        localdir = directory / f'anchor_id{record["gt_id"]:03d}_f{f+1:06d}'
        localdir.mkdir(exist_ok=True)
        localpaths = {}
        with Image.open(paths[f]) as source:
            frame = source.convert('RGB')
        marked = frame.copy()
        draw = ImageDraw.Draw(marked)
        for lab,tid in local_labels.items():
            ti = int(np.flatnonzero(ids==tid)[0])
            b = boxes[ti,f]
            p = localdir/f'{lab}.jpg'
            native_crop(frame,b).save(p,quality=95)
            localpaths[tid] = [str(p)]
            x,y,w,h = map(float,b)
            draw.rectangle((x,y,x+w,y+h),outline=(255,255,0),width=2)
            draw.rectangle((x,max(0,y-23),x+48,max(0,y-23)+23),fill=(255,255,0))
            draw.text((x+2,max(0,y-23)),lab,fill=(0,0,0),font=FONT)
        marked.thumbnail((1280,1280),Image.Resampling.LANCZOS)
        fullpath = localdir/'full_frame.jpg'
        marked.save(fullpath,quality=95)
        localpages = gallery(local_labels,localpaths,localdir,'local_gallery')
        record['local_gallery'] = {'images':[str(fullpath)]+localpages,'label_to_gt_id':local_labels,
                                  'frame_id_1based':f+1,'time_s':f/fps}
    write(RES/'per_sequence'/f'{seq}.json',records)
    print(f'PREPARED {seq} IDs={len(records)} complete={sum(r["crop_complete"] for r in records)} anchors={sum(r["anchor"] is not None for r in records)}',flush=True)
    return records


def main():
    start = time.monotonic()
    RES.mkdir(parents=True,exist_ok=True)
    protocol_path = RES/'protocol_locked.json'
    assert not protocol_path.exists(), 'Already locked; do not rerun preparation in place.'
    write(RES/'authorization.json', {'at':now(),'latest_user_message':'我同意','approved_action':'Strong-VLM DanceTrack val GT-crop appearance supplementation, uniqueness checking, agent visual spot-checks; stop before Stage 3.',
                                    'project_root':str(ROOT),'basis':'Original task section 3.4; explicit acceptance of preceding proposal.'})
    CONFIG['locked_at'] = now()
    write(protocol_path, CONFIG)
    write(RES/'prompts_locked.json', {'system':SYSTEM,'generate':GENERATE,'blind_match':MATCH,'reference_instant_match':LOCAL})
    write(RES/'protocol_receipt.json', {'at':now(),'protocol_sha256':sha(protocol_path),'prompts_sha256':sha(RES/'prompts_locked.json')})
    with (ROOT/'research_log.md').open('a') as log:
        log.write(f'\n## Stage 2 approved appearance supplement — {now()}\n\nUser approved original3.4 fallback. Plan: all273 Dance val IDs get disjoint GT crops; official Qwen3-VL-32B-Instruct BF16 proposes truthful appearance phrases; blind held-out same-video matching and fixed-anchor full-frame matching reject ambiguity; agent visually checks examples; report and stop. No source edits, QA, trackers or training. Frozen protocol SHA256 `{sha(protocol_path)}`. Same-model verification is a consistency check, not independent human truth.\n')
    metas = [m for m in read(ROOT/'results/stage2/sequence_metadata.json') if m['dataset']=='DanceTrack' and m['source_split']=='val']
    allrows = []
    with cf.ThreadPoolExecutor(max_workers=4) as pool:
        for seqrows in pool.map(process,metas):
            allrows.extend(seqrows)
    assert len(allrows)==273 and len({r['unit_key'] for r in allrows})==273
    write_rows(RES/'crop_manifest.jsonl',allrows)
    artifacts = [protocol_path,RES/'prompts_locked.json',RES/'crop_manifest.jsonl',Path(__file__),ROOT/'src/appearance_common.py']
    imagepaths = sorted({Path(p) for r in allrows for p in [r['target_image']]+r['generation_paths']+r['validation_paths']+r['global_gallery']['images']+r['generation_gallery']['images']+(r['local_gallery']['images'] if r['local_gallery'] else [])})
    files = artifacts+imagepaths
    (RES/'preinference_snapshot.sha256').write_text(''.join(f'{sha(p)}  {p}\n' for p in files))
    write(RES/'preparation_summary.json', {'completed_at':now(),'seconds':time.monotonic()-start,'videos':len(metas),'IDs':len(allrows),
          'complete_disjoint_crops':sum(r['crop_complete'] for r in allrows),'anchors':sum(r['anchor'] is not None for r in allrows),
          'geometric_quality_anchors':sum(bool(r['anchor'] and r['anchor']['geometric_quality_pass']) for r in allrows),
          'image_artifacts_hashed':len(imagepaths),'relaxed_selections':sum(s['fallback']!='none' for r in allrows for s in r['crop_records'])})
    print(json.dumps(read(RES/'preparation_summary.json')),flush=True)


if __name__=='__main__':
    main()
