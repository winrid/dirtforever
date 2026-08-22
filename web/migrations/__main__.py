"""Apply pending data migrations.  Run from the ``web`` directory:

    python -m migrations [--dry-run] [--data-dir PATH]

``run.sh`` invokes this before starting gunicorn, so a deploy that ships a
migration applies it before any request is served.  A failure exits non-zero
and takes the deploy down with it, which is the point: serving data the code
no longer understands is worse than not serving.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import revert, run_pending


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    # Resolve the default the same way server.py does -- $DATA_DIR, else the
    # 'data' directory beside server.py -- rather than relative to the cwd.
    # run.sh cds into web/ so a relative 'data' happens to agree today, but a
    # migration writing a different directory than the app reads would be
    # silent, and with `set -e` a wrong path aborts the whole service start.
    default_data_dir = os.environ.get(
        'DATA_DIR', str(Path(__file__).resolve().parents[1] / 'data'))
    ap.add_argument('--data-dir', default=default_data_dir,
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
