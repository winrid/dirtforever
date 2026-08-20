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

from . import run_pending


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data-dir', default=os.environ.get('DATA_DIR', 'data'),
                    help='JSON store root (default: $DATA_DIR, else ./data)')
    ap.add_argument('--dry-run', action='store_true',
                    help='report what would change without writing')
    args = ap.parse_args()
    try:
        run_pending(Path(args.data_dir), dry_run=args.dry_run)
    except Exception as exc:  # noqa: BLE001 - deploy gate: report and fail loudly
        print(f'migrations: FAILED - {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
