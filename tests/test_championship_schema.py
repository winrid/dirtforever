"""Stage-1 foundation: championship game-data mappings + schema helpers.

Covers the new best-guess Surface Deg / Service Area mappings, the verified
route helper, and the web-side duration helpers + ``normalize_championship``
adapter that bridges the legacy single-event JSON and the new v2 multi-event
championship shape.
"""
from __future__ import annotations

import importlib
import os
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

from dr2server.game_data import (
    Location,
    VERIFIED_TRACK_IDS,
    get_tracks_for_location,
    get_verified_routes_for_location,
    surface_degrad_for_level,
    service_area_for_level,
    stage_conditions_for_web,
    SURFACE_DEGRAD_LEVELS,
    SERVICE_AREA_LEVELS,
    STAGE_CONDITIONS_OPTIONS,
    STAGE_CONDITIONS_LABELS,
)

WEB_DIR = Path(__file__).resolve().parents[1] / "web"


def _load():
    os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
    os.environ.setdefault("SECRET_KEY", "test-secret")
    os.environ.setdefault("WTF_CSRF_ENABLED", "0")
    # web/server.py is shadowed by the repo-root launcher server.py.  Force
    # web/ to the front of sys.path and evict any stale root-`server` module so
    # `import server` resolves to the web app, no matter the test run order.
    while str(WEB_DIR) in sys.path:
        sys.path.remove(str(WEB_DIR))
    sys.path.insert(0, str(WEB_DIR))
    mod = sys.modules.get("server")
    if mod is None or not hasattr(mod, "normalize_championship"):
        sys.modules.pop("server", None)
        mod = importlib.import_module("server")
    return mod


# ── game_data mappings ───────────────────────────────────

def test_verified_routes_match_track_helper() -> None:
    locs_with_routes = [loc for loc in Location if get_verified_routes_for_location(int(loc))]
    assert locs_with_routes, "expected at least one location with verified routes"
    for loc in locs_with_routes:
        routes = get_verified_routes_for_location(int(loc))
        ids = [tid for tid, _n, _km in routes]
        # Same ids and order as the plain verified-track helper.
        assert ids == get_tracks_for_location(int(loc))
        for tid, name, km in routes:
            assert tid in VERIFIED_TRACK_IDS
            assert isinstance(name, str) and name
            assert isinstance(km, float)


def test_surface_degrad_mapping() -> None:
    for label, val in SURFACE_DEGRAD_LEVELS:
        assert surface_degrad_for_level(label) == val
    # Unknown label falls back to the engine default.
    assert surface_degrad_for_level("nonsense") == 0.25
    assert surface_degrad_for_level("None") == 0.0


def test_service_area_mapping() -> None:
    for label, has_area, sid in SERVICE_AREA_LEVELS:
        assert service_area_for_level(label) == (has_area, sid)
    assert service_area_for_level("nope") == (True, 2)
    # "None" disables the service area entirely.
    assert service_area_for_level("None") == (False, 0)


def test_stage_conditions_options() -> None:
    assert STAGE_CONDITIONS_OPTIONS
    for cid, label in STAGE_CONDITIONS_OPTIONS:
        assert STAGE_CONDITIONS_LABELS[cid] == label
    assert STAGE_CONDITIONS_OPTIONS == sorted(STAGE_CONDITIONS_OPTIONS)


# ── web/server.py schema helpers ─────────────────────────

def test_duration_helpers() -> None:
    server = _load()
    assert server._event_timedelta({"days": 2, "hours": 3, "mins": 30}) == timedelta(
        days=2, hours=3, minutes=30
    )
    assert server._event_timedelta({}) == timedelta(0)
    events = [{"duration": {"days": 1}}, {"duration": {"hours": 12}}]
    assert server.championship_duration(events) == timedelta(days=1, hours=12)
    assert server.bucket_for_duration(timedelta(hours=20)) == "daily"
    assert server.bucket_for_duration(timedelta(days=3)) == "weekly"
    assert server.bucket_for_duration(timedelta(days=20)) == "monthly"


def test_stage_routes_align_with_stages() -> None:
    server = _load()
    assert set(server.STAGE_ROUTES.keys()) == set(server.STAGES.keys())
    for _loc, routes in server.STAGE_ROUTES.items():
        for tid, name, km in routes:
            assert isinstance(tid, int)
            assert isinstance(name, str)
            assert isinstance(km, float)


def test_normalize_legacy_event() -> None:
    server = _load()
    legacy = {
        "id": "evt-abc",
        "type": "weekly",
        "location": "Finland",
        "car_class": "Group A",
        "surface": "Gravel",
        "conditions": "Dusk",
        "stages": [{"name": "X", "distance_km": 5.0, "conditions": "Dusk"}],
    }
    champ = server.normalize_championship(legacy)
    assert len(champ["events"]) == 1
    ev = champ["events"][0]
    assert ev["location"] == "Finland"
    assert ev["car_class"] == "Group A"
    assert ev["duration"]  # derived from the legacy type
    st = ev["stages"][0]
    assert st["conditions_id"] == stage_conditions_for_web("Dusk")
    assert champ["settings"] == server.DEFAULT_CHAMP_SETTINGS
    # Input is never mutated.
    assert "events" not in legacy
    assert "settings" not in legacy


def test_normalize_v2_event_preserves_fields() -> None:
    server = _load()
    v2 = {
        "id": "evt-xyz",
        "schema_version": 2,
        "settings": {"hardcore_damage": False},
        "events": [
            {
                "location": "Sweden",
                "car_class": "Group A",
                "duration": {"days": 2, "hours": 0, "mins": 0},
                "stages": [
                    {
                        "name": "Hamra",
                        "track_id": 590,
                        "distance_km": 7.1,
                        "conditions_id": 4,
                        "conditions": "Dusk / Cloudy / Dry",
                        "surface_deg": "Medium",
                        "service_area": "None",
                    }
                ],
            }
        ],
    }
    champ = server.normalize_championship(v2)
    assert len(champ["events"]) == 1
    st = champ["events"][0]["stages"][0]
    assert st["track_id"] == 590
    assert st["conditions_id"] == 4
    assert st["surface_deg"] == "Medium"
    assert st["service_area"] == "None"
    # Partial settings merge over the defaults.
    assert champ["settings"]["hardcore_damage"] is False
    assert champ["settings"]["allow_assists"] is True
