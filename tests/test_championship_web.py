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

from dr2server.game_data import (
    Location,
    get_verified_routes_for_location,
    stage_conditions_for_location,
)

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


def test_championship_start_time_uses_browser_epoch() -> None:
    """The picker is read in the viewer's timezone, so enhance.js posts the
    chosen instant as epoch seconds; the server must honour it over the raw
    (server-zone) wall-clock string."""
    server = _load()
    server.app.config["WTF_CSRF_ENABLED"] = False
    uname = "champtz"
    if not server.get_user(uname):
        server.create_user(uname, "tz@example.com", "pw", email_verified=True)
    server.save_club({
        "id": "tzclub", "name": "TZ", "created_by": uname,
        "members": [uname], "created_at": "2026-01-01T00:00:00",
    })
    client = server.app.test_client()
    with client.session_transaction() as sess:
        sess["username"] = uname

    r = client.post("/clubs/tzclub/championship/new",
                    data={"num_events": "1", "num_stages": "1"})
    draft_id = r.headers["Location"].rstrip("/").split("/")[-1]
    la, _ = _two_locations()
    ra = get_verified_routes_for_location(int(la))
    client.post(f"/clubs/tzclub/championship/{draft_id}", data={
        "action": "save", "name": "TZ Champ",
        "events[0][location]": la.display_name, "events[0][car_class]": "Group A",
        "events[0][duration_days]": "1", "events[0][duration_hours]": "0",
        "events[0][duration_mins]": "0",
        "events[0][stages][0][route]": str(ra[0][0]),
        "events[0][stages][0][conditions]": "1",
        "events[0][stages][0][surface_deg]": "Medium",
        "events[0][stages][0][service_area]": "Medium",
    })

    # The preview hands the browser real instants to localize.
    r = client.get(f"/clubs/tzclub/championship/{draft_id}/preview")
    body = r.get_data(as_text=True)
    assert 'data-min-epoch="' in body
    assert 'data-start-epoch="' in body
    assert 'name="start_at_epoch"' in body

    picked = datetime.now() + timedelta(days=2)
    epoch = picked.timestamp()
    r = client.post(f"/clubs/tzclub/championship/{draft_id}/submit", data={
        "name": "TZ Champ",
        # Stale/mismatched wall-clock text; the epoch is authoritative.
        "start_at": (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M"),
        "start_at_epoch": str(epoch),
    })
    assert r.status_code == 302
    matches = [e for e in server.get_all_events()
               if e.get("name") == "TZ Champ" and e.get("club_id") == "tzclub"]
    assert len(matches) == 1
    ev = matches[0]
    try:
        start = datetime.fromisoformat(ev["start_time"])
        assert start == picked.replace(second=0, microsecond=0)
    finally:
        p = os.path.join(server.EVENTS_DIR, ev["id"] + ".json")
        if os.path.exists(p):
            os.remove(p)


def _one_event_draft(client, server, club_id, name):
    """Generate + fill a 1-event / 1-stage draft; returns its draft id."""
    r = client.post(f"/clubs/{club_id}/championship/new",
                    data={"num_events": "1", "num_stages": "1"})
    draft_id = r.headers["Location"].rstrip("/").split("/")[-1]
    la, _ = _two_locations()
    ra = get_verified_routes_for_location(int(la))
    client.post(f"/clubs/{club_id}/championship/{draft_id}", data={
        "action": "save", "name": name,
        "events[0][location]": la.display_name, "events[0][car_class]": "Group A",
        "events[0][duration_days]": "1", "events[0][duration_hours]": "0",
        "events[0][duration_mins]": "0",
        "events[0][stages][0][route]": str(ra[0][0]),
        "events[0][stages][0][conditions]": "1",
        "events[0][stages][0][surface_deg]": "Medium",
        "events[0][stages][0][service_area]": "Medium",
    })
    return draft_id


def _owner_client(server, uname, club_id):
    server.app.config["WTF_CSRF_ENABLED"] = False
    if not server.get_user(uname):
        server.create_user(uname, f"{uname}@example.com", "pw", email_verified=True)
    server.save_club({
        "id": club_id, "name": club_id, "created_by": uname,
        "members": [uname], "created_at": "2026-01-01T00:00:00",
    })
    client = server.app.test_client()
    with client.session_transaction() as sess:
        sess["username"] = uname
    return client


def _live_event(server, club_id, eid, name="Live One", days=3):
    """Persist a currently-running club event and return it."""
    now = datetime.now()
    ev = {
        "id": eid, "name": name, "type": "weekly", "club_id": club_id,
        "location": "Poland", "car_class": "Group A", "surface": "Gravel",
        "conditions": "Clear", "stages": [],
        "start_time": (now - timedelta(hours=1)).isoformat(),
        "end_time": (now + timedelta(days=days)).isoformat(),
        "active": True, "featured": False,
    }
    server.save_event(ev)
    return ev


def test_one_live_championship_per_club() -> None:
    """The game carries one event cursor per club, so overlapping club events
    would leave one unreachable in game.  Both creation paths must refuse."""
    server = _load()
    client = _owner_client(server, "slotowner", "slotclub")
    live = _live_event(server, "slotclub", "evt-slot-live")

    try:
        # Quick Event starts now -> always overlaps a live one.
        # The form posts a StageConditions id, not a weather word: conditions
        # are per-location now, so the id has to be one Poland can load.
        quick = {
            "name": "Quick Clash", "location": "Poland", "car_class": "Group A",
            "conditions": str(stage_conditions_for_location("Poland")[0]),
            "duration": "24h", "num_stages": "1",
        }
        r = client.post("/clubs/slotclub/events", data=quick, follow_redirects=True)
        assert r.status_code == 200
        assert "is still running in this club" in r.get_data(as_text=True)
        assert not [e for e in server.get_all_events() if e.get("name") == "Quick Clash"]

        # Same form succeeds once the slot is free; the gate is the only reason
        # it bounced above.
        os.remove(os.path.join(server.EVENTS_DIR, live["id"] + ".json"))
        client.post("/clubs/slotclub/events", data=quick)
        made = [e for e in server.get_all_events() if e.get("name") == "Quick Clash"]
        assert len(made) == 1
        os.remove(os.path.join(server.EVENTS_DIR, made[0]["id"] + ".json"))
        server.save_event(live)

        # A championship starting inside the live window is refused too.
        draft_id = _one_event_draft(client, server, "slotclub", "Champ Clash")
        overlap = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
        r = client.post(f"/clubs/slotclub/championship/{draft_id}/submit",
                        data={"name": "Champ Clash", "start_at": overlap})
        assert r.status_code == 302
        assert r.headers["Location"].endswith("/preview")
        assert not [e for e in server.get_all_events() if e.get("name") == "Champ Clash"]

        # Starting after it ends is the supported (RaceNet back-to-back) shape.
        after = (datetime.fromisoformat(live["end_time"]) + timedelta(minutes=1)
                 ).strftime("%Y-%m-%dT%H:%M")
        r = client.post(f"/clubs/slotclub/championship/{draft_id}/submit",
                        data={"name": "Champ Clash", "start_at": after})
        assert r.status_code == 302
        made = [e for e in server.get_all_events() if e.get("name") == "Champ Clash"]
        assert len(made) == 1
    finally:
        for e in server.get_all_events():
            if e.get("club_id") == "slotclub":
                p = os.path.join(server.EVENTS_DIR, e["id"] + ".json")
                if os.path.exists(p):
                    os.remove(p)


def test_preview_defaults_start_to_when_the_club_frees_up() -> None:
    server = _load()
    client = _owner_client(server, "slotdefault", "slotdefclub")
    live = _live_event(server, "slotdefclub", "evt-slotdef-live", days=2)
    try:
        draft_id = _one_event_draft(client, server, "slotdefclub", "Next Up")
        r = client.get(f"/clubs/slotdefclub/championship/{draft_id}/preview")
        body = r.get_data(as_text=True)
        end_epoch = int(datetime.fromisoformat(live["end_time"]).timestamp())
        assert f'data-min-epoch="{end_epoch}"' in body
        assert f'data-start-epoch="{end_epoch}"' in body
        assert "already has a championship running" in body
    finally:
        for e in server.get_all_events():
            if e.get("club_id") == "slotdefclub":
                p = os.path.join(server.EVENTS_DIR, e["id"] + ".json")
                if os.path.exists(p):
                    os.remove(p)


def test_scheduled_championship_is_labelled_upcoming() -> None:
    """A future-start event isn't served to the game, so the site must not show
    it as if it were live: that mismatch is what reads as 'it never appeared'."""
    server = _load()
    client = _owner_client(server, "upcomingowner", "upcomingclub")
    now = datetime.now()
    ev = {
        "id": "evt-upcoming-1", "name": "Later Champ", "type": "weekly",
        "club_id": "upcomingclub", "location": "Poland", "car_class": "Group A",
        "surface": "Gravel", "conditions": "Clear", "stages": [],
        "start_time": (now + timedelta(hours=3)).isoformat(),
        "end_time": (now + timedelta(days=7)).isoformat(),
        "active": True, "featured": False,
    }
    server.save_event(ev)
    try:
        assert server.event_is_upcoming(ev) is True
        assert server.event_is_active(ev) is False  # not served to the game yet

        body = client.get("/clubs/upcomingclub").get_data(as_text=True)
        assert "Starts in" in body

        body = client.get("/events/evt-upcoming-1").get_data(as_text=True)
        assert "Starts in" in body
    finally:
        p = os.path.join(server.EVENTS_DIR, ev["id"] + ".json")
        if os.path.exists(p):
            os.remove(p)


def test_builder_limits_stay_mutually_consistent() -> None:
    """The editor must not be able to express a championship that submit then
    rejects: the worst case it can build is MAX_CHAMP_EVENTS rallies at
    MAX_EVENT_DAYS each, so the total ceiling has to clear that."""
    server = _load()
    worst_case = timedelta(days=server.MAX_CHAMP_EVENTS * server.MAX_EVENT_DAYS)
    assert worst_case <= server.MAX_CHAMP_DURATION


def test_championship_accepts_twelve_events_and_long_rallies() -> None:
    """Upstream RaceNet clubs run up to 12 events, and a club asked for rallies
    longer than a week, so both must survive generate -> edit -> submit."""
    server = _load()
    client = _owner_client(server, "twelveowner", "twelveclub")

    n = server.MAX_CHAMP_EVENTS
    assert n == 12
    r = client.post("/clubs/twelveclub/championship/new",
                    data={"num_events": str(n), "num_stages": "1"})
    assert r.status_code == 302
    draft_id = r.headers["Location"].rstrip("/").split("/")[-1]
    draft = server.get_draft(draft_id)
    assert len(draft["events"]) == n

    # 12 rallies, each running longer than the old 7-day ceiling.
    days = server.MAX_EVENT_DAYS
    assert days > 7
    form = {"action": "save", "name": "Twelve Round Series"}
    for i, ev in enumerate(draft["events"]):
        form[f"events[{i}][location]"] = ev["location"]
        form[f"events[{i}][car_class]"] = ev["car_class"]
        form[f"events[{i}][duration_days]"] = str(days)
        form[f"events[{i}][duration_hours]"] = "0"
        form[f"events[{i}][duration_mins]"] = "0"
        for j, st in enumerate(ev["stages"]):
            form[f"events[{i}][stages][{j}][route]"] = str(st["track_id"])
            form[f"events[{i}][stages][{j}][conditions]"] = str(st["conditions_id"])
            form[f"events[{i}][stages][{j}][surface_deg]"] = st["surface_deg"]
            form[f"events[{i}][stages][{j}][service_area]"] = st["service_area"]
    r = client.post(f"/clubs/twelveclub/championship/{draft_id}", data=form)
    assert r.status_code == 302

    start_at = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
    r = client.post(f"/clubs/twelveclub/championship/{draft_id}/submit",
                    data={"name": "Twelve Round Series", "start_at": start_at})
    assert r.status_code == 302
    matches = [e for e in server.get_all_events()
               if e.get("name") == "Twelve Round Series"]
    assert len(matches) == 1
    ev = matches[0]
    try:
        assert len(ev["events"]) == 12
        start = datetime.fromisoformat(ev["start_time"])
        end = datetime.fromisoformat(ev["end_time"])
        assert end - start == timedelta(days=12 * days)
    finally:
        p = os.path.join(server.EVENTS_DIR, ev["id"] + ".json")
        if os.path.exists(p):
            os.remove(p)


def test_event_duration_beyond_the_cap_is_rejected() -> None:
    server = _load()
    client = _owner_client(server, "longowner", "longclub")
    draft_id = _one_event_draft(client, server, "longclub", "Too Long")
    draft = server.get_draft(draft_id)
    ev = draft["events"][0]
    st = ev["stages"][0]
    client.post(f"/clubs/longclub/championship/{draft_id}", data={
        "action": "save", "name": "Too Long",
        "events[0][location]": ev["location"],
        "events[0][car_class]": ev["car_class"],
        "events[0][duration_days]": str(server.MAX_EVENT_DAYS + 1),
        "events[0][duration_hours]": "0", "events[0][duration_mins]": "0",
        "events[0][stages][0][route]": str(st["track_id"]),
        "events[0][stages][0][conditions]": str(st["conditions_id"]),
        "events[0][stages][0][surface_deg]": st["surface_deg"],
        "events[0][stages][0][service_area]": st["service_area"],
    })
    start_at = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
    r = client.post(f"/clubs/longclub/championship/{draft_id}/submit",
                    data={"name": "Too Long", "start_at": start_at})
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/preview")
    assert not [e for e in server.get_all_events() if e.get("name") == "Too Long"]


def test_validation_rejects_conditions_the_location_cannot_load() -> None:
    """Conditions are validated per location, exactly as routes already are.

    This is the last gate before publish. Validating conditions against the
    global label table would accept a real id whose lighting the location does
    not ship, which loads the stage with a broken sky -- the bug the
    per-location table exists to prevent.
    """
    server = _load()
    routes = get_verified_routes_for_location(int(Location.GERMANY))
    germany = stage_conditions_for_location(Location.GERMANY)
    # 38 (Daytime / Overcast / Dry) is a real id, but only Poland and Argentina
    # ship the lighting for it.
    assert 38 not in germany

    def events(cid: int) -> list[dict]:
        return [{
            "location": Location.GERMANY.display_name, "car_class": "R5",
            "duration": {"days": 1, "hours": 0, "mins": 0},
            "stages": [{"track_id": routes[0][0], "conditions_id": cid,
                        "surface_deg": "Medium", "service_area": "Medium"}],
        }]

    def conditions_errors(cid: int) -> list[str]:
        return [e for e in server._validate_championship(events(cid))
                if "conditions" in e]

    assert not conditions_errors(germany[0])
    assert conditions_errors(38)
    # 34 renders the same label as 20 but no location ships its lighting.
    assert conditions_errors(34)


def test_club_event_form_works_without_javascript() -> None:
    """The conditions select must ship real options, not just a placeholder.

    enhance.js narrows it to the chosen location, but a select holding only
    `<option value="">` while marked `required` cannot be submitted at all with
    JS off -- the browser blocks it before the server sees anything. Every
    location's options are rendered grouped instead, and the server rejects a
    location/conditions pair that does not match.
    """
    server = _load()
    server.app.config["WTF_CSRF_ENABLED"] = False
    uname = "nojsowner"
    if not server.get_user(uname):
        server.create_user(uname, "nojs@example.com", "pw", email_verified=True)
    server.save_club({
        "id": "nojsclub", "name": "NoJS", "created_by": uname,
        "members": [uname], "created_at": "2026-01-01T00:00:00",
    })
    client = server.app.test_client()
    with client.session_transaction() as sess:
        sess["username"] = uname

    html = client.get("/clubs/nojsclub").get_data(as_text=True)
    select = html[html.index('id="ev_conditions"'):]
    select = select[:select.index("</select>")]
    assert "<optgroup" in select, "conditions select renders no options without JS"
    served = sum(len(ids) for ids in
                 __import__("dr2server.game_data", fromlist=["x"])
                 .STAGE_CONDITIONS_BY_LOCATION.values())
    assert select.count("<option value=") == served + 1  # +1 placeholder

    # A location/conditions pair the game can load is accepted...
    good = stage_conditions_for_location(Location.GERMANY)[1]
    client.post("/clubs/nojsclub/events", data={
        "name": "NoJS Good", "location": Location.GERMANY.display_name,
        "car_class": "R5", "conditions": str(good),
        "num_stages": "1", "duration": "24h"})
    made = [e for e in server.get_all_events() if e.get("name") == "NoJS Good"]
    assert made and made[0]["stages"][0]["conditions_id"] == good

    # ...and one from another location's group is not.
    server.save_club({
        "id": "nojsclub2", "name": "NoJS2", "created_by": uname,
        "members": [uname], "created_at": "2026-01-01T00:00:00",
    })
    assert 38 not in stage_conditions_for_location(Location.GERMANY)
    client.post("/clubs/nojsclub2/events", data={
        "name": "NoJS Mismatch", "location": Location.GERMANY.display_name,
        "car_class": "R5", "conditions": "38",
        "num_stages": "1", "duration": "24h"})
    assert not [e for e in server.get_all_events() if e.get("name") == "NoJS Mismatch"]
