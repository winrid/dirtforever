"""Give every club an explicit admins list.

Clubs used to have exactly one privileged person, created_by.  Owners can now
promote members to admin, stored as club['admins'] (usernames, never the owner).
Readers stay dumb and trust what is on disk, so backfill an empty list on every
club that predates the field.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import Result, backup

ID = '0004_club_admins'
DESCRIPTION = 'backfill an empty admins list on every club'


def run(data_dir: Path, dry_run: bool = False) -> Result:
    result = Result()
    clubs_dir = data_dir / 'clubs'
    if not clubs_dir.is_dir():
        result.note('no clubs directory; nothing to do')
        return result

    todo: list[tuple[Path, dict]] = []
    for path in sorted(clubs_dir.glob('*.json')):
        try:
            doc = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as exc:
            result.note(f'{path.name}: unreadable ({exc}) - skipped')
            continue
        result.scanned += 1
        if isinstance(doc, dict) and not isinstance(doc.get('admins'), list):
            todo.append((path, doc))

    if not todo:
        return result

    if not dry_run:
        result.backup_dir = backup(data_dir, ID, ['clubs'])
        result.note(f'backed up clubs to {result.backup_dir}')

    for path, doc in todo:
        rel = f'clubs/{path.name}'
        result.change(file=rel, path='admins', before=doc.get('admins'), after=[])
        doc['admins'] = []
        result.changed += 1
        if not dry_run:
            tmp = path.with_suffix('.tmp')
            tmp.write_text(json.dumps(doc, indent=2), encoding='utf-8')
            tmp.replace(path)
    result.note(f'{result.changed} club(s) given an admins list')
    return result
