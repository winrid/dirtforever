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


# ---------------------------------------------------------------------------
# Locations — LocationId maps to a rally region
# ---------------------------------------------------------------------------

class Location(IntEnum):
    """Rally/rallycross location IDs (LocationId in the EgoNet protocol)."""
    MONTE_CARLO  = 1
    SWEDEN       = 2
    WALES        = 3
    ARGENTINA    = 5
    NEW_ENGLAND  = 10
    POLAND       = 13
    NEW_ZEALAND  = 16
    YAS_MARINA   = 19
    MONTALEGRE   = 20
    AUSTRALIA    = 31
    SCOTLAND     = 34
    SPAIN        = 36
    FINLAND      = 37
    GREECE       = 46

    # --- metadata accessors -------------------------------------------------

    @property
    def display_name(self) -> str:
        return _LOCATION_META[self]["display_name"]

    @property
    def country(self) -> str:
        return _LOCATION_META[self]["country"]

    @property
    def discipline(self) -> str:
        return _LOCATION_META[self]["discipline"]

    def __str__(self) -> str:
        return self.display_name


_LOCATION_META: Dict[Location, dict] = {
    Location.MONTE_CARLO: {"display_name": "Monte Carlo",  "country": "Monaco",      "discipline": "rally"},
    Location.SWEDEN:      {"display_name": "Sweden",       "country": "Sweden",      "discipline": "rally"},
    Location.WALES:       {"display_name": "Wales",        "country": "UK",          "discipline": "rally"},
    Location.ARGENTINA:   {"display_name": "Argentina",    "country": "Argentina",   "discipline": "rally"},
    Location.NEW_ENGLAND: {"display_name": "New England",  "country": "USA",         "discipline": "rally"},
    Location.POLAND:      {"display_name": "Poland",       "country": "Poland",      "discipline": "rally"},
    Location.NEW_ZEALAND: {"display_name": "New Zealand",  "country": "New Zealand", "discipline": "rally"},
    Location.YAS_MARINA:  {"display_name": "Yas Marina",   "country": "UAE",         "discipline": "rallycross"},
    Location.MONTALEGRE:  {"display_name": "Montalegre",   "country": "Portugal",    "discipline": "rallycross"},
    Location.AUSTRALIA:   {"display_name": "Australia",    "country": "Australia",   "discipline": "rally"},
    Location.SCOTLAND:    {"display_name": "Scotland",     "country": "UK",          "discipline": "rally"},
    Location.SPAIN:       {"display_name": "Spain",        "country": "Spain",       "discipline": "rally"},
    Location.FINLAND:     {"display_name": "Finland",      "country": "Finland",     "discipline": "rally"},
    Location.GREECE:      {"display_name": "Greece",       "country": "Greece",      "discipline": "rally"},
}


# ---------------------------------------------------------------------------
# Track models — TrackModelId maps to a specific stage route
# ---------------------------------------------------------------------------

class Track(IntEnum):
    """Stage/track route IDs (TrackModelId in the EgoNet protocol)."""

    # New Zealand (Location.NEW_ZEALAND = 16)
    WAIMARAMA_POINT_REV  = 585
    TE_AWANGA            = 586
    WAIMARAMA_POINT      = 587
    ELSTHORPE_SPRINT     = 589
    OCEAN_BEACH          = 590
    OCEAN_BEACH_REV      = 591
    TE_AWANGA_REV        = 592
    WAIMARAMA_LONG       = 595

    # Argentina (Location.ARGENTINA = 5)
    CAMINO_A_LA_PUERTA       = 478
    VALLE_DE_LOS_PUENTES     = 480
    VALLE_DE_LOS_PUENTES_REV = 481

    # Spain (Location.SPAIN = 36)
    CENTENERA       = 610
    RIBADELLES      = 614
    RIBADELLES_REV  = 615

    # Australia (Location.AUSTRALIA = 31)
    ROCKTON_PLAINS          = 566
    ROCKTON_PLAINS_REV      = 567
    YAMBULLA_ASCENT         = 568
    YAMBULLA_DESCENT        = 569
    MONARO                  = 570
    MONARO_REV              = 571

    # Poland (Location.POLAND = 13)
    ZAGORZE      = 442
    ZAGORZE_REV  = 443
    KOPINA       = 446
    KOPINA_REV   = 448

    # USA / New England (Location.NEW_ENGLAND = 10)
    BEAVER_CREEK_TRAIL          = 574
    BEAVER_CREEK_TRAIL_REV      = 575
    HANCOCK_CREEK_BURST         = 576
    HANCOCK_CREEK_BURST_REV     = 577
    FULLER_MOUNTAIN             = 578
    FULLER_MOUNTAIN_REV         = 579
    FURY_LAKE_DEPART            = 580
    FURY_LAKE_DEPART_REV        = 581
    HANCOCK_HILL_SPRINT         = 582
    HANCOCK_HILL_SPRINT_REV     = 583

    # Rallycross — Montalegre (Location.MONTALEGRE = 20)
    MONTALEGRE_FULL    = 537
    MONTALEGRE_JUNIOR  = 538

    # Monte Carlo (Location.MONTE_CARLO = 1)
    GORDOLON_ROQUEBILLIERE  = 462
    COL_DE_TURINI_SPRINT    = 464

    # Wales (Location.WALES = 3)
    SWEET_LAMB       = 496
    GEUFRON_FOREST   = 511
    GEUFRON_FOREST_REV = 512
    PANT_MAWR        = 515
    PANT_MAWR_REV    = 516

    # --- metadata accessors -------------------------------------------------

    @property
    def display_name(self) -> str:
        return _TRACK_META[self]["display_name"]

    @property
    def location(self) -> Location:
        return _TRACK_META[self]["location"]

    @property
    def length_km(self) -> float:
        return _TRACK_META[self]["length_km"]

    @property
    def discipline(self) -> str:
        return _TRACK_META[self].get("discipline", "rally")

    def __str__(self) -> str:
        return self.display_name


_TRACK_META: Dict[Track, dict] = {
    # New Zealand
    Track.WAIMARAMA_POINT_REV:  {"display_name": "Waimarama Point (Reverse)",    "location": Location.NEW_ZEALAND, "length_km": 7.0},
    Track.TE_AWANGA:            {"display_name": "Te Awanga",                     "location": Location.NEW_ZEALAND, "length_km": 7.0},
    Track.WAIMARAMA_POINT:      {"display_name": "Waimarama Point",               "location": Location.NEW_ZEALAND, "length_km": 7.0},
    Track.ELSTHORPE_SPRINT:     {"display_name": "Elsthorpe Sprint",              "location": Location.NEW_ZEALAND, "length_km": 5.0},
    Track.OCEAN_BEACH:          {"display_name": "Ocean Beach",                   "location": Location.NEW_ZEALAND, "length_km": 5.0},
    Track.OCEAN_BEACH_REV:      {"display_name": "Ocean Beach (Reverse)",         "location": Location.NEW_ZEALAND, "length_km": 5.0},
    Track.TE_AWANGA_REV:        {"display_name": "Te Awanga (Reverse)",           "location": Location.NEW_ZEALAND, "length_km": 7.0},
    Track.WAIMARAMA_LONG:       {"display_name": "Waimarama Long",                "location": Location.NEW_ZEALAND, "length_km": 16.0},

    # Argentina
    Track.CAMINO_A_LA_PUERTA:       {"display_name": "Camino a la Puerta",            "location": Location.ARGENTINA, "length_km": 7.5},
    Track.VALLE_DE_LOS_PUENTES:     {"display_name": "Valle de los puentes",          "location": Location.ARGENTINA, "length_km": 7.5},
    Track.VALLE_DE_LOS_PUENTES_REV: {"display_name": "Valle de los puentes (Reverse)","location": Location.ARGENTINA, "length_km": 7.5},

    # Spain
    Track.CENTENERA:      {"display_name": "Centenera",                     "location": Location.SPAIN, "length_km": 7.0},
    Track.RIBADELLES:     {"display_name": "Ribadelles",                    "location": Location.SPAIN, "length_km": 14.0},
    Track.RIBADELLES_REV: {"display_name": "Ribadelles (Reverse)",          "location": Location.SPAIN, "length_km": 14.0},

    # Australia
    Track.ROCKTON_PLAINS:      {"display_name": "Rockton Plains",                "location": Location.AUSTRALIA, "length_km": 7.0},
    Track.ROCKTON_PLAINS_REV:  {"display_name": "Rockton Plains (Reverse)",      "location": Location.AUSTRALIA, "length_km": 7.0},
    Track.YAMBULLA_ASCENT:     {"display_name": "Yambulla Mountain Ascent",      "location": Location.AUSTRALIA, "length_km": 7.0},
    Track.YAMBULLA_DESCENT:    {"display_name": "Yambulla Mountain Descent",     "location": Location.AUSTRALIA, "length_km": 7.0},
    Track.MONARO:              {"display_name": "Monaro",                        "location": Location.AUSTRALIA, "length_km": 12.0},
    Track.MONARO_REV:          {"display_name": "Monaro (Reverse)",              "location": Location.AUSTRALIA, "length_km": 12.0},

    # Poland
    Track.ZAGORZE:     {"display_name": "Zagorze",                       "location": Location.POLAND, "length_km": 7.0},
    Track.ZAGORZE_REV: {"display_name": "Zagorze (Reverse)",             "location": Location.POLAND, "length_km": 7.0},
    Track.KOPINA:      {"display_name": "Kopina",                        "location": Location.POLAND, "length_km": 7.0},
    Track.KOPINA_REV:  {"display_name": "Kopina (Reverse)",              "location": Location.POLAND, "length_km": 7.0},

    # USA / New England
    Track.BEAVER_CREEK_TRAIL:      {"display_name": "Beaver Creek Trail",            "location": Location.NEW_ENGLAND, "length_km": 7.5},
    Track.BEAVER_CREEK_TRAIL_REV:  {"display_name": "Beaver Creek Trail (Reverse)",  "location": Location.NEW_ENGLAND, "length_km": 7.5},
    Track.HANCOCK_CREEK_BURST:     {"display_name": "Hancock Creek Burst",           "location": Location.NEW_ENGLAND, "length_km": 7.5},
    Track.HANCOCK_CREEK_BURST_REV: {"display_name": "Hancock Creek Burst (Reverse)", "location": Location.NEW_ENGLAND, "length_km": 7.5},
    Track.FULLER_MOUNTAIN:         {"display_name": "Fuller Mountain",               "location": Location.NEW_ENGLAND, "length_km": 12.0},
    Track.FULLER_MOUNTAIN_REV:     {"display_name": "Fuller Mountain (Reverse)",     "location": Location.NEW_ENGLAND, "length_km": 12.0},
    Track.FURY_LAKE_DEPART:        {"display_name": "Fury Lake Depart",              "location": Location.NEW_ENGLAND, "length_km": 5.0},
    Track.FURY_LAKE_DEPART_REV:    {"display_name": "Fury Lake Depart (Reverse)",    "location": Location.NEW_ENGLAND, "length_km": 5.0},
    Track.HANCOCK_HILL_SPRINT:     {"display_name": "Hancock Hill Sprint",           "location": Location.NEW_ENGLAND, "length_km": 5.0},
    Track.HANCOCK_HILL_SPRINT_REV: {"display_name": "Hancock Hill Sprint (Reverse)", "location": Location.NEW_ENGLAND, "length_km": 5.0},

    # Rallycross — Montalegre
    Track.MONTALEGRE_FULL:   {"display_name": "Montalegre Full",   "location": Location.MONTALEGRE, "length_km": 1.0, "discipline": "rallycross"},
    Track.MONTALEGRE_JUNIOR: {"display_name": "Montalegre Junior", "location": Location.MONTALEGRE, "length_km": 0.8, "discipline": "rallycross"},

    # Monte Carlo
    Track.GORDOLON_ROQUEBILLIERE: {"display_name": "Gordolon - Roquebillière", "location": Location.MONTE_CARLO, "length_km": 9.8},
    Track.COL_DE_TURINI_SPRINT:   {"display_name": "Col de Turini Sprint",     "location": Location.MONTE_CARLO, "length_km": 5.0},

    # Wales
    Track.SWEET_LAMB:        {"display_name": "Sweet Lamb",                    "location": Location.WALES, "length_km": 9.9},
    Track.GEUFRON_FOREST:    {"display_name": "Geufron Forest",                "location": Location.WALES, "length_km": 5.0},
    Track.GEUFRON_FOREST_REV:{"display_name": "Geufron Forest (Reverse)",      "location": Location.WALES, "length_km": 5.0},
    Track.PANT_MAWR:         {"display_name": "Pant Mawr",                     "location": Location.WALES, "length_km": 5.0},
    Track.PANT_MAWR_REV:     {"display_name": "Pant Mawr (Reverse)",           "location": Location.WALES, "length_km": 5.0},
}


# ---------------------------------------------------------------------------
# Vehicle classes — Requirements.Value maps to a vehicle class
# ---------------------------------------------------------------------------

class VehicleClass(IntEnum):
    """Vehicle class IDs used in challenge Requirements."""
    GROUP_A        = 86
    H1_FWD         = 100
    H2_FWD         = 101
    H2_RWD         = 102
    H3_RWD         = 103
    GROUP_B_RWD    = 104
    GROUP_B_4WD    = 105
    R2             = 106
    F2_KIT_CAR     = 107
    R5             = 108
    RALLY_GT       = 109
    NR4_R4         = 110
    CC_4WD         = 111   # 2000cc 4WD
    # Rallycross classes
    RX_SUPER_1600    = 200
    RX_SUPERCARS     = 201
    RX_SUPERCARS_2019 = 202

    @property
    def label(self) -> str:
        return _VEHICLE_CLASS_LABELS[self]

    def __str__(self) -> str:
        return self.label


_VEHICLE_CLASS_LABELS: Dict[VehicleClass, str] = {
    VehicleClass.GROUP_A:          "Group A",
    VehicleClass.H1_FWD:           "H1 FWD",
    VehicleClass.H2_FWD:           "H2 FWD",
    VehicleClass.H2_RWD:           "H2 RWD",
    VehicleClass.H3_RWD:           "H3 RWD",
    VehicleClass.GROUP_B_RWD:      "Group B RWD",
    VehicleClass.GROUP_B_4WD:      "Group B 4WD",
    VehicleClass.R2:               "R2",
    VehicleClass.F2_KIT_CAR:       "F2 Kit Car",
    VehicleClass.R5:               "R5",
    VehicleClass.RALLY_GT:         "Rally GT",
    VehicleClass.NR4_R4:           "NR4/R4",
    VehicleClass.CC_4WD:           "2000cc 4WD",
    VehicleClass.RX_SUPER_1600:    "RX Super 1600",
    VehicleClass.RX_SUPERCARS:     "RX Supercars",
    VehicleClass.RX_SUPERCARS_2019:"RX Supercars 2019",
}


# ---------------------------------------------------------------------------
# Vehicles — VehicleId maps to car metadata
# ---------------------------------------------------------------------------

class Vehicle(IntEnum):
    """Vehicle IDs (VehicleId in the EgoNet protocol)."""
    # H1 FWD
    LANCIA_FULVIA_HF     = 468
    MINI_COOPER_S        = 469
    CITROEN_DS_21        = 470
    # H2 FWD
    VW_GOLF_GTI_16V      = 471
    # H2 RWD
    FORD_ESCORT_MK2      = 478
    ALPINE_A110_1600S    = 480
    # Group B 4WD
    AUDI_SPORT_QUATTRO_S1_E2 = 513
    MG_METRO_6R4             = 511
    # Group A
    MITSUBISHI_LANCER_EVO6   = 529
    # R5
    CITROEN_C3_R5         = 558
    VW_POLO_R5            = 559
    FORD_FIESTA_R5        = 555
    SKODA_FABIA_R5        = 556
    MITSUBISHI_SPACE_STAR_R5 = 557
    # Rally GT
    PORSCHE_911_RGT       = 547
    ASTON_MARTIN_V8       = 548
    # 2000cc 4WD
    SUBARU_IMPREZA_2001   = 382
    SUBARU_IMPREZA_S4     = 395

    @property
    def display_name(self) -> str:
        return _VEHICLE_META[self]["display_name"]

    @property
    def vehicle_class(self) -> VehicleClass:
        return _VEHICLE_META[self]["vehicle_class"]

    @property
    def abbrev(self) -> str:
        return _VEHICLE_META[self]["abbrev"]

    def __str__(self) -> str:
        return self.display_name


_VEHICLE_META: Dict[Vehicle, dict] = {
    # H1 FWD
    Vehicle.LANCIA_FULVIA_HF:  {"display_name": "Lancia Fulvia HF",        "vehicle_class": VehicleClass.H1_FWD,      "abbrev": "ful"},
    Vehicle.MINI_COOPER_S:     {"display_name": "Mini Cooper S",            "vehicle_class": VehicleClass.H1_FWD,      "abbrev": "mcs"},
    Vehicle.CITROEN_DS_21:     {"display_name": "Citroen DS 21",            "vehicle_class": VehicleClass.H1_FWD,      "abbrev": "cds"},
    # H2 FWD
    Vehicle.VW_GOLF_GTI_16V:   {"display_name": "Volkswagen Golf GTI 16V",  "vehicle_class": VehicleClass.H2_FWD,      "abbrev": "gti"},
    # H2 RWD
    Vehicle.FORD_ESCORT_MK2:   {"display_name": "Ford Escort Mk II",        "vehicle_class": VehicleClass.H2_RWD,      "abbrev": "mr5"},
    Vehicle.ALPINE_A110_1600S: {"display_name": "Alpine A110 1600 S",       "vehicle_class": VehicleClass.H2_RWD,      "abbrev": "alp"},
    # Group B 4WD
    Vehicle.AUDI_SPORT_QUATTRO_S1_E2: {"display_name": "Audi Sport Quattro S1 E2", "vehicle_class": VehicleClass.GROUP_B_4WD, "abbrev": "aqe"},
    Vehicle.MG_METRO_6R4:             {"display_name": "MG Metro 6R4",             "vehicle_class": VehicleClass.GROUP_B_4WD, "abbrev": "6r4"},
    # Group A
    Vehicle.MITSUBISHI_LANCER_EVO6:   {"display_name": "Mitsubishi Lancer Evo VI", "vehicle_class": VehicleClass.GROUP_A,    "abbrev": "ev6"},
    # R5
    Vehicle.CITROEN_C3_R5:        {"display_name": "Citroen C3 R5",            "vehicle_class": VehicleClass.R5, "abbrev": "c3r"},
    Vehicle.VW_POLO_R5:           {"display_name": "Volkswagen Polo R5",       "vehicle_class": VehicleClass.R5, "abbrev": "pr5"},
    Vehicle.FORD_FIESTA_R5:       {"display_name": "Ford Fiesta R5",           "vehicle_class": VehicleClass.R5, "abbrev": "fr5"},
    Vehicle.SKODA_FABIA_R5:       {"display_name": "Skoda Fabia R5",           "vehicle_class": VehicleClass.R5, "abbrev": "sr5"},
    Vehicle.MITSUBISHI_SPACE_STAR_R5: {"display_name": "Mitsubishi Space Star R5", "vehicle_class": VehicleClass.R5, "abbrev": "msr"},
    # Rally GT
    Vehicle.PORSCHE_911_RGT:  {"display_name": "Porsche 911 RGT Rally",    "vehicle_class": VehicleClass.RALLY_GT, "abbrev": "99r"},
    Vehicle.ASTON_MARTIN_V8:  {"display_name": "Aston Martin V8 Vantage",  "vehicle_class": VehicleClass.RALLY_GT, "abbrev": "amr"},
    # 2000cc 4WD
    Vehicle.SUBARU_IMPREZA_2001: {"display_name": "Subaru Impreza 2001",      "vehicle_class": VehicleClass.CC_4WD, "abbrev": "srs"},
    Vehicle.SUBARU_IMPREZA_S4:   {"display_name": "Subaru Impreza S4 Rally",  "vehicle_class": VehicleClass.CC_4WD, "abbrev": "srs_05"},
}


# ---------------------------------------------------------------------------
# Discipline types
# ---------------------------------------------------------------------------

class Discipline(IntEnum):
    """Discipline IDs used in challenge/event definitions."""
    RALLY       = 1
    RALLYCROSS  = 2

    @property
    def label(self) -> str:
        return _DISCIPLINE_LABELS[self]

    def __str__(self) -> str:
        return self.label


_DISCIPLINE_LABELS: Dict[Discipline, str] = {
    Discipline.RALLY:      "Rally",
    Discipline.RALLYCROSS: "Rallycross",
}


# ---------------------------------------------------------------------------
# Weather presets
# ---------------------------------------------------------------------------

class WeatherPreset(IntEnum):
    """WeatherPresetId values for stage definitions."""
    CLEAR_OVERCAST = 1
    HEAVY_CLOUD    = 2
    LIGHT_RAIN     = 3
    HEAVY_RAIN     = 4

    @property
    def label(self) -> str:
        return _WEATHER_LABELS[self]

    def __str__(self) -> str:
        return self.label


_WEATHER_LABELS: Dict[WeatherPreset, str] = {
    WeatherPreset.CLEAR_OVERCAST: "Clear / Overcast",
    WeatherPreset.HEAVY_CLOUD:    "Heavy Cloud",
    WeatherPreset.LIGHT_RAIN:     "Light Rain",
    WeatherPreset.HEAVY_RAIN:     "Heavy Rain",
}


# ---------------------------------------------------------------------------
# Time of day
# ---------------------------------------------------------------------------

class TimeOfDay(IntEnum):
    """TimeOfDayId values for stage definitions."""
    DAYTIME   = 1
    DUSK_DAWN = 2
    NIGHT     = 3
    MIDDAY    = 4

    @property
    def label(self) -> str:
        return _TIME_OF_DAY_LABELS[self]

    def __str__(self) -> str:
        return self.label


_TIME_OF_DAY_LABELS: Dict[TimeOfDay, str] = {
    TimeOfDay.DAYTIME:   "Daytime",
    TimeOfDay.DUSK_DAWN: "Dusk / Dawn",
    TimeOfDay.NIGHT:     "Night",
    TimeOfDay.MIDDAY:    "Midday",
}


# ---------------------------------------------------------------------------
# Surface conditions
# ---------------------------------------------------------------------------

class SurfaceCondition(IntEnum):
    """SurfaceCondId / StageConditions values for stage definitions."""
    DRY  = 1
    WET  = 16
    DAMP = 38

    @property
    def label(self) -> str:
        return _SURFACE_LABELS[self]

    def __str__(self) -> str:
        return self.label


_SURFACE_LABELS: Dict[SurfaceCondition, str] = {
    SurfaceCondition.DRY:  "Dry",
    SurfaceCondition.WET:  "Wet",
    SurfaceCondition.DAMP: "Damp",
}


# ---------------------------------------------------------------------------
# Race status codes (from StageComplete.RaceStatus)
# ---------------------------------------------------------------------------

class RaceStatus(IntEnum):
    """RaceStatus codes returned in StageComplete requests."""
    UNKNOWN  = 0
    FINISHED = 1
    DNF      = 2
    RETIRED  = 5

    @property
    def label(self) -> str:
        return _RACE_STATUS_LABELS[self]

    def __str__(self) -> str:
        return self.label


_RACE_STATUS_LABELS: Dict[RaceStatus, str] = {
    RaceStatus.UNKNOWN:  "Unknown",
    RaceStatus.FINISHED: "Finished",
    RaceStatus.DNF:      "DNF",
    RaceStatus.RETIRED:  "Retired",
}


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

WEATHER_PRESETS: Dict[int, str] = {int(w): w.label for w in WeatherPreset}

TIME_OF_DAY: Dict[int, str] = {int(t): t.label for t in TimeOfDay}

SURFACE_CONDITIONS: Dict[int, str] = {int(s): s.label for s in SurfaceCondition}

RACE_STATUS: Dict[int, str] = {int(r): r.label for r in RaceStatus}


# ---------------------------------------------------------------------------
# Helpers — same signatures as before; now implemented via enums
# ---------------------------------------------------------------------------

def get_tracks_for_location(location_id: int) -> List[int]:
    """Return all known TrackModelIds (as ints) for a given LocationId."""
    loc = Location(location_id)
    return [int(t) for t in Track if _TRACK_META[t]["location"] == loc]


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
