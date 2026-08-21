"""Repair stage conditions that the stage's location cannot load.

StageConditions is a global enum, but each location only ships lighting assets
for a subset of it.  Events written before that was understood picked from one
global list regardless of location, so roughly 42% of the (location,
conditions) pairs in circulation asked for lighting the location does not have
— the stage then loads with a broken skybox rather than failing, and RaceNet
never validated it either.  Germany, for instance, has no ``midday_overcast``,
so id 38 (Daytime / Overcast / Dry) renders wrong there while being perfectly
valid at Poland.

This rewrites stored events and championship drafts so every stage carries a
conditions id its own location actually supports:

* an id outside the location's verified set becomes the location's first
  option (the same value the create forms now pre-select),
* a stage with no id at all gets one derived from its stored label, falling
  back to the location's first option,
* the human-readable ``conditions`` label is re-derived so the site shows what
  the game will really load.

Locations we have not verified (Twin Peaks, which the game does not offer in
the Freeplay builder) are left untouched: there is nothing to validate against
and guessing would be worse than leaving the stored value alone.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dr2server.game_data import (  # noqa: E402
    stage_conditions_for_location,
    stage_conditions_label,
    stage_conditions_sibling_for_location,
)

from . import Result, backup  # noqa: E402

ID = '0001_per_location_stage_conditions'
DESCRIPTION = 'point every stage at conditions its location can actually load'

# Events written before conditions were per-location stored one of these short
# labels and no id at all.  Bridge them to the full label so such a stage keeps
# the weather its owner picked wherever that location offers it.
LEGACY_LABELS = {
    'Clear':      'Daytime / Clear / Dry',
    'Overcast':   'Daytime / Overcast / Dry',
    'Light Rain': 'Daytime / Showers / Wet',
    'Heavy Rain': 'Daytime / Heavy Rain / Wet',
    'Dusk':       'Dusk / Cloudy / Dry',
    'Night':      'Night / Clear / Dry',
}


def _resolve(location: str, stage: dict[str, Any]) -> int | None:
    """The conditions id this stage should carry, or None to leave it alone."""
    valid = stage_conditions_for_location(location)
    if not valid:
        return None            # unverified location — nothing to validate against

    raw = stage.get('conditions_id')
    try:
        cid = int(raw) if raw is not None else None
    except (TypeError, ValueError):
        cid = None

    if cid in valid:
        return cid

    # The id is absent, or names conditions this location cannot load.  Either
    # way, try to preserve what the owner actually picked by matching on the
    # LABEL before falling back to the location's first option.
    #
    # This matters most for the twin pairs, where an id the location cannot
    # load usually has a sibling that renders the identical label and can:
    # the old builder's canonical "Sunset / Cloudy / Wet" was 34, which no
    # location can load, while 20 gives the same label at 18 of them.  Without
    # this, every such stage would silently become Daytime / Clear / Dry.
    sibling = (stage_conditions_sibling_for_location(location, cid)
               if cid is not None else None)
    if sibling is not None:
        return sibling

    # No id to match on (or an unknown one): the label the file stored is the
    # only remaining evidence of what was intended.
    label = LEGACY_LABELS.get(str(stage.get('conditions') or '').strip(),
                              str(stage.get('conditions') or '').strip())
    wanted = label.replace(' Surface', '').strip().lower()
    if wanted:
        for candidate in valid:
            if stage_conditions_label(candidate).lower() == wanted:
                return candidate
    return valid[0]


def _migrate_stages(location: str, stages: list[dict[str, Any]]) -> int:
    changed = 0
    for stage in stages:
        if not isinstance(stage, dict):
            continue
        cid = _resolve(location, stage)
        if cid is None:
            continue
        label = stage_conditions_label(cid)
        if stage.get('conditions_id') != cid or stage.get('conditions') != label:
            stage['conditions_id'] = cid
            stage['conditions'] = label
            changed += 1
    return changed


def _migrate_championship(champ: dict[str, Any]) -> int:
    """Fix every sub-event, plus the legacy top-level mirrors."""
    changed = 0
    top_location = champ.get('location', '')
    for ev in champ.get('events') or []:
        # Sub-events carry their own location; fall back to the championship's
        # so an older file missing it still gets validated.
        changed += _migrate_stages(ev.get('location') or top_location,
                                   ev.get('stages') or [])

    # Legacy single-event shape (and the top-level mirror v2 events also keep).
    top_stages = champ.get('stages') or []
    if top_stages:
        changed += _migrate_stages(champ.get('location', ''), top_stages)

    # Keep the event-level label in step with what stage 1 will actually load.
    first = None
    if champ.get('events') and (champ['events'][0].get('stages') or []):
        first = champ['events'][0]['stages'][0]
    elif top_stages:
        first = top_stages[0]
    if first and first.get('conditions') and champ.get('conditions') != first['conditions']:
        champ['conditions'] = first['conditions']
        changed += 1
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
            result.note(f'{subdir}/{path.name}: unreadable ({exc}) — skipped')
            continue
        if not isinstance(doc, dict):
            continue
        result.scanned += 1
        if _migrate_championship(doc):
            result.changed += 1
            result.note(f'{subdir}/{path.name}: conditions corrected')
            if not dry_run:
                tmp = path.with_suffix('.tmp')
                tmp.write_text(json.dumps(doc, indent=2), encoding='utf-8')
                tmp.replace(path)


def run(data_dir: Path, dry_run: bool = False) -> Result:
    result = Result()
    subdirs = ['events', 'championship_drafts']
    if not dry_run:
        dest = backup(data_dir, ID, subdirs)
        result.note(f'backed up {", ".join(subdirs)} to {dest}')
    for subdir in subdirs:
        _migrate_dir(data_dir, subdir, result, dry_run)
    return result
