"""Reorder stages[] in every web event JSON to match the canonical
dispatcher order (dr2server.game_data.Track / VERIFIED_TRACK_IDS), so the
i-th stage on the website corresponds to the same track the dispatcher
sends to the game as stage_id=i.

The need for this migration is documented in
web/server.py's STAGES comment block: previously the web-side STAGES list
was a hand-curated subset/ordering of each location's stages and did not
match dr2server's tracks_for_location() iteration, so submitted stage
times got attributed to the wrong stage name on the leaderboard.

Run from the repo root:

    uv run python scripts/migrate_stage_order.py            # apply
    uv run python scripts/migrate_stage_order.py --dry-run  # preview only

The data directory is read from the same ``DATA_DIR`` env var the web
server uses (default: ``web/data`` next to the source tree). On a
production host where the data lives elsewhere, point the script at it:

    DATA_DIR=/var/lib/dirtforever/data uv run python scripts/migrate_stage_order.py --dry-run

Backups of every changed file are written next to the original as
``<name>.bak.<timestamp>`` so the migration is reversible.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from typing import Any


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_web_module():
    """Import web.server. Requires SECRET_KEY in env (placeholder is fine
    for a migration that never serves a request). The web module reads
    DATA_DIR from the environment the same way the running server does,
    so on a production host the operator points the migration at the
    real data directory by setting DATA_DIR.
    """
    os.environ.setdefault("SECRET_KEY", "migration-only")
    sys.path.insert(0, REPO_ROOT)
    import web.server as web_server  # type: ignore
    return web_server


def _backup(path: str, ts: str) -> str:
    backup = f"{path}.bak.{ts}"
    with open(path, "rb") as src, open(backup, "wb") as dst:
        dst.write(src.read())
    return backup


def _write_json(path: str, data: dict[str, Any]) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def migrate(dry_run: bool = False) -> int:
    web_server = _load_web_module()
    stages_map: dict[str, list[tuple[str, float]]] = web_server.STAGES
    events_dir: str = web_server.EVENTS_DIR
    results_dir: str = web_server.RESULTS_DIR
    print(f"events dir:  {events_dir}")
    print(f"results dir: {results_dir}")
    if not os.path.isdir(events_dir):
        print(f"error: events directory does not exist: {events_dir}", file=sys.stderr)
        print("set DATA_DIR to point at the runtime data directory and try again.",
              file=sys.stderr)
        return 2

    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    changed = 0
    skipped: list[str] = []
    truncated: list[str] = []

    for fname in sorted(os.listdir(events_dir)):
        if not fname.endswith(".json"):
            continue
        evt_path = os.path.join(events_dir, fname)
        with open(evt_path) as f:
            event = json.load(f)

        location = event.get("location")
        old_stages = event.get("stages", [])
        if not location or not old_stages:
            continue
        canonical = stages_map.get(location)
        if not canonical:
            skipped.append(
                f"{fname}: location {location!r} has no canonical tracks "
                f"(unverified) — leaving stages unchanged"
            )
            continue

        current_n = len(old_stages)
        new_n = min(current_n, len(canonical))
        if new_n < current_n:
            truncated.append(
                f"{fname}: {location} has only {len(canonical)} verified "
                f"tracks; truncating event from {current_n} → {new_n} stages"
            )

        cond_default = event.get("conditions", "Clear")
        new_stages: list[dict[str, Any]] = []
        for i in range(new_n):
            name, dist = canonical[i]
            old_cond = (old_stages[i] or {}).get("conditions", cond_default)
            new_stages.append({
                "name": name,
                "distance_km": dist,
                "conditions": old_cond,
            })

        if new_stages == old_stages:
            continue

        print(f"\n{fname}: rewriting {len(old_stages)} → {len(new_stages)} stages")
        for i, (oldS, newS) in enumerate(zip(old_stages, new_stages + [None] * max(0, len(old_stages) - len(new_stages)))):
            old_label = f"{oldS['name']} ({oldS['distance_km']} km)"
            new_label = (
                f"{newS['name']} ({newS['distance_km']} km)"
                if newS else "<dropped>"
            )
            print(f"  [{i}] {old_label}  →  {new_label}")

        results_path = os.path.join(results_dir, fname)
        results: dict[str, Any] | None = None
        if os.path.exists(results_path):
            with open(results_path) as f:
                results = json.load(f)
            entries = results.get("entries", [])
            for entry in entries:
                entry_stages = entry.get("stages", [])[:new_n]
                entry["stages"] = entry_stages
                entry["total_time_ms"] = sum(
                    (s.get("time_ms", 0) or 0) + (s.get("penalties_ms", 0) or 0)
                    for s in entry_stages
                )
            entries.sort(key=lambda e: e.get("total_time_ms", 0))
            print(f"  results: updated {len(entries)} entries (truncated to {new_n} stages, totals recomputed, re-sorted)")

        if dry_run:
            continue

        _backup(evt_path, ts)
        event["stages"] = new_stages
        _write_json(evt_path, event)

        if results is not None:
            _backup(results_path, ts)
            _write_json(results_path, results)

        changed += 1

    print("\n── summary ───────────────────────────────────────")
    print(f"changed events: {changed}")
    if truncated:
        print(f"truncated ({len(truncated)}):")
        for line in truncated:
            print(f"  - {line}")
    if skipped:
        print(f"skipped ({len(skipped)}):")
        for line in skipped:
            print(f"  - {line}")
    if dry_run:
        print("(dry run — no files written)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="Show changes without writing any files.")
    args = ap.parse_args()
    return migrate(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
