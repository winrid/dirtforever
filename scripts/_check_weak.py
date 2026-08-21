"""Find twin decisions whose stated evidence does not actually discriminate."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
d = json.loads((ROOT / 'runtime/discovery/audit.json').read_text())
twins = [r for r in d['rows'] if len(r['candidates']) > 1]

print('Rows where BOTH twins\' lighting files are present (archive cannot decide):')
for r in twins:
    if len(r['ships']) > 1:
        decisive = 'officials' if r['officials'] else ('load' if r['load'] else 'NOTHING')
        print(f"  {r['location']:15} {r['label']:26} picked {r['served']:<3} "
              f"via {r['how']:10} ships {r['ships']}  -> settled by {decisive}")

print()
print('Rows resting on no direct evidence at all:')
for r in twins:
    if not r['officials'] and not r['load'] and not r['ships']:
        print(f"  {r['location']:15} {r['label']:26} picked {r['served']:<3} via {r['how']}")

print()
served_ids = {r['served'] for r in d['rows']}
for cid in (2, 16, 20, 34, 38, 42):
    n = sum(1 for r in d['rows'] if r['served'] == cid)
    print(f'  id {cid:<3} served at {n:>2} locations')
