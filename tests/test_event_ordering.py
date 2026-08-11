"""Event listings order live -> upcoming -> ended, deterministically.

The on-disk store hands events back in filename (= random event id) order, so
without an explicit sort every listing - the site pages and the two game API
feeds - showed finished championships above live ones in an order that read as
arbitrary. These tests pin the bucket order and the within-bucket tiebreaks.
"""
from __future__ import annotations

import importlib
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parents[1] / "web"


def _load():
    os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
    os.environ.setdefault("SECRET_KEY", "test-secret")
    os.environ.setdefault("WTF_CSRF_ENABLED", "0")
    while str(WEB_DIR) in sys.path:
        sys.path.remove(str(WEB_DIR))
    sys.path.insert(0, str(WEB_DIR))
    mod = sys.modules.get("server")
    if mod is None or not hasattr(mod, "sort_events"):
        sys.modules.pop("server", None)
        mod = importlib.import_module("server")
    return mod


NOW = datetime(2026, 6, 1, 12, 0, 0)


def _evt(eid: str, start_days: float, end_days: float, active: bool = True) -> dict:
    return {
        "id": eid,
        "name": eid,
        "active": active,
        "start_time": (NOW + timedelta(days=start_days)).isoformat(),
        "end_time": (NOW + timedelta(days=end_days)).isoformat(),
    }


def test_buckets_live_then_upcoming_then_ended() -> None:
    server = _load()
    ended = _evt("evt-ended", -30, -10)
    upcoming = _evt("evt-upcoming", 2, 9)
    live = _evt("evt-live", -1, 6)
    order = [e["id"] for e in server.sort_events([ended, upcoming, live], NOW)]
    assert order == ["evt-live", "evt-upcoming", "evt-ended"]


def test_within_bucket_tiebreaks() -> None:
    server = _load()
    events = [
        _evt("evt-live-late", -1, 20),
        _evt("evt-live-soon", -1, 2),
        _evt("evt-up-later", 10, 20),
        _evt("evt-up-next", 1, 5),
        _evt("evt-ended-old", -90, -60),
        _evt("evt-ended-recent", -30, -1),
    ]
    order = [e["id"] for e in server.sort_events(events, NOW)]
    assert order == [
        # live: soonest to close first, so a driver sees what's about to expire
        "evt-live-soon", "evt-live-late",
        # upcoming: soonest to open first
        "evt-up-next", "evt-up-later",
        # ended: most recently finished first
        "evt-ended-recent", "evt-ended-old",
    ]


def test_order_is_stable_regardless_of_input_order() -> None:
    server = _load()
    events = [_evt(f"evt-{i}", -1, 5) for i in range(5)]
    forward = [e["id"] for e in server.sort_events(events, NOW)]
    backward = [e["id"] for e in server.sort_events(list(reversed(events)), NOW)]
    # Identical windows: the id tiebreak keeps the order from wobbling between
    # requests (the events dir listing order is not something we control).
    assert forward == backward == [f"evt-{i}" for i in range(5)]


def test_deactivated_and_malformed_events_sort_last() -> None:
    server = _load()
    live = _evt("evt-live", -1, 5)
    deactivated = _evt("evt-off", -1, 5, active=False)
    no_end = {"id": "evt-nodates", "name": "evt-nodates", "active": False}
    bad = {"id": "evt-bad", "name": "evt-bad", "active": True,
           "start_time": "not-a-date", "end_time": "also-not-a-date"}
    order = [e["id"] for e in server.sort_events([no_end, bad, deactivated, live], NOW)]
    # `bad` has an unparseable end_time, so event_is_active() treats it as
    # open-ended and it stays in the live bucket, behind the real live event.
    assert order[:2] == ["evt-live", "evt-bad"]
    assert set(order[2:]) == {"evt-off", "evt-nodates"}
    assert order[2] == "evt-off"  # ended-with-a-date beats dateless


def test_game_apis_serve_live_events_soonest_closing_first() -> None:
    server = _load()
    server.app.config["TESTING"] = True
    token = "df_ordering_test_token"
    uname = "orderingdriver"
    if not server.get_user(uname):
        server.create_user(uname, "ord@example.com", "pw", email_verified=True)
    user = server.get_user(uname)
    user["game_token"] = token
    user["clubs"] = ["orderclub"]
    server.save_user(user)
    server.save_club({
        "id": "orderclub", "name": "Order Club", "created_by": uname,
        "members": [uname], "created_at": "2026-01-01T00:00:00",
    })

    now = datetime.now()

    def _win(start_days: float, end_days: float) -> dict:
        return {
            "start_time": (now + timedelta(days=start_days)).isoformat(),
            "end_time": (now + timedelta(days=end_days)).isoformat(),
        }

    # Ids are deliberately anti-sorted so a filename ordering would fail.
    for eid, club, win in [
        ("evt-aaa-club-late", "orderclub", _win(-1, 20)),
        ("evt-zzz-club-soon", "orderclub", _win(-1, 2)),
        ("evt-mmm-club-ended", "orderclub", _win(-30, -1)),
        ("evt-aaa-official-late", None, _win(-1, 20)),
        ("evt-zzz-official-soon", None, _win(-1, 2)),
        ("evt-mmm-official-upcoming", None, _win(3, 10)),
    ]:
        server.save_event({
            "id": eid, "name": eid, "type": "club" if club else "daily",
            "location": "Finland", "car_class": "Group B (RWD)",
            "surface": "Gravel", "conditions": "Day",
            "stages": [{"name": "Stage 1", "distance_km": 10.0, "conditions": "Day"}],
            "active": True, "featured": False, "club_id": club, "system": False,
            **win,
        })

    client = server.app.test_client()
    hdrs = {"Authorization": f"Bearer {token}"}

    clubs = client.get("/api/game/clubs", headers=hdrs).get_json()
    assert [e["id"] for e in clubs["events"]] == [
        "evt-zzz-club-soon", "evt-aaa-club-late",
    ]

    challenges = client.get("/api/game/challenges", headers=hdrs).get_json()
    assert [e["id"] for e in challenges["events"]] == [
        "evt-zzz-official-soon", "evt-aaa-official-late",
    ]
