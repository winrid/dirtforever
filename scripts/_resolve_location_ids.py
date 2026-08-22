"""Resolve each location's in-game conditions list to concrete ids."""
import json, sys, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dr2server.egonet import decode_stream
from dr2server.game_data import TRACKS, Location

merged = {int(k): v for k, v in
          json.load(open('data/verified/condition_labels.json')).items()}
by_label = collections.defaultdict(list)
for cid, lbl in merged.items():
    by_label[lbl.lower()].append(cid)

# Ground truth: ids RaceNet's own official events used, per location.
LID = {int(l): l.name for l in Location}
officials = collections.defaultdict(set)
d = decode_stream(open('data/upstream_templates/RaceNetChallenges_GetChallenges.bin','rb').read())
val = lambda x: getattr(x, 'value', x)
for c in d['Challenges']:
    for e in c['Events']:
        for s in e['Stages']:
            t = TRACKS.get(val(s['TrackModelId']))
            if t:
                officials[LID[t['location_id']]].add(val(s['StageConditions']))

NAME = json.load(open('scripts/_loc_name_map.json'))
sweep = json.load(open('data/verified/conditions_by_location.json'))

def key(l): return l.replace(' Surface', '').strip().lower()

resolved, dropped = {}, []
for probe_name, labels in sweep.items():
    loc = NAME.get(probe_name)
    if not loc:
        continue
    ids = []
    for lbl in labels:
        cands = by_label.get(key(lbl), [])
        if len(cands) == 1:
            ids.append((cands[0], lbl))
        elif len(cands) > 1:
            evidenced = [c for c in cands if c in officials.get(loc, set())]
            if len(evidenced) == 1:
                ids.append((evidenced[0], lbl))
            else:
                dropped.append((loc, lbl, sorted(cands)))
        else:
            dropped.append((loc, lbl, []))
    resolved[loc] = ids

print(f"{'location':14} {'n':>3}  ids")
for loc, ids in resolved.items():
    print(f'{loc:14} {len(ids):>3}  {[c for c, _ in ids]}')
print(f'\ndropped {len(dropped)} options that two ids could satisfy:')
for loc, lbl, cands in dropped:
    print(f'  {loc:14} {lbl:34} candidates {cands}')
json.dump({loc: [c for c, _ in ids] for loc, ids in resolved.items()},
          open('runtime/discovery/resolved_ids.json', 'w'), indent=2)
