"""Map all Time Trial locations and their stages by reading the UI.

Starting state: Freeplay menu with TIME TRIAL tile highlighted.

For each location:
  1. Enter (open TT / select current location)
  2. Enter (confirm location → stage select screen)
  3. OCR the right-side panel to read the stage name
  4. Press Right on the Stage row to cycle to next stage
  5. OCR again — if same name as before, we hit the end
  6. Repeat until end detected
  7. Escape (back to location picker)
  8. Right (next location in picker)
  9. Goto 1

For rallycross locations: no stage picker, just conditions.
  Detect by checking if "Stage" row is absent.

Output: JSON mapping {location_name: [stage_name, ...]}
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

AHK = "C:/Program Files/AutoHotkey/v2/AutoHotkey64.exe"
SEND = "C:/Users/winrid/dr2server/scripts/send_key.ahk"
NIRCMD = "C:/Users/winrid/Downloads/nircmd-x64/nircmd.exe"
CROP = "C:/Users/winrid/dr2server/scripts/crop.py"
TESS = "C:/Program Files/Tesseract-OCR/tesseract.exe"
DISC = "C:/Users/winrid/dr2server/runtime/discovery"

# Crop regions on 1920x1080 full screenshot (calibrated 2026-04-13):
# Location city name on stage-select: "HAWKES BAY" in white text
LOCATION_HEADER = (550, 290, 900, 350)
# Stage name on right panel: "Elsthorpe Sprint Reverse" — clean white text
STAGE_NAME_PANEL = (1150, 360, 1500, 410)
# "Stages" label (to detect rally vs RX — rally has "Stages", RX doesn't)
STAGE_ROW = (560, 370, 700, 400)


def send(key: str, count: int = 1, delay: int = 1000) -> None:
    subprocess.run([AHK, SEND, key, str(count), str(delay)], check=False)


def shot(tag: str) -> str:
    os.makedirs(DISC, exist_ok=True)
    out = os.path.join(DISC, f"{tag}.png")
    subprocess.run([NIRCMD, "savescreenshotfull", out], check=False)
    return out


def crop(src: str, out: str, rect: tuple) -> None:
    subprocess.run(["python", CROP, src, out, *(str(v) for v in rect)],
                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def ocr_region(full_path: str, region: tuple, tag: str) -> str:
    """Crop a region from a full screenshot and OCR it."""
    cropped = os.path.join(DISC, f"{tag}.png")
    crop(full_path, cropped, region)
    base = cropped[:-4]
    subprocess.run([TESS, cropped, base, "--psm", "7"],
                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        with open(f"{base}.txt", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


def ocr_sparse(full_path: str, region: tuple, tag: str) -> str:
    """Crop + OCR with PSM 11 (sparse text) for multi-line headers."""
    cropped = os.path.join(DISC, f"{tag}.png")
    crop(full_path, cropped, region)
    base = cropped[:-4]
    subprocess.run([TESS, cropped, base, "--psm", "11"],
                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        with open(f"{base}.txt", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


def read_stage_name(idx: int) -> str:
    """Screenshot and OCR the stage name from the right panel."""
    full = shot(f"map_stage_{idx}")
    # Use the right-panel area where stage name is displayed
    name = ocr_region(full, STAGE_NAME_PANEL, f"map_stage_{idx}_name")
    return name.strip()


def read_location_name(idx: int) -> str:
    """Screenshot and OCR the location header."""
    full = shot(f"map_loc_{idx}")
    text = ocr_sparse(full, LOCATION_HEADER, f"map_loc_{idx}_header")
    # Location header is multi-line: "CATAMARCA PROVINCE\nARGENTINA"
    # Take all non-empty lines
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return " / ".join(lines) if lines else "(unknown)"


def has_stage_selector(idx: int) -> bool:
    """Check if the stage select screen has a 'Stage' row (rally) vs not (RX)."""
    full = f"{DISC}/map_loc_{idx}.png"
    if not os.path.exists(full):
        full = shot(f"map_loc_{idx}")
    text = ocr_region(full, STAGE_ROW, f"map_stage_row_{idx}")
    return "stage" in text.lower()


def main() -> None:
    max_locations = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    max_stages_per = int(sys.argv[2]) if len(sys.argv) > 2 else 15

    graph: Dict[str, List[str]] = {}

    # Enter TT once → location picker (remembers last position, likely 26/26).
    # Left at position 1 EXITS the picker, so we can't overshoot.
    # Left exactly 25 times: 26→1.  Right at 26 does nothing (no wrap).
    send("Enter", delay=3000)
    print("Entered TT. Pressing Left 25x to reach position 1...", flush=True)
    send("Left", count=25, delay=250)
    time.sleep(1)

    for loc_idx in range(max_locations):
        print(f"\n{'='*50}", flush=True)
        print(f"Location {loc_idx}", flush=True)

        # We're on the location picker with the current location highlighted.
        # Enter to confirm this location → stage select screen.
        send("Enter", delay=2500)

        # Read location name from header
        loc_name = read_location_name(loc_idx)
        print(f"  Location: {loc_name}", flush=True)

        # Try to read stages. Rally locations have a Stage row with
        # Right/Left arrows; RX locations have no stage picker.
        # We detect RX by checking if the first stage read is empty or
        # matches generic patterns.
        stages = []
        prev_name = None
        for stage_idx in range(max_stages_per):
            name = read_stage_name(loc_idx * 100 + stage_idx)

            # If first stage read is empty, this is likely an RX location
            if stage_idx == 0 and (not name or len(name) < 3):
                print(f"  (no stage name — likely rallycross)", flush=True)
                stages = ["Full Circuit"]
                break

            # End detection: same name as previous = wrapped
            if name == prev_name and stage_idx > 0:
                print(f"  (end detected — wrapped at stage {stage_idx})", flush=True)
                break

            stages.append(name)
            prev_name = name
            print(f"  Stage {stage_idx}: {name}", flush=True)

            # Right to next stage
            send("Right", delay=1200)

        graph[loc_name] = stages

        # Escape back to location picker
        send("Escape", delay=1500)
        # Right to next location
        send("Right", delay=1000)

    # Save results
    out_path = os.path.join(DISC, "tt_location_graph.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)
    print(f"\nWrote {out_path}", flush=True)
    print(f"\n{'='*50}", flush=True)
    print(f"Total locations: {len(graph)}", flush=True)
    for loc, stages in graph.items():
        print(f"  {loc}: {len(stages)} stages", flush=True)


if __name__ == "__main__":
    main()
