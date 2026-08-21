"""Re-derive every conditions decision from source and cross-check it.

Rebuilds the per-location table from the raw evidence rather than reading the
committed result, so a mistake in the pipeline shows up as a disagreement here
instead of being restated. Emits JSON for the audit page.

Evidence, strongest first:
  load      the stage was loaded in-game and the sky judged by eye
  officials the id RaceNet's own official events used at that location
  archive   the location's .nefs table lists the lighting file the id needs
  rx        an encrypted RX circuit matching the readable ones exactly
"""
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))

from _twin_hypothesis import lighting_by_location, racenet_officials, TWINS  # noqa: E402
from dr2server.game_data import (  # noqa: E402
    Location, STAGE_CONDITIONS_BY_LOCATION, STAGE_CONDITIONS_LABELS,
)

TWIN_FILE = {2: 'midday_over', 38: 'midday_overcast',
             16: 'sunset_dry',  42: 'sunset_overcast',
             20: 'sunset_wet',  34: 'sunset_cloudy'}

name_map = json.loads((ROOT / 'scripts/_loc_name_map.json').read_text())
sweep = json.loads((ROOT / 'data/verified/conditions_by_location.json').read_text())
labels = {int(k): v for k, v in
          json.loads((ROOT / 'data/verified/condition_labels.json').read_text()).items()}
loads = json.loads((ROOT / 'runtime/discovery/twin_results.json').read_text())

lighting, _encrypted = lighting_by_location()
officials = racenet_officials()

by_label = collections.defaultdict(list)
for cid, lbl in labels.items():
    by_label[lbl].append(cid)


def key(label):
    return label.replace(' Surface', '').strip()


rows, problems = [], []
for probe, opts in sorted(sweep.items()):
    loc_name = name_map.get(probe)
    if not loc_name or not opts:
        continue
    loc = Location[loc_name]
    served = list(STAGE_CONDITIONS_BY_LOCATION.get(loc, ()))
    is_rx = loc.discipline == 'rallycross'

    for i, raw_label in enumerate(opts):
        label = key(raw_label)
        cands = sorted(by_label.get(label, []))
        chosen = served[i] if i < len(served) else None

        # Independently re-derive what the choice should be.
        if len(cands) == 1:
            derived, how = cands[0], 'only id with this label'
        else:
            used = sorted(set(cands) & officials.get(loc_name, set()))
            ok = {int(c) for c, v in loads.get(loc_name, {}).items() if v == 'ok'}
            bad = {int(c) for c, v in loads.get(loc_name, {}).items() if v == 'broken'}
            hit_ok, hit_bad = sorted(ok & set(cands)), sorted(bad & set(cands))
            if hit_ok:
                derived, how = hit_ok[0], 'load'
            elif hit_bad:
                derived, how = [c for c in cands if c not in hit_bad][0], 'load (elimination)'
            elif len(used) == 1:
                derived, how = used[0], 'officials'
            elif loc_name in lighting:
                has = [c for c in cands if TWIN_FILE.get(c) in lighting[loc_name]]
                if len(has) == 1:
                    derived, how = has[0], 'archive'
                elif len(has) == 2:
                    # Both files present: the archive does not discriminate.
                    attested = [c for c in has
                                if any(c in ids for ids in officials.values())]
                    derived = attested[0] if len(attested) == 1 else min(has)
                    how = 'tie (attested)' if len(attested) == 1 else 'tie (arbitrary)'
                else:
                    derived, how = None, 'no evidence'
            elif is_rx:
                derived, how = cands[0], 'rx'
            else:
                derived, how = None, 'no evidence'

        row = {
            'location': loc_name, 'discipline': loc.discipline,
            'label': label, 'candidates': cands, 'served': chosen,
            'derived': derived, 'how': how,
            'officials': sorted(officials.get(loc_name, set()) & set(cands)),
            'ships': ([f for f in (TWIN_FILE.get(c) for c in cands) if f and
                       loc_name in lighting and f in lighting[loc_name]]
                      if len(cands) > 1 else []),
            'load': {c: v for c, v in loads.get(loc_name, {}).items()
                     if int(c) in cands},
        }
        rows.append(row)
        if chosen != derived:
            problems.append(row)
        if chosen is not None and STAGE_CONDITIONS_LABELS.get(chosen) != label:
            problems.append({**row, 'how': 'LABEL MISMATCH'})

    if len(served) != len(opts):
        problems.append({'location': loc_name, 'label': '(count)',
                         'served': len(served), 'derived': len(opts),
                         'how': 'COUNT MISMATCH', 'candidates': [],
                         'officials': [], 'ships': [], 'load': {},
                         'discipline': loc.discipline})

out = {'rows': rows, 'problems': problems}
(ROOT / 'runtime/discovery/audit.json').write_text(json.dumps(out, indent=1))

twins = [r for r in rows if len(r['candidates']) > 1]
print(f'{len(rows)} options across {len({r["location"] for r in rows})} locations')
print(f'{len(twins)} of them are twin decisions')
print('by evidence:', dict(collections.Counter(r['how'] for r in twins)))
print(f'disagreements between served and re-derived: {len(problems)}')
for p in problems:
    print('  !!', p['location'], p['label'], p['served'], '!=', p['derived'], p['how'])
