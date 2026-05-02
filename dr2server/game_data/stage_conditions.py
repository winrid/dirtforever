"""Stage conditions ID mappings for DiRT Rally 2.0.

Decoded from the game catalogue's four enum dimensions.

The game's stage-data struct exposes four separate fields alongside the
composite StageConditions id:

  StageConditions (composite index, see decode_stage_conditions below)
  WeatherPresetId (index into WeatherBucket)
  TimeOfDayId     (index into TimeOfDayBucket)
  SurfaceCondId   (index into SurfaceType)

The individual dimension enums below come from the game catalogue strings:
  GAME__CATALOGUE__SECTION__SURFACE_TYPE__{gravel,tarmac,snow,ice}
  GAME__CATALOGUE__SECTION__PRECIPITATION_TYPE__{NoPrecipitation,Rain,Snow}
and from frontend/configs/environment_image_mapping.xml, which collapses
the raw time-of-day / weather variants into six buckets each.

The specific integer IDs for these enums are server-assigned and not known
yet — the member values below are ordinal placeholders that will be pinned
during the manual-testing pass.  Upstream club captures always have
(WeatherPresetId, TimeOfDayId, SurfaceCondId) = (1, 4, 1), i.e. clear /
midday / gravel — confirmed by user saying ConditionsId=1 shows
"Daytime / Clear / Dry Surface".
"""

from __future__ import annotations

from enum import IntEnum
from typing import Any, Dict, List


class SurfaceType(IntEnum):
    """Terrain surface type (SurfaceCondId in stage data).

    Catalogue: GAME__CATALOGUE__SECTION__SURFACE_TYPE__*
    """
    GRAVEL = 1  # confirmed: upstream club data always uses 1
    TARMAC = 2  # unconfirmed ordinal
    SNOW   = 3  # unconfirmed ordinal
    ICE    = 4  # unconfirmed ordinal

    @property
    def label(self) -> str:
        return _SURFACE_TYPE_LABELS[self]

    def __str__(self) -> str:
        return self.label


_SURFACE_TYPE_LABELS: Dict[SurfaceType, str] = {
    SurfaceType.GRAVEL: "Gravel",
    SurfaceType.TARMAC: "Tarmac",
    SurfaceType.SNOW:   "Snow",
    SurfaceType.ICE:    "Ice",
}


class PrecipitationType(IntEnum):
    """Precipitation state for a stage.

    Catalogue: GAME__CATALOGUE__SECTION__PRECIPITATION_TYPE__*
    """
    NONE = 1  # unconfirmed ordinal
    RAIN = 2
    SNOW = 3

    @property
    def label(self) -> str:
        return _PRECIPITATION_LABELS[self]

    def __str__(self) -> str:
        return self.label


_PRECIPITATION_LABELS: Dict[PrecipitationType, str] = {
    PrecipitationType.NONE: "None",
    PrecipitationType.RAIN: "Rain",
    PrecipitationType.SNOW: "Snow",
}


class TimeOfDayBucket(IntEnum):
    """TimeOfDayId after environment_image_mapping.xml collapses variants.

    Raw variants in lighting filenames: civildawn, dawn, earlymorning, morning,
    midday, earlyafternoon, lateafternoon, sunset, twilight, night.  These map
    down to the six buckets below.
    """
    DAWN     = 1  # unconfirmed
    MORNING  = 2
    MIDDAY   = 4  # confirmed from upstream: TimeOfDayId=4 in all captured stages
    SUNSET   = 5
    TWILIGHT = 6
    NIGHT    = 7

    @property
    def label(self) -> str:
        return _TIME_OF_DAY_LABELS[self]

    def __str__(self) -> str:
        return self.label


_TIME_OF_DAY_LABELS: Dict[TimeOfDayBucket, str] = {
    TimeOfDayBucket.DAWN:     "Dawn",
    TimeOfDayBucket.MORNING:  "Morning",
    TimeOfDayBucket.MIDDAY:   "Midday",
    TimeOfDayBucket.SUNSET:   "Sunset",
    TimeOfDayBucket.TWILIGHT: "Twilight",
    TimeOfDayBucket.NIGHT:    "Night",
}

# Back-compat alias for code still importing the old name.
TimeOfDay = TimeOfDayBucket


class WeatherBucket(IntEnum):
    """WeatherPresetId after environment_image_mapping.xml collapses variants.

    Raw variants: clear, cloud_overcast, cloud_partly_cloudy, cloudy, fog,
    fog_mist, fog_patches, rain_*, snow_*.  Mapped to six buckets below.
    """
    CLEAR    = 1  # confirmed from upstream: WeatherPresetId=1 in all captured stages
    OVERCAST = 2  # unconfirmed
    CLOUDY   = 3
    MIST     = 4
    RAIN     = 5
    SNOW     = 6

    @property
    def label(self) -> str:
        return _WEATHER_LABELS[self]

    def __str__(self) -> str:
        return self.label


_WEATHER_LABELS: Dict[WeatherBucket, str] = {
    WeatherBucket.CLEAR:    "Clear",
    WeatherBucket.OVERCAST: "Overcast",
    WeatherBucket.CLOUDY:   "Cloudy",
    WeatherBucket.MIST:     "Mist",
    WeatherBucket.RAIN:     "Rain",
    WeatherBucket.SNOW:     "Snow",
}

# Back-compat alias.
WeatherPreset = WeatherBucket


# ---------------------------------------------------------------------------
# StageConditions composite-ID labels (verified in-game 2026-04-11)
# ---------------------------------------------------------------------------
# Earlier notes hypothesised a packed-nibble encoding (high=surface,
# low=preset) but the in-game discovery round REJECTED that theory.  Example:
# SC=9 has high nibble 0 but is "Wet"; SC=16 has high nibble 1 but is "Dry".
# The integer is an arbitrary index into a table the game maintains
# internally.  Every StageConditions value observed in upstream club data has
# been pinned below by probing it in-game on Spain / Descenso and OCR'ing
# the Event Details panel.

STAGE_CONDITIONS_LABELS: Dict[int, str] = {
    1:  "Daytime / Clear / Dry",
    3:  "Night / Clear / Dry",
    4:  "Dusk / Cloudy / Dry",
    5:  "Dusk / Overcast / Dry",
    9:  "Daytime / Heavy Rain / Wet",
    11: "Daytime / Cloudy / Wet",
    16: "Sunset / Cloudy / Dry",
    17: "Sunset / Overcast / Dry",
    20: "Sunset / Cloudy / Wet",
    26: "Daytime / Showers / Wet",
    35: "Sunset / Light Showers / Wet",
    38: "Daytime / Overcast / Dry",
    39: "Sunset / Light Rain / Wet",
    40: "Dusk / Showers / Wet",
    42: "Sunset / Cloudy / Dry",   # matches SC=16 in our OCR — needs re-probe
    47: "Sunset / Clear / Dry",
}


def stage_conditions_label(value: int) -> str:
    """Return the human-readable label for a StageConditions / ConditionsId.

    Falls back to ``"Conditions #N"`` for unknown values so the web leaderboard
    can display something until the ID is mapped in-game.
    """
    return STAGE_CONDITIONS_LABELS.get(int(value), f"Conditions #{int(value)}")


# StageConditions integer values observed in the wild (upstream club data +
# time-trial captures).  Kept as a sorted list for UI dropdowns.
OBSERVED_STAGE_CONDITIONS: List[int] = sorted(STAGE_CONDITIONS_LABELS.keys())


def decode_stage_conditions(value: int) -> Dict[str, Any]:
    """Backwards-compatible shim used by scripts/watch_testing.py.

    Returns a dict describing the stage-conditions integer using the verified
    STAGE_CONDITIONS_LABELS table.  The old packed-nibble fields are kept for
    compatibility but are no longer authoritative.
    """
    return {
        "label":             stage_conditions_label(value),
        "surface_state_int": (value >> 4) & 0xF,
        "preset_index":      value & 0xF,
    }
