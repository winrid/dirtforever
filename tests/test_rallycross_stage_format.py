"""Rallycross club events are served as lapped races, the way RaceNet did.

With the circuit ids right, an RX club event still crashed the game on stage
load because the stage carried the rally shape (StageType 0, NumberLaps 0).
Every discipline-2 stage in the RaceNet templates is StageType 2/3/4 with
laps, HasServiceArea=True, SvcSettingsId=5, SurfaceDegrad=0.0, and the event
carries NumberRestarts=5.  These pin that shape on both builder paths.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock

from dr2server.dispatcher import RpcDispatcher
from dr2server.game_data import (
    Location, Track, rallycross_stage_plan,
    RX_GRID_ENTRANTS, RX_NUMBER_RESTARTS, RX_SVC_SETTINGS_ID,
)
from tests.test_championship_dispatch import _FullStubClient


def _rx_event(stage_count: int, **extra) -> dict:
    return {
        "id": "evt-rx", "name": "rx test", "club_id": "club-rx",
        "location": "Barcelona", "car_class": "Group B Rallycross",
        "start_time": "2026-08-18T13:59:31", "end_time": "2026-08-29T13:59:31",
        "stages": [{"name": "Circuit de Barcelona-Catalunya", "conditions_id": 1,
                    "service_area": "Medium", "surface_deg": "Medium"}
                   for _ in range(stage_count)],
        **extra,
    }


def _serve(event: dict) -> dict:
    club = [{"id": "club-rx", "name": "RX Club", "created_by": "HappyHydra"}]
    disp = RpcDispatcher(account_store=MagicMock(),
                         api_client=_FullStubClient(clubs=club, events=[event]))
    out = disp._clubs_from_api()
    assert out and out["ok"] and len(out["Challenges"]) == 1
    return out["Challenges"][0]["Events"][0]


def _v(x):
    return getattr(x, "value", x)


def test_plan_shapes() -> None:
    assert rallycross_stage_plan(1) == [(2, 6)]
    assert rallycross_stage_plan(2) == [(2, 4), (4, 6)]
    assert rallycross_stage_plan(3) == [(2, 4), (3, 6), (4, 6)]
    # RaceNet's weekly / championship format.
    assert rallycross_stage_plan(6) == [(2, 4)] * 4 + [(3, 6), (4, 6)]


def test_single_stage_rx_event_is_the_solo_daily_format() -> None:
    ev = _serve(_rx_event(1))
    assert _v(ev["DisciplineId"]) == 2
    assert _v(ev["LocationId"]) == int(Location.BARCELONA)
    assert ev["NumberRestarts"] == RX_NUMBER_RESTARTS
    assert ev["NumberEntrants"] == 0
    (stage,) = ev["Stages"]
    assert _v(stage["TrackModelId"]) == int(Track.BARCELONA)
    assert stage["StageType"] == 2
    assert stage["NumberLaps"] == 6
    assert stage["HasServiceArea"] is True
    assert _v(stage["SvcSettingsId"]) == RX_SVC_SETTINGS_ID
    assert stage["SurfaceDegrad"] == 0.0


def test_multi_stage_rx_event_is_the_knockout_format_with_a_grid() -> None:
    ev = _serve(_rx_event(6))
    assert ev["NumberEntrants"] == RX_GRID_ENTRANTS
    assert [(s["StageType"], s["NumberLaps"]) for s in ev["Stages"]] == \
        [(2, 4)] * 4 + [(3, 6), (4, 6)]
    # The stored rally-style service-area level does not leak through.
    assert all(s["HasServiceArea"] is True and _v(s["SvcSettingsId"]) == RX_SVC_SETTINGS_ID
               for s in ev["Stages"])


def test_rally_events_keep_the_rally_shape() -> None:
    rally = _rx_event(2, location="Germany", car_class="R5")
    rally["stages"] = [{"name": "Oberstein", "conditions_id": 9,
                        "service_area": "Medium", "surface_deg": "Medium"}] * 2
    ev = _serve(rally)
    assert _v(ev["DisciplineId"]) == 1
    assert ev["NumberRestarts"] == 0 and ev["NumberEntrants"] == 0
    assert all(s["StageType"] == 0 and s["NumberLaps"] == 0 for s in ev["Stages"])


def test_debug_probe_path_uses_the_rx_shape(tmp_path: Path) -> None:
    probe = tmp_path / "probe.json"
    probe.write_text(json.dumps({"probes": [
        {"name": "RX", "location_id": int(Location.BIKERNIEKI),
         "track_model_id": int(Track.BIKERNIEKI), "stage_conditions": 1,
         "vehicle_class_id": 92},
    ]}), encoding="utf-8")
    disp = RpcDispatcher(account_store=MagicMock())
    old = os.environ.get("DR2_DEBUG_CLUBS_FILE")
    os.environ["DR2_DEBUG_CLUBS_FILE"] = str(probe)
    try:
        out = disp._debug_clubs_from_file(str(probe))
    finally:
        if old is None:
            os.environ.pop("DR2_DEBUG_CLUBS_FILE", None)
        else:
            os.environ["DR2_DEBUG_CLUBS_FILE"] = old
    ev = out["Challenges"][0]["Events"][0]
    assert _v(ev["DisciplineId"]) == 2
    assert ev["NumberRestarts"] == RX_NUMBER_RESTARTS
    (stage,) = ev["Stages"]
    assert (stage["StageType"], stage["NumberLaps"]) == (2, 6)
    assert stage["HasServiceArea"] is True
    assert _v(stage["SvcSettingsId"]) == RX_SVC_SETTINGS_ID
