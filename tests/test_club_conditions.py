"""Web club-event conditions must map to verified StageConditions ints.

Regression test for club events ignoring the chosen weather: the dispatcher
used to build Stages without passing stage_conditions, so every club event
loaded as the default "Daytime / Clear / Dry" regardless of the form choice.
"""
from __future__ import annotations

from dr2server.game_data import (
    STAGE_CONDITIONS_LABELS,
    WEB_CONDITIONS_TO_STAGE_CONDITIONS,
    stage_conditions_for_web,
)

# The labels offered by the web club-event form (web/server.py CONDITIONS).
WEB_CONDITIONS = ["Clear", "Overcast", "Light Rain", "Heavy Rain", "Dusk", "Night"]


def test_every_web_condition_is_mapped() -> None:
    for label in WEB_CONDITIONS:
        assert label in WEB_CONDITIONS_TO_STAGE_CONDITIONS, (
            f"web condition {label!r} has no StageConditions mapping"
        )


def test_mapped_values_are_all_verified() -> None:
    # Unverified StageConditions ints can crash the game client, so every
    # mapped value must come from the in-game-verified label table.
    for label, sc in WEB_CONDITIONS_TO_STAGE_CONDITIONS.items():
        assert sc in STAGE_CONDITIONS_LABELS, (
            f"{label!r} -> {sc} is not a verified StageConditions value"
        )


def test_wet_conditions_map_to_wet() -> None:
    for label in ("Light Rain", "Heavy Rain"):
        sc = stage_conditions_for_web(label)
        assert "Wet" in STAGE_CONDITIONS_LABELS[sc], (
            f"{label!r} -> {sc} ({STAGE_CONDITIONS_LABELS[sc]}) is not Wet"
        )


def test_clear_maps_to_dry() -> None:
    assert stage_conditions_for_web("Clear") == 1
    assert STAGE_CONDITIONS_LABELS[1] == "Daytime / Clear / Dry"


def test_unknown_label_falls_back_to_clear_dry() -> None:
    assert stage_conditions_for_web("") == 1
    assert stage_conditions_for_web("Hurricane") == 1
