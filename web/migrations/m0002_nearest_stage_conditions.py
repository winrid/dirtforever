"""Put back the weather 0001 flattened.

0001 pointed every stage at conditions its own location can load, which was the
point, but it resolved an unavailable pick by exact label and then fell back to
the location's *first* option -- which is dry almost everywhere.  So a stage
someone deliberately made wet came out clear and dry: Argentina ships three wet
options, and a Daytime / Heavy Rain / Wet stage there still became Daytime /
Clear / Dry.  544 of the 1919 stages it rewrote came out on a surface nobody
asked for, and 395 of those had one available at their own location.

nearest_stage_conditions_for_location() now scores the location's set instead:
keep the surface, then take the closest option in weather and time of day.  This
re-resolves the stages 0001 rewrote, using 0001's own change log for what each
one originally asked for, since the store no longer remembers.

Only stages still holding exactly what 0001 wrote are touched.  Anything edited
since -- by hand or through the site -- is left alone, so this cannot undo
someone's later choice.  Runs after 0001 on a fresh store too: 0001 writes its
log, this reads it back, and both end up where a single better migration would
have landed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dr2server.game_data import (  # noqa: E402
    nearest_stage_conditions_for_location,
    stage_conditions_label,
)

from . import BACKUP_DIR, Result, backup  # noqa: E402

ID = '0002_nearest_stage_conditions'
DESCRIPTION = 'keep the surface a stage asked for instead of resetting it to the location default'

PRIOR = '0001_per_location_stage_conditions'

# 0001 bridged these short labels, written before conditions carried an id, to
# the full label.  Read its log the same way it wrote it.
LEGACY_LABELS = {
    'Clear':      'Daytime / Clear / Dry',
    'Overcast':   'Daytime / Overcast / Dry',
    'Light Rain': 'Daytime / Showers / Wet',
    'Heavy Rain': 'Daytime / Heavy Rain / Wet',
    'Dusk':       'Dusk / Cloudy / Dry',
    'Night':      'Night / Clear / Dry',
}


def _prior_logs(data_dir: Path) -> list[Path]:
    """0001's change logs, oldest first.

    A retried deploy can leave more than one, and a later run only logs what it
    still found to change, so the older logs hold the earlier originals.
    """
    root = data_dir / BACKUP_DIR
    if not root.is_dir():
        return []
    return sorted(root.glob(f'{PRIOR}*/changes.json'))


def _intended(change: dict[str, Any]) -> tuple[Any, str]:
    """(id, label) this stage asked for before 0001 rewrote it."""
    before = change.get('before')
    if not isinstance(before, dict):
        return None, ''
    label = str(before.get('conditions') or '').strip()
    return before.get('conditions_id'), LEGACY_LABELS.get(label, label)


def _node_at(doc: dict[str, Any], path: str) -> Any:
    """Walk a changes.json path like "events[0].stages[1]" to the dict it names."""
    node: Any = doc
    for part in path.split('.'):
        name, _, index = part.partition('[')
        node = node[name]
        if index:
            node = node[int(index.rstrip(']'))]
    return node


def run(data_dir: Path, dry_run: bool = False) -> Result:
    result = Result()
    logs = _prior_logs(data_dir)
    if not logs:
        result.note(f'no {PRIOR} change log to read; nothing to re-resolve')
        return result

    # Collapse the logs into one entry per stage, oldest winning: that is the
    # value the store actually held before any of this started.
    wanted: dict[tuple[str, str], dict[str, Any]] = {}
    for log in logs:
        try:
            doc = json.loads(log.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as exc:
            result.note(f'{log.name}: unreadable ({exc}) - skipped')
            continue
        for change in doc.get('changes', []):
            if change.get('path') == 'conditions':
                continue          # the event-level mirror, re-derived below
            wanted.setdefault((change['file'], change['path']), change)
    result.note(f'read {len(wanted)} stage rewrites from {len(logs)} log(s)')

    by_file: dict[str, list[dict[str, Any]]] = {}
    for (rel, _path), change in wanted.items():
        by_file.setdefault(rel, []).append(change)

    if not dry_run:
        result.backup_dir = backup(data_dir, ID, ['events', 'championship_drafts'])
        result.note(f'backed up events, championship_drafts to {result.backup_dir}')

    for rel, changes in sorted(by_file.items()):
        path = data_dir / rel
        if not path.exists():
            continue
        try:
            doc = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as exc:
            result.note(f'{rel}: unreadable ({exc}) - skipped')
            continue
        result.scanned += 1
        changed = 0

        for change in sorted(changes, key=lambda c: c['path']):
            location = change.get('location') or doc.get('location') or ''
            try:
                stage = _node_at(doc, change['path'])
            except (KeyError, IndexError, TypeError):
                continue          # the file has been restructured since
            if not isinstance(stage, dict):
                continue
            after = change.get('after') or {}
            if stage.get('conditions_id') != after.get('conditions_id'):
                continue          # written since 0001 ran; not ours to touch

            cid, label = _intended(change)
            better = nearest_stage_conditions_for_location(location, cid, label)
            if better is None or better == stage.get('conditions_id'):
                continue
            better_label = stage_conditions_label(better)
            result.change(
                file=rel, path=change['path'],
                before={'conditions_id': stage.get('conditions_id'),
                        'conditions': stage.get('conditions')},
                after={'conditions_id': better, 'conditions': better_label},
                location=location, asked_for=label or cid)
            stage['conditions_id'] = better
            stage['conditions'] = better_label
            changed += 1

        if not changed:
            continue

        # Keep the event-level label in step with what stage 1 will now load,
        # the same mirror 0001 maintained.
        first = None
        events = doc.get('events') or []
        if events and (events[0].get('stages') or []):
            first = events[0]['stages'][0]
        elif doc.get('stages'):
            first = doc['stages'][0]
        if first and first.get('conditions') and doc.get('conditions') != first['conditions']:
            result.change(file=rel, path='conditions',
                          before=doc.get('conditions'), after=first['conditions'],
                          location=doc.get('location', ''))
            doc['conditions'] = first['conditions']

        result.changed += 1
        result.note(f'{rel}: {changed} stage(s) re-resolved')
        if not dry_run:
            tmp = path.with_suffix('.tmp')
            tmp.write_text(json.dumps(doc, indent=2), encoding='utf-8')
            tmp.replace(path)

    return result
