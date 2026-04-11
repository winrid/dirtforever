"""Capture watcher for the manual enum-mapping testing round.

Streams every new EgoNet request from captures/ and prints a single line per
relevant request, showing every identifier we still need to map.  Emit nothing
for calls we don't care about so the user sees only the useful signal.

Each stdout line is one event — this script is designed to be run under the
Monitor tool so events stream to the conversation in real time.
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Dict, Optional

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAP_DIR = os.path.join(HERE, "captures")

# Load the decoder lazily so the monitor still works if the module breaks.
try:
    sys.path.insert(0, HERE)
    from dr2server.game_data import decode_stage_conditions  # type: ignore[import-not-found]
except Exception:  # pragma: no cover
    def decode_stage_conditions(v: int) -> Dict[str, Any]:
        return {"label": f"SC#{v}", "surface_state_int": v >> 4, "preset_index": v & 0xF}


# Functions we want to surface — everything else is noise for this testing pass.
INTERESTING: set[str] = {
    "TimeTrial.GetLeaderboardId",
    "TimeTrial.PostTime",
    "RaceNetLeaderboard.GetLeaderboardEntries",
    "RaceNetLeaderboard.GetFriendsEntries",
    "Clubs.GetClubs",
    "Clubs.GetChampionshipLeaderboard",
    "Vehicle.SetCurrentVehicle",
    "Inventory.SetCurrentLivery",
    "RaceNetUser.UpdateProfile",
    "StageBegin",
    "StageComplete",
}


def _int(v: Any) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, dict):
        v = v.get("value", v)
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _summary(func: str, db: Dict[str, Any]) -> Optional[str]:
    """Return a single-line summary, or None to suppress."""
    short = func.split(".")[-1] if "." in func else func
    bits: list[str] = []

    # Always show these when present
    for k in ("VehicleClassId", "TrackModelId", "LocationId",
              "VehicleId", "LiveryId", "NationalityId",
              "ConditionsId", "Category",
              "StageConditions", "WeatherPresetId", "TimeOfDayId", "SurfaceCondId",
              "LeaderboardId", "StartRank", "Limit"):
        v = _int(db.get(k))
        if v is not None:
            bits.append(f"{k}={v}")

    # StageConditions / ConditionsId: decode composite IDs inline
    for cond_key in ("StageConditions", "ConditionsId"):
        v = _int(db.get(cond_key))
        if v is not None:
            d = decode_stage_conditions(v)
            bits.append(
                f"(decode: surface={d['surface_state_int']} preset={d['preset_index']})"
            )
            break

    # StageTime (float) for PostTime
    st = db.get("StageTime")
    if isinstance(st, (int, float)) and st:
        bits.append(f"StageTime={float(st):.3f}s")

    if not bits:
        return f"{short:26}  (no ID fields)"

    return f"{short:26} " + " ".join(bits)


def main() -> None:
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
    if not os.path.isdir(CAP_DIR):
        print(f"captures dir not found: {CAP_DIR}", flush=True)
        sys.exit(1)

    seen = set(os.listdir(CAP_DIR))
    print(f"watching {CAP_DIR} ({len(seen)} baseline)", flush=True)

    while True:
        try:
            current = set(os.listdir(CAP_DIR))
        except FileNotFoundError:
            time.sleep(1)
            continue

        new = current - seen
        seen = current
        for fn in sorted(new):
            path = os.path.join(CAP_DIR, fn)
            try:
                with open(path, encoding="utf-8") as f:
                    d = json.load(f)
            except Exception:
                continue
            func = d.get("headers", {}).get("X-EgoNet-Function", "")
            if func not in INTERESTING:
                continue
            db = d.get("decoded_body", {}) or {}
            line = _summary(func, db)
            if line:
                print(line, flush=True)
        time.sleep(0.5)


if __name__ == "__main__":
    main()
