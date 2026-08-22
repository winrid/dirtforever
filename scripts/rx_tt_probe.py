"""Probe rallycross circuit TrackModelIds through Freeplay > Time Trial.

Starting state: MAIN MENU with the TIME TRIAL tile highlighted, and the TT
location picker remembering the position of the *previous* RX circuit (the
script presses Right once to advance).  The picker order (26 entries) puts the
13 RX circuits at 14..26:

  14 Mettet, 15 Trois-Rivieres, 16 Lydden Hill, 17 Silverstone, 18 Loheac,
  19 Estering, 20 Bikernieki, 21 Hell, 22 Montalegre, 23 Killarney,
  24 Barcelona, 25 Holjes, 26 Yas Marina

Per circuit: Enter (picker) -> Right -> Enter (circuit select) -> Down ->
Enter (vehicle select) -> Enter (start).  TimeTrial.GetLeaderboardId fires
during the load and carries the TrackModelId.  We then wait for the
SERVICE AREA screen (OCR) and quit: Up, Enter, Up (YES), Enter -> main menu.

Usage: rx_tt_probe.py <first_picker_index> <last_picker_index>
Results append to runtime/discovery/rx_tt_results.json.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

AHK = "C:/Program Files/AutoHotkey/v2/AutoHotkey64.exe"
SEND = "C:/Users/winrid/dr2server/scripts/send_key.ahk"
NIRCMD = "C:/Users/winrid/Downloads/nircmd-x64/nircmd.exe"
CROP = "C:/Users/winrid/dr2server/scripts/crop.py"
TESS = "C:/Program Files/Tesseract-OCR/tesseract.exe"
LATEST = "C:/Users/winrid/dr2server/scripts/latest_tt.py"
DISC = "C:/Users/winrid/dr2server/runtime/discovery"
RESULTS = f"{DISC}/rx_tt_results.json"

PICKER = {
    14: "METTET", 15: "TROIS_RIVIERES", 16: "LYDDEN_HILL", 17: "SILVERSTONE",
    18: "LOHEAC", 19: "ESTERING", 20: "BIKERNIEKI", 21: "HELL",
    22: "MONTALEGRE", 23: "KILLARNEY", 24: "BARCELONA", 25: "HOLJES",
    26: "YAS_MARINA",
}


def send(key: str, count: int = 1, delay: int = 900) -> None:
    subprocess.run([AHK, SEND, key, str(count), str(delay)], check=False)
    time.sleep(delay / 1000)


def latest_tt() -> str:
    out = subprocess.run(["python", LATEST], capture_output=True, text=True).stdout.strip()
    return out.split(" ")[0] if out else "-"


def wait_capture(before: str, timeout: int = 60):
    out = subprocess.run(["python", LATEST, str(timeout), before],
                         capture_output=True, text=True).stdout.strip()
    print("   capture:", out, flush=True)
    if "no new capture" in out:
        return None
    try:
        return int(out.split("track=")[1].split()[0])
    except Exception:
        return None


def ocr_region(name: str, box, psm: int = 7) -> str:
    # nircmd directly: "bash" from a python subprocess resolves to WSL's bash,
    # which cannot run the C:/ shell helpers.  The game window sits at the
    # top-left of the desktop and send_key.ahk keeps it focused.
    src = f"{DISC}/{name}_c.png"
    subprocess.run([NIRCMD, "savescreenshotfull", src], capture_output=True)
    crop = f"{DISC}/{name}_ocr.png"
    subprocess.run(["python", CROP, src, crop, *map(str, box), "2"], capture_output=True)
    subprocess.run([TESS, crop, f"{DISC}/{name}_ocr", "--psm", str(psm)], capture_output=True)
    try:
        with open(f"{DISC}/{name}_ocr.txt", encoding="utf-8", errors="replace") as f:
            return " ".join(f.read().split())
    except FileNotFoundError:
        return ""


# Page header ("/ MAIN MENU") on the 1920x1080 game window.  The red italic
# "/ SERVICE AREA" header does NOT OCR on the busy service-area background, so
# that screen is detected by its white menu list instead ("Quit to Main Menu").
HEADER = (150, 80, 700, 140)
MENU = (170, 220, 620, 510)
REGIONS = {"HEADER": (HEADER, 7), "MENU": (MENU, 6)}


def wait_header(substr: str, timeout: int, tag: str, region: str = "HEADER") -> bool:
    box, psm = REGIONS[region]
    deadline = time.time() + timeout
    n = 0
    txt = ""
    while time.time() < deadline:
        txt = ocr_region(f"{tag}_{n % 2}", box, psm)
        needles = (substr,) if isinstance(substr, str) else tuple(substr)
        if any(s in txt.upper() for s in needles):
            print(f"   header '{txt}' after {int(timeout - (deadline - time.time()))}s", flush=True)
            return True
        n += 1
        time.sleep(1)
    print(f"   timeout waiting for header '{substr}' (last: '{txt}')", flush=True)
    return False


def main() -> None:
    first, last = int(sys.argv[1]), int(sys.argv[2])
    results = {}
    if os.path.exists(RESULTS):
        with open(RESULTS, encoding="utf-8") as f:
            results = json.load(f)

    for idx in range(first, last + 1):
        name = PICKER[idx]
        print(f"\n=== [{idx}/26] {name}", flush=True)

        # main menu (TIME TRIAL highlighted) -> location picker
        send("Enter", delay=2500)
        send("Right", delay=1200)
        send("Enter", delay=2500)          # circuit select
        send("Down", delay=800)
        send("Enter", delay=2500)          # vehicle select
        before = latest_tt()
        send("Enter", delay=2000)          # start -> load
        track = wait_capture(before, timeout=60)
        results[name] = {"picker_index": idx, "track_model_id": track}
        with open(RESULTS, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"   {name} -> {track}", flush=True)

        # wait for the stage to load (SERVICE AREA screen), then quit
        loaded = wait_header(("MAIN MENU", "TUNE VEHICLE", "LEADERBOARD", "OPTIONS"),
                             420, f"rxp_{idx}", region="MENU")
        if not loaded:
            print("   giving up on this run; stopping so state can be inspected", flush=True)
            return
        time.sleep(2)
        send("Up", delay=800)
        send("Enter", delay=2000)          # quit -> YES/NO dialog
        send("Up", delay=800)
        send("Enter", delay=2000)          # YES
        # The "/ MAIN MENU" header is dimmed during the fade-in, so also accept
        # the tab strip that sits inside the MENU region on that screen.
        back = wait_header("MAIN MENU", 30, f"rxq_{idx}") or \
            wait_header(("FREEPLAY", "MCRAE", "MY TEAM"), 90, f"rxq_{idx}", region="MENU")
        if not back:
            print("   did not get back to main menu; stopping", flush=True)
            return
        time.sleep(2)

    print("\nDONE", json.dumps(results, indent=2), flush=True)


if __name__ == "__main__":
    main()
