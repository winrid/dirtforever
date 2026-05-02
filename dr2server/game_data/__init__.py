"""Game content ID mappings for DiRT Rally 2.0.

These IDs are used in the EgoNet protocol to reference game content.
Sourced from upstream proxy captures and community documentation.

LocationId and TrackModelId are the key IDs needed to define club events.
The game renders everything client-side — the server just tells it which
location/track/conditions to load.

All plain dicts have been replaced with IntEnum classes so IDs are usable
directly as integers while still carrying human-readable metadata.

Usage examples::

    from dr2server.game_data import Location, Track, VehicleClass

    Location.NEW_ZEALAND          # <Location.NEW_ZEALAND: 16>
    int(Location.NEW_ZEALAND)     # 16
    Location.NEW_ZEALAND.display_name   # "New Zealand"
    Location.NEW_ZEALAND.country        # "New Zealand"
    Location.NEW_ZEALAND.discipline     # "rally"

    Track.OCEAN_BEACH             # <Track.OCEAN_BEACH: 590>
    Track.OCEAN_BEACH.display_name      # "Ocean Beach"
    Track.OCEAN_BEACH.location          # <Location.NEW_ZEALAND: 16>
    Track.OCEAN_BEACH.length_km         # 5.0

    VehicleClass.R5.label               # "R5"
"""

from __future__ import annotations

from enum import IntEnum
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Simple label mixin — used for enums whose metadata is a single string label.
# ---------------------------------------------------------------------------

class _LabelMixin(IntEnum):
    """IntEnum extended with a ``label`` property backed by a class-level dict."""

    @property
    def label(self) -> str:  # type: ignore[override]
        return self.__class__._labels[self]  # type: ignore[attr-defined]

    def __str__(self) -> str:
        return self.label



from .location import Location, _LOCATION_META
from .track import Track, _TRACK_META
from .vehicle_class import VehicleClass, _VEHICLE_CLASS_LABELS
from .vehicle import Vehicle, _VEHICLE_META
from .discipline import Discipline, _DISCIPLINE_LABELS
from .stage_conditions import (
    SurfaceType, _SURFACE_TYPE_LABELS,
    PrecipitationType, _PRECIPITATION_LABELS,
    TimeOfDayBucket, _TIME_OF_DAY_LABELS, TimeOfDay,
    WeatherBucket, _WEATHER_LABELS, WeatherPreset,
    STAGE_CONDITIONS_LABELS, stage_conditions_label,
    OBSERVED_STAGE_CONDITIONS, decode_stage_conditions,
)


from .time_trial import TimeTrialCategory
from .race_status import RaceStatus, _RACE_STATUS_LABELS


# ---------------------------------------------------------------------------
# Backward-compatible plain-dict aliases
# ---------------------------------------------------------------------------
# These preserve compatibility with any code that still accesses the old dicts
# by integer key.  New code should use the enums directly.

LOCATIONS: Dict[int, dict] = {
    loc: _LOCATION_META[loc]
    for loc in Location
}

TRACKS: Dict[int, dict] = {
    int(t): {
        "name":        _TRACK_META[t]["display_name"],
        "location_id": int(_TRACK_META[t]["location"]),
        "length_km":   _TRACK_META[t]["length_km"],
        **( {"discipline": _TRACK_META[t]["discipline"]} if "discipline" in _TRACK_META[t] else {} ),
    }
    for t in Track
}

VEHICLE_CLASSES: Dict[int, str] = {
    int(vc): vc.label for vc in VehicleClass
}

VEHICLES: Dict[int, dict] = {
    int(v): {
        "name":   _VEHICLE_META[v]["display_name"],
        "class":  int(_VEHICLE_META[v]["vehicle_class"]),
        "abbrev": _VEHICLE_META[v]["abbrev"],
    }
    for v in Vehicle
}

DISCIPLINES: Dict[int, str] = {int(d): d.label for d in Discipline}

WEATHER_PRESETS: Dict[int, str] = {int(w): w.label for w in WeatherBucket}

TIME_OF_DAY: Dict[int, str] = {int(t): t.label for t in TimeOfDayBucket}

SURFACE_TYPES: Dict[int, str] = {int(s): s.label for s in SurfaceType}

PRECIPITATION_TYPES: Dict[int, str] = {int(p): p.label for p in PrecipitationType}

RACE_STATUS: Dict[int, str] = {int(r): r.label for r in RaceStatus}


# ---------------------------------------------------------------------------
# Track verification and helpers
# ---------------------------------------------------------------------------

from .helpers import (
    VERIFIED_TRACK_IDS, is_track_verified,
    get_tracks_for_location, get_vehicles_for_class,
    get_rally_locations, get_rallycross_locations,
)
