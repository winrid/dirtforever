"""Iterate through debug-clubs probes and OCR the resolved stage info.

For each probe club in the Clubs list, this script:
  1. Sends F1 to enter Event Details
  2. Sends Up to highlight the stage tile (revealing the detail panel)
  3. Screenshots + crops to the game window
  4. OCRs the right-hand detail panel (stage name, conditions, surface type)
  5. Sends Escape twice to return to the Clubs list
  6. Sends Right to move to the next probe
  7. Writes the accumulated results to findings.json

Starting state: Clubs list, first probe tile highlighted.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List

AHK = "C:/Program Files/AutoHotkey/v2/AutoHotkey64.exe"
SEND = "C:/Users/winrid/dr2server/scripts/send_key.ahk"
CROP = "C:/Users/winrid/dr2server/scripts/crop.py"
TESS = "C:/Program Files/Tesseract-OCR/tesseract.exe"
NIRCMD = "C:/Users/winrid/Downloads/nircmd-x64/nircmd.exe"
DISC = "C:/Users/winrid/dr2server/runtime/discovery"

GAME_RECT = (456, 125, 1496, 932)  # fullscreen -> game window crop

# Right-hand detail panel region in FULL-SCREENSHOT (1920x1080) pixel coords.
# Covers "Stage name / Length / Elevation / Service Area / Conditions / Surface Type"
# rows.  Computed as GAME_RECT[:2] + (640, 260) to (1040, 482).
PANEL_RECT = (1096, 385, 1496, 607)


def send_key(key: str, count: int = 1, delay_ms: int = 1500) -> None:
    subprocess.run([AHK, SEND, key, str(count), str(delay_ms)], check=False)


def shot(name: str) -> str:
    os.makedirs(DISC, exist_ok=True)
    out = os.path.join(DISC, f"{name}.png")
    subprocess.run([NIRCMD, "savescreenshotfull", out], check=False)
    return out


def crop(src: str, out: str, rect: tuple) -> None:
    # No upscaling — panel coords are native.
    subprocess.run(
        ["python", CROP, src, out, *(str(v) for v in rect)],
        check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def ocr(image_path: str) -> str:
    base = image_path.removesuffix(".png")
    subprocess.run(
        [TESS, image_path, base, "--psm", "6"],
        check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        with open(f"{base}.txt", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def probe_one(probe: Dict[str, Any], idx: int) -> Dict[str, Any]:
    tag = f"p{idx+1:02d}_T{probe['track_model_id']}"

    send_key("F1", delay_ms=2500)
    send_key("Up", delay_ms=1500)

    full = shot(tag + "_full")
    panel_path = os.path.join(DISC, tag + "_panel.png")
    crop(full, panel_path, PANEL_RECT)

    text = ocr(panel_path)

    # One Escape from the Event Details screen returns to the Clubs list.
    send_key("Escape", delay_ms=2000)
    send_key("Right", delay_ms=1500)

    return {
        "probe_name":     probe.get("name", ""),
        "location_id":    probe["location_id"],
        "track_model_id": probe["track_model_id"],
        "stage_conditions": probe.get("stage_conditions", 1),
        "ocr_text":       text.strip(),
        "panel_image":    panel_path,
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: probe_loop.py <probes.json>")
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        spec = json.load(f)
    probes = spec["probes"]

    results: List[Dict[str, Any]] = []
    for idx, probe in enumerate(probes):
        print(f"[{idx+1}/{len(probes)}] probing {probe.get('name')}")
        results.append(probe_one(probe, idx))
        time.sleep(0.2)

    out_path = os.path.join(DISC, "probe_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Wrote {out_path}")

    # Also print a concise summary
    print()
    print("=" * 60)
    for r in results:
        name_lines = [ln for ln in r["ocr_text"].splitlines() if ln.strip()]
        first = name_lines[0] if name_lines else "(no ocr)"
        print(f"T{r['track_model_id']:4d}  {first}")


if __name__ == "__main__":
    main()
