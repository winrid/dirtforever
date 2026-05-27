"""Migrate leaderboard files that were saved with vehicle_class_id=0.

A bug in the dispatcher fell back to vclass=0 when GetLeaderboardId hadn't
been seen for the session, so PostTime entries got written into
`0_{track}_{conditions}_{category}.json`. We rewrite each such entry into
the file matching its true vclass (derived from vehicle_id) and remove the
originals.

Run with:
    uv run python scripts/backfill_tt_vclass.py /path/to/time_trials --apply

Without --apply this is a dry run.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any


# So we can import dr2server.game_data when run from the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dr2server.game_data import VEHICLES, VEHICLE_CLASSES  # noqa: E402


def _load(path: str) -> list[dict[str, Any]]:
    with open(path, 'r') as f:
        return json.load(f)


def _save(path: str, entries: list[dict[str, Any]]) -> None:
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(entries, f, indent=2)
    os.replace(tmp, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('tt_dir', help='Path to data/time_trials directory')
    parser.add_argument('--apply', action='store_true',
                        help='Actually write the changes; otherwise dry run')
    args = parser.parse_args()

    tt_dir = args.tt_dir
    if not os.path.isdir(tt_dir):
        print(f'not a directory: {tt_dir}', file=sys.stderr)
        return 2

    fixed_files = 0
    moved_entries = 0
    dropped_entries = 0

    for fn in sorted(os.listdir(tt_dir)):
        if not fn.endswith('.json'):
            continue
        stem = fn[:-5]
        parts = stem.split('_')
        if len(parts) != 4:
            continue
        try:
            vclass, track, conditions, category = (int(p) for p in parts)
        except ValueError:
            continue
        if vclass != 0:
            continue

        src_path = os.path.join(tt_dir, fn)
        entries = _load(src_path)
        # Group entries by their real vclass.
        by_vclass: dict[int, list[dict[str, Any]]] = {}
        unresolved: list[dict[str, Any]] = []
        for e in entries:
            vid = int(e.get('vehicle_id', 0))
            meta = VEHICLES.get(vid)
            if meta is None:
                unresolved.append(e)
                continue
            by_vclass.setdefault(int(meta['class']), []).append(e)

        print(f'\n{fn}: {len(entries)} entries -> '
              f'{ {VEHICLE_CLASSES.get(k, str(k)): len(v) for k, v in by_vclass.items()} }'
              + (f' (unresolved: {len(unresolved)})' if unresolved else ''))

        if not args.apply:
            continue

        for real_vclass, new_entries in by_vclass.items():
            dest = os.path.join(
                tt_dir,
                f'{real_vclass}_{track}_{conditions}_{category}.json',
            )
            existing = _load(dest) if os.path.exists(dest) else []
            # Keep at most one entry per user — the better time wins.
            best: dict[str, dict[str, Any]] = {}
            for e in existing + new_entries:
                u = e['username']
                if u not in best or e['stage_time_ms'] < best[u]['stage_time_ms']:
                    best[u] = e
            merged = sorted(best.values(), key=lambda e: e['stage_time_ms'])
            _save(dest, merged)
            moved_entries += len(new_entries)
            print(f'  -> wrote {len(new_entries)} into {os.path.basename(dest)} '
                  f'(total now {len(merged)})')

        if unresolved:
            dropped_entries += len(unresolved)
            print(f'  ! dropping {len(unresolved)} entries with unknown vehicle_id')

        os.remove(src_path)
        fixed_files += 1
        print(f'  removed {fn}')

    mode = 'APPLY' if args.apply else 'DRY RUN'
    print(f'\n[{mode}] files rewritten: {fixed_files}, '
          f'entries moved: {moved_entries}, dropped: {dropped_entries}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
