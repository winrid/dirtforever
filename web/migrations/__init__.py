"""Data migrations for the on-disk JSON store.

The store is plain JSON files under ``DATA_DIR`` (events, clubs, users,
results, drafts, ...), so schema and value changes have to be applied to the
data itself rather than papered over when reading.  Readers stay dumb: they
trust what is on disk, and anything that needs fixing is fixed here, once, at
deploy time.

Adding a migration
------------------
Drop a module in this package named ``mNNNN_short_name.py`` exposing::

    ID = '0002_short_name'          # must match the filename stem
    DESCRIPTION = 'what it does'

    def run(data_dir: Path, dry_run: bool = False) -> Result:
        ...

``run`` reports what it touched via :class:`Result`.  It must be safe to run
against already-migrated data (it simply finds nothing to change), because a
partially-applied run is retried on the next deploy.

Running
-------
``python -m migrations`` from the ``web`` directory, which ``run.sh`` does
before starting gunicorn.  Applied ids are recorded in
``DATA_DIR/migrations.json`` so each runs exactly once.
"""
from __future__ import annotations

import importlib
import json
import pkgutil
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterator, Protocol

STATE_FILE = 'migrations.json'
BACKUP_DIR = '_migration_backups'


@dataclass
class Result:
    """What a migration did, for the deploy log and for tests."""
    scanned: int = 0
    changed: int = 0
    notes: list[str] = field(default_factory=list)

    def note(self, msg: str) -> None:
        self.notes.append(msg)


class Migration(Protocol):
    ID: str
    DESCRIPTION: str

    def run(self, data_dir: Path, dry_run: bool = False) -> Result: ...


def discover() -> list[Any]:
    """Every migration module in this package, ordered by id."""
    mods = []
    for info in pkgutil.iter_modules(__path__):
        if not info.name.startswith('m'):
            continue
        mod = importlib.import_module(f'{__name__}.{info.name}')
        stem = info.name[1:]
        if getattr(mod, 'ID', None) != stem:
            raise RuntimeError(
                f'migration {info.name} declares ID {getattr(mod, "ID", None)!r}, '
                f'which does not match its filename stem {stem!r}'
            )
        mods.append(mod)
    return sorted(mods, key=lambda m: m.ID)


def _state_path(data_dir: Path) -> Path:
    return data_dir / STATE_FILE


def load_state(data_dir: Path) -> dict[str, Any]:
    path = _state_path(data_dir)
    if not path.exists():
        return {'applied': []}
    try:
        state = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        # A corrupt state file would silently re-run every migration, which is
        # worse than stopping: migrations are idempotent but backups are not.
        raise RuntimeError(f'{path} is unreadable; refusing to guess what has run')
    state.setdefault('applied', [])
    return state


def applied_ids(data_dir: Path) -> set[str]:
    return {entry['id'] for entry in load_state(data_dir)['applied']}


def record(data_dir: Path, migration_id: str, result: Result) -> None:
    state = load_state(data_dir)
    state['applied'].append({
        'id': migration_id,
        'at': datetime.now().isoformat(timespec='seconds'),
        'scanned': result.scanned,
        'changed': result.changed,
    })
    path = _state_path(data_dir)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, indent=2), encoding='utf-8')
    tmp.replace(path)


def backup(data_dir: Path, migration_id: str, subdirs: Iterator[str] | list[str]) -> Path:
    """Copy the directories a migration is about to rewrite.

    Cheap insurance for a JSON store: the whole thing is a few MB, and a bad
    migration is otherwise unrecoverable.
    """
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    base = data_dir / BACKUP_DIR / f'{migration_id}-{stamp}'
    # Two runs inside the same second (a retried deploy) must not merge their
    # backups into one directory.
    dest, n = base, 1
    while dest.exists():
        dest = base.with_name(f'{base.name}-{n}')
        n += 1
    for name in subdirs:
        src = data_dir / name
        if src.is_dir():
            shutil.copytree(src, dest / name)
    return dest


def run_pending(data_dir: Path, dry_run: bool = False,
                log: Callable[[str], None] = print) -> int:
    """Apply every migration not yet recorded.  Returns the number applied."""
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        raise RuntimeError(f'DATA_DIR {data_dir} does not exist')

    done = applied_ids(data_dir)
    pending = [m for m in discover() if m.ID not in done]
    if not pending:
        log(f'migrations: up to date ({len(done)} applied)')
        return 0

    for mod in pending:
        # Deploy output lands in journald and in dev consoles that are not
        # always UTF-8, so the runner's own logging stays ASCII: a
        # UnicodeEncodeError here would take the whole start-up down.
        log(f'migrations: applying {mod.ID} - {mod.DESCRIPTION}')
        result = mod.run(data_dir, dry_run=dry_run)
        for note in result.notes:
            log(f'  {note}')
        log(f'  scanned {result.scanned}, changed {result.changed}')
        if dry_run:
            log('  dry run - not recorded')
        else:
            record(data_dir, mod.ID, result)
    return len(pending)
