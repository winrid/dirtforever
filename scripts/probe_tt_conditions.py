"""Enumerate valid StageConditions ids per location from real RaceNet.

Talks straight to the live EgoNet host with a session id harvested from a
proxied Login.Login, so no game automation is involved.

Oracle: TimeTrial.GetLeaderboardId may mint an id for any (track, conditions)
tuple, so an id alone proves nothing.  The discriminator is the leaderboard
population -- RaceNetLeaderboard.GetLeaderboardEntries.TotalEntries -- which is
non-zero only for combinations the game actually offers players.

Usage:
    python scripts/probe_tt_conditions.py --session <id> --validate
    python scripts/probe_tt_conditions.py --session <id> --sweep
"""
from __future__ import annotations

import argparse
import http.client
import json
import ssl
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dr2server.egonet import UInt32, decode_stream, encode_stream  # noqa: E402
from dr2server.game_data import (  # noqa: E402
    LOCATIONS, TRACKS, Location, get_verified_routes_for_location,
)

UPSTREAM = "159.153.126.42"
PATH = "/RP17/1.18.0/STEAM/"
OUT = Path(__file__).resolve().parent.parent / "runtime" / "ttprobe" / "conditions_by_location.json"


def _val(x: Any) -> Any:
    return getattr(x, "value", x)


class Upstream:
    """Minimal EgoNet client against the real RaceNet host."""

    def __init__(self, session: str, delay: float = 0.1) -> None:
        self.session = session
        self.delay = delay
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        self._ctx = ctx
        self.calls = 0

    def call(self, function: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        body = encode_stream(params)
        headers = {
            "Content-Type": "application/egonet-stream",
            "User-Agent": "Codemasters-Egonet",
            "X-EgoNet-Function": function,
            "X-EgoNet-SessionID": self.session,
            "X-EgoNet-Game-Version": "1309032",
            "Host": "prod.egonet.codemasters.com",
        }
        conn = http.client.HTTPSConnection(UPSTREAM, 443, timeout=20, context=self._ctx)
        try:
            conn.request("POST", PATH, body=body, headers=headers)
            resp = conn.getresponse()
            raw = resp.read()
            result = resp.getheader("X-EgoNet-Result")
        finally:
            conn.close()
        self.calls += 1
        time.sleep(self.delay)
        if result != "0":
            return None
        try:
            return decode_stream(raw)
        except Exception:
            return None

    def leaderboard_id(self, track: int, conditions: int, vclass: int,
                       category: int = 2) -> Optional[int]:
        # Field order mirrors the game's own request byte-for-byte.
        d = self.call("TimeTrial.GetLeaderboardId", {
            "VehicleClassId": UInt32(vclass),
            "TrackModelId":   UInt32(track),
            "StageTime":      0.0,
            "ConditionsId":   UInt32(conditions),
            "Category":       category,
        })
        if not d:
            return None
        lb = _val(d.get("LeaderboardId"))
        return int(lb) if lb is not None else None

    def total_entries(self, leaderboard_id: int) -> Optional[int]:
        d = self.call("RaceNetLeaderboard.GetLeaderboardEntries", {
            "Limit":           1,
            "UseRaceNetNames": False,
            "PlayerBest":      0,
            "FilterFlags":     4,
            "SinglePlatform":  False,
            "StartRank":       0,
            "LeaderboardId":   leaderboard_id,
        })
        if not d:
            return None
        te = _val(d.get("TotalEntries"))
        return int(te) if te is not None else None

    def populated(self, track: int, conditions: int, vclass: int) -> tuple[Optional[int], Optional[int]]:
        lb = self.leaderboard_id(track, conditions, vclass)
        if lb is None:
            return None, None
        return lb, self.total_entries(lb)


def rally_locations() -> list[tuple[str, int, int]]:
    """(name, location_id, representative verified track) for every location."""
    out = []
    for loc in Location:
        routes = get_verified_routes_for_location(int(loc))
        if routes:
            out.append((loc.name, int(loc), routes[0][0]))
    return out


def cmd_validate(up: Upstream, vclass: int) -> None:
    """Confirm the oracle discriminates before spending a full sweep on it."""
    germany = [t for t, m in TRACKS.items() if m["location_id"] == int(Location.GERMANY)]
    track = 489 if 489 in germany else germany[0]
    print(f"Validating on track {track} ({TRACKS[track]['name']}), vclass {vclass}\n")
    print(f"{'conditions':>10}  {'leaderboardId':>14}  {'totalEntries':>12}   note")
    for cond, note in [(1, "known-good (game sent this)"),
                       (38, "what we serve for Germany"),
                       (3, "what we serve elsewhere; never seen upstream"),
                       (200, "nonsense control"),
                       (251, "nonsense control")]:
        lb, te = up.populated(track, cond, vclass)
        print(f"{cond:>10}  {str(lb):>14}  {str(te):>12}   {note}")
    print("\nOracle is usable if the known-good row has entries and the nonsense "
          "controls do not.")


def cmd_class_scan(up: Upstream, track: int) -> None:
    """Find a vehicle class with a well-populated leaderboard to sweep with."""
    from dr2server.game_data import VEHICLE_CLASSES
    print(f"{'vclass':>7}  {'entries':>8}  name")
    for vc in sorted(VEHICLE_CLASSES):
        lb, te = up.populated(track, 1, vc)
        if te:
            print(f"{vc:>7}  {te:>8}  {VEHICLE_CLASSES[vc]}")


def cmd_sweep(up: Upstream, vclass: int, lo: int, hi: int) -> None:
    results: Dict[str, Any] = {}
    for name, loc_id, track in rally_locations():
        valid = []
        for cond in range(lo, hi + 1):
            lb, te = up.populated(track, cond, vclass)
            if te:
                valid.append({"conditions_id": cond, "leaderboard_id": lb, "entries": te})
        results[name] = {
            "location_id": loc_id,
            "probe_track": track,
            "probe_track_name": TRACKS.get(track, {}).get("name", "?"),
            "valid": valid,
        }
        print(f"{name:14} {[v['conditions_id'] for v in valid]}", flush=True)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(results, indent=2))
    print(f"\n{up.calls} upstream calls; wrote {OUT}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", required=True, help="upstream X-EgoNet-SessionID")
    ap.add_argument("--vclass", type=int, default=73)
    ap.add_argument("--delay", type=float, default=0.1)
    ap.add_argument("--lo", type=int, default=0)
    ap.add_argument("--hi", type=int, default=63)
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--class-scan", type=int, metavar="TRACK")
    ap.add_argument("--sweep", action="store_true")
    args = ap.parse_args()

    up = Upstream(args.session, args.delay)
    if args.validate:
        cmd_validate(up, args.vclass)
    if args.class_scan:
        cmd_class_scan(up, args.class_scan)
    if args.sweep:
        cmd_sweep(up, args.vclass, args.lo, args.hi)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
