"""Donation tracking storage + status.

Monthly donation totals live in a single JSON file under ``DATA_DIR``. The
store is updated by *verified* PayPal webhooks (see ``paypal.py`` and the
``/api/paypal/webhook`` route in ``server.py``) and read by the ``/donate``
page, the ``/api/donations/status`` endpoint, and the desktop app's
"Budget Coverage" footer bar.

This module is intentionally self-contained: it derives ``DATA_DIR`` from the
environment the same way ``server.py`` does and uses its own fcntl-locked file
helpers. It deliberately does *not* ``from server import ...`` — the repo has
both a root ``server.py`` (the game server) and this ``web/server.py``, and
``web/server.py`` puts the repo root on ``sys.path``, so a bare ``import
server`` resolves to the wrong module when the web app runs as ``__main__``.
Owning the donations file outright sidesteps that entirely; only donation code
ever touches ``donations.json``, so the locking stays correct.
"""
from __future__ import annotations

import fcntl
import json
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator

# Same derivation as server.py: env override, else <web>/data.
_BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get('DATA_DIR', os.path.join(_BASE, 'data'))
DONATIONS_PATH = os.path.join(DATA_DIR, 'donations.json')

# $100/mo by default; overridable via .env without touching the data file.
DEFAULT_GOAL_CENTS = int(os.environ.get('DONATION_GOAL_CENTS', '10000'))
HISTORY_MONTHS = 6


# ── File helpers (fcntl-locked, mirroring server.py's data layer) ────────

def _load(path: str) -> Any:
    with open(path) as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        try:
            return json.load(f)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _save(path: str, data: Any) -> None:
    with open(path, 'w') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            json.dump(data, f, indent=2)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


@contextmanager
def _atomic_update(path: str) -> Iterator[Any]:
    """Hold LOCK_EX across read+mutate+write so concurrent writers serialize."""
    with open(path, 'r+') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            data = json.load(f)
            yield data
            f.seek(0)
            f.truncate()
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


# ── Donations ────────────────────────────────────────────────────────────

def _month_key(when: datetime) -> str:
    """UTC month bucket, e.g. '2026-05'. Matches the codebase's naive-UTC use."""
    return when.strftime('%Y-%m')


def ensure_store() -> None:
    """Create donations.json with defaults if it doesn't exist yet.

    ``_atomic_update`` opens with ``'r+'`` and requires the file to exist, so
    every reader/writer calls this first.
    """
    if os.path.exists(DONATIONS_PATH):
        return
    os.makedirs(DATA_DIR, exist_ok=True)
    _save(DONATIONS_PATH, {'goal_cents': DEFAULT_GOAL_CENTS, 'months': {}})


def record_donation(txn_id: str, amount_cents: int, when: datetime) -> bool:
    """Add a donation to its UTC month bucket. Idempotent per ``txn_id``.

    Returns True if recorded, False if the txn was already counted (a
    redelivered webhook) or the amount is non-positive. PayPal can deliver the
    same webhook event more than once, so dedupe is mandatory.
    """
    if amount_cents <= 0 or not txn_id:
        return False
    ensure_store()
    month = _month_key(when)
    with _atomic_update(DONATIONS_PATH) as data:
        months = data.setdefault('months', {})
        bucket = months.setdefault(month, {'raised_cents': 0, 'txn_ids': []})
        if txn_id in bucket['txn_ids']:
            return False
        bucket['txn_ids'].append(txn_id)
        bucket['raised_cents'] = int(bucket.get('raised_cents', 0)) + int(amount_cents)
    return True


def _percent(raised: int, goal: int) -> int:
    if goal <= 0:
        return 0
    return max(0, min(100, round(raised * 100 / goal)))


def get_status(now: datetime) -> dict[str, Any]:
    """Current-month progress + recent monthly history (newest first)."""
    ensure_store()
    data = _load(DONATIONS_PATH)
    goal = int(data.get('goal_cents', DEFAULT_GOAL_CENTS))
    months = data.get('months', {})
    cur = _month_key(now)
    raised = int(months.get(cur, {}).get('raised_cents', 0))

    history = []
    for key in sorted(months.keys(), reverse=True)[:HISTORY_MONTHS]:
        m_raised = int(months[key].get('raised_cents', 0))
        history.append({
            'month': key,
            'raised_cents': m_raised,
            'goal_cents': goal,
            'percent': _percent(m_raised, goal),
        })

    return {
        'goal_cents': goal,
        'month': cur,
        'raised_cents': raised,
        'percent': _percent(raised, goal),
        'history': history,
        'updated_at': now.isoformat(),
    }
