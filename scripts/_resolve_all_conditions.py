"""Build the final per-location conditions table, twins included.

Three ids are shared by a pair that renders the same label but selects
different lighting, so a location loads only the twin whose file it ships.
Resolution, strongest evidence first:

  load-verified  the stage was loaded in-game and the sky rendered correctly
                 (or, for Poland/16, visibly tore)
  archive        the location's .nefs file table shows which of the pair's
                 lighting files it ships
  rx-inferred    an encrypted rallycross archive whose in-game option list is
                 identical to the readable RX circuits, all of which ship the
                 same lighting set

Nothing is dropped: every option the game offers gets an id.
"""
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from _twin_hypothesis import (  # noqa: E402
    lighting_by_location, racenet_officials, TWINS,
)
from dr2server.game_data import Location                   # noqa: E402

NAME = json.loads((ROOT / 'scripts/_loc_name_map.json').read_text())
sweep = json.loads((ROOT / 'data/verified/conditions_by_location.json').read_text())
labels = {int(k): v for k, v in
          json.loads((ROOT / 'data/verified/condition_labels.json').read_text()).items()}
verified = json.loads((ROOT / 'runtime/discovery/twin_results.json').read_text())

# Which lighting file each twin selects, established from RaceNet's own choices
# and confirmed by loading Poland twice (42 rendered, 16 tore the sky).
TWIN_FILE = {2: 'midday_over', 38: 'midday_overcast',
             16: 'sunset_dry',  42: 'sunset_overcast',
             20: 'sunset_wet',  34: 'sunset_cloudy'}

lighting, _ = lighting_by_location()
officials = racenet_officials()
by_label = collections.defaultdict(list)
for cid, lbl in labels.items():
    by_label[lbl].append(cid)


def key(l):
    return l.replace(' Surface', '').strip()


def resolve(loc, label, pair):
    a, b = pair
    ok = {int(c) for c, v in verified.get(loc, {}).items() if v == 'ok'}
    bad = {int(c) for c, v in verified.get(loc, {}).items() if v == 'broken'}
    if ok & {a, b}:
        return next(iter(ok & {a, b})), 'load-verified'
    if bad & {a, b}:                       # the other one by elimination
        return (b if a in bad else a), 'load-verified'
    # What RaceNet's own events used AT THIS LOCATION outranks the archive: it
    # is a direct observation of the pair being resolved, and it settles the
    # locations that ship both files, where the archive says nothing.
    used = set(officials.get(loc, set())) & {a, b}
    if len(used) == 1:
        return next(iter(used)), 'officials'
    if loc in lighting:
        has = {i for i in pair if TWIN_FILE[i] in lighting[loc]}
        if len(has) == 1:
            return next(iter(has)), 'archive'
        if len(has) == 2:
            # Both files are present, so the archive does NOT discriminate here
            # -- calling this 'archive' would claim evidence we do not have.
            # Prefer the twin RaceNet's own events are attested to use anywhere
            # (20 at Poland; 34 appears only in a club-builder capture and is
            # served by no location), and say plainly that is the reason.
            attested = {i for i in pair if any(i in ids for ids in officials.values())}
            if len(attested) == 1:
                return next(iter(attested)), 'tie-attested'
            return min(pair), 'tie-arbitrary'
    try:
        if Location[loc].discipline == 'rallycross':
            return a, 'rx-inferred'        # every readable RX circuit ships it
    except KeyError:
        pass
    return None, 'unresolved'


out, prov = {}, collections.Counter()
unresolved = []
for probe, opts in sweep.items():
    loc = NAME.get(probe)
    if not loc:
        continue
    ids = []
    for lbl in opts:
        k = key(lbl)
        cands = by_label.get(k, [])
        if len(cands) == 1:
            ids.append(cands[0])
        elif len(cands) > 1:
            cid, how = resolve(loc, k, tuple(sorted(cands)))
            prov[how] += 1
            if cid is None:
                unresolved.append((loc, k))
            else:
                ids.append(cid)
        else:
            unresolved.append((loc, k))
    out[loc] = ids

print(f"{'location':14}{'n':>3}  ids")
for loc in sorted(out):
    print(f'{loc:14}{len(out[loc]):>3}  {out[loc]}')
print('\ntwin provenance:', dict(prov))
print('unresolved:', unresolved or 'none')
total_opts = sum(len(v) for v in sweep.values() if v)
print(f'\n{sum(len(v) for v in out.values())} ids for {total_opts} in-game options')
(ROOT / 'runtime/discovery/resolved_ids.json').write_text(
    json.dumps(out, indent=2, sort_keys=True), encoding='utf-8')
