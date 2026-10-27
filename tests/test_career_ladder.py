"""My Team career ladder must be served from per-player state, not templates.

The game compares the server's career Championship + Progress with its local
save on every My Team visit and resets the championship on any mismatch
("discrepancy between local and server save data", GitHub issue #68).  The
old handlers served frozen captured binaries (Get and Reset even disagreed
with each other) and dropped every StageBegin/StageComplete, so the dialog
fired after every race.

These tests pin the generated wire output against the upstream templates,
walk the state machine through whole championships, and prove progress
survives a server restart through the web user record.
"""
from __future__ import annotations

import http.client
import json
import random
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from dr2server import career
from dr2server.career import (
    STATE_BETWEEN_STAGES, STATE_EVENT_FINISHED, STATE_NOT_STARTED,
    STATE_STAGE_ACTIVE, CareerLadder, build_championship, fresh_progress,
    generate_spec, progress_to_egonet, spec_from_championship,
    tier_list_to_egonet,
)
from dr2server.dispatcher import RpcDispatcher
from dr2server.egonet import Int64, UInt16, UInt32, decode_stream, encode_stream
from dr2server.game_data import (
    Location, get_tracks_for_location, rallycross_stage_plan,
    stage_conditions_for_location,
)
from dr2server.httpd import App, create_server
from dr2server.models import StageBeginRequest, StageCompleteRequest

from .conftest import GAME_TOKEN, GAME_USER

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "data" / "upstream_templates"
RPC_PATH = "/RP17/1.18.0/STEAM/"

CAREER_METHODS = [
    "RaceNetCareerLadder.GetRallyTierList",
    "RaceNetCareerLadder.GetRallycrossTierList",
    "RaceNetCareerLadder.GetRallyChampionship",
    "RaceNetCareerLadder.GetRallycrossChampionship",
    "RaceNetCareerLadder.ResetRallyChampionship",
    "RaceNetCareerLadder.ResetRallycrossChampionship",
    "RaceNetCareerLadder.RallyChampionshipBegin",
    "RaceNetCareerLadder.RallycrossChampionshipBegin",
    "RaceNetCareerLadder.RallyStageBegin",
    "RaceNetCareerLadder.RallycrossStageBegin",
    "RaceNetCareerLadder.RallyStageComplete",
    "RaceNetCareerLadder.RallycrossStageComplete",
]


def _template(name: str) -> dict:
    return decode_stream((TEMPLATE_DIR / f"RaceNetCareerLadder_{name}.bin").read_bytes())


def _shape(v):
    """Nested (key, type-name) structure, so wire types are compared too."""
    if isinstance(v, dict):
        return tuple((k, _shape(x)) for k, x in v.items())
    if isinstance(v, list):
        return ("list", _shape(v[0]) if v else None)
    return type(v).__name__


def _begin(e: int, s: int, vehicle: int = 478) -> StageBeginRequest:
    return StageBeginRequest(vehicle_id=vehicle, vehicle_inst_id=55, livery_id=2915,
                             stage_index=s, event_index=e, tyres_remaining=4, tyre_compound=1)


def _complete(e: int, s: int, seconds: float = 60.0, rank: int = 1, status: int = 0,
              engine: float = 0.0) -> StageCompleteRequest:
    req = StageCompleteRequest(vehicle_id=478, vehicle_inst_id=55, livery_id=2915,
                               stage_index=s, event_index=e, stage_time=seconds,
                               champ_rank=rank, event_rank=rank, meters_driven=4200,
                               race_status=status)
    req.comp_damage.engine = engine
    return req


# --------------------------------------------------------------------------
# Wire shape against the upstream templates
# --------------------------------------------------------------------------

@pytest.mark.parametrize("name,discipline", [
    ("GetRallyChampionship", "rally"),
    ("ResetRallyChampionship", "rally"),
    ("GetRallycrossChampionship", "rallycross"),
    ("ResetRallycrossChampionship", "rallycross"),
])
def test_builder_reproduces_template_championship_bytes(name, discipline):
    tpl = _template(name)
    spec = spec_from_championship(tpl["Championship"], discipline)
    rebuilt = build_championship(spec).to_egonet()
    assert encode_stream(rebuilt) == encode_stream(tpl["Championship"])


@pytest.mark.parametrize("discipline,name", [("rally", "ResetRallyChampionship"),
                                             ("rallycross", "ResetRallycrossChampionship")])
def test_fresh_progress_matches_reset_template_bytes(discipline, name):
    tpl = _template(name)
    assert encode_stream(progress_to_egonet(fresh_progress(discipline))) == encode_stream(tpl["Progress"])
    # The career Progress carries no TuningSetup / VehicleMud.
    assert "TuningSetup" not in progress_to_egonet(fresh_progress(discipline))


@pytest.mark.parametrize("discipline,name", [("rally", "GetRallyTierList"),
                                             ("rallycross", "GetRallycrossTierList")])
def test_tier_list_matches_template_bytes(discipline, name):
    tpl = _template(name)
    assert encode_stream(tier_list_to_egonet(discipline, 0, 0)) == encode_stream(tpl["TierList"])
    other = tier_list_to_egonet(discipline, 2, 1)
    assert (other["PlayerTier"], other["PrevPlayerTier"]) == (2, 1)
    assert all(isinstance(row["DriverID"], UInt32) for row in other["TierList"])
    assert [r["DriverID"].value for r in other["TierList"]] == [r["DriverID"].value for r in tpl["TierList"]["TierList"]]


def test_generated_rally_championship_has_template_shape_and_valid_content():
    tpl = _template("GetRallyChampionship")["Championship"]
    spec = generate_spec("rally", 0, random.Random(7), now=1_700_000_000)
    wire = build_championship(spec).to_egonet()
    assert _shape(wire) == _shape(tpl)

    locs = [e["LocationId"].value for e in wire["Events"]]
    assert len(locs) == 6 and len(set(locs)) == 6
    assert int(Location.TWIN_PEAKS) not in locs
    for ev in wire["Events"]:
        loc = ev["LocationId"].value
        assert ev["DisciplineId"].value == 1
        assert (ev["NumberRestarts"], ev["NumberEntrants"]) == (5, 30)
        tracks = [s["TrackModelId"].value for s in ev["Stages"]]
        assert len(tracks) == 4 and len(set(tracks)) == 4
        assert set(tracks) <= set(get_tracks_for_location(loc))
        assert [s["StageId"] for s in ev["Stages"]] == [0, 1, 2, 3]
        for j, st in enumerate(ev["Stages"]):
            assert st["StageConditions"].value in stage_conditions_for_location(loc)
            assert st["HasServiceArea"] is (j % 2 == 0)
            assert st["SvcSettingsId"].value == (3 if j % 2 == 0 else 0)
            assert (st["StageType"], st["NumberLaps"], st["SurfaceDegrad"]) == (0, 0, 0.0)
    assert wire["DifficultyLevel"] == 50 and wire["NumEntrants"] == 30
    assert wire["EntryWindow"]["End"].value == 1_700_000_000 + career.ENTRY_WINDOW_SECONDS
    assert [t["PercentLimit"] for t in wire["Reward"]["TierRewards"]] == [10, 35, 75, 100]


def test_generated_rallycross_championship_has_template_shape_and_valid_content():
    tpl = _template("GetRallycrossChampionship")["Championship"]
    spec = generate_spec("rallycross", 0, random.Random(3), now=1_700_000_000)
    wire = build_championship(spec).to_egonet()
    assert _shape(wire) == _shape(tpl)

    locs = [e["LocationId"].value for e in wire["Events"]]
    assert len(locs) == 3 and len(set(locs)) == 3
    plan = rallycross_stage_plan(6)
    for ev in wire["Events"]:
        loc = ev["LocationId"].value
        assert Location(loc).discipline == "rallycross"
        assert ev["DisciplineId"].value == 2
        assert (ev["NumberRestarts"], ev["NumberEntrants"]) == (5, 20)
        assert [s["StageId"] for s in ev["Stages"]] == [1, 2, 3, 4, 5, 6]
        assert [(s["StageType"], s["NumberLaps"]) for s in ev["Stages"]] == plan
        assert len({s["TrackModelId"].value for s in ev["Stages"]}) == 1
        assert len({s["StageConditions"].value for s in ev["Stages"]}) == 1
        for st in ev["Stages"]:
            assert st["TrackModelId"].value in get_tracks_for_location(loc)
            assert st["StageConditions"].value in stage_conditions_for_location(loc)
            assert st["HasServiceArea"] is True and st["SvcSettingsId"].value == 5
            assert st["DryingTime"] == 600
    assert wire["DifficultyLevel"] == 0 and wire["NumEntrants"] == 20


def test_higher_tier_scales_credits():
    base = generate_spec("rally", 0, random.Random(1), now=1)
    high = generate_spec("rally", 3, random.Random(1), now=1)
    assert high["max_event_credits"] > base["max_event_credits"]
    assert high["tier_rewards"][0][0] > base["tier_rewards"][0][0]
    assert all(v % 100 == 0 for v in (high["max_event_credits"], high["tier_rewards"][0][0]))


# --------------------------------------------------------------------------
# State machine (in-memory ladder)
# --------------------------------------------------------------------------

def _ladder(**kw) -> CareerLadder:
    kw.setdefault("rng", random.Random(11))
    kw.setdefault("log", lambda _msg: None)
    kw.setdefault("now", lambda: 1_700_000_000.0)
    return CareerLadder(**kw)


def test_get_after_reset_is_identical_and_in_template_key_order():
    ladder = _ladder()
    reset = ladder.reset_championship("rally")
    got = ladder.get_championship("rally")
    assert list(reset) == ["Championship", "TierList", "Progress"]
    assert list(got) == ["Championship", "Progress", "IsNewChamp"]
    assert encode_stream(got["Championship"]) == encode_stream(reset["Championship"])
    assert encode_stream(got["Progress"]) == encode_stream(reset["Progress"])
    assert got["IsNewChamp"] is False
    assert got["Progress"]["State"] == STATE_NOT_STARTED
    # A second Get without anything happening is still identical.
    again = ladder.get_championship("rally")
    assert encode_stream(again["Championship"]) == encode_stream(got["Championship"])


def test_reset_produces_a_different_championship_at_the_same_tier():
    ladder = _ladder()
    first = ladder.get_championship("rallycross")["Championship"]
    second = ladder.reset_championship("rallycross")["Championship"]
    assert encode_stream(first) != encode_stream(second)
    assert ladder.tier_list("rallycross")["TierList"]["PlayerTier"] == 0


def test_full_rallycross_championship_promotes_and_starts_a_new_one():
    ladder = _ladder()
    before = encode_stream(ladder.get_championship("rallycross")["Championship"])

    resp = ladder.championship_begin("rallycross", _begin(0, 0))
    assert list(resp) == ["Progress", "ResultCode"]
    assert resp["Progress"]["State"] == STATE_BETWEEN_STAGES
    assert resp["Progress"]["VehicleId"].value == 478

    total = 0
    for e in range(3):
        for s in range(6):
            b = ladder.stage_begin("rallycross", _begin(e, s))["Progress"]
            assert (b["EventIndex"], b["StageIndex"], b["State"]) == (e, s, STATE_STAGE_ACTIVE)
            assert b["StageTimeMs"].value == 0
            if (e, s) != (0, 0):
                # Damage from the previous stage is carried into the next.
                assert b["VehicleDamage"]["Engine"] == pytest.approx(0.25)
            c = ladder.stage_complete("rallycross", _complete(e, s, seconds=61.5, rank=1, engine=0.25))
            assert list(c) == ["Progress", "EventReward", "ChampReward", "ResearchTarget",
                               "ResearchPercent", "OldResearchTgt", "OldResearchPct", "ResultCode"]
            total += 61500
            p = c["Progress"]
            assert p["StageTimeMs"].value == 61500
            assert p["ChampTimeMs"].value == total
            assert isinstance(p["VehicleDamage"]["QuickRepairs"], UInt16)
            assert isinstance(p["VehicleInstId"], Int64)
            if s < 5:
                assert (p["EventIndex"], p["StageIndex"], p["State"]) == (e, s + 1, STATE_BETWEEN_STAGES)
            else:
                assert (p["EventIndex"], p["StageIndex"], p["State"]) == (e, 5, STATE_EVENT_FINISHED)

    # Championship over: a fresh one at the next tier, flagged as new.
    after = ladder.get_championship("rallycross")
    assert after["IsNewChamp"] is True
    assert after["Progress"]["State"] == STATE_NOT_STARTED
    assert after["Progress"]["ChampTimeMs"].value == 0
    assert encode_stream(after["Championship"]) != before
    tiers = ladder.tier_list("rallycross")["TierList"]
    assert (tiers["PlayerTier"], tiers["PrevPlayerTier"]) == (1, 0)
    # Starting the new championship clears the flag.
    ladder.championship_begin("rallycross", _begin(0, 0))
    assert ladder.get_championship("rallycross")["IsNewChamp"] is False


def test_relegation_and_tier_clamps():
    ladder = _ladder()
    # Bottom of the field at tier 0 stays at tier 0.
    ladder.championship_begin("rally", _begin(0, 0))
    for e in range(6):
        for s in range(4):
            ladder.stage_begin("rally", _begin(e, s))
            ladder.stage_complete("rally", _complete(e, s, rank=30))
    assert ladder.tier_list("rally")["TierList"]["PlayerTier"] == 0

    # Mid-field keeps the tier; a podium at the top tier stays there.
    state = ladder._state("rally")
    state["tier"] = career.MAX_TIER
    ladder.championship_begin("rally", _begin(0, 0))
    for e in range(6):
        for s in range(4):
            ladder.stage_begin("rally", _begin(e, s))
            ladder.stage_complete("rally", _complete(e, s, rank=1))
    assert ladder.tier_list("rally")["TierList"]["PlayerTier"] == career.MAX_TIER

    state["tier"] = 2
    ladder.championship_begin("rally", _begin(0, 0))
    for e in range(6):
        for s in range(4):
            ladder.stage_begin("rally", _begin(e, s))
            ladder.stage_complete("rally", _complete(e, s, rank=28))
    assert ladder.tier_list("rally")["TierList"]["PlayerTier"] == 1
    assert len(state["history"]) == 3


def test_dnf_keeps_position_and_duplicate_complete_is_ignored():
    ladder = _ladder()
    ladder.championship_begin("rally", _begin(0, 0))
    ladder.stage_begin("rally", _begin(0, 0))
    dnf = ladder.stage_complete("rally", _complete(0, 0, seconds=30, status=2))["Progress"]
    assert (dnf["EventIndex"], dnf["StageIndex"], dnf["State"]) == (0, 0, STATE_BETWEEN_STAGES)
    assert dnf["ChampTimeMs"].value == 0

    ladder.stage_begin("rally", _begin(0, 0))
    ok = ladder.stage_complete("rally", _complete(0, 0, seconds=100))["Progress"]
    assert (ok["StageIndex"], ok["ChampTimeMs"].value) == (1, 100_000)
    dup = ladder.stage_complete("rally", _complete(0, 0, seconds=100))["Progress"]
    assert (dup["StageIndex"], dup["ChampTimeMs"].value) == (1, 100_000)


def test_stage_begin_adopts_the_clients_position():
    ladder = _ladder()
    ladder.championship_begin("rally", _begin(0, 0))
    p = ladder.stage_begin("rally", _begin(2, 3))["Progress"]
    assert (p["EventIndex"], p["StageIndex"], p["State"]) == (2, 3, STATE_STAGE_ACTIVE)
    # Out-of-range indices are clamped rather than rejected.
    p = ladder.stage_begin("rally", _begin(99, 99))["Progress"]
    assert (p["EventIndex"], p["StageIndex"]) == (5, 3)


def test_backend_outage_never_overwrites_server_state():
    saved = []
    calls = {"n": 0}
    stored = {"rally": None}

    def load():
        calls["n"] += 1
        if calls["n"] == 1:
            return None  # transient failure
        return {"rally": stored["rally"]} if stored["rally"] else {}

    def save(discipline, state):
        saved.append((discipline, json.loads(json.dumps(state))))
        return True

    # A state the backend already holds from another machine.
    stored["rally"] = career.new_state("rally", tier=2, prev_tier=1, rng=random.Random(5), now=5)
    stored["rally"]["progress"]["event_index"] = 3

    ladder = _ladder(load=load, save=save)
    first = ladder.get_championship("rally")
    assert saved == []  # nothing written while the backend was unreachable
    assert first["Progress"]["EventIndex"] == 0  # in-memory placeholder
    second = ladder.get_championship("rally")
    assert second["Progress"]["EventIndex"] == 3  # backend copy adopted
    assert ladder.tier_list("rally")["TierList"]["PlayerTier"] == 2
    ladder.stage_begin("rally", _begin(3, 0))
    assert saved and saved[-1][0] == "rally" and saved[-1][1]["progress"]["state"] == STATE_STAGE_ACTIVE


def test_invalid_stored_state_is_regenerated():
    def load():
        return {"rally": {"version": 1, "discipline": "rally", "spec": {"events": []}}, "rallycross": "junk"}

    ladder = _ladder(load=load, save=lambda d, s: True)
    assert ladder.get_championship("rally")["Progress"]["State"] == STATE_NOT_STARTED
    assert len(ladder.get_championship("rallycross")["Championship"]["Events"]) == 3


# --------------------------------------------------------------------------
# Dispatcher wiring
# --------------------------------------------------------------------------

@pytest.mark.parametrize("method", CAREER_METHODS)
def test_every_career_method_succeeds_with_empty_params_and_no_backend(method):
    d = RpcDispatcher(account_store=MagicMock(), api_client=None)
    resp = d.dispatch(method, {})
    assert resp["ok"] is True and "stub" not in resp
    encode_stream({k: v for k, v in resp.items() if k != "ok"})  # must be encodable


def test_offline_dispatcher_keeps_progress_in_memory():
    d = RpcDispatcher(account_store=MagicMock(), api_client=None)
    d.dispatch("RaceNetCareerLadder.RallycrossChampionshipBegin", {})
    d.dispatch("RaceNetCareerLadder.RallycrossStageBegin", {"EventIndex": 0, "StageIndex": 0})
    d.dispatch("RaceNetCareerLadder.RallycrossStageComplete",
               {"EventIndex": 0, "StageIndex": 0, "StageTime": 70.0, "RaceStatus": 0})
    got = d.dispatch("RaceNetCareerLadder.GetRallycrossChampionship", {})
    assert (got["Progress"]["StageIndex"], got["Progress"]["ChampTimeMs"].value) == (1, 70_000)


# --------------------------------------------------------------------------
# Full chain: egonet -> dispatcher -> web user record -> fresh server
# --------------------------------------------------------------------------

def _egonet(host: str, port: int, method: str, params: dict) -> dict:
    body = encode_stream(params)
    conn = http.client.HTTPConnection(host, port, timeout=10)
    try:
        conn.request("POST", RPC_PATH, body=body, headers={
            "Content-Type": "application/egonet-stream",
            "X-EgoNet-Function": method,
            "Content-Length": str(len(body)),
        })
        resp = conn.getresponse()
        raw = resp.read()
        assert {k.lower(): v for k, v in resp.getheaders()}["x-egonet-result"] == "0"
        return decode_stream(raw)
    finally:
        conn.close()


def test_career_progress_survives_a_server_restart(dr2_server, tmp_path) -> None:
    host, port, _app, web_app = dr2_server

    first = _egonet(host, port, "RaceNetCareerLadder.GetRallyChampionship", {})
    _egonet(host, port, "RaceNetCareerLadder.RallyChampionshipBegin", {"VehicleId": UInt32(478)})
    _egonet(host, port, "RaceNetCareerLadder.RallyStageBegin",
            {"VehicleId": UInt32(478), "VehicleInstId": Int64(55), "EventIndex": 0, "StageIndex": 0})
    done = _egonet(host, port, "RaceNetCareerLadder.RallyStageComplete",
                   {"VehicleId": UInt32(478), "EventIndex": 0, "StageIndex": 0,
                    "StageTime": 123.456, "RaceStatus": 0, "ChampRank": 1})
    assert done["Progress"]["StageIndex"] == 1

    user = json.loads((web_app.data_dir / "users" / f"{GAME_USER}.json").read_text(encoding="utf-8"))
    rally = user["career"]["rally"]
    assert rally["progress"]["stage_index"] == 1
    assert rally["progress"]["champ_time_ms"] == 123_456
    assert "rallycross" not in user["career"]

    # A brand-new local server (new process in real life) against the same
    # account must see the same championship and the stored position.
    app2 = App(data_root=tmp_path / "data2", capture_root=tmp_path / "cap2",
               api_url=web_app.url, api_token=GAME_TOKEN)
    srv = create_server("127.0.0.1", 0, app2)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        port2 = srv.server_address[1]
        again = _egonet("127.0.0.1", port2, "RaceNetCareerLadder.GetRallyChampionship", {})
        assert encode_stream(again["Championship"]) == encode_stream(first["Championship"])
        assert again["Progress"]["StageIndex"] == 1
        assert again["Progress"]["ChampTimeMs"].value == 123_456
        tiers = _egonet("127.0.0.1", port2, "RaceNetCareerLadder.GetRallyTierList", {})
        assert tiers["TierList"]["PlayerTier"] == 0
    finally:
        srv.shutdown()
        srv.server_close()


def test_web_career_endpoint(web_app) -> None:
    web_app.reset()
    web_app.seed_user(GAME_USER, game_token=GAME_TOKEN)

    def call(method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", web_app.port, timeout=10)
        headers = {"Authorization": f"Bearer {GAME_TOKEN}"}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        try:
            conn.request(method, path, body=data, headers=headers)
            resp = conn.getresponse()
            return resp.status, json.loads(resp.read())
        finally:
            conn.close()

    status, body = call("GET", "/api/game/career")
    assert (status, body) == (200, {"ok": True, "career": {}})

    status, body = call("POST", "/api/game/career", {"discipline": "rally", "state": {"tier": 1}})
    assert (status, body["ok"]) == (200, True)
    status, _ = call("POST", "/api/game/career", {"discipline": "rallycross", "state": {"tier": 2}})
    assert status == 200
    _, body = call("GET", "/api/game/career")
    assert body["career"] == {"rally": {"tier": 1}, "rallycross": {"tier": 2}}

    # Replacing one discipline leaves the other alone.
    call("POST", "/api/game/career", {"discipline": "rally", "state": {"tier": 3}})
    _, body = call("GET", "/api/game/career")
    assert body["career"] == {"rally": {"tier": 3}, "rallycross": {"tier": 2}}

    status, _ = call("POST", "/api/game/career", {"discipline": "karting", "state": {}})
    assert status == 400
    status, _ = call("POST", "/api/game/career", {"discipline": "rally", "state": [1, 2]})
    assert status == 400
    status, _ = call("POST", "/api/game/career", {"discipline": "rally", "state": {"blob": "x" * 40_000}})
    assert status == 413
    _, body = call("GET", "/api/game/career")
    assert body["career"]["rally"] == {"tier": 3}
