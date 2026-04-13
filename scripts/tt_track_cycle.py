"""Cycle through Time Trial tracks and capture TrackModelIds.

Starting state: Freeplay menu with TIME TRIAL highlighted.

For each track index:
  1. Enter → Enter (TT → location picker → confirm location)
  2. Right × track_index (select track N)
  3. Down Down Enter (confirm — ONE enter only, do NOT start driving)
  4. Wait for stage load + GetLeaderboardId capture
  5. Escape (pause menu) → Up (Quit to Main Menu) → Enter → Enter (confirm)
  6. Wait for return to Freeplay
  7. Repeat

Stops when GetLeaderboardId returns a TrackModelId we've already seen in
this run (indicates the track picker wrapped around).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from typing import Set

AHK = "C:/Program Files/AutoHotkey/v2/AutoHotkey64.exe"
SEND = "C:/Users/winrid/dr2server/scripts/send_key.ahk"
CAPDIR = "C:/Users/winrid/dr2server/captures"


def send(key: str, count: int = 1, delay: int = 1000) -> None:
    subprocess.run([AHK, SEND, key, str(count), str(delay)], check=False)


def latest_leaderboard_capture():
    """Return (filename, TrackModelId) for the most recent GetLeaderboardId."""
    for fn in sorted(os.listdir(CAPDIR), reverse=True)[:30]:
        try:
            with open(os.path.join(CAPDIR, fn)) as f:
                d = json.load(f)
        except Exception:
            continue
        if d.get("headers", {}).get("X-EgoNet-Function") != "TimeTrial.GetLeaderboardId":
            continue
        tm = d.get("decoded_body", {}).get("TrackModelId")
        if isinstance(tm, dict):
            tm = tm.get("value", tm)
        return (fn, int(tm) if tm is not None else None)
    return (None, None)


def check_known(tm: int) -> str:
    try:
        sys.path.insert(0, "C:/Users/winrid/dr2server")
        from dr2server.game_data import Track
        t = Track(tm)
        return f"{t.display_name} ({t.location.display_name})"
    except (ValueError, ImportError):
        return "*** NEW ***"


def main() -> None:
    max_tracks = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    loc_offset = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    seen: Set[int] = set()
    results = []

    for track_idx in range(max_tracks):
        print(f"\n--- Location {loc_offset} Track {track_idx} ---", flush=True)

        # Enter TT
        send("Enter", delay=2000)
        # Right × loc_offset to select the Nth location
        for _ in range(loc_offset):
            send("Right", delay=600)
        # Enter to confirm location
        send("Enter", delay=2000)

        # Right × track_idx to select track N
        for _ in range(track_idx):
            send("Right", delay=800)

        # Down Down Enter (CONFIRM button) then Enter (car select)
        send("Down", delay=800)
        send("Down", delay=800)
        send("Enter", delay=2000)  # hits CONFIRM
        send("Enter", delay=2000)  # confirms car selection → stage loads

        # Record the latest capture BEFORE we wait, so we detect NEW ones.
        before_fn, _ = latest_leaderboard_capture()

        # Wait for stage to load (up to 40s, polling for a NEW capture file)
        print("  waiting for capture...", flush=True)
        deadline = time.time() + 40
        new_tm = None
        while time.time() < deadline:
            time.sleep(2)
            cur_fn, cur_tm = latest_leaderboard_capture()
            if cur_fn is not None and cur_fn != before_fn:
                new_tm = cur_tm
                break

        if new_tm is not None:
            label = check_known(new_tm)
            is_new = new_tm not in seen
            seen.add(new_tm)
            results.append({"track_idx": track_idx, "tm": new_tm, "label": label})
            tag = "NEW" if is_new else "known"
            print(f"  CAPTURED: T{new_tm} = {label}  [{tag}]", flush=True)
        else:
            print("  no new capture (timeout)", flush=True)

        # Quit: wait for pre-race menu to appear (~25s from confirm),
        # then Escape → Up → Enter → Up → Enter.
        # The confirm dialog shows YES/NO vertically with NO default.
        # Up selects YES.
        time.sleep(25)
        send("Escape", delay=1500)  # open pause menu
        send("Up", delay=800)       # wrap to Quit to Main Menu
        send("Enter", delay=1500)   # opens quit confirm dialog (NO default)
        send("Up", delay=800)       # select YES
        send("Enter", delay=5000)   # confirm quit → back to Freeplay

        # Wait for freeplay to reload
        time.sleep(3)

        # Don't stop on timeout — might be a loading hiccup.
        # The caller can Ctrl-C to stop manually.

    print("\n=== RESULTS ===", flush=True)
    for r in results:
        print(f"  track_idx={r['track_idx']:2d}  T{r['tm']:4d}  {r['label']}", flush=True)
    print(f"Total: {len(results)} tracks captured", flush=True)


if __name__ == "__main__":
    main()
