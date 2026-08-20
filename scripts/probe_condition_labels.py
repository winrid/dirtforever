"""Map StageConditions ids to the labels the game renders for them.

Serves one debug club per candidate id (see DR2_DEBUG_CLUBS_FILE in
dr2server/dispatcher.py), then walks the in-game Clubs list reading each
event's stage detail panel, where the game resolves the id we sent into a
"Time / Weather / Surface" label.

This is the only way to name an id we have never seen in a capture: RaceNet
does not expose the mapping, and the location archives only reveal which
lighting files exist, not which id selects them.

Run with the game on the Clubs list with the FIRST probe club selected, and
the server started with DR2_DEBUG_CLUBS_FILE pointing at the same probe file.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

AHK = "C:/Program Files/AutoHotkey/v2/AutoHotkey64.exe"
SEND = "C:/Users/winrid/dr2server/scripts/send_key.ahk"
NIRCMD = "C:/Users/winrid/Downloads/nircmd-x64/nircmd.exe"
TESS = "C:/Program Files/Tesseract-OCR/tesseract.exe"
DISC = Path("C:/Users/winrid/dr2server/runtime/discovery")
SHOT = DISC / "_label_probe.png"
CROP = DISC / "_label_probe_c.png"

# Full-desktop pixel boxes.
BOX_INDEX = (1660, 650, 1780, 690)    # "02 / 07" position counter
BOX_COND = (1150, 525, 1790, 570)     # "Conditions" row of the stage panel
BOX_HEADER = (175, 92, 820, 128)      # red breadcrumb

_LABEL_RE = re.compile(
    r"(Daytime|Dawn|Dusk|Night|Sunset|Sunrise|Morning|Evening|Midday|Noon)\s*/\s*"
    r"([A-Za-z ]+?)\s*/\s*"
    r"(Compacted Snow|Light Snow|Slush|Snow|Icy|Ice|Dry|Wet|Damp)"
    r"(?:\s+Surface)?", re.I)


def press(key: str, count: int = 1, delay: int = 400) -> None:
    subprocess.run([AHK, SEND, key, str(count), str(delay)],
                   check=False, capture_output=True)
    # send_key.ahk only sleeps BETWEEN presses, so settle here (capped at 1s).
    time.sleep(min(delay, 1000) / 1000.0)


def _ocr(box, psm: str = "7", scale: int = 2, whitelist: str = "") -> str:
    subprocess.run([NIRCMD, "savescreenshotfull", str(SHOT)],
                   check=False, capture_output=True)
    im = Image.open(SHOT).crop(box)
    im = im.resize((im.size[0] * scale, im.size[1] * scale))
    im.save(CROP)
    cmd = [TESS, str(CROP), "stdout", "--psm", psm]
    if whitelist:
        cmd += ["-c", f"tessedit_char_whitelist={whitelist}"]
    out = subprocess.run(cmd, capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    return " ".join((out.stdout or "").split()).strip()


# Some ids have no translated string, so the game prints the raw localisation
# key instead ("lng_conditions_dusk_rain_showers"). That still names the preset,
# so capture it rather than treating the id as unreadable.
# Tesseract reads the leading lowercase L of "lng_" as a capital I.
_LNG_RE = re.compile(r"[il]ng(_[a-z_]+)", re.I)


def read_label(timeout: float = 4.0) -> str:
    """The Conditions row; blank only while the panel is still drawing."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        raw = _ocr(BOX_COND)
        m = _LABEL_RE.search(raw)
        if m:
            tod, weather, surface = (g.strip().title() for g in m.groups())
            return f"{tod} / {weather} / {surface}"
        k = _LNG_RE.search(raw.replace(" ", ""))
        if k:
            return f"lng{k.group(1).lower()}"
        time.sleep(0.25)
    return ""


def read_index(timeout: float = 3.0) -> int | None:
    """1-based position in the Clubs list, from its "02 / 07" counter.

    The selection moves through the three visible tiles rather than scrolling
    them, so the selected tile's name is not at a fixed screen position -- but
    this counter is, and it identifies the probe just as well.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        raw = _ocr(BOX_INDEX, scale=3, whitelist="0123456789/ ")
        m = re.match(r"(\d{1,3})\s*/\s*(\d{1,3})", raw)
        if m:
            return int(m.group(1))
        time.sleep(0.25)
    return None


def probe_one() -> tuple[int | None, str]:
    idx = read_index()
    press("F1", 1, 900)        # Event Details -> CURRENT EVENT
    press("Up", 1, 700)        # focus stage 01 so its detail panel renders
    label = read_label()
    press("Escape", 1, 900)    # back to the Clubs list
    return idx, label


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("probe_file", help="the DR2_DEBUG_CLUBS_FILE being served")
    ap.add_argument("--out", default=str(DISC / "condition_labels.json"))
    args = ap.parse_args()

    spec = json.loads(Path(args.probe_file).read_text(encoding="utf-8"))
    expected = [int(p["stage_conditions"]) for p in spec["probes"]]

    out_path = Path(args.out)
    found: dict[str, str] = {}
    if out_path.exists():
        found = json.loads(out_path.read_text(encoding="utf-8"))

    for i, want in enumerate(expected):
        idx, label = probe_one()
        if idx is None:
            print(f"[{i+1}/{len(expected)}] could not read list position; stopping",
                  flush=True)
            break
        if idx != i + 1:
            # Navigation drifted: the list is not where we think it is, and
            # recording a label against the wrong id is worse than stopping.
            print(f"[{i+1}/{len(expected)}] list is at position {idx}; stopping",
                  flush=True)
            break
        found[str(want)] = label
        print(f"[{i+1}/{len(expected)}] {want:>3} -> {label or '(no label)'}",
              flush=True)
        out_path.write_text(json.dumps(found, indent=2, sort_keys=True),
                            encoding="utf-8")
        press("Right", 1, 500)
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
