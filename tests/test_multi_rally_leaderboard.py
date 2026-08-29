"""Snapshot tests for a multi-rally championship's in-game results.

Each rally of a championship is served to the game as its own challenge, so
every board and Progress block the game sees for rally k must be scoped to
rally k's stages: the stage-result screen, the challenge leaderboard, and
ChampTimeMs. The bug this pins (Club 622 "Years of Group B", 2026-08) was
rally 2+ boards showing running championship totals, so drivers never saw a
per-rally result or standing.

Runs the real dispatcher against the real web app (`dr2_server` fixture),
with a 2-rally championship (2 stages each) and three drivers:

  ann  finished both rallies
  bob  finished rally 1 and stage 0 of rally 2
  sgt  (the local player) finished rally 1 only -> rally 2 is the active one

Responses are snapshotted under tests/snapshots/multi-rally/.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from dr2server.dispatcher import _stable_int_id

from .conftest import GAME_USER, SNAPSHOTS_DIR
from .normalize import normalize_decoded_body
from .snapshot import assert_snapshot
from .test_full_session import _normalize_db, _serialize_decoded_body

EVENT_ID = "evt-multi-rally"
SNAPS: Path = SNAPSHOTS_DIR / "multi-rally"


def _stage(name: str) -> Dict[str, Any]:
    return {"name": name, "distance_km": 10.0, "conditions": "Day"}


def _times(*ms: int) -> list[Dict[str, Any]]:
    return [{"time_ms": t, "penalties_ms": 0, "submitted_at": "2026-01-02T00:00:00",
             "vehicle_id": 393} for t in ms]


def _seed(web_app) -> None:
    web_app.seed_event(
        EVENT_ID, club_id="test-club", name="Two Rallies",
        events=[
            {"location": "Finland", "car_class": "Group B (RWD)",
             "stages": [_stage("R1 S1"), _stage("R1 S2")]},
            {"location": "Finland", "car_class": "Group B (RWD)",
             "stages": [_stage("R2 S1"), _stage("R2 S2")]},
        ],
    )
    # Rally 1 = flat stages 0-1, rally 2 = flat stages 2-3. sgt is slowest
    # over rally 1 and ann is far ahead on the championship total, so a board
    # that leaked rally-1 times would order and gap these differently.
    web_app.seed_results(EVENT_ID, [
        {"username": "ann", "vehicle_id": 393, "stages": _times(100_000, 100_000, 70_000, 80_000)},
        {"username": "bob", "vehicle_id": 393, "stages": _times(110_000, 110_000, 60_000)},
        {"username": GAME_USER, "vehicle_id": 393, "stages": _times(300_000, 300_000)},
    ])


def _snap(name: str, value: Any) -> None:
    assert_snapshot(name, normalize_decoded_body(_serialize_decoded_body(value)), SNAPS)


def _names_and_times(resp: Dict[str, Any]) -> list[tuple[str, int]]:
    return [(e["Presence"]["Name"], int(e["CumulativeBest"].value))
            for e in resp["Entries"]]


def test_rally_two_boards_and_progress_are_scoped_to_rally_two(dr2_server) -> None:
    _host, _port, app, web_app = dr2_server
    _seed(web_app)
    disp = app.dispatcher

    # Serving the club list is what registers the active challenge id
    # (base + rally index) for the championship.
    disp._clubs_from_api()
    base = _stable_int_id(EVENT_ID, base=200000, offset=0)
    served = base + 1  # sgt finished rally 1 -> rally 2 is active
    assert disp._challenge_subevent_map[served] == 1

    # 1. Stage-result board for rally 2 stage 1 (the ids the game asks for
    #    come from Stage.leaderboard_id = base*10 + rally*1_000_000 + stage).
    lb_r2_s1 = base * 10 + 1_000_000 + 0
    resp = disp._leaderboard({"LeaderboardId": lb_r2_s1, "PlayerBest": 0})
    _snap("01_lb_rally2_stage1", resp)
    assert _names_and_times(resp) == [("bob", 60_000), ("ann", 70_000)]

    # 2. Challenge-level board for the served rally-2 challenge: sgt hasn't
    #    started rally 2, so it shows the finished-rally standings.
    resp = disp._leaderboard({"LeaderboardId": served + 800000, "PlayerBest": 0})
    _snap("02_lb_rally2_challenge", resp)
    assert _names_and_times(resp) == [("ann", 150_000)]

    # 3. StageBegin for rally 2 stage 1: fresh rally, ChampTimeMs must be 0
    #    even though sgt has 600s of rally-1 time on the books.
    resp = disp._stage_begin({
        "ChallengeId": served, "EventIndex": 0, "StageIndex": 0,
        "VehicleId": 393, "LiveryId": 0, "TyreCompound": 7, "TyresRemaining": 2,
    })
    _snap("03_stage_begin_rally2_stage1", resp)
    assert int(resp["Progress"]["ChampTimeMs"].value) == 0

    # 4. StageComplete: ChampTimeMs is this rally's time only.
    resp = disp._stage_complete({
        "ChallengeId": served, "EventIndex": 0, "StageIndex": 0,
        "VehicleId": 393, "StageTime": 65.0, "RaceStatus": 0,
        "MetersDriven": 10000, "DistanceDriven": 10000,
    })
    _snap("04_stage_complete_rally2_stage1", resp)
    assert int(resp["Progress"]["ChampTimeMs"].value) == 65_000
    assert int(resp["Progress"]["StageIndex"]) == 1

    # 5. The same stage board now ranks sgt inside rally 2 on rally-2 time.
    resp = disp._leaderboard({"LeaderboardId": lb_r2_s1, "PlayerBest": 0})
    _snap("05_lb_rally2_stage1_after", resp)
    assert _names_and_times(resp) == [("bob", 60_000), ("sgt", 65_000), ("ann", 70_000)]
    assert resp["PlayerRank"] == 2

    # 6. Next StageBegin carries only rally-2 time forward.
    resp = disp._stage_begin({
        "ChallengeId": served, "EventIndex": 0, "StageIndex": 1,
        "VehicleId": 393, "LiveryId": 0, "TyreCompound": 7, "TyresRemaining": 2,
    })
    _snap("06_stage_begin_rally2_stage2", resp)
    assert int(resp["Progress"]["ChampTimeMs"].value) == 65_000

    # 7. Championship points standings are unaffected (per-rally scoring).
    club_int = next(k for k, v in disp._club_id_map.items() if v == "test-club")
    resp = disp._clubs_leaderboard({"ClubId": club_int, "StartRank": 0, "Limit": 50})
    _snap("07_championship_points", resp)

    # 8. What landed on disk: sgt's flat stage 2 (rally 2, stage 1).
    assert_snapshot("_db_state", _normalize_db(web_app.read_db_state()), SNAPS)
    sgt = next(e for e in web_app.read_results(EVENT_ID)["entries"]
               if e["username"] == GAME_USER)
    assert [s["time_ms"] for s in sgt["stages"]] == [300_000, 300_000, 65_000]
    assert sgt["car"] == "Ford RS200"
