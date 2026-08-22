"""Championship points: each rally of a championship is scored on its own
finishing order with the WRC scale (25-18-15-12-10-8-6-4-2-1), and a driver's
championship total is the sum across rallies. The game only displays the
``Points`` integer we send, so the web leaderboard API must carry it.
"""
from __future__ import annotations

import importlib
import os
import sys
import tempfile
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
    if mod is None or not hasattr(mod, "_championship_points"):
        sys.modules.pop("server", None)
        mod = importlib.import_module("server")
    return mod


def _champ_event(event_id: str, club_id: str, layout: list[int]) -> dict:
    events = []
    for ei, n in enumerate(layout):
        events.append({
            "location": "Finland", "car_class": "Group A", "surface": "Gravel",
            "duration": {"days": 1, "hours": 0, "mins": 0},
            "stages": [{"name": f"S{ei}-{si}", "track_id": None, "distance_km": 5.0,
                        "conditions_id": 1, "conditions": "x",
                        "surface_deg": "Medium", "service_area": "Medium"}
                       for si in range(n)],
        })
    return {
        "id": event_id, "schema_version": 2, "name": "Champ", "type": "weekly",
        "club_id": club_id, "start_time": "2026-01-01T00:00:00",
        "end_time": "2027-01-01T00:00:00", "active": True, "featured": False,
        "settings": {}, "location": "Finland", "car_class": "Group A",
        "surface": "Gravel", "conditions": "x",
        "stages": events[0]["stages"], "events": events,
    }


def _entry(username: str, *stage_times_ms: int) -> dict:
    """A results entry whose flat stage list has the given times; 0 = DNF."""
    stages = [{"time_ms": t, "penalties_ms": 0} for t in stage_times_ms]
    return {
        "username": username,
        "car": "Car",
        "total_time_ms": sum(t for t in stage_times_ms if t > 0),
        "stages": stages,
    }


# Two rallies: rally 0 = flat stages 0-1, rally 1 = flat stage 2.
LAYOUT = [2, 1]
ENTRIES = [
    _entry("alice", 100, 100, 100),  # wins both rallies
    _entry("carol", 120, 120, 110),  # P3 in rally 0, P2 in rally 1
    _entry("bob", 110, 110, 0),      # P2 in rally 0, did not finish rally 1
    _entry("dave", 0, 130, 130),     # did not finish rally 0, P3 in rally 1
]


def test_points_follow_wrc_scale_per_rally_and_sum_across_rallies() -> None:
    server = _load()
    assert server.RALLY_POINTS == (25, 18, 15, 12, 10, 8, 6, 4, 2, 1)
    pts = server._championship_points(_champ_event("pts-1", "c", LAYOUT), ENTRIES)
    assert pts == {
        "alice": 25 + 25,
        "carol": 15 + 18,
        "bob": 18,        # nothing from the rally he did not finish
        "dave": 15,       # nothing from the rally he did not finish
    }


def test_positions_beyond_tenth_score_nothing() -> None:
    server = _load()
    entries = [_entry(f"d{i:02d}", 1000 + i) for i in range(12)]
    pts = server._championship_points(_champ_event("pts-2", "c", [1]), entries)
    assert [pts[f"d{i:02d}"] for i in range(12)] == [
        25, 18, 15, 12, 10, 8, 6, 4, 2, 1, 0, 0,
    ]


def test_every_entry_is_present_even_with_zero_points() -> None:
    server = _load()
    entries = [_entry("finisher", 500), _entry("dnf", 0)]
    pts = server._championship_points(_champ_event("pts-3", "c", [1]), entries)
    assert pts == {"finisher": 25, "dnf": 0}


def test_game_leaderboard_api_carries_points() -> None:
    server = _load()
    server.app.config["TESTING"] = True
    token = "df_points_test_token"
    uname = "pointsdriver"
    if not server.get_user(uname):
        server.create_user(uname, "pts@example.com", "pw", email_verified=True)
    user = server.get_user(uname)
    user["game_token"] = token
    server.save_user(user)

    event = _champ_event("pts-api", "pointsclub", LAYOUT)
    server.save_event(event)
    server.save_results("pts-api", {"event_id": "pts-api", "entries": ENTRIES})

    client = server.app.test_client()
    resp = client.get("/api/game/leaderboard/pts-api",
                      headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    by_name = {e["username"]: e for e in body["entries"]}
    assert by_name["alice"]["points"] == 50
    assert by_name["carol"]["points"] == 33
    assert by_name["bob"]["points"] == 18
    assert by_name["dave"]["points"] == 15
    # The endpoint's own order is still the flat time order the stage
    # leaderboards rely on; the client re-sorts championship rows by points.
    assert [e["username"] for e in body["entries"]] == [
        "alice", "carol", "bob", "dave",
    ]
