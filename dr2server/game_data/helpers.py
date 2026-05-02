"""Helper functions and track verification data for DiRT Rally 2.0 game data."""

from __future__ import annotations

from typing import List

from .location import Location, _LOCATION_META
from .track import Track, _TRACK_META
from .vehicle import Vehicle, _VEHICLE_META
from .vehicle_class import VehicleClass


# ---------------------------------------------------------------------------
# Track verification
# ---------------------------------------------------------------------------
# Every entry in this set has been confirmed in-game on 2026-04-11 via the
# automated enum-mapping discovery round: the server served a probe event
# with the given TrackModelId, and the stage name shown on the Event Details
# panel matched the stage recorded in runtime/discovery/track_mapping.json.
#
# Add a track id to this set only after confirming in-game that the stage
# loading screen matches its assigned location and display name.

VERIFIED_TRACK_IDS: set[int] = {
    437, 439, 441, 442, 443, 446, 448, 462, 464, 467, 469, 472,
    478, 480, 490, 496, 511, 512, 515, 516, 519, 520, 527, 528,
    537, 538, 566, 568, 569, 570, 571, 572, 573, 574, 575, 576,
    577, 578, 579, 580, 581, 582, 583, 584, 585, 586, 587, 588,
    589, 590, 591, 592, 593, 594, 595, 596, 597, 598, 599, 600,
    601, 602, 603, 604, 605, 606, 607, 608, 609, 610, 611, 612,
    613, 614, 615, 616, 617, 620, 621, 622, 623, 624, 625, 626,
    627, 628, 629, 630, 631, 632, 633, 634, 635, 636, 637, 659,
    661, 663, 667,
}


def is_track_verified(track_id: int) -> bool:
    return int(track_id) in VERIFIED_TRACK_IDS


# ---------------------------------------------------------------------------
# Helpers — same signatures as before; now implemented via enums
# ---------------------------------------------------------------------------

def get_tracks_for_location(location_id: int) -> List[int]:
    """Return verified TrackModelIds (as ints) for a given LocationId.

    Only tracks in ``VERIFIED_TRACK_IDS`` are returned.  Returning an
    unverified track to the game client causes the wrong stage to load
    (different location from what the user picked), so unverified tracks
    are filtered out.  Callers should treat an empty list as "we don't
    have a known-good stage for this location yet".
    """
    loc = Location(location_id)
    return [
        int(t) for t in Track
        if _TRACK_META[t]["location"] == loc and int(t) in VERIFIED_TRACK_IDS
    ]


def get_vehicles_for_class(class_id: int) -> List[int]:
    """Return all known VehicleIds (as ints) for a given vehicle class."""
    vc = VehicleClass(class_id)
    return [int(v) for v in Vehicle if _VEHICLE_META[v]["vehicle_class"] == vc]


def get_rally_locations() -> List[int]:
    """Return all rally (non-rallycross) location IDs as ints."""
    return [int(loc) for loc in Location if _LOCATION_META[loc]["discipline"] == "rally"]


def get_rallycross_locations() -> List[int]:
    """Return all rallycross location IDs as ints."""
    return [int(loc) for loc in Location if _LOCATION_META[loc]["discipline"] == "rallycross"]
