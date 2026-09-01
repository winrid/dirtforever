"""Overall championship standings must score unfinished stages as bogey time.

total_time_ms only sums the stages a driver actually set a time on, so
ordering by it alone put whoever retired earliest on top of the standings
(reported by a club owner). The original game scored every unfinished stage
with a fixed "bogey time" instead: 15:00.000 for a sprint stage, 30:00.000
for a long stage (the 4 longest routes of the stage's own location; there is
no global distance threshold), 15:00.000 on rallycross, accumulating per
stage, with DNF drivers ranked by the adjusted total, interleaved with slow
finishers. Every surface that ranks the overall table - the stored results
order, the event/rally pages, /leaderboards, the game leaderboard API, and
profile positions - must use that adjusted total.
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
    if mod is None or not hasattr(mod, "_overall_standings"):
        sys.modules.pop("server", None)
        mod = importlib.import_module("server")
    return mod


def _champ_event(event_id, club_id, layout):
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


def _stage(t, p=0):
    return {"time_ms": t, "penalties_ms": p, "submitted_at": None}


def test_overall_standings_scores_unfinished_stages_as_bogey_time() -> None:
    server = _load()
    ev = _champ_event("evt-unit-standings", "c", [2, 2])
    entries = [
        # Stored ascending by raw total: the partial driver used to be P1.
        {"username": "quitter", "stages": [_stage(50_000)], "total_time_ms": 50_000},
        {"username": "winner", "stages": [_stage(90_000)] * 4, "total_time_ms": 360_000},
        {"username": "runner_up", "stages": [_stage(100_000)] * 4, "total_time_ms": 400_000},
        # Slower than three bogeys on real times: a DNF driver may outrank a
        # slow finisher - bogey totals interleave, DNFs are not forced last.
        {"username": "slowpoke", "stages": [_stage(800_000)] * 4, "total_time_ms": 3_200_000},
        # Padding zeros from a mid-event join must not count as completed.
        {"username": "late_joiner",
         "stages": [_stage(0), _stage(0), _stage(40_000)], "total_time_ms": 40_000},
    ]
    rows = server._overall_standings(ev, entries)
    assert [r["username"] for r in rows] == [
        "winner", "runner_up", "late_joiner", "quitter", "slowpoke"]
    # 5 km Finland stages are sprints: 15:00.000 bogey per unfinished stage.
    assert [r["total_time_ms"] for r in rows] == [
        360_000, 400_000,
        40_000 + 3 * server.BOGEY_SHORT_MS,
        50_000 + 3 * server.BOGEY_SHORT_MS,
        3_200_000,
    ]
    assert [r["stages_done"] for r in rows] == [4, 4, 1, 1, 4]
    assert all(r["stages_total"] == 4 for r in rows)


def test_bogey_classification_follows_the_location_not_a_global_cutoff() -> None:
    server = _load()
    # Long = among the 4 longest routes of the stage's own location.
    kms = sorted(km for _n, km in server.STAGES["Finland"])
    ev = _champ_event("evt-unit-bogey", "c", [2])
    ev["events"][0]["stages"][0]["distance_km"] = kms[-1]   # longest route
    ev["events"][0]["stages"][1]["distance_km"] = kms[0]    # shortest route
    assert server._flat_stage_bogeys_ms(ev) == [
        server.BOGEY_LONG_MS, server.BOGEY_SHORT_MS]
    # The threshold is per-location: Argentina's ~8 km route takes the long
    # bogey while Poland's ~9 km routes are sprints.
    assert server._long_stage_cutoff_km("Argentina") < 9.0
    assert server._long_stage_cutoff_km("Poland") > 9.3
    # Rallycross circuits always take the short bogey.
    for loc in server.RX_LOCATIONS:
        assert server._long_stage_cutoff_km(loc) is None


def _setup_session(server, event_id, club_id, prefix):
    """Create the club, a 2x2 championship, and four drivers via the real
    game API: two full finishers (one faster), and two one-stage drivers
    (one of them joining mid-event so earlier stages are zero-padded)."""
    server.app.config["WTF_CSRF_ENABLED"] = False
    server.app.config["TESTING"] = True
    client = server.app.test_client()

    tokens = {}
    for i, uname in enumerate(("winner", "runner_up", "quitter", "late_joiner")):
        full = f"{prefix}_{uname}"
        token = "df_" + f"{i:02d}{prefix}".ljust(32, "f")[:32]
        u = server.get_user(full) or server.create_user(
            full, f"{full}@e.com", "pw", email_verified=True)
        u["game_token"] = token
        u["clubs"] = [club_id]
        server.save_user(u)
        tokens[uname] = token

    server.save_club({
        "id": club_id, "name": "Standings Club",
        "created_by": f"{prefix}_winner",
        "members": [f"{prefix}_{u}" for u in tokens],
        "created_at": "2026-01-01T00:00:00",
    })
    server.save_event(_champ_event(event_id, club_id, [2, 2]))

    def complete(uname, ei, si, t):
        return client.post("/api/game/stage-complete", json={
            "event_id": event_id, "event_index": ei, "stage_index": si,
            "time_ms": t, "race_status": 0,
        }, headers={"Authorization": f"Bearer {tokens[uname]}"})

    for (ei, si) in [(0, 0), (0, 1), (1, 0), (1, 1)]:
        assert complete("winner", ei, si, 90_000).status_code == 200
        assert complete("runner_up", ei, si, 100_000).status_code == 200
    # One stage each: quitter stops after the first stage; late_joiner's
    # first submission is rally 2 stage 1 (flat index 2), padding 0 and 1.
    quit_resp = complete("quitter", 0, 0, 50_000)
    assert quit_resp.status_code == 200
    late_resp = complete("late_joiner", 1, 0, 40_000)
    assert late_resp.status_code == 200
    return client, tokens, quit_resp, late_resp


def _cleanup(server, event_id):
    for d in (server.EVENTS_DIR, server.RESULTS_DIR):
        p = os.path.join(d, event_id + ".json")
        if os.path.exists(p):
            os.remove(p)


def test_submit_and_game_leaderboard_rank_partial_drivers_last() -> None:
    server = _load()
    eid = "evt-standings-api"
    try:
        client, tokens, quit_resp, late_resp = _setup_session(
            server, eid, "standclub-api", "sapi")

        # The position echoed back to the game must not call a retiree P1.
        # quitter submits before late_joiner exists, so 3 of 3 at that point;
        # late_joiner then slots in at 3 on the faster single-stage time.
        assert quit_resp.get_json()["position"] == 3
        assert late_resp.get_json()["position"] == 3

        stored = [e["username"] for e in server.get_results(eid)["entries"]]
        assert stored == ["sapi_winner", "sapi_runner_up",
                          "sapi_late_joiner", "sapi_quitter"]

        r = client.get(f"/api/game/leaderboard/{eid}",
                       headers={"Authorization": f"Bearer {tokens['winner']}"})
        assert r.status_code == 200
        entries = r.get_json()["entries"]
        assert [(e["rank"], e["username"]) for e in entries] == [
            (1, "sapi_winner"), (2, "sapi_runner_up"),
            (3, "sapi_late_joiner"), (4, "sapi_quitter")]
    finally:
        _cleanup(server, eid)


def test_event_detail_page_orders_and_flags_partial_entries() -> None:
    server = _load()
    eid = "evt-standings-page"
    try:
        client, _tokens, _q, _l = _setup_session(
            server, eid, "standclub-page", "spage")
        html = client.get(f"/events/{eid}").data.decode()
        order = [html.index(f"spage_{u}") for u in
                 ("winner", "runner_up", "late_joiner", "quitter")]
        assert order == sorted(order), "standings rows out of order"
        # Partial entries are flagged with completed/total stages.
        assert "1/4" in html
        assert "4/4" in html
    finally:
        _cleanup(server, eid)


def test_rally_page_includes_dnf_entries_with_bogey_totals() -> None:
    server = _load()
    eid = "evt-standings-rally"
    try:
        client, _t, _q, _l = _setup_session(
            server, eid, "standclub-rally", "srally")
        html = client.get(f"/events/{eid}/rally/0").data.decode()
        # Rally 1 = flat stages 0-1. quitter ran only stage 0 (one bogey);
        # late_joiner ran neither stage of this rally (two bogeys).
        order = [html.index(f"srally_{u}") for u in
                 ("winner", "runner_up", "quitter", "late_joiner")]
        assert order == sorted(order), "rally standings out of order"
        assert "(1 DNF)" in html
        assert "(2 DNF)" in html
    finally:
        _cleanup(server, eid)


def test_leaderboards_page_overall_and_stage_views() -> None:
    server = _load()
    eid = "evt-standings-lb"
    try:
        client, _tokens, _q, _l = _setup_session(
            server, eid, "standclub-lb", "slb")

        html = client.get(f"/leaderboards?tab=events&event={eid}").data.decode()
        order = [html.index(f"slb_{u}") for u in
                 ("winner", "runner_up", "late_joiner", "quitter")]
        assert order == sorted(order), "overall leaderboard out of order"

        # Stage 0: late_joiner only has a padding zero there and must not
        # appear at all (a 0:00 used to render on top).
        html = client.get(
            f"/leaderboards?tab=events&event={eid}&stage=0").data.decode()
        assert "slb_late_joiner" not in html
        assert html.index("slb_quitter") < html.index("slb_winner")
    finally:
        _cleanup(server, eid)
