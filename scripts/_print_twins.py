"""Print every twin decision with the evidence behind it."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
d = json.loads((ROOT / 'runtime/discovery/audit.json').read_text())
twins = [r for r in d['rows'] if len(r['candidates']) > 1]

hdr = f"{'location':15}{'label':26}{'cands':10}{'pick':6}{'via':20}evidence"
print(hdr)
print('-' * len(hdr))
for r in sorted(twins, key=lambda r: (r['how'], r['location'])):
    ev = []
    if r['officials']:
        ev.append(f"RaceNet used {r['officials']}")
    if r['ships']:
        ev.append(f"ships {r['ships']}")
    if r['load']:
        ev.append(f"loaded {r['load']}")
    print(f"{r['location']:15}{r['label']:26}{str(r['candidates']):10}"
          f"{str(r['served']):6}{r['how']:20}{'; '.join(ev) or '-'}")
