"""Apply pending data migrations.  Run from the ``web`` directory:

    python -m migrations [--dry-run] [--data-dir PATH]

``run.sh`` invokes this before starting gunicorn, so a deploy that ships a
migration applies it before any request is served.  A failure exits non-zero
and takes the deploy down with it, which is the point: serving data the code
no longer understands is worse than not serving.

The store it writes is the one the app reads, which means reading DATA_DIR out
of the deploy's ``.env`` ourselves: nothing sources that file into the service
environment, and the app only sees it because server.py loads it at import.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import revert, run_pending

# Same file server.py reads at import time, resolved the same way: relative to
# this module, not to the cwd the runner happens to be invoked from.
ENV_FILE = Path(__file__).resolve().parents[2] / '.env'


def _load_dotenv(path: Path) -> None:
    """Read the deploy's .env, exactly as server.py does at import time.

    DATA_DIR lives in that file, not in the service environment: nothing
    sources it, and server.py only picks it up because it loads the file
    itself.  Without this the runner falls back to web/data, which does not
    exist on a deploy, and `set -e` in run.sh turns that into a dead service.
    Deliberately duplicated rather than imported from server: importing it
    would pull in the whole Flask app (and its required SECRET_KEY) just to
    resolve one path, and `server` resolves to a different module depending on
    the cwd the runner is invoked from.
    """
    if not path.exists():
        return
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, val = line.split('=', 1)
        os.environ.setdefault(key.strip(), val.strip())


def _default_data_dir() -> str:
    """Where the runner writes when --data-dir is not given.

    Resolve it the same way server.py does -- .env, then $DATA_DIR, then the
    'data' directory beside server.py -- rather than relative to the cwd.
    run.sh cds into web/ so a relative 'data' happens to agree today, but a
    migration writing a different directory than the app reads would be
    silent, and with `set -e` a wrong path aborts the whole service start.
    """
    _load_dotenv(ENV_FILE)
    return os.environ.get(
        'DATA_DIR', str(Path(__file__).resolve().parents[1] / 'data'))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data-dir', default=_default_data_dir(),
                    help='JSON store root (default: $DATA_DIR, else web/data)')
    ap.add_argument('--dry-run', action='store_true',
                    help='report what would change without writing')
    ap.add_argument('--revert', metavar='CHANGES_JSON',
                    help='put back the values listed in a changes.json written '
                         'by an earlier run (value by value, so anything '
                         'written since is left alone)')
    args = ap.parse_args()
    try:
        if args.revert:
            n = revert(Path(args.data_dir), Path(args.revert))
            print(f'migrations: reverted {n} values')
            return 0
        run_pending(Path(args.data_dir), dry_run=args.dry_run)
    except Exception as exc:  # noqa: BLE001 - deploy gate: report and fail loudly
        print(f'migrations: FAILED - {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
