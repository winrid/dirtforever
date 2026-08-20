"""Rewrite the conditions tables in game_data.py from the in-game probes."""
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

merged = {int(k): v for k, v in
          json.load(open(ROOT / 'data/verified/condition_labels.json')).items()}
resolved = json.load(open(ROOT / 'runtime/discovery/resolved_ids.json'))

by_label = collections.defaultdict(list)
for cid, lbl in merged.items():
    by_label[lbl].append(cid)

lines = ['STAGE_CONDITIONS_LABELS: Dict[int, str] = {']
for cid in sorted(merged):
    lbl = merged[cid]
    note = ''
    if lbl.startswith('lng_'):
        note = '  # untranslated in-game; the raw key is what the game shows'
    elif len(by_label[lbl]) > 1:
        others = [c for c in by_label[lbl] if c != cid]
        note = f'  # same label as {others}'
    lines.append(f'    {cid:>2}: {lbl!r},{note}')
lines.append('}')
labels_block = '\n'.join(lines)

lines = ['STAGE_CONDITIONS_BY_LOCATION: Dict[Location, tuple[int, ...]] = {']
from dr2server.game_data import Location  # noqa: E402
for loc in Location:
    ids = resolved.get(loc.name)
    if not ids:
        lines.append(f'    # {loc.name}: not offered in the Freeplay builder, so unverified')
        continue
    lines.append(f'    Location.{loc.name}: ({", ".join(str(i) for i in ids)},),')
    for cid in ids:
        lines.append(f'        # {cid:>2} {merged[cid]}')
lines.append('}')
table_block = '\n'.join(lines)

path = ROOT / 'dr2server/game_data.py'
src = path.read_text(encoding='utf-8')

start = src.index('STAGE_CONDITIONS_LABELS: Dict[int, str] = {')
end = src.index('\n}\n', start) + 2
src = src[:start] + labels_block + src[end:]

start = src.index('STAGE_CONDITIONS_BY_LOCATION: Dict[Location, tuple[int, ...]] = {')
end = src.index('\n}\n', start) + 2
src = src[:start] + table_block + src[end:]

path.write_text(src, encoding='utf-8')
print('labels:', len(merged), 'locations:', len(resolved))
print('ambiguous:', {l: sorted(i) for l, i in by_label.items() if len(i) > 1})
