"""Record the Stage Conditions each location offers, from the Freeplay builder.

Freeplay -> Custom -> Create Championship -> (location) -> Edit Stage exposes a
"Stage Conditions" selector that lists only the conditions a location actually
ships lighting for.  That makes it the authoritative per-location set: the Time
Trial menu shows a narrower subset, and RaceNet validates nothing at all.

Nothing is created and no request is made -- the selector is read, not used.

Start with the game on the LOCATION SELECT screen.  Writes
runtime/discovery/conditions_by_location.json incrementally so an interrupted
run keeps what it already collected.
"""
from __future__ import annotations

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
SHOT = DISC / "_probe.png"
CROP = DISC / "_probe_c.png"
OUT = DISC / "conditions_by_location.json"

# Full-desktop pixel boxes.
BOX_HEADER = (175, 92, 820, 128)      # red "/ BREADCRUMB"
BOX_TITLE = (170, 172, 1250, 240)     # location name
BOX_COND = (570, 345, 1220, 390)      # Stage Conditions value
BOX_SURE = (700, 370, 1400, 450)      # "ARE YOU SURE?" exit prompt
# Rallycross has no per-stage track select: its conditions live on a "Weather"
# row of the EVENT SETTINGS screen instead.
BOX_COND_RX = (570, 385, 1240, 440)
BOX_ROWS = (175, 300, 620, 560)       # EVENT SETTINGS label column
MAX_OPTIONS = 30

_LABEL_RE = re.compile(
    r"(Daytime|Dusk|Night|Sunset|Morning|Midday)\s*/\s*"
    r"([A-Za-z ]+?)\s*/\s*"
    # Snow locations render "Daytime / Cloudy / Snow" with no "Surface" suffix.
    r"(Compacted Snow|Light Snow|Slush|Snow|Icy|Ice|Dry|Wet|Damp)"
    r"(?:\s+Surface)?", re.I)


def press(key: str, count: int = 1, delay: int = 300) -> None:
    subprocess.run([AHK, SEND, key, str(count), str(delay)],
                   check=False, capture_output=True)
    # send_key.ahk only sleeps BETWEEN presses, so a single press returns while
    # the UI is still animating.  Settle here (capped at 1s per repo rule).
    time.sleep(min(delay, 1000) / 1000.0)


def _grab() -> Image.Image:
    subprocess.run([NIRCMD, "savescreenshotfull", str(SHOT)],
                   check=False, capture_output=True)
    return Image.open(SHOT)


def _tess(im: Image.Image, psm: str) -> str:
    im.save(CROP)
    out = subprocess.run([TESS, str(CROP), "stdout", "--psm", psm],
                         capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    return " ".join((out.stdout or "").split()).strip()


def ocr(box: tuple[int, int, int, int], psm: str = "7", scale: int = 2) -> str:
    im = _grab().crop(box)
    return _tess(im.resize((im.size[0] * scale, im.size[1] * scale)), psm)


def ocr_red(box: tuple[int, int, int, int], psm: str = "7") -> str:
    """OCR red UI text (the breadcrumb), which sits on bright backgrounds.

    Plain greyscale loses it entirely, so isolate pixels where red dominates
    and render them black-on-white for tesseract.
    """
    im = _grab().crop(box).convert("RGB")
    px = im.load()
    mask = Image.new("L", im.size, 255)
    mp = mask.load()
    for y in range(im.size[1]):
        for x in range(im.size[0]):
            r, g, b = px[x, y]
            if r - max(g, b) > 35 and r > 90:
                mp[x, y] = 0
    mask = mask.resize((mask.size[0] * 2, mask.size[1] * 2))
    return _tess(mask, psm).upper()


def normalise(raw: str) -> str:
    m = _LABEL_RE.search(raw)
    if not m:
        return ""
    tod, weather, surface = (g.strip().title() for g in m.groups())
    return f"{tod} / {weather} / {surface}"


def header(timeout: float = 3.0) -> str:
    """Breadcrumb text; blank mid-transition, so poll until it resolves."""
    deadline = time.time() + timeout
    h = ocr_red(BOX_HEADER)
    while not h.strip() and time.time() < deadline:
        time.sleep(0.2)
        h = ocr_red(BOX_HEADER)
    return h


def read_condition(previous: str | None = None, timeout: float = 2.0,
                   box=None) -> str:
    box = box or BOX_COND
    deadline = time.time() + timeout
    label = normalise(ocr(box))
    while previous is not None and label == previous and time.time() < deadline:
        time.sleep(0.15)
        label = normalise(ocr(box))
    return label


def to_location_select() -> bool:
    """Steer to LOCATION SELECT from wherever we are.

    Escaping blindly overshoots out of the builder, so read the breadcrumb and
    move forward again when we have gone too far.
    """
    for _ in range(12):
        if "SURE" in ocr(BOX_SURE, psm="6").upper():
            press("Up", 1, 250)
            press("Enter", 1, 800)
            continue
        h = header()
        if "LOCATION" in h:
            return True
        if "TRACK SELECT" in h or "CONFIGURE" in h or "EVENT SETTINGS" in h:
            press("Escape", 1, 700)
            continue
        if "CREATE CHAMPIONSHIP" in h:
            press("Enter", 1, 900)
            continue
        if "CUSTOM" in h:
            press("Enter", 1, 900)
            continue
        if "MAIN MENU" in h:
            print("backed out to MAIN MENU; cannot recover", flush=True)
            return False
        press("Escape", 1, 600)
    return "LOCATION" in header()


def enumerate_at(box) -> list[str]:
    """Rewind to the first option, then walk right to the last.

    The selector does not wrap: pressing Right past the end is a no-op, so a
    label that stops changing marks the end of the list.
    """
    press("Left", MAX_OPTIONS, 60)
    seq = [read_condition(box=box)]
    if not seq[0]:
        return []
    for _ in range(MAX_OPTIONS):
        press("Right")
        label = read_condition(previous=seq[-1], box=box)
        if not label or label == seq[-1]:
            break
        seq.append(label)
    return seq


def probe_one() -> tuple[str, list[str]]:
    """Read one location's conditions, taking whichever route its discipline uses."""
    name = ocr(BOX_TITLE, psm="7") or "?"
    press("Enter", 1, 900)              # -> EVENT SETTINGS
    if "WEATHER" in ocr(BOX_ROWS, psm="6").upper():
        # Rallycross: conditions are the third row here.
        press("Down", 2, 250)
        seq = enumerate_at(BOX_COND_RX)
    else:
        # Rally: conditions live per stage, behind Confirm -> Edit Stage.
        press("Down", 2, 250)
        press("Enter", 1, 900)          # -> CONFIGURE EVENT
        press("Left", 1, 500)           # select stage 01
        press("Enter", 1, 900)          # -> TRACK SELECT
        press("Down", 1, 400)           # highlight Stage Conditions
        deadline = time.time() + 5
        while not normalise(ocr(BOX_COND)) and time.time() < deadline:
            time.sleep(0.3)
        seq = enumerate_at(BOX_COND)
    to_location_select()
    return name, seq


def main() -> int:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 26
    if not to_location_select():
        print("not on LOCATION SELECT; aborting", flush=True)
        return 1
    results: dict[str, list[str]] = {}
    if OUT.exists():
        results = json.loads(OUT.read_text())
    for i in range(count):
        name, seq = probe_one()
        results[name] = seq
        OUT.write_text(json.dumps(results, indent=2))
        print(f"[{i+1}/{count}] {name}: {len(seq)}", flush=True)
        for s in seq:
            print(f"      {s}", flush=True)
        press("Right", 1, 600)  # next location
    print(f"wrote {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
