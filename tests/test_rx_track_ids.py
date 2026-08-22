"""The rallycross circuit TrackModelIds are pinned to what the game sends.

PR #19 replaced three discovery-verified ids with values from an unrelated id
space, and nothing caught it: the enum stayed self-consistent and the game
silently served the wrong (or no) circuit.  These pin the enum, and the
verified-route allow-list, to the ids captured in-game on 2026-08-22
(data/verified/rx_track_ids.json) so a future edit has to change the captured
evidence too.
"""
from __future__ import annotations

import json
from pathlib import Path

from dr2server.game_data import (
    Location, Track, VERIFIED_TRACK_IDS, get_tracks_for_location,
)

GROUND_TRUTH = Path(__file__).resolve().parents[1] / "data" / "verified" / "rx_track_ids.json"


def _captured() -> dict[str, dict]:
    return json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))["circuits"]


def test_every_rallycross_circuit_was_captured() -> None:
    rx_locations = {loc.name for loc in Location if loc.discipline == "rallycross"}
    assert set(_captured()) == rx_locations


def test_track_enum_matches_captured_ids() -> None:
    for name, rec in _captured().items():
        assert int(Track[name]) == rec["track_model_id"], name
        assert int(Track[name].location) == rec["location_id"], name


def test_captured_ids_are_served_as_verified_routes() -> None:
    for name, rec in _captured().items():
        assert rec["track_model_id"] in VERIFIED_TRACK_IDS, name
        # One circuit per venue: the dispatcher must resolve exactly this id.
        assert get_tracks_for_location(rec["location_id"]) == [rec["track_model_id"]], name


def test_rallycross_ids_do_not_collide_with_rally_routes() -> None:
    rx_ids = {rec["track_model_id"] for rec in _captured().values()}
    rally_ids = {int(t) for t in Track if t.discipline != "rallycross"}
    assert not (rx_ids & rally_ids)
