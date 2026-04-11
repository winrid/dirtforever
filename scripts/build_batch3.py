"""Build probes_batch3.json covering all remaining unknown tracks.

Uses the block→real-location mapping discovered in batches 1 and 2 so that
every probe sends a valid Event.LocationId matching the track's real location.
"""
import json

# Map: block integer value (track's original block key) → real Location.new_value.
# Derived from batches 1 and 2.
BLOCK_TO_REAL = {
    2:  2,   # Sweden→Greece
    3:  3,   # Wales→Wales
    5:  5,   # Argentina→Germany
    10: 10,  # NewEngland→Hell
    13: 13,  # Poland→Finland
    14: 14,  # Germany→Sweden
    16: 16,  # NewZealand→Australia
    17: 17,  # France→Argentina
    19: 19,  # YasMarina→Montalegre
    20: 20,  # Montalegre→Barcelona
    31: 31,  # Australia→Spain
    34: 34,  # Scotland→NewZealand
    36: 36,  # Spain→Poland
    37: 37,  # Finland→NewEngland
    46: 46,  # Greece→Scotland
}

# Already tested in batches 1 and 2:
ALREADY_TESTED = {
    626, 628, 630, 632, 634, 636,  # batch 1 Finland block
    659, 661, 663, 667,             # batch 1 Greece block
    462, 464, 437, 439, 472, 480, 478, 511, 515, 519, 527,
    568, 586, 572, 604, 537, 538, 566, 574, 570, 596, 614, 620,
    580,                            # confirmed earlier (Spain Descenso)
}

# All track IDs grouped by block, from game_data.py Track enum.
BLOCKS = {
    2:  [467, 469],  # Sweden block minus already-tested 462, 464
    3:  [441, 442, 443, 446, 448],  # Wales minus 437, 439
    5:  [490, 496],  # Argentina minus 472, 480
    13: [512, 516],  # Poland minus 511, 515
    14: [520, 528],  # Germany minus 519, 527
    16: [569, 584, 585, 587, 588, 589, 590, 591, 592, 593],  # NZ minus 568, 586
    17: [573, 605, 606, 607, 608, 609, 610, 611, 612, 613],  # France minus 572, 604
    31: [575, 576, 577, 578, 579, 581, 582, 583],            # Australia minus 566, 574, 580
    34: [571, 594, 595, 597, 598, 599, 600, 601, 602, 603],  # Scotland minus 570, 596
    36: [615, 616, 617, 621, 622, 623, 624, 625],            # Spain minus 614, 620
    37: [627, 629, 631, 633, 635, 637],                      # Finland minus tested
}

probes = []
for block, ids in BLOCKS.items():
    loc = BLOCK_TO_REAL[block]
    for tid in ids:
        if tid in ALREADY_TESTED:
            continue
        probes.append({
            "name": f"B{block:02d}T{tid}",
            "location_id": loc,
            "track_model_id": tid,
            "stage_conditions": 1,
        })

print(f"Total probes: {len(probes)}")
out = {"probes": probes}
with open("C:/Users/winrid/dr2server/runtime/discovery/probes_batch3.json", "w") as f:
    json.dump(out, f, indent=2)
print("Wrote probes_batch3.json")
