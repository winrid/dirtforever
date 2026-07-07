"""Stage-2 end-to-end: the championship builder routes create a v2 event.

Drives the real Flask routes (generate -> edit -> submit) via the test client
and asserts the persisted on-disk event matches the v2 schema, including
per-stage route/conditions/surface-deg/service-area, the advanced toggles, and
the summed start/end window.
"""
from __future__ import annotations

import importlib
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from dr2server.game_data import Location, get_verified_routes_for_location

WEB_DIR = Path(__file__).resolve().parents[1] / "web"


def _load():
    os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
    os.environ.setdefault("SECRET_KEY", "test-secret")
    os.environ.setdefault("WTF_CSRF_ENABLED", "0")
    while str(WEB_DIR) in sys.path:
        sys.path.remove(str(WEB_DIR))
    sys.path.insert(0, str(WEB_DIR))
    mod = sys.modules.get("server")
    if mod is None or not hasattr(mod, "normalize_championship"):
        sys.modules.pop("server", None)
        mod = importlib.import_module("server")
    return mod


def _two_locations():
    locs = [loc for loc in Location if get_verified_routes_for_location(int(loc))]
    return locs[0], locs[1]


def test_championship_builder_creates_v2_event() -> None:
    server = _load()
    server.app.config["WTF_CSRF_ENABLED"] = False
    server.app.config["TESTING"] = True

    uname = "champbuilder"
    if not server.get_user(uname):
        server.create_user(uname, "cb@example.com", "pw", email_verified=True)
    server.save_club({
        "id": "champclub", "name": "Champ Club", "created_by": uname,
        "members": [uname], "created_at": "2026-01-01T00:00:00",
    })

    client = server.app.test_client()
    with client.session_transaction() as sess:
        sess["username"] = uname

    # 1. Generate a 2-event / 2-stage draft.
    r = client.post("/clubs/champclub/championship/new",
                    data={"num_events": "2", "num_stages": "2"})
    assert r.status_code == 302
    draft_id = r.headers["Location"].rstrip("/").split("/")[-1]
    assert draft_id.startswith("champ-draft-")

    la, lb = _two_locations()
    ra = get_verified_routes_for_location(int(la))
    rb = get_verified_routes_for_location(int(lb))

    # 2. Fill the editor and save.
    form = {
        "action": "save",
        "name": "Test Champ",
        "events[0][location]": la.display_name,
        "events[0][car_class]": "Group A",
        "events[0][duration_days]": "2",
        "events[0][duration_hours]": "0",
        "events[0][duration_mins]": "0",
        "events[0][stages][0][route]": str(ra[0][0]),
        "events[0][stages][0][conditions]": "4",
        "events[0][stages][0][surface_deg]": "Max",
        "events[0][stages][0][service_area]": "None",
        "events[0][stages][1][route]": str(ra[1 % len(ra)][0]),
        "events[0][stages][1][conditions]": "1",
        "events[0][stages][1][surface_deg]": "Medium",
        "events[0][stages][1][service_area]": "Medium",
        "events[1][location]": lb.display_name,
        "events[1][car_class]": "Group A",
        "events[1][duration_days]": "1",
        "events[1][duration_hours]": "0",
        "events[1][duration_mins]": "0",
        "events[1][stages][0][route]": str(rb[0][0]),
        "events[1][stages][0][conditions]": "3",
        "events[1][stages][0][surface_deg]": "Low",
        "events[1][stages][0][service_area]": "Short",
    }
    r = client.post(f"/clubs/champclub/championship/{draft_id}", data=form)
    assert r.status_code == 302
    draft = server.get_draft(draft_id)
    assert len(draft["events"]) == 2
    assert draft["events"][0]["stages"][0]["track_id"] == ra[0][0]
    assert draft["events"][0]["stages"][0]["conditions_id"] == 4

    # 3. Submit with a future start + advanced toggles.
    start_at = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
    r = client.post(f"/clubs/champclub/championship/{draft_id}/submit", data={
        "name": "Test Champ",
        "start_at": start_at,
        "adv_hardcore_damage": "1",
        "adv_force_cockpit": "1",
        # unexpected_moments + allow_assists left unchecked
    })
    assert r.status_code == 302
    assert server.get_draft(draft_id) is None  # draft consumed

    matches = [e for e in server.get_all_events()
               if e.get("name") == "Test Champ" and e.get("club_id") == "champclub"]
    assert len(matches) == 1
    ev = matches[0]
    try:
        assert ev["schema_version"] == 2
        assert len(ev["events"]) == 2
        s0 = ev["events"][0]["stages"][0]
        assert s0["track_id"] == ra[0][0]
        assert s0["conditions_id"] == 4
        assert s0["conditions"]              # label mirror populated
        assert s0["surface_deg"] == "Max"
        assert s0["service_area"] == "None"
        # Advanced toggles: checked -> True, unchecked -> False.
        assert ev["settings"]["hardcore_damage"] is True
        assert ev["settings"]["force_cockpit_camera"] is True
        assert ev["settings"]["allow_assists"] is False
        assert ev["settings"]["unexpected_moments"] is False
        # Top-level mirrors of events[0].
        assert ev["location"] == la.display_name
        assert ev["stages"] == ev["events"][0]["stages"]
        # end = start + (2 days + 1 day).
        start = datetime.fromisoformat(ev["start_time"])
        end = datetime.fromisoformat(ev["end_time"])
        assert end - start == timedelta(days=3)
    finally:
        p = os.path.join(server.EVENTS_DIR, ev["id"] + ".json")
        if os.path.exists(p):
            os.remove(p)


def test_championship_submit_rejects_mixed_classes() -> None:
    server = _load()
    server.app.config["WTF_CSRF_ENABLED"] = False
    uname = "champmixed"
    if not server.get_user(uname):
        server.create_user(uname, "cm@example.com", "pw", email_verified=True)
    server.save_club({
        "id": "mixedclub", "name": "Mixed", "created_by": uname,
        "members": [uname], "created_at": "2026-01-01T00:00:00",
    })
    client = server.app.test_client()
    with client.session_transaction() as sess:
        sess["username"] = uname

    r = client.post("/clubs/mixedclub/championship/new",
                    data={"num_events": "2", "num_stages": "1"})
    draft_id = r.headers["Location"].rstrip("/").split("/")[-1]
    la, lb = _two_locations()
    ra = get_verified_routes_for_location(int(la))
    rb = get_verified_routes_for_location(int(lb))
    form = {
        "action": "save", "name": "Mixed Champ",
        "events[0][location]": la.display_name, "events[0][car_class]": "Group A",
        "events[0][duration_days]": "1", "events[0][duration_hours]": "0", "events[0][duration_mins]": "0",
        "events[0][stages][0][route]": str(ra[0][0]), "events[0][stages][0][conditions]": "1",
        "events[0][stages][0][surface_deg]": "Medium", "events[0][stages][0][service_area]": "Medium",
        "events[1][location]": lb.display_name, "events[1][car_class]": "R5",
        "events[1][duration_days]": "1", "events[1][duration_hours]": "0", "events[1][duration_mins]": "0",
        "events[1][stages][0][route]": str(rb[0][0]), "events[1][stages][0][conditions]": "1",
        "events[1][stages][0][surface_deg]": "Medium", "events[1][stages][0][service_area]": "Medium",
    }
    client.post(f"/clubs/mixedclub/championship/{draft_id}", data=form)
    start_at = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
    r = client.post(f"/clubs/mixedclub/championship/{draft_id}/submit",
                    data={"name": "Mixed Champ", "start_at": start_at})
    # Mixed classes bounce back to the preview; no event is written, draft kept.
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/preview")
    assert server.get_draft(draft_id) is not None
    assert not [e for e in server.get_all_events() if e.get("name") == "Mixed Champ"]
