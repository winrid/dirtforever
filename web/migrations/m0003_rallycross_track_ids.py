"""Point every rallycross stage at the circuit's real TrackModelId.

The 13 rallycross route ids in ``game_data.Track`` were wrong from May to
August 2026 (131..176, an unrelated id space) until they were captured
in-game on 2026-08-22 (``data/verified/rx_track_ids.json``).  Events and
championship drafts written in between stored the wrong id on every
rallycross stage.  The game side self-heals — the dispatcher falls back to the
location's only circuit when a stored id is not a verified route — but the
site does not: the route name renders blank and the edit form rejects the
stage with "pick a route".

Each rallycross location has exactly one circuit, so the repair is total: a
stage at a rallycross location whose ``track_id`` is not that circuit's id
(wrong, or missing altogether) gets the circuit's id.  Rally locations are
left alone; their routes were never affected.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dr2server.game_data import Location, Track  # noqa: E402

from . import Result, backup  # noqa: E402

ID = '0003_rallycross_track_ids'
DESCRIPTION = 'rewrite rallycross stage track_ids to the captured circuit ids'

# {location display name: the one verified circuit TrackModelId}
RX_CIRCUIT_ID: dict[str, int] = {
    loc.display_name: next(int(t) for t in Track if t.location is loc)
    for loc in Location
    if loc.discipline == 'rallycross'
}


def _migrate_stages(location: str, stages: list[dict[str, Any]],
                    result: Result, file: str, where: str) -> int:
    circuit = RX_CIRCUIT_ID.get(location)
    if circuit is None:
        return 0                       # rally location: nothing to repair
    changed = 0
    for i, stage in enumerate(stages):
        if not isinstance(stage, dict):
            continue
        raw = stage.get('track_id')
        try:
            tid = int(raw) if raw is not None else None
        except (TypeError, ValueError):
            tid = None
        if tid == circuit:
            continue
        result.change(file=file, path=f'{where}stages[{i}]',
                      before={'track_id': stage.get('track_id')},
                      after={'track_id': circuit},
                      location=location)
        stage['track_id'] = circuit
        changed += 1
    return changed


def _migrate_championship(champ: dict[str, Any], result: Result, file: str) -> int:
    """Fix every sub-event, plus the legacy top-level stage list."""
    changed = 0
    top_location = champ.get('location', '')
    for ei, ev in enumerate(champ.get('events') or []):
        changed += _migrate_stages(ev.get('location') or top_location,
                                   ev.get('stages') or [],
                                   result, file, f'events[{ei}].')
    changed += _migrate_stages(top_location, champ.get('stages') or [],
                               result, file, '')
    return changed


def _migrate_dir(data_dir: Path, subdir: str, result: Result,
                 dry_run: bool) -> None:
    root = data_dir / subdir
    if not root.is_dir():
        return
    for path in sorted(root.glob('*.json')):
        try:
            doc = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as exc:
            result.note(f'{subdir}/{path.name}: unreadable ({exc}) - skipped')
            continue
        if not isinstance(doc, dict):
            continue
        result.scanned += 1
        if _migrate_championship(doc, result, f'{subdir}/{path.name}'):
            result.changed += 1
            result.note(f'{subdir}/{path.name}: rallycross track ids corrected')
            if not dry_run:
                tmp = path.with_suffix('.tmp')
                tmp.write_text(json.dumps(doc, indent=2), encoding='utf-8')
                tmp.replace(path)


def run(data_dir: Path, dry_run: bool = False) -> Result:
    result = Result()
    subdirs = ['events', 'championship_drafts']
    if not dry_run:
        result.backup_dir = backup(data_dir, ID, subdirs)
        result.note(f'backed up {", ".join(subdirs)} to {result.backup_dir}')
    for subdir in subdirs:
        _migrate_dir(data_dir, subdir, result, dry_run)
    return result
