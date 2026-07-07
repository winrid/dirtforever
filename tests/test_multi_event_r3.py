"""Ground-truth spec test for the RaceNet multi-event championship model.

Backed by a sanitized reference capture of a real 2-event club championship
(tests/fixtures/captures/multi-event-r3/r3_reference.json, captured against
upstream 2026-07-07).  These assertions pin the behaviour the server must
reproduce; see notes/protocol_notes.md -> "Club Championships — Multi-Event
Model".  Pure data assertions, so this runs without the web app.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURE = (Path(__file__).parent / "fixtures" / "captures" / "multi-event-r3"
           / "r3_reference.json")


@pytest.fixture(scope="module")
def ref():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _state(ref, label):
    return next(s for s in ref["club_states"] if s["label"] == label)


def test_amount_of_events_constant_across_progression(ref):
    """The club advertises the total event count; it never changes as you play."""
    e1 = _state(ref, "event1_active")
    e2 = _state(ref, "event2_active")
    assert e1["club"]["AmountOfEvents"] == 2
    assert e2["club"]["AmountOfEvents"] == 2


def test_event_index_advances_on_completion(ref):
    """Finishing event 1 advances the club's EventIndex 0 -> 1 (server-driven)."""
    assert _state(ref, "event1_active")["club"]["EventIndex"] == 0
    assert _state(ref, "event2_active")["club"]["EventIndex"] == 1


def test_only_active_event_is_served_as_own_challenge(ref):
    """Each event is served as its OWN single-event Challenge, one at a time —
    never one Challenge holding multiple events."""
    for st in ref["club_states"]:
        assert st["challenge"]["num_events_in_challenge"] == 1
    e1, e2 = _state(ref, "event1_active"), _state(ref, "event2_active")
    # Distinct ChallengeID and EventId per event.
    assert e1["challenge"]["ChallengeID"] != e2["challenge"]["ChallengeID"]
    assert e1["event"]["EventId"] != e2["event"]["EventId"]


def test_event_windows_are_back_to_back(ref):
    """Event k+1's entry window opens exactly when event k's closes."""
    e1, e2 = _state(ref, "event1_active"), _state(ref, "event2_active")
    assert e2["challenge"]["EntryWindow"]["Start"] == e1["challenge"]["EntryWindow"]["End"]


def test_stage_requests_carry_no_championship_index(ref):
    """StageBegin/StageComplete always report EventIndex=0 — the active event is
    identified by ChallengeId, not by a game-supplied championship index."""
    assert ref["stage_requests"], "expected stage lifecycle requests in fixture"
    for req in ref["stage_requests"]:
        assert req["EventIndex"] == 0, req
        assert req["StageIndex"] == 0, req
    # The two events are distinguished purely by ChallengeId.
    begins = [r for r in ref["stage_requests"] if r["fn"].endswith("StageBegin")]
    assert {r["ChallengeId"] for r in begins} == {946876, 946877}


def test_telemetry_sees_each_event_as_standalone(ref):
    """Per-drive telemetry reports event_count=1/event_index=0 for every event —
    the client never sees the championship-relative position."""
    staged = [t for t in ref["telemetry"] if t["event"] == "StageEnded"]
    assert staged, "expected a StageEnded telemetry record"
    for t in staged:
        assert t["event_index"] == 0
        assert t["event_count"] == 1
        assert t["stage_index"] == 0
        assert t["stage_count"] == 1
