"""Guards for car-class label resolution.

The web UI offered the label "2000cc", which the game server's resolver didn't
recognise.  A club event with that class was then built with an empty/invalid
Requirement, which crashes the game client.  These tests lock in that every
web-facing label resolves to a confirmed class, and that unknown labels resolve
to None (so callers skip the event rather than guess a fallback class).
"""
from __future__ import annotations

from dr2server.game_data import (
    CONFIRMED_VEHICLE_CLASS_IDS,
    VehicleClass,
    vehicle_class_id_for_label,
)

# The exact labels the web "Create Event" dropdown offers (web/server.py CAR_CLASSES).
WEB_CAR_CLASS_LABELS = [
    "Group A", "Group B (4WD)", "Group B (RWD)", "R5", "NR4/R4",
    "H2 (RWD)", "Rally GT", "F2 Kit Car", "2000cc",
]


def test_every_web_label_resolves_to_a_confirmed_class() -> None:
    for label in WEB_CAR_CLASS_LABELS:
        vclass_id = vehicle_class_id_for_label(label)
        assert vclass_id is not None, f"web label {label!r} resolves to None"
        assert vclass_id in CONFIRMED_VEHICLE_CLASS_IDS, (
            f"web label {label!r} -> {vclass_id} not in confirmed set"
        )


def test_2000cc_maps_to_2000cc_4wd() -> None:
    # The regression: "2000cc" used to resolve to None and crash the game.
    assert vehicle_class_id_for_label("2000cc") == int(VehicleClass.CC_4WD)


def test_unknown_label_resolves_to_none_not_a_fallback() -> None:
    assert vehicle_class_id_for_label("Banana Cars") is None
    assert vehicle_class_id_for_label("") is None


def test_confirmed_set_tracks_the_enum() -> None:
    # The dispatcher derives "confirmed" from the enum so it can't go stale.
    assert CONFIRMED_VEHICLE_CLASS_IDS == frozenset(int(vc) for vc in VehicleClass)
    # Spot-check classes that a hard-coded list had previously omitted.
    assert int(VehicleClass.RGT) in CONFIRMED_VEHICLE_CLASS_IDS
    assert int(VehicleClass.RX_SUPERCARS_2019) in CONFIRMED_VEHICLE_CLASS_IDS
