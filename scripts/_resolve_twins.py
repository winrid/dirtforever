"""Decide which twin id each location can load, from its lighting files.

Two ids can render the same label but select different lighting, so a location
loads only the twin whose file it ships -- Poland has sunset_overcast but not
sunset_dry, and 42 loads there while 16 tears the sky (verified in-game
2026-08-20).

Each id's lighting file is inferred from which locations OFFER that id: an id
is offered exactly where its file exists, so intersecting the offering
locations' file sets leaves the file it needs.
"""
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from _twin_hypothesis import lighting_by_location, TWINS   # noqa: E402

NAME = json.loads((ROOT / 'scripts/_loc_name_map.json').read_text())
sweep = json.loads((ROOT / 'data/verified/conditions_by_location.json').read_text())
labels = {int(k): v for k, v in
          json.loads((ROOT / 'data/verified/condition_labels.json').read_text()).items()}

lighting, encrypted = lighting_by_location()

# Which locations offer each label.
offers = collections.defaultdict(set)
for probe, opts in sweep.items():
    loc = NAME.get(probe)
    if loc:
        for lbl in opts:
            offers[lbl.replace(' Surface', '').strip()].add(loc)

# For an unambiguous label, the file it needs is shipped by every location that
# offers it and by no location that does not -- that pins the file exactly.
by_label_ids = collections.defaultdict(list)
for cid, lbl in labels.items():
    by_label_ids[lbl].append(cid)


def candidate_files(label):
    locs = offers.get(label, set()) & set(lighting)
    others = set(lighting) - locs
    if not locs:
        return set()
    common = set.intersection(*(lighting[l] for l in locs))
    return {f for f in common if not any(f in lighting[o] for o in others)}


print('Inferred lighting file per unambiguous label:')
label_file = {}
for lbl, ids in sorted(by_label_ids.items()):
    if len(ids) > 1 or lbl.startswith('lng_'):
        continue
    files = candidate_files(lbl)
    if len(files) == 1:
        label_file[lbl] = next(iter(files))
        print(f'  {lbl:34} -> {label_file[lbl]}')

print('\nTwin resolution per location:')
resolved_twins = {}
for lbl, (a, b) in TWINS.items():
    locs = sorted(offers.get(lbl, set()))
    print(f'\n=== {lbl}  ({a} vs {b})')
    for loc in locs:
        if loc not in lighting:
            print(f'  {loc:14} <archive encrypted - needs an in-game load test>')
            continue
        files = lighting[loc]
        print(f'  {loc:14} ships: {sorted(f for f in files if f.startswith(lbl.split(" / ")[0].lower().replace("daytime","midday").replace("sunset","sunset")))}')
    resolved_twins[lbl] = locs
