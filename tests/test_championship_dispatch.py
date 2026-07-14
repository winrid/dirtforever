"""Dispatcher championship building.

A multi-event championship is served the RaceNet way: ONE active sub-event at a
time, as its own single-event Challenge, with the Club advertising
AmountOfEvents=N / EventIndex=current and advancing on completion (verified
2026-07-07 — see notes/protocol_notes.md).  ``_build_events_for_champ`` still
builds every sub-event for the single-event / legacy paths, and event index 0
keeps the exact ids the single-event path always produced.
"""
from __future__ import annotations

import calendar
from datetime import datetime
from unittest.mock import MagicMock

from dr2server.dispatcher import RpcDispatcher
from dr2server.game_data import (
    Location,
    get_tracks_for_location,
    get_verified_routes_for_location,
)


from dr2server.game_data import vehicle_class_id_for_label


class _StubClient:
    """Minimal api_client: resolve locations by display name, return verified
    routes for a location (matching how the web builder picks routes)."""

    def resolve_location_id(self, name):
        for loc in Location:
            if loc.display_name == name:
                return int(loc)
        return None

    def tracks_for_location(self, location_id):
        return get_tracks_for_location(location_id)

    def resolve_vclass_id(self, label):
        return vehicle_class_id_for_label(label)


class _FullStubClient(_StubClient):
    def __init__(self, clubs, events, my_progress=None):
        self._data = {"clubs": clubs, "events": events}
        self._my_progress = my_progress

    def get_clubs(self):
        return self._data

    def get_my_progress(self):
        return self._my_progress


def _dispatcher() -> RpcDispatcher:
    return RpcDispatcher(account_store=MagicMock(), api_client=_StubClient())


def _two_locations_with_routes():
    locs = [loc for loc in Location if get_verified_routes_for_location(int(loc))]
    assert len(locs) >= 2, "need two locations with verified routes for this test"
    return locs[0], locs[1]


def test_multi_event_challenge_structure() -> None:
    disp = _dispatcher()
    loc_a, loc_b = _two_locations_with_routes()
    routes_a = get_verified_routes_for_location(int(loc_a))
    routes_b = get_verified_routes_for_location(int(loc_b))

    chal_id = 200123
    champ = {
        "id": "evt-champ01",
        "name": "Test Championship",
        "car_class": "Group A",
        "start_time": "2026-07-10T18:00:00",
        "end_time": "2026-07-16T18:00:00",
        "settings": {"hardcore_damage": False, "force_cockpit_camera": True},
        "events": [
            {
                "location": loc_a.display_name,
                "stages": [
                    {"track_id": routes_a[0][0], "conditions_id": 4,
                     "surface_deg": "Max", "service_area": "None"},
                    {"track_id": routes_a[1 % len(routes_a)][0], "conditions_id": 1,
                     "surface_deg": "Medium", "service_area": "Long"},
                ],
            },
            {
                "location": loc_b.display_name,
                "stages": [
                    {"track_id": routes_b[0][0], "conditions_id": 3,
                     "surface_deg": "None", "service_area": "Short"},
                ],
            },
        ],
    }

    events = disp._build_events_for_champ(champ, chal_id)
    assert len(events) == 2

    e0, e1 = events
    # Event 0 keeps the single-event ids exactly.
    assert e0.event_id == chal_id
    assert e0.leaderboard_id == chal_id + 900000
    assert e0.stages[0].leaderboard_id == chal_id * 10 + 0
    assert e0.stages[1].leaderboard_id == chal_id * 10 + 1
    # Event 1 gets distinct, non-colliding ids.
    assert e1.event_id == chal_id + 10_000_000
    assert e1.leaderboard_id == chal_id + 900000 + 10_000_000
    assert e1.stages[0].leaderboard_id == chal_id * 10 + 1_000_000

    # Per-stage values flow through.
    s0 = e0.stages[0]
    assert s0.track_model_id == routes_a[0][0]
    assert s0.stage_conditions == 4
    assert s0.surface_degrad == 1.0            # "Max"
    assert s0.has_service_area is False        # "None"
    assert s0.svc_settings_id == 0
    s1 = e0.stages[1]
    assert s1.surface_degrad == 0.5            # "Medium"
    assert s1.has_service_area is True         # "Long"
    assert s1.svc_settings_id == 4             # "Long" (verified RaceNet ordinal)

    # Challenge-level: advanced toggles + entry window.
    egonet = disp._challenge_egonet(
        champ, chal_id, 2001,
        [{"Type": 1, "Value": 100}], events, 0, "Fallback",
    )
    assert egonet["IsHardcore"] is False       # hardcore_damage=False
    assert egonet["ExteriorCams"] is False     # force_cockpit_camera=True => no exterior cams

    win = disp._window_for(champ)
    assert win.start == calendar.timegm(datetime(2026, 7, 10, 18, 0, 0).timetuple())
    assert win.end == calendar.timegm(datetime(2026, 7, 16, 18, 0, 0).timetuple())


def test_force_cockpit_inverts_exterior_cams() -> None:
    disp = _dispatcher()
    loc_a, _ = _two_locations_with_routes()
    champ = {
        "id": "evt-x", "name": "X", "car_class": "Group A",
        "settings": {"force_cockpit_camera": True},
        "events": [{"location": loc_a.display_name, "stages": [{}]}],
    }
    events = disp._build_events_for_champ(champ, 200999)
    egonet = disp._challenge_egonet(champ, 200999, 2001,
                                    [{"Type": 1, "Value": 100}], events, 0, "X")
    assert egonet["ExteriorCams"] is False  # cockpit forced => no exterior cams


def test_clubs_from_api_multi_event_full_path() -> None:
    loc_a, loc_b = _two_locations_with_routes()
    ra = get_verified_routes_for_location(int(loc_a))
    rb = get_verified_routes_for_location(int(loc_b))
    champ = {
        "id": "evt-full01",
        "name": "Full Path Champ",
        "club_id": "club-x",
        "car_class": "Group A",
        "start_time": "2026-07-10T18:00:00",
        "end_time": "2026-07-16T18:00:00",
        "settings": {"hardcore_damage": False, "force_cockpit_camera": True,
                     "allow_assists": False, "unexpected_moments": True},
        "events": [
            {"location": loc_a.display_name,
             "stages": [{"track_id": ra[0][0], "conditions_id": 4,
                         "surface_deg": "Max", "service_area": "Medium"}]},
            {"location": loc_b.display_name,
             "stages": [{"track_id": rb[0][0], "conditions_id": 1,
                         "surface_deg": "Low", "service_area": "None"}]},
        ],
    }
    club = [{"id": "club-x", "name": "Club X", "created_by": "me"}]

    # No progress yet: the club serves ONLY event 0, as its own single-event
    # Challenge, and advertises AmountOfEvents=2 / EventIndex=0.
    disp = RpcDispatcher(account_store=MagicMock(),
                         api_client=_FullStubClient(clubs=club, events=[champ]))
    out = disp._clubs_from_api()

    assert out and out["ok"]
    assert len(out["Challenges"]) == 1
    ch = out["Challenges"][0]
    assert ch["Name"] == "Full Path Champ"
    assert len(ch["Events"]) == 1              # ONE event per challenge (not 2 inline)
    assert ch["IsHardcore"] is False
    assert ch["ExteriorCams"] is False         # force cockpit => no exterior cams
    assert ch["AllowAssists"] is False
    assert ch["UnxpectdMoments"] is True
    # The served (active) event is event 0 — loc_a's track.
    assert ch["Events"][0]["Stages"][0]["TrackModelId"].value == ra[0][0]

    assert len(out["Clubs"]) == 1
    club_out = out["Clubs"][0]
    assert club_out["AmountOfEvents"] == 2     # total events in the championship
    assert club_out["EventIndex"] == 0         # currently on event 0
    chal_id_e0 = ch["ChallengeID"]

    # After completing event 0, the club advances to event 1: a DISTINCT
    # ChallengeID, EventIndex=1, now serving loc_b's track.
    progressed = {"events": [{"event_id": "evt-full01",
                              "completed_stages": [{"event_index": 0, "stage_index": 0}]}]}
    disp2 = RpcDispatcher(account_store=MagicMock(),
                          api_client=_FullStubClient(clubs=club, events=[champ],
                                                     my_progress=progressed))
    out2 = disp2._clubs_from_api()
    ch2 = out2["Challenges"][0]
    club2 = out2["Clubs"][0]
    assert club2["AmountOfEvents"] == 2
    assert club2["EventIndex"] == 1                       # advanced to event 1
    assert ch2["ChallengeID"] != chal_id_e0              # distinct per-event challenge
    assert len(ch2["Events"]) == 1
    assert ch2["Events"][0]["Stages"][0]["TrackModelId"].value == rb[0][0]
    # Completing event 0 must NOT mark the now-active event 1 as done: with no
    # stages completed in event 1, it has no Progress entry (stays enterable).
    assert out2["Progress"] == []

    # Finish event 1 too (championship complete): the Progress entry is keyed to
    # the SERVED (last) challenge and is State=2 (finished), so the client shows
    # it complete instead of enterable.
    done = {"events": [{"event_id": "evt-full01", "completed_stages": [
        {"event_index": 0, "stage_index": 0}, {"event_index": 1, "stage_index": 1}]}]}
    disp3 = RpcDispatcher(account_store=MagicMock(),
                          api_client=_FullStubClient(clubs=club, events=[champ],
                                                     my_progress=done))
    out3 = disp3._clubs_from_api()
    served_cid = out3["Challenges"][0]["ChallengeID"]
    assert out3["Clubs"][0]["EventIndex"] == 1            # caps at N-1 when complete
    assert len(out3["Progress"]) == 1
    prog = out3["Progress"][0]
    assert prog["ChallengeID"] == served_cid             # keyed to the SERVED challenge
    assert prog["State"] == 2                             # finished, not enterable


def test_dispatcher_layout_offset_and_total() -> None:
    class _Champ:
        def get_event(self, _eid):
            return {"events": [{"stages": [1, 2]}, {"stages": [3]}, {"stages": [4, 5, 6]}]}

    d = RpcDispatcher(account_store=MagicMock(), api_client=_Champ())
    assert d._champ_layout("x") == [2, 1, 3]
    assert d._stage_offset("x", 0) == 0        # event 0: no offset, no fetch
    assert d._stage_offset("x", 1) == 2
    assert d._stage_offset("x", 2) == 3
    assert d._total_stages_for_event("x") == 6  # championship-wide total

    class _Legacy:
        def get_event(self, _eid):
            return {"stages": [0, 0, 0, 0]}     # no events[] -> single event

    d2 = RpcDispatcher(account_store=MagicMock(), api_client=_Legacy())
    assert d2._total_stages_for_event("x") == 4
    assert d2._stage_offset("x", 0) == 0


def test_legacy_single_event_positional_fallback() -> None:
    disp = _dispatcher()
    loc_a, _ = _two_locations_with_routes()
    track_ids = get_tracks_for_location(int(loc_a))
    # No events[] and no per-stage track_id -> positional assignment, ids unchanged.
    legacy = {
        "id": "evt-legacy",
        "location": loc_a.display_name,
        "car_class": "Group A",
        "stages": [{"conditions": "Clear"}, {"conditions": "Dusk"}],
    }
    events = disp._build_events_for_champ(legacy, 262345)
    assert len(events) == 1
    e0 = events[0]
    assert e0.event_id == 262345
    assert e0.stages[0].track_model_id == track_ids[0]
    assert e0.stages[1].track_model_id == track_ids[1 % len(track_ids)]
    # Legacy service-area fallback alternates by parity.
    assert e0.stages[0].has_service_area is True
    assert e0.stages[1].has_service_area is False
