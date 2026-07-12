"""Official auto-generated events must only use verified-track locations.

The generator used to roll from every location in STAGES, so most official
daily/weekly/monthly events landed on rallycross circuits / Monte Carlo that
have no verified routes and never appear in-game. It must now only pick
locations the game can deliver, and never exceed their verified route count
(which would duplicate stages).
"""
from __future__ import annotations

import importlib
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parents[1] / "web"


def _load():
    os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
    os.environ.setdefault("SECRET_KEY", "test-secret")
    os.environ.setdefault("WTF_CSRF_ENABLED", "0")
    if str(WEB_DIR) not in sys.path:
        sys.path.insert(0, str(WEB_DIR))
    server = importlib.import_module("server")
    gen = importlib.import_module("events_generator")
    return server, gen


def test_generator_only_uses_verified_locations():
    server, gen = _load()
    start = datetime(2026, 1, 1, 10, 0, 0)
    end = datetime(2026, 1, 8, 10, 0, 0)
    seen = set()
    # Many distinct slot_ids -> many deterministic rolls across the pool.
    for i in range(300):
        for etype in ("daily", "weekly", "monthly"):
            ev = gen.generate_event(etype, f"{etype}-{i}", start, end, 1, set(), set())
            loc = ev["location"]
            seen.add(loc)
            cap = server.VERIFIED_STAGE_COUNTS.get(loc, 0)
            assert cap > 0, f"generated {etype} event on unverified location {loc!r}"
            n = len(ev["stages"])
            assert 1 <= n <= cap, (
                f"{etype} event on {loc!r} has {n} stages > {cap} verified routes"
            )
    # Sanity: we sampled a spread, and never an unverified location.
    assert len(seen) >= 3
    assert "Barcelona" not in seen


def test_monthly_uses_all_verified_routes():
    server, gen = _load()
    start = datetime(2026, 1, 1, 10, 0, 0)
    end = datetime(2026, 2, 1, 10, 0, 0)
    ev = gen.generate_event("monthly", "monthly-x", start, end, 1, set(), set())
    loc = ev["location"]
    # A full monthly rally should use every verified route for its location.
    assert len(ev["stages"]) == server.VERIFIED_STAGE_COUNTS[loc]
