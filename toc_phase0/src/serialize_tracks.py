"""Materialize each (video, phrase) JSON and raw-fact evidence text."""
import json
from pathlib import Path

from track_facts import query_document, serialize

ROOT=Path(__file__).resolve().parents[1]


def main():
    frozen=json.loads((ROOT/'results/stage3_tracker_frozen.json').read_text())
    threshold=frozen['output_score_threshold']
    tasks=json.loads((ROOT/'results/stage3_tracking_tasks.json').read_text())
    rows=[]
    for task in tasks:
        raw=json.loads((ROOT/'tracks/raw'/(task['video_id']+'.json')).read_text())
        assert raw['complete'] and raw['queries']==task['queries']
        for index,query in enumerate(raw['queries']):
            document=query_document(raw,index,threshold)
            directory=ROOT/'tracks/by_query'/task['video_id'];directory.mkdir(parents=True,exist_ok=True)
            json_path=directory/f'query_{index:02d}.json'; text_path=json_path.with_suffix('.txt')
            json_path.write_text(json.dumps(document,ensure_ascii=False,separators=(',',':'))+'\n')
            text_path.write_text(serialize(document))
            rows.append(dict(video_id=task['video_id'],query=query,json_path=str(json_path),text_path=str(text_path),
                             track_count=len(document['tracks']),observations=sum(len(t['observations']) for t in document['tracks'])))
    assert len(rows)==899
    (ROOT/'results/stage3_track_index.json').write_text(json.dumps(rows,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(dict(video_query_pairs=len(rows),empty_pairs=sum(r['track_count']==0 for r in rows),
                          observations=sum(r['observations'] for r in rows)),indent=2))


if __name__=='__main__':main()
