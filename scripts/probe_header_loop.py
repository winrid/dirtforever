"""Probe-loop variant that captures the event header (country name) only.

Does NOT press Up — keeps the top-level event details view where the
right panel shows "<CITY> / <COUNTRY>".

Starting state: Clubs list, first probe highlighted.
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

# Event header is shown in the upper-right of the event details page.
# Country name appears around x=1250-1500, y=300-370 on a 1920x1080 full shot.
HEADER_RECT = (1200, 280, 1500, 400)


def send_key(key: str, count: int = 1, delay_ms: int = 1500) -> None:
    subprocess.run([AHK, SEND, key, str(count), str(delay_ms)], check=False)


def shot(name: str) -> str:
    os.makedirs(DISC, exist_ok=True)
    out = os.path.join(DISC, f"{name}.png")
    subprocess.run([NIRCMD, "savescreenshotfull", out], check=False)
    return out


def crop(src: str, out: str, rect: tuple) -> None:
    subprocess.run(["python", CROP, src, out, *(str(v) for v in rect)],
                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def ocr(image_path: str) -> str:
    base = image_path.removesuffix(".png")
    subprocess.run([TESS, image_path, base, "--psm", "6"],
                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        with open(f"{base}.txt", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def probe_one(probe: Dict[str, Any], idx: int) -> Dict[str, Any]:
    tag = f"h{idx+1:02d}_L{probe['location_id']}"

    send_key("F1", delay_ms=2500)

    full = shot(tag + "_full")
    header_path = os.path.join(DISC, tag + "_header.png")
    crop(full, header_path, HEADER_RECT)
    text = ocr(header_path)

    send_key("Escape", delay_ms=2000)
    send_key("Right", delay_ms=1500)

    return {
        "probe_name":    probe.get("name", ""),
        "location_id":   probe["location_id"],
        "track_model_id": probe["track_model_id"],
        "ocr_text":      text.strip(),
        "header_image":  header_path,
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: probe_header_loop.py <probes.json>")
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        spec = json.load(f)
    probes = spec["probes"]

    results: List[Dict[str, Any]] = []
    for idx, probe in enumerate(probes):
        print(f"[{idx+1}/{len(probes)}] probing {probe.get('name')}")
        results.append(probe_one(probe, idx))
        time.sleep(0.2)

    out_path = os.path.join(DISC, "header_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Wrote {out_path}")

    print()
    print("=" * 60)
    for r in results:
        # Only interested in the country name line; typical UI: "JÄMSÄ\nFINLAND"
        lines = [ln.strip() for ln in r["ocr_text"].splitlines() if ln.strip()]
        print(f"L{r['location_id']:4d}  {' | '.join(lines)}")


if __name__ == "__main__":
    main()
