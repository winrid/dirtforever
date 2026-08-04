"""Official (non-club) challenges — the game's Events page.

RaceNetChallenges.GetChallenges must serve the auto-generated
daily/weekly/monthly events the RaceNet way: ClubId=0, lng_* display names,
Category tab ids 1/2/3, Mode=0, UseInvVehicle=True and a 10-minute
EntryWindow submit grace — all values sourced from the upstream capture in
data/upstream_templates/RaceNetChallenges_GetChallenges.bin.
"""
from __future__ import annotations

import calendar
from datetime import datetime
from unittest.mock import MagicMock

from dr2server.dispatcher import RpcDispatcher
from dr2server.game_data import Location, get_verified_routes_for_location

from .test_championship_dispatch import _StubClient


class _ChallengesStubClient(_StubClient):
    def __init__(self, events, my_progress=None):
        self._events = events
        self._my_progress = my_progress

    def get_challenges(self):
        return self._events

    def get_my_progress(self):
        return self._my_progress


def _verified_location():
    for loc in Location:
        routes = get_verified_routes_for_location(int(loc))
        if routes:
            return loc, routes
    raise AssertionError("need a location with verified routes")


def _official_event(event_type: str, eid: str) -> dict:
    loc, routes = _verified_location()
    return {
        "id": eid,
        "name": f"{event_type.title()} #1 {loc.display_name}",
        "type": event_type,
        "car_class": "Group A",
        "start_time": "2026-08-03T10:00:00",
        "end_time": "2026-08-04T10:00:00",
        "settings": {"hardcore_damage": False},
        "club_id": None,
        "system": True,
        "events": [{
            "location": loc.display_name,
            "car_class": "Group A",
            "stages": [{"track_id": routes[0][0], "conditions_id": 1}],
        }],
    }


def _epoch(iso: str) -> int:
    return calendar.timegm(datetime.fromisoformat(iso).timetuple())


def test_daily_official_challenge_matches_upstream_shape() -> None:
    wevt = _official_event("daily", "evt-daily1")
    disp = RpcDispatcher(account_store=MagicMock(),
                         api_client=_ChallengesStubClient([wevt]))

    resp = disp._get_challenges({})
    assert resp["ok"] is True
    assert resp["Progress"] == []
    assert len(resp["Challenges"]) == 1
    ch = resp["Challenges"][0]

    # Official-only values from the upstream capture.
    assert ch["Name"] == "lng_daily_challenge"
    assert ch["ChallengeType"] == 1
    assert ch["ScoringType"] == 0
    assert ch["ClubId"].value == 0
    assert ch["Category"].value == 1
    assert ch["Mode"].value == 0
    assert ch["UseInvVehicle"] is True
    assert ch["AttemptsAllowed"] == 1

    # Entry window follows the event schedule, with the 600s submit grace.
    win = ch["EntryWindow"]
    assert win["Start"].value == _epoch("2026-08-03T10:00:00")
    assert win["LastEntry"].value == _epoch("2026-08-04T10:00:00")
    assert win["End"].value == win["LastEntry"].value + 600

    # Settings flow through like club championships.
    assert ch["IsHardcore"] is False

    # Events/stages resolve through the shared championship builder.
    assert len(ch["Events"]) == 1
    assert len(ch["Events"][0]["Stages"]) == 1

    # StageBegin/StageComplete can route the challenge back to the web event.
    assert disp._challenge_event_map[ch["ChallengeID"]] == "evt-daily1"


def test_weekly_monthly_and_custom_categories() -> None:
    events = [
        _official_event("weekly", "evt-weekly1"),
        _official_event("monthly", "evt-monthly1"),
        _official_event("custom", "evt-custom1"),
    ]
    disp = RpcDispatcher(account_store=MagicMock(),
                         api_client=_ChallengesStubClient(events))
    chs = disp._get_challenges({})["Challenges"]
    assert len(chs) == 3
    weekly, monthly, custom = chs
    assert weekly["Name"] == "lng_weekly_challenge_header"
    assert weekly["Category"].value == 2
    assert monthly["Name"] == "lng_monthly_challenge_header"
    assert monthly["Category"].value == 3
    # Unknown period: keep the event's own name, use the 'special' tab.
    assert custom["Name"] == events[2]["name"]
    assert custom["Category"].value == 4


def test_unmappable_car_class_is_skipped() -> None:
    wevt = _official_event("daily", "evt-badclass")
    wevt["car_class"] = "Not A Real Class"
    disp = RpcDispatcher(account_store=MagicMock(),
                         api_client=_ChallengesStubClient([wevt]))
    resp = disp._get_challenges({})
    assert resp["Challenges"] == []


def test_local_only_mode_serves_template() -> None:
    """Without an api_client the handler keeps the pre-existing behaviour:
    the captured upstream binary template (structurally valid, expired)."""
    disp = RpcDispatcher(account_store=MagicMock(), api_client=None)
    resp = disp._get_challenges({})
    assert isinstance(resp, bytes) and len(resp) > 0


def test_web_endpoint_serves_only_active_official_events() -> None:
    from .test_championship_web import _load

    server = _load()
    server.app.config["WTF_CSRF_ENABLED"] = False
    server.app.config["TESTING"] = True

    uname = "officialevt"
    if not server.get_user(uname):
        server.create_user(uname, "oe@example.com", "pw", email_verified=True)
    user = server.get_user(uname)
    token = "df_officialevt_token"
    user["game_token"] = token
    server.save_user(user)

    now = datetime.now()
    active = {
        "id": "evt-off-active", "name": "Daily official", "type": "daily",
        "car_class": "Group A", "location": "Sweden", "stages": [],
        "start_time": now.replace(year=now.year - 1).isoformat(),
        "end_time": now.replace(year=now.year + 1).isoformat(),
        "active": True, "club_id": None, "system": True,
    }
    club_owned = dict(active, id="evt-off-club", club_id="someclub")
    expired = dict(active, id="evt-off-expired",
                   end_time=now.replace(year=now.year - 1).isoformat())
    for e in (active, club_owned, expired):
        server.save_event(e)

    client = server.app.test_client()
    resp = client.get("/api/game/challenges",
                      headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    ids = [e["id"] for e in data["events"]]
    assert "evt-off-active" in ids
    assert "evt-off-club" not in ids
    assert "evt-off-expired" not in ids
    # Events come back normalized (v2 shape) for the dispatcher.
    served = next(e for e in data["events"] if e["id"] == "evt-off-active")
    assert "events" in served and "settings" in served
