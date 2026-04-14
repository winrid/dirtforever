"""Merge the 3 probe batch results into one master mapping by track id."""
from __future__ import annotations

import json
import os
import re
from typing import Optional, Dict, List, Tuple

DISC = "C:/Users/winrid/dr2server/runtime/discovery"

# Batches and their expected paths.  batch3 overwrote probe_results.json
# so we also pull the saved batch1 and batch2 data from the per-panel txt files
# (they're stored per-probe via panel_path OCR output).
# Actually, we stored probe_results.json after each batch — but the final file
# only has batch 3.  We have to reconstruct batches 1 and 2 from the hand-
# recorded findings in the conversation, or re-run them.  For now, we'll take
# batch 3 as canonical and add the known-good batch-1/batch-2 entries by
# scanning their panel .txt files.

def extract_name(ocr: str) -> str:
    """First non-empty line is the stage name (best-effort)."""
    for line in ocr.splitlines():
        line = line.strip()
        if not line:
            continue
        # Clean OCR artifacts
        if "Length" in line and "mi" in line:
            continue  # OCR caught the wrong row
        return line
    return ""

def load_panel_txts() -> Dict[int, str]:
    """Re-read all existing panel .txt files and build track_id -> name map."""
    out = {}
    for fn in os.listdir(DISC):
        if not fn.endswith("_panel.txt"):
            continue
        m = re.match(r"p\d+_T(\d+)_panel\.txt", fn)
        if not m:
            continue
        tid = int(m.group(1))
        with open(os.path.join(DISC, fn), encoding="utf-8", errors="replace") as f:
            text = f.read()
        name = extract_name(text)
        if name:
            out[tid] = name
    return out

# We also need to pull batch 1 and 2 results.  Those panels were overwritten
# by batch 3's filenames (p01_T626 etc. — batch 3 reused p01, p02 names).
# Re-reading the current panel files mostly gives batch 3 results.  Batch 1
# and 2 names we need to capture here manually from the conversation record.

BATCH_1_2 = {
    # batch 4 retry
    512: "Pitkajarvi",
    # batch 1 (Finland->NE + Greece->Scotland)
    626: "North Fork Pass",
    628: "Hancock Creek Burst",
    630: "Fuller Mountain Ascent",
    632: "Beaver Creek Trail Forward",
    634: "Hancock Hill Sprint Forward",
    636: "Tolt Valley Sprint Forward",
    659: "Old Butterstone Muir",
    661: "Rosebank Farm Reverse",
    663: "Newhouse Bridge",
    667: "Annbank Station Reverse",
    # batch 2
    462: "Fourkéta Kourva",
    464: "Ampelonas Ormi",
    437: "Sweet Lamb",
    439: "Pant Mawr",
    472: "Oberstein",
    480: "Hammerstein",
    478: "Full Circuit",           # Hell RX
    511: "Kakaristo",
    515: "Kotajarvi",
    519: "Älgsjön Sprint",
    527: "Östra Hinnsjön",
    568: "Mount Kaye Pass",
    586: "Yambulla Mountain Descent",
    572: "Las Juntas",
    604: "Camino a La Puerta",
    537: "Full Circuit",           # Montalegre RX
    538: "Full Circuit",           # Barcelona RX
    566: "Comienzo De Bellriu",
    574: "Final de Bellriu",
    570: "Te Awanga Forward",
    596: "Ocean Beach Sprint Forward",
    614: "Zarobka",
    620: "Jezioro Rotcze",
    580: "Descenso por carretera",  # already confirmed before batches
}

# Block → real Location value (based on old block key = new location id).
BLOCK_TO_LOCATION = {
    2:  "GREECE",
    3:  "WALES",
    5:  "GERMANY",
    10: "HELL",
    13: "FINLAND",
    14: "SWEDEN",
    16: "AUSTRALIA",
    17: "ARGENTINA",
    19: "MONTALEGRE",
    20: "BARCELONA",
    31: "SPAIN",
    34: "NEW_ZEALAND",
    36: "POLAND",
    37: "NEW_ENGLAND",
    46: "SCOTLAND",
}

def track_to_block(tid: int) -> Optional[int]:
    """Determine which block a track belonged to in the (wrong) original enum."""
    # From the hand-compiled BLOCKS in build_batch3.py + memory of enum layout
    tables = {
        2:  {462, 464, 467, 469},
        3:  {437, 439, 441, 442, 443, 446, 448},
        5:  {472, 480, 490, 496},
        10: {478},
        13: {511, 512, 515, 516},
        14: {519, 520, 527, 528},
        16: {568, 569, 584, 585, 586, 587, 588, 589, 590, 591, 592, 593},
        17: {572, 573, 604, 605, 606, 607, 608, 609, 610, 611, 612, 613},
        19: {537},
        20: {538},
        31: {566, 574, 575, 576, 577, 578, 579, 580, 581, 582, 583},
        34: {570, 571, 594, 595, 597, 598, 599, 600, 601, 602, 603, 596},
        36: {614, 615, 616, 617, 620, 621, 622, 623, 624, 625},
        37: {626, 627, 628, 629, 630, 631, 632, 633, 634, 635, 636, 637},
        46: {659, 661, 663, 667},
    }
    for block, ids in tables.items():
        if tid in ids:
            return block
    return None


def main() -> None:
    master: Dict[int, dict] = {}

    # Start with panel txt files (batch 3 overwrote batch 1/2 files)
    for tid, name in load_panel_txts().items():
        master[tid] = {"name": name, "source": "panel_txt"}

    # Override with known-good hand-recorded names (takes priority)
    for tid, name in BATCH_1_2.items():
        master[tid] = {"name": name, "source": "batch1/2/4"}

    # Attach real location
    for tid, info in master.items():
        block = track_to_block(tid)
        info["block"] = block
        info["real_location"] = BLOCK_TO_LOCATION.get(block) if block else None

    out_path = os.path.join(DISC, "track_mapping.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(master, f, indent=2, sort_keys=True)
    print(f"Wrote {out_path} with {len(master)} tracks")

    # Also print grouped by location
    by_loc: Dict[Optional[str], list] = {}
    for tid, info in sorted(master.items()):
        by_loc.setdefault(info["real_location"], []).append((tid, info["name"]))
    for loc in sorted(by_loc.keys() or [], key=lambda x: (x is None, x)):
        tracks = by_loc[loc]
        print(f"\n== {loc} ({len(tracks)} tracks) ==")
        for tid, name in tracks:
            print(f"  {tid:4d}  {name}")


if __name__ == "__main__":
    main()
