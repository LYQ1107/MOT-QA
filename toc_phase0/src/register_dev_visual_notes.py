"""Record source-only development observations before inspecting new tracker IDs."""
import json
from pathlib import Path
from run_stage3_masa import ROOT,now,write_json

notes={
 'charades_5QXCO':'Multiple cardboard boxes in a dim background; partial blocking by a person, no unambiguous complete occlusion and return of the queried set.',
 'charades_DOUFF':'Phone remains in hand; fingers partly cover it. No unambiguous sustained complete occlusion in source overview.',
 'charades_J8KPE':'Cabinet door rotates and partly leaves the right boundary; person blocks parts. Orientation/boundary and full occlusion cannot be separated confidently.',
 'charades_MPX3X':'Green bottle moves from table to hand/hip; hand and body partly cover it, no confirmed full-hidden return in overview.',
 'perception_test_video_10175':'Blue cup remains at the back of the table. Dense review confirms one arm occlusion; other cloth/hand crossings leave a visible blue part.',
 'perception_test_video_10998':'Green knife handle often stays visible during manipulation. Partial hand coverage does not establish full occlusion.',
 'perception_test_video_3937':'Several books including two red covers; stacking creates terminal occlusion, no confirmed reappearance. Referent ambiguity excludes this from the identity-return rate.',
 'perception_test_video_5866':'Multiple white caps; hands manipulate similar instances. Physical instance identity is ambiguous, excluded from identity-return rate.',
 'perception_test_video_7116':'Two white eggs on a plate; dense review confirms forearm fully hides both at frames 20-23. Later crossings leave one or both partly visible.'
}
events=[
 dict(event_id='dev_blue_cup_arm',video_id='perception_test_video_10175',query='blue cup',before_frame=10,
      fully_hidden_frames=[11,12,13,14],after_frame=16,source_evidence='dev_dense_source/perception_test_video_10175_window00_page00.jpg',
      physical_target='stationary blue cup below the red round object at the back of the table',
      note='Cup body fully behind forearm; red object above the cup may remain visible. Return is clear at frame 16.'),
 dict(event_id='dev_eggs_forearm',video_id='perception_test_video_7116',query='eggs',before_frame=19,
      fully_hidden_frames=[20,21,22,23],after_frame=24,source_evidence='dev_dense_source/perception_test_video_7116_window00_page00.jpg',
      physical_target='two white eggs in the stationary shallow plate',
      note='Both white eggs fully behind forearm. Plural target is evaluated as the set of boxes matching these eggs, not the brown onion at the right.')
]
selection=json.loads((ROOT/'results/improvement_dev_visual_selection.json').read_text())
split=json.loads((ROOT/'results/dev_test_split_locked.json').read_text())
assert set(notes).issubset(set(split['dev_video_ids']))
path=ROOT/'results/improvement_dev_source_visual_notes.json'
assert not path.exists()
write_json(path,dict(registered_at=now(),scope='development_only',source_only=True,new_tracker_outputs_read=False,
                    answers_or_metadata_read=False,overview_videos=9,overview_pages=18,dense_windows=6,dense_pages=12,
                    notes=notes,confirmed_full_occlusion_return_events=events,
                    limitation='Small convenience sample; report missing target boxes separately, and do not equate geometry proxies with physical occlusion truth.'))
path.chmod(0o444)
print(json.dumps(dict(source_videos=len(notes),confirmed_events=len(events),path=str(path))))
