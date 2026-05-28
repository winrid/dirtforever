"""Web club-event conditions must map to verified StageConditions ints.

Regression test for club events ignoring the chosen weather: the dispatcher
used to build Stages without passing stage_conditions, so every club event
loaded as the default "Daytime / Clear / Dry" regardless of the form choice.
"""
from __future__ import annotations

from dr2server.game_data import (
    STAGE_CONDITIONS_LABELS,
    WEB_CONDITIONS_TO_STAGE_LABEL,
    stage_conditions_for_web,
)

# The labels offered by the web club-event form (web/server.py CONDITIONS).
WEB_CONDITIONS = ["Clear", "Overcast", "Light Rain", "Heavy Rain", "Dusk", "Night"]


def test_every_web_condition_is_mapped() -> None:
    for label in WEB_CONDITIONS:
        assert label in WEB_CONDITIONS_TO_STAGE_LABEL, (
            f"web condition {label!r} has no StageConditions mapping"
        )


def test_mapped_labels_are_all_verified() -> None:
    # Unverified StageConditions can crash the game client, so every target
    # label must exist in the in-game-verified table (and thus resolve to an id).
    verified_labels = set(STAGE_CONDITIONS_LABELS.values())
    for web_label, stage_label in WEB_CONDITIONS_TO_STAGE_LABEL.items():
        assert stage_label in verified_labels, (
            f"{web_label!r} -> {stage_label!r} is not a verified StageConditions label"
        )
        assert stage_conditions_for_web(web_label) in STAGE_CONDITIONS_LABELS


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
