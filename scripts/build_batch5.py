"""Build batch 5 probes file for LocationId candidate sweep.

Sweeps integer LocationId values 1-50, skipping the 18 already-confirmed,
using TrackModelId=580 (Descenso, known good) so the game has a valid stage
regardless of what header it renders.
"""
import json

KNOWN_LOCS = {2, 3, 5, 9, 10, 13, 14, 16, 17, 18, 19, 20, 31, 34, 36, 37, 38, 46}

candidates = [v for v in range(1, 51) if v not in KNOWN_LOCS]
print(f"sweep {len(candidates)} candidate location IDs: {candidates}")

probes = [
    {
        "name": f"LOC {v:03d}",
        "location_id": v,
        "track_model_id": 580,   # known working
        "stage_conditions": 1,
    }
    for v in candidates
]

with open("C:/Users/winrid/dr2server/runtime/discovery/probes_batch5.json", "w") as f:
    json.dump({"probes": probes}, f, indent=2)
print("Wrote probes_batch5.json")
