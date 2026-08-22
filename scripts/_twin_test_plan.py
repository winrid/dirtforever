"""Work out the fewest in-game load tests that resolve every twin option.

Locations shipping the same lighting behave identically, so one test per
distinct group settles all of them. Where an archive is readable the rule is
already decided by which file the location ships; only encrypted (DLC)
archives need a load test, and those group by their offered label list.
"""
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from _twin_hypothesis import lighting_by_location, TWINS   # noqa: E402

NAME = json.loads((ROOT / 'scripts/_loc_name_map.json').read_text())
sweep = json.loads((ROOT / 'data/verified/conditions_by_location.json').read_text())
lighting, encrypted = lighting_by_location()

offers = collections.defaultdict(set)
for probe, opts in sweep.items():
    loc = NAME.get(probe)
    if loc:
        for lbl in opts:
            offers[lbl.replace(' Surface', '').strip()].add(loc)

# Twin -> the lighting file it selects, established from RaceNet's own choices
# plus the Poland load test (42 rendered, 16 tore the sky).
TWIN_FILE = {
    2: 'midday_over',   38: 'midday_overcast',
    16: 'sunset_dry',   42: 'sunset_overcast',
    20: 'sunset_wet',   34: 'sunset_cloudy',
}

decided, needs_test = {}, collections.defaultdict(list)
for lbl, (a, b) in TWINS.items():
    for loc in sorted(offers.get(lbl, set())):
        if loc in lighting:
            has_a = TWIN_FILE[a] in lighting[loc]
            has_b = TWIN_FILE[b] in lighting[loc]
            if has_a and not has_b:
                decided[(loc, lbl)] = a
            elif has_b and not has_a:
                decided[(loc, lbl)] = b
            elif has_a and has_b:
                decided[(loc, lbl)] = a      # both present; prefer the one
                                             # RaceNet used at such locations
            else:
                needs_test[lbl].append(loc)  # neither file: hypothesis is wrong
        else:
            needs_test[lbl].append(loc)

print('Decided from archives:', len(decided))
for lbl, (a, b) in TWINS.items():
    picks = collections.Counter(v for (l, lb), v in decided.items() if lb == lbl)
    print(f'  {lbl:30} {dict(picks)}')

print('\nNeed an in-game load test:')
total = 0
for lbl, locs in needs_test.items():
    print(f'  {lbl:30} {locs}')
    total += len(locs)
print(f'\n{total} (location, label) pairs need testing')

# Encrypted locations with identical offered lists behave identically.
groups = collections.defaultdict(list)
for probe, opts in sweep.items():
    loc = NAME.get(probe)
    if loc and loc not in lighting:
        groups[tuple(sorted(o.replace(' Surface', '').strip() for o in opts))].append(loc)
print('\nEncrypted locations grouped by identical offered list:')
for opts, locs in groups.items():
    twins = [l for l in opts if l in TWINS]
    if twins:
        print(f'  {sorted(locs)}  twins: {twins}')
