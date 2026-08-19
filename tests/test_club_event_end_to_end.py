"""End-to-end: create a club event in the web UI, then play it in the game.

The two halves of this project were each well covered and still shipped a bug
that made a whole discipline unplayable.  A rallycross club event created
through the Quick Event form showed as Live on the site and never appeared in
game: the web app happily served it from /api/game/clubs, and the dispatcher
then dropped it because the location resolved no tracks.  Both sides were
green, because the web tests stop at "the event is in the JSON" and the
dispatcher tests start from a hand-written dict.

These tests join the seam.  They drive the real Flask routes to create an
event, assert the views a driver actually looks at, and then hand the real
/api/game/clubs response to the real RpcDispatcher, asserting a playable
Challenge comes out the far end.

The api_client here is the production ``DirtForeverClient`` with only its HTTP
read swapped for the Flask test client, so location/track/class resolution runs
the shipping code rather than a stub.  A stub is what let the original bug
through.
"""
from __future__ import annotations

import importlib
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import MagicMock

from dr2server.api_client import DirtForeverClient
from dr2server.dispatcher import RpcDispatcher
from dr2server.game_data import Location, Track

WEB_DIR = Path(__file__).resolve().parents[1] / "web"

# Rallycross circuit the original bug was reported on.
RX_LOCATION = "Lydden Hill"


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
    mod.app.config["WTF_CSRF_ENABLED"] = False
    mod.app.config["TESTING"] = True
    return mod


class _WebBackedClient(DirtForeverClient):
    """The real game api_client, reading through the Flask test client.

    Only ``_get`` is overridden, so every method above it (``get_clubs``,
    ``get_my_progress``) runs its shipping implementation against the real
    route output, Bearer auth included.
    """

    def __init__(self, flask_client: Any, token: str) -> None:
        super().__init__(base_url="http://web.test", api_token=token)
        self._flask = flask_client

    def _get(self, path: str) -> Optional[Dict[str, Any]]:
        resp = self._flask.get(path, headers=self._auth_headers())
        if resp.status_code != 200:
            return None
        return resp.get_json()  # type: ignore[no-any-return]


def _owner(server: Any, uname: str, club_id: str) -> tuple[Any, str]:
    """A verified club owner: returns (logged-in test client, game token)."""
    token = f"df_{uname}_token"
    if not server.get_user(uname):
        server.create_user(uname, f"{uname}@example.com", "pw", email_verified=True)
    user = server.get_user(uname)
    user["game_token"] = token
    user["clubs"] = [club_id]
    server.save_user(user)
    server.save_club({
        "id": club_id, "name": club_id, "created_by": uname,
        "members": [uname], "created_at": "2026-01-01T00:00:00",
        "visibility": "public", "join_policy": "open", "pending_requests": [],
    })
    client = server.app.test_client()
    with client.session_transaction() as sess:
        sess["username"] = uname
    return client, token


def _two_rally_locations(server: Any) -> tuple[str, str]:
    """Two rally (non-RX) locations the builder offers routes for."""
    locs = [l for l in sorted(server.STAGES)
            if l not in server.RX_LOCATIONS and server.STAGE_ROUTES.get(l)]
    assert len(locs) >= 2, "need two rally locations with routes"
    return locs[0], locs[1]


def _served_challenges(server: Any, client: Any, token: str) -> Any:
    """What the game receives: the real /api/game/clubs response, run through
    the real dispatcher."""
    disp = RpcDispatcher(account_store=MagicMock(),
                         api_client=_WebBackedClient(client, token))
    return disp._clubs_from_api()


def _cleanup(server: Any, *event_ids: str) -> None:
    for eid in event_ids:
        p = os.path.join(server.EVENTS_DIR, f"{eid}.json")
        if os.path.exists(p):
            os.remove(p)


def test_quick_event_on_a_rallycross_circuit_reaches_the_game() -> None:
    """The reported bug, end to end: Quick Event -> site views -> game.

    Note the class is a rally one: the Quick Event dropdown offers no RX
    classes yet, which is why the reported event carried "R2" on an RX
    circuit.  That gap is about which car the game asks for, not about whether
    the championship is served at all, which is what this test pins.
    """
    server = _load()
    client, token = _owner(server, "rxquick", "rxquickclub")

    r = client.post("/clubs/rxquickclub/events", data={
        "name": "RX Quick", "location": RX_LOCATION, "car_class": "R2",
        "conditions": "Clear", "duration": "24h", "num_stages": "1",
    }, follow_redirects=True)
    assert r.status_code == 200

    made = [e for e in server.get_all_events() if e.get("name") == "RX Quick"]
    assert len(made) == 1, "Quick Event form did not create the event"
    ev = made[0]
    try:
        assert server.event_is_active(ev), "event should be live right now"

        # The views a driver looks at.
        club_page = client.get("/clubs/rxquickclub").get_data(as_text=True)
        assert "RX Quick" in club_page
        detail = client.get(f"/events/{ev['id']}").get_data(as_text=True)
        assert "RX Quick" in detail
        assert RX_LOCATION in detail

        # The web API hands it to the game...
        api = client.get("/api/game/clubs",
                         headers={"Authorization": f"Bearer {token}"}).get_json()
        assert api["ok"]
        assert ev["id"] in [e["id"] for e in api["events"]]

        # ...and the game builds a playable challenge from it.  This is the
        # hop that used to fail while everything above it passed.
        out = _served_challenges(server, client, token)
        assert out is not None, "dispatcher served nothing for a live RX event"
        assert len(out["Challenges"]) == 1
        game_ev = out["Challenges"][0]["Events"][0]
        assert game_ev["LocationId"].value == int(Location.LYDDEN_HILL)
        assert game_ev["DisciplineId"].value == 2  # rallycross game mode
        assert game_ev["Stages"][0]["TrackModelId"].value == int(Track.LYDDEN_HILL)
    finally:
        _cleanup(server, ev["id"])


def test_championship_builder_on_a_rallycross_circuit_reaches_the_game() -> None:
    """The builder's route dropdown must offer RX routes, and what it saves
    must survive the trip to the game."""
    server = _load()
    client, token = _owner(server, "rxchamp", "rxchampclub")

    routes = server.STAGE_ROUTES[RX_LOCATION]
    assert routes, f"builder offers no routes for {RX_LOCATION}"

    r = client.post("/clubs/rxchampclub/championship/new",
                    data={"num_events": "1", "num_stages": "1"})
    draft_id = r.headers["Location"].rstrip("/").split("/")[-1]
    client.post(f"/clubs/rxchampclub/championship/{draft_id}", data={
        "action": "save", "name": "RX Champ",
        "events[0][location]": RX_LOCATION,
        "events[0][car_class]": "R2",
        "events[0][duration_days]": "1",
        "events[0][duration_hours]": "0",
        "events[0][duration_mins]": "0",
        "events[0][stages][0][route]": str(routes[0][0]),
        "events[0][stages][0][conditions]": "1",
        "events[0][stages][0][surface_deg]": "Medium",
        "events[0][stages][0][service_area]": "Medium",
    })
    start_at = (datetime.now() - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M")
    submit = client.post(f"/clubs/rxchampclub/championship/{draft_id}/submit",
                         data={"name": "RX Champ", "start_at": start_at})
    assert submit.status_code == 302

    made = [e for e in server.get_all_events() if e.get("name") == "RX Champ"]
    assert len(made) == 1, (
        "builder rejected a rallycross championship; "
        f"submit redirected to {submit.headers['Location']}"
    )
    ev = made[0]
    try:
        assert ev["events"][0]["stages"][0]["track_id"] == routes[0][0]
        detail = client.get(f"/events/{ev['id']}").get_data(as_text=True)
        assert "RX Champ" in detail

        out = _served_challenges(server, client, token)
        assert out is not None, "dispatcher served nothing for the RX championship"
        game_ev = out["Challenges"][0]["Events"][0]
        assert game_ev["DisciplineId"].value == 2
        assert game_ev["Stages"][0]["TrackModelId"].value == routes[0][0]
    finally:
        _cleanup(server, ev["id"])


def test_every_location_the_create_form_offers_can_be_served() -> None:
    """Anything the form lets an owner pick must be playable.

    This is the invariant the rallycross bug broke, stated directly: the
    create-event dropdown offered 13 circuits that the game could never
    deliver, so owners could build events that silently went nowhere.  Adding a
    location to the form without a route mapping fails here instead of in a
    player's game.
    """
    server = _load()
    client, token = _owner(server, "everyloc", "everylocclub")

    offered = sorted(server.STAGES)
    assert RX_LOCATION in offered, "form no longer offers the RX circuits"

    now = datetime.now()
    made: list[str] = []
    for i, loc in enumerate(offered):
        eid = f"evt-loc-{i:03d}"
        server.save_event({
            "id": eid, "name": f"Loc {loc}", "type": "daily",
            "club_id": "everylocclub", "location": loc, "car_class": "R2",
            "surface": server.LOCATION_SURFACE.get(loc, "Gravel"),
            "conditions": "Clear",
            "stages": [{"name": loc, "distance_km": 5.0, "conditions": "Clear"}],
            "start_time": (now - timedelta(hours=1)).isoformat(),
            "end_time": (now + timedelta(hours=1)).isoformat(),
            "active": True, "featured": False,
        })
        made.append(eid)

    try:
        out = _served_challenges(server, client, token)
        assert out is not None, "dispatcher served nothing at all"
        served = {
            int(ch["Events"][0]["LocationId"].value)
            for ch in out["Challenges"] if ch["Events"]
        }
        by_name = {loc.display_name: int(loc) for loc in Location}
        unplayable = [loc for loc in offered if by_name.get(loc) not in served]
        assert not unplayable, (
            "the create-event form offers locations the game cannot deliver: "
            f"{unplayable}"
        )
    finally:
        _cleanup(server, *made)


def test_mixed_class_championship_asks_for_a_different_car_per_rally() -> None:
    """Per-rally classes, end to end: builder -> views -> game, at both rallies.

    ``test_per_rally_vehicle_class_requirement`` covers the dispatcher from a
    hand-written dict, and ``test_championship_submit_keeps_per_rally_classes``
    covers the web side.  Neither joins them, which is the seam the rallycross
    bug slipped through, so drive the whole thing: build a Group A + R5
    championship in the real builder, then read the class the game is actually
    told to require at rally 1 and at rally 2.
    """
    server = _load()
    client, token = _owner(server, "mixede2e", "mixede2eclub")

    loc_a, loc_b = _two_rally_locations(server)
    ra = server.STAGE_ROUTES[loc_a]
    rb = server.STAGE_ROUTES[loc_b]

    r = client.post("/clubs/mixede2eclub/championship/new",
                    data={"num_events": "2", "num_stages": "1"})
    draft_id = r.headers["Location"].rstrip("/").split("/")[-1]
    client.post(f"/clubs/mixede2eclub/championship/{draft_id}", data={
        "action": "save", "name": "Mixed E2E",
        "events[0][location]": loc_a, "events[0][car_class]": "Group A",
        "events[0][duration_days]": "1", "events[0][duration_hours]": "0",
        "events[0][duration_mins]": "0",
        "events[0][stages][0][route]": str(ra[0][0]),
        "events[0][stages][0][conditions]": "1",
        "events[0][stages][0][surface_deg]": "Medium",
        "events[0][stages][0][service_area]": "Medium",
        "events[1][location]": loc_b, "events[1][car_class]": "R5",
        "events[1][duration_days]": "1", "events[1][duration_hours]": "0",
        "events[1][duration_mins]": "0",
        "events[1][stages][0][route]": str(rb[0][0]),
        "events[1][stages][0][conditions]": "1",
        "events[1][stages][0][surface_deg]": "Medium",
        "events[1][stages][0][service_area]": "Medium",
    })
    start_at = (datetime.now() - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M")
    submit = client.post(f"/clubs/mixede2eclub/championship/{draft_id}/submit",
                         data={"name": "Mixed E2E", "start_at": start_at})
    assert submit.status_code == 302

    made = [e for e in server.get_all_events() if e.get("name") == "Mixed E2E"]
    assert len(made) == 1, (
        "builder rejected a mixed-class championship; "
        f"submit redirected to {submit.headers['Location']}"
    )
    ev = made[0]
    group_a = server.vehicle_class_id_for_label("Group A")
    r5 = server.vehicle_class_id_for_label("R5")
    try:
        # The view names both classes rather than just rally 1's.
        detail = client.get(f"/events/{ev['id']}").get_data(as_text=True)
        assert "Group A + R5" in detail

        # Rally 1: the game is told to require Group A.
        out = _served_challenges(server, client, token)
        assert out is not None, "dispatcher served nothing for the championship"
        assert out["Clubs"][0]["EventIndex"] == 0
        reqs = [r["Value"].value for r in out["Challenges"][0]["Requirements"]]
        assert reqs == [group_a], f"rally 1 should require Group A, got {reqs}"

        # Finish rally 1's only stage.  Progress is derived from stored results
        # by /api/game/my-progress, so this advances the championship through
        # the real endpoint rather than a stubbed progress dict.
        server.save_results(ev["id"], {
            "event_id": ev["id"],
            "entries": [{
                "username": "mixede2e", "display_name": "mixede2e",
                "vehicle_id": 0,
                "stages": [{"time_ms": 90_000, "penalties_ms": 0,
                            "meters_driven": 5000, "distance_driven": 5000,
                            "vehicle_id": 0, "livery_id": 0}],
            }],
        })

        # Rally 2: a distinct Challenge that now requires R5.
        out2 = _served_challenges(server, client, token)
        assert out2["Clubs"][0]["EventIndex"] == 1, "championship did not advance"
        reqs2 = [r["Value"].value for r in out2["Challenges"][0]["Requirements"]]
        assert reqs2 == [r5], f"rally 2 should require R5, got {reqs2}"
        assert out2["Challenges"][0]["ChallengeID"] != out["Challenges"][0]["ChallengeID"]
    finally:
        _cleanup(server, ev["id"])
        p = os.path.join(server.RESULTS_DIR, f"{ev['id']}.json")
        if os.path.exists(p):
            os.remove(p)
