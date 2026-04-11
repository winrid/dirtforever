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
    """Rally/rallycross location IDs (LocationId in the EgoNet protocol).

    Verified by in-game testing — map names are from the stage loading screen.
    """
    GREECE          = 2   # Greece rally
    WALES           = 3   # Wales rally
    GERMANY         = 5   # Germany rally
    LYDDEN_HILL     = 9   # Lydden Hill RX (England)
    HELL            = 10  # Hell RX (Norway)
    FINLAND         = 13  # Finland rally
    SWEDEN          = 14  # Sweden rally
    AUSTRALIA       = 16  # Australia rally
    ARGENTINA       = 17  # Argentina rally
    LOHEAC          = 18  # Loheac RX (France)
    MONTALEGRE      = 19  # Montalegre RX (Portugal)
    BARCELONA       = 20  # Barcelona RX (Spain)
    SPAIN           = 31  # Spain rally (Ribadelles)
    NEW_ZEALAND     = 34  # New Zealand rally
    POLAND          = 36  # Poland rally
    NEW_ENGLAND     = 37  # New England rally (USA)
    SILVERSTONE     = 38  # Silverstone RX (England)
    SCOTLAND        = 46  # Scotland rally

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
    Location.GREECE:      {"display_name": "Greece",         "country": "Greece",      "discipline": "rally"},
    Location.WALES:       {"display_name": "Wales",          "country": "UK",          "discipline": "rally"},
    Location.GERMANY:     {"display_name": "Germany",        "country": "Germany",     "discipline": "rally"},
    Location.LYDDEN_HILL: {"display_name": "Lydden Hill",    "country": "England",     "discipline": "rallycross"},
    Location.HELL:        {"display_name": "Hell",           "country": "Norway",      "discipline": "rallycross"},
    Location.FINLAND:     {"display_name": "Finland",        "country": "Finland",     "discipline": "rally"},
    Location.SWEDEN:      {"display_name": "Sweden",         "country": "Sweden",      "discipline": "rally"},
    Location.AUSTRALIA:   {"display_name": "Australia",      "country": "Australia",   "discipline": "rally"},
    Location.ARGENTINA:   {"display_name": "Argentina",      "country": "Argentina",   "discipline": "rally"},
    Location.LOHEAC:      {"display_name": "Loheac",         "country": "France",      "discipline": "rallycross"},
    Location.MONTALEGRE:  {"display_name": "Montalegre",     "country": "Portugal",    "discipline": "rallycross"},
    Location.BARCELONA:   {"display_name": "Barcelona",      "country": "Spain",       "discipline": "rallycross"},
    Location.SPAIN:       {"display_name": "Spain",          "country": "Spain",       "discipline": "rally"},
    Location.NEW_ZEALAND: {"display_name": "New Zealand",    "country": "New Zealand", "discipline": "rally"},
    Location.POLAND:      {"display_name": "Poland",         "country": "Poland",      "discipline": "rally"},
    Location.NEW_ENGLAND: {"display_name": "New England",    "country": "USA",         "discipline": "rally"},
    Location.SILVERSTONE: {"display_name": "Silverstone",    "country": "England",     "discipline": "rallycross"},
    Location.SCOTLAND:    {"display_name": "Scotland",       "country": "UK",          "discipline": "rally"},
}


# ---------------------------------------------------------------------------
# Track models — TrackModelId maps to a specific stage route
# ---------------------------------------------------------------------------
#
# ID assignments come from upstream challenge data (authoritative).
# Stage names come from community documentation where the ID count
# matches the expected 12 (6 routes × forward + reverse); otherwise
# generic names are used (Stage N / Stage N (Reverse)).
#
# Locations without confirmed track IDs (Monte Carlo) have no Track entries.

class Track(IntEnum):
    """Stage/track route IDs (TrackModelId in the EgoNet protocol)."""

    # Sweden (Location.SWEDEN = 2) — 4 IDs, generic names
    SWEDEN_STAGE_1        = 462
    SWEDEN_STAGE_1_REV    = 464
    SWEDEN_STAGE_2        = 467
    SWEDEN_STAGE_2_REV    = 469

    # Wales (Location.WALES = 3) — 7 IDs, generic names
    WALES_STAGE_1         = 437
    WALES_STAGE_2         = 439
    WALES_STAGE_3         = 441
    WALES_STAGE_4         = 442
    WALES_STAGE_4_REV     = 443
    WALES_STAGE_5         = 446
    WALES_STAGE_5_REV     = 448

    # Argentina (Location.ARGENTINA = 5) — 4 IDs, generic names
    ARGENTINA_STAGE_1     = 472
    ARGENTINA_STAGE_2     = 480
    ARGENTINA_STAGE_3     = 490
    ARGENTINA_STAGE_4     = 496

    # New England / USA (Location.NEW_ENGLAND = 10) — 1 ID
    NEW_ENGLAND_STAGE_1   = 478

    # Poland (Location.POLAND = 13) — 4 IDs, generic names
    POLAND_STAGE_1        = 511
    POLAND_STAGE_1_REV    = 512
    POLAND_STAGE_2        = 515
    POLAND_STAGE_2_REV    = 516

    # Germany (Location.GERMANY = 14) — 4 IDs, generic names
    GERMANY_STAGE_1       = 519
    GERMANY_STAGE_1_REV   = 520
    GERMANY_STAGE_2       = 527
    GERMANY_STAGE_2_REV   = 528

    # New Zealand (Location.NEW_ZEALAND = 16) — 12 IDs, named
    OCEAN_BEACH           = 568
    OCEAN_BEACH_REV       = 569
    WAIMARAMA_POINT       = 584
    WAIMARAMA_POINT_REV   = 585
    TE_AWANGA             = 586
    TE_AWANGA_REV         = 587
    ELSTHORPE_SPRINT      = 588
    ELSTHORPE_SPRINT_REV  = 589
    WAIMARAMA_LONG        = 590
    WAIMARAMA_LONG_REV    = 591
    TARINAKI              = 592
    TARINAKI_REV          = 593

    # France (Location.ARGENTINA = 17) — 12 IDs, generic names
    FRANCE_STAGE_1        = 572
    FRANCE_STAGE_1_REV    = 573
    FRANCE_STAGE_2        = 604
    FRANCE_STAGE_2_REV    = 605
    FRANCE_STAGE_3        = 606
    FRANCE_STAGE_3_REV    = 607
    FRANCE_STAGE_4        = 608
    FRANCE_STAGE_4_REV    = 609
    FRANCE_STAGE_5        = 610
    FRANCE_STAGE_5_REV    = 611
    FRANCE_STAGE_6        = 612
    FRANCE_STAGE_6_REV    = 613

    # Yas Marina Rallycross (Location.MONTALEGRE = 19) — 1 ID
    YAS_MARINA_STAGE_1    = 537

    # Montalegre Rallycross (Location.MONTALEGRE = 20) — 1 ID
    MONTALEGRE_STAGE_1    = 538

    # Australia (Location.AUSTRALIA = 16) — 10 IDs, generic names, UNVERIFIED.
    # 580 was previously labeled AUSTRALIA_STAGE_5 here but in-game testing
    # showed it is actually Spain / Descenso por carretera — see Spain block
    # below. The rest of this block remains speculative.
    AUSTRALIA_STAGE_1     = 566
    AUSTRALIA_STAGE_2     = 574
    AUSTRALIA_STAGE_2_REV = 575
    AUSTRALIA_STAGE_3     = 576
    AUSTRALIA_STAGE_3_REV = 577
    AUSTRALIA_STAGE_4     = 578
    AUSTRALIA_STAGE_4_REV = 579
    AUSTRALIA_STAGE_5_REV = 581
    AUSTRALIA_STAGE_6     = 582
    AUSTRALIA_STAGE_6_REV = 583

    # Scotland (Location.SCOTLAND = 34) — 12 IDs, named
    NEWHOUSE_BRIDGE       = 570
    NEWHOUSE_BRIDGE_REV   = 571
    SOUTH_MORNINGSIDE     = 594
    SOUTH_MORNINGSIDE_REV = 595
    GLENFINNAN            = 596
    GLENFINNAN_REV        = 597
    ANNBANK_STATION       = 598
    ANNBANK_STATION_REV   = 599
    OLD_BUTTERSTONE_MUIR  = 600
    OLD_BUTTERSTONE_MUIR_REV = 601
    ROSEBANK_FARM         = 602
    ROSEBANK_FARM_REV     = 603

    # Spain (Location.SPAIN = 31) — verified stage IDs live in two ranges.
    # DESCENSO_POR_CARRETERA at 580 is confirmed by in-game testing; the
    # previous 618/619 assignment was wrong and has been removed. The
    # remaining 614-625 names (Centenera, Ribadelles, Subida, Ascenso bosque,
    # Camino rocoso) are still from community docs and unverified.
    DESCENSO_POR_CARRETERA = 580
    CENTENERA              = 614
    CENTENERA_REV          = 615
    RIBADELLES             = 616
    RIBADELLES_REV         = 617
    SUBIDA_POR_CARRETERA       = 620
    SUBIDA_POR_CARRETERA_REV   = 621
    ASCENSO_BOSQUE         = 622
    ASCENSO_BOSQUE_REV     = 623
    CAMINO_ROCOSO          = 624
    CAMINO_ROCOSO_REV      = 625

    # Finland (Location.FINLAND = 37) — 12 IDs, named
    KAKARISTO             = 626
    KAKARISTO_REV         = 627
    NOORMARKKU            = 628
    NOORMARKKU_REV        = 629
    JYRKYSJARVI           = 630
    JYRKYSJARVI_REV       = 631
    KAILAJARVI            = 632
    KAILAJARVI_REV        = 633
    PITKAJÄRVI            = 634
    PITKAJÄRVI_REV        = 635
    HÄMELAHTI             = 636
    HÄMELAHTI_REV         = 637

    # Greece (Location.GREECE = 46) — 4 IDs, generic names
    GREECE_STAGE_1        = 659
    GREECE_STAGE_2        = 661
    GREECE_STAGE_3        = 663
    GREECE_STAGE_4        = 667

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
    # Sweden — 4 IDs
    Track.SWEDEN_STAGE_1:        {"display_name": "Stage 1",                    "location": Location.SWEDEN,      "length_km": 7.0},
    Track.SWEDEN_STAGE_1_REV:    {"display_name": "Stage 1 (Reverse)",          "location": Location.SWEDEN,      "length_km": 7.0},
    Track.SWEDEN_STAGE_2:        {"display_name": "Stage 2",                    "location": Location.SWEDEN,      "length_km": 7.0},
    Track.SWEDEN_STAGE_2_REV:    {"display_name": "Stage 2 (Reverse)",          "location": Location.SWEDEN,      "length_km": 7.0},

    # Wales — 7 IDs
    Track.WALES_STAGE_1:         {"display_name": "Stage 1",                    "location": Location.WALES,       "length_km": 7.0},
    Track.WALES_STAGE_2:         {"display_name": "Stage 2",                    "location": Location.WALES,       "length_km": 7.0},
    Track.WALES_STAGE_3:         {"display_name": "Stage 3",                    "location": Location.WALES,       "length_km": 7.0},
    Track.WALES_STAGE_4:         {"display_name": "Stage 4",                    "location": Location.WALES,       "length_km": 7.0},
    Track.WALES_STAGE_4_REV:     {"display_name": "Stage 4 (Reverse)",          "location": Location.WALES,       "length_km": 7.0},
    Track.WALES_STAGE_5:         {"display_name": "Stage 5",                    "location": Location.WALES,       "length_km": 7.0},
    Track.WALES_STAGE_5_REV:     {"display_name": "Stage 5 (Reverse)",          "location": Location.WALES,       "length_km": 7.0},

    # Argentina — 4 IDs
    Track.ARGENTINA_STAGE_1:     {"display_name": "Stage 1",                    "location": Location.ARGENTINA,   "length_km": 7.5},
    Track.ARGENTINA_STAGE_2:     {"display_name": "Stage 2",                    "location": Location.ARGENTINA,   "length_km": 7.5},
    Track.ARGENTINA_STAGE_3:     {"display_name": "Stage 3",                    "location": Location.ARGENTINA,   "length_km": 7.5},
    Track.ARGENTINA_STAGE_4:     {"display_name": "Stage 4",                    "location": Location.ARGENTINA,   "length_km": 7.5},

    # New England — 1 ID
    Track.NEW_ENGLAND_STAGE_1:   {"display_name": "Stage 1",                    "location": Location.NEW_ENGLAND, "length_km": 7.5},

    # Poland — 4 IDs
    Track.POLAND_STAGE_1:        {"display_name": "Stage 1",                    "location": Location.POLAND,      "length_km": 7.0},
    Track.POLAND_STAGE_1_REV:    {"display_name": "Stage 1 (Reverse)",          "location": Location.POLAND,      "length_km": 7.0},
    Track.POLAND_STAGE_2:        {"display_name": "Stage 2",                    "location": Location.POLAND,      "length_km": 7.0},
    Track.POLAND_STAGE_2_REV:    {"display_name": "Stage 2 (Reverse)",          "location": Location.POLAND,      "length_km": 7.0},

    # Germany — 4 IDs
    Track.GERMANY_STAGE_1:       {"display_name": "Stage 1",                    "location": Location.GERMANY,     "length_km": 7.0},
    Track.GERMANY_STAGE_1_REV:   {"display_name": "Stage 1 (Reverse)",          "location": Location.GERMANY,     "length_km": 7.0},
    Track.GERMANY_STAGE_2:       {"display_name": "Stage 2",                    "location": Location.GERMANY,     "length_km": 7.0},
    Track.GERMANY_STAGE_2_REV:   {"display_name": "Stage 2 (Reverse)",          "location": Location.GERMANY,     "length_km": 7.0},

    # New Zealand — 12 IDs, named
    Track.OCEAN_BEACH:           {"display_name": "Ocean Beach",                "location": Location.NEW_ZEALAND, "length_km": 5.0},
    Track.OCEAN_BEACH_REV:       {"display_name": "Ocean Beach (Reverse)",      "location": Location.NEW_ZEALAND, "length_km": 5.0},
    Track.WAIMARAMA_POINT:       {"display_name": "Waimarama Point",            "location": Location.NEW_ZEALAND, "length_km": 7.0},
    Track.WAIMARAMA_POINT_REV:   {"display_name": "Waimarama Point (Reverse)",  "location": Location.NEW_ZEALAND, "length_km": 7.0},
    Track.TE_AWANGA:             {"display_name": "Te Awanga",                  "location": Location.NEW_ZEALAND, "length_km": 7.0},
    Track.TE_AWANGA_REV:         {"display_name": "Te Awanga (Reverse)",        "location": Location.NEW_ZEALAND, "length_km": 7.0},
    Track.ELSTHORPE_SPRINT:      {"display_name": "Elsthorpe Sprint",           "location": Location.NEW_ZEALAND, "length_km": 5.0},
    Track.ELSTHORPE_SPRINT_REV:  {"display_name": "Elsthorpe Sprint (Reverse)", "location": Location.NEW_ZEALAND, "length_km": 5.0},
    Track.WAIMARAMA_LONG:        {"display_name": "Waimarama Long",             "location": Location.NEW_ZEALAND, "length_km": 16.0},
    Track.WAIMARAMA_LONG_REV:    {"display_name": "Waimarama Long (Reverse)",   "location": Location.NEW_ZEALAND, "length_km": 16.0},
    Track.TARINAKI:              {"display_name": "Tarinaki",                   "location": Location.NEW_ZEALAND, "length_km": 7.0},
    Track.TARINAKI_REV:          {"display_name": "Tarinaki (Reverse)",         "location": Location.NEW_ZEALAND, "length_km": 7.0},

    # France — 12 IDs, generic names
    Track.FRANCE_STAGE_1:        {"display_name": "Stage 1",                    "location": Location.ARGENTINA,      "length_km": 7.0},
    Track.FRANCE_STAGE_1_REV:    {"display_name": "Stage 1 (Reverse)",          "location": Location.ARGENTINA,      "length_km": 7.0},
    Track.FRANCE_STAGE_2:        {"display_name": "Stage 2",                    "location": Location.ARGENTINA,      "length_km": 7.0},
    Track.FRANCE_STAGE_2_REV:    {"display_name": "Stage 2 (Reverse)",          "location": Location.ARGENTINA,      "length_km": 7.0},
    Track.FRANCE_STAGE_3:        {"display_name": "Stage 3",                    "location": Location.ARGENTINA,      "length_km": 7.0},
    Track.FRANCE_STAGE_3_REV:    {"display_name": "Stage 3 (Reverse)",          "location": Location.ARGENTINA,      "length_km": 7.0},
    Track.FRANCE_STAGE_4:        {"display_name": "Stage 4",                    "location": Location.ARGENTINA,      "length_km": 7.0},
    Track.FRANCE_STAGE_4_REV:    {"display_name": "Stage 4 (Reverse)",          "location": Location.ARGENTINA,      "length_km": 7.0},
    Track.FRANCE_STAGE_5:        {"display_name": "Stage 5",                    "location": Location.ARGENTINA,      "length_km": 7.0},
    Track.FRANCE_STAGE_5_REV:    {"display_name": "Stage 5 (Reverse)",          "location": Location.ARGENTINA,      "length_km": 7.0},
    Track.FRANCE_STAGE_6:        {"display_name": "Stage 6",                    "location": Location.ARGENTINA,      "length_km": 7.0},
    Track.FRANCE_STAGE_6_REV:    {"display_name": "Stage 6 (Reverse)",          "location": Location.ARGENTINA,      "length_km": 7.0},

    # Yas Marina Rallycross — 1 ID
    Track.YAS_MARINA_STAGE_1:    {"display_name": "Yas Marina",                 "location": Location.MONTALEGRE,  "length_km": 1.2, "discipline": "rallycross"},

    # Montalegre Rallycross — 1 ID
    Track.MONTALEGRE_STAGE_1:    {"display_name": "Montalegre",                 "location": Location.MONTALEGRE, "length_km": 1.0, "discipline": "rallycross"},

    # Australia — 10 IDs, generic names, UNVERIFIED
    Track.AUSTRALIA_STAGE_1:     {"display_name": "Stage 1",                    "location": Location.AUSTRALIA,   "length_km": 7.0},
    Track.AUSTRALIA_STAGE_2:     {"display_name": "Stage 2",                    "location": Location.AUSTRALIA,   "length_km": 7.0},
    Track.AUSTRALIA_STAGE_2_REV: {"display_name": "Stage 2 (Reverse)",          "location": Location.AUSTRALIA,   "length_km": 7.0},
    Track.AUSTRALIA_STAGE_3:     {"display_name": "Stage 3",                    "location": Location.AUSTRALIA,   "length_km": 7.0},
    Track.AUSTRALIA_STAGE_3_REV: {"display_name": "Stage 3 (Reverse)",          "location": Location.AUSTRALIA,   "length_km": 7.0},
    Track.AUSTRALIA_STAGE_4:     {"display_name": "Stage 4",                    "location": Location.AUSTRALIA,   "length_km": 12.0},
    Track.AUSTRALIA_STAGE_4_REV: {"display_name": "Stage 4 (Reverse)",          "location": Location.AUSTRALIA,   "length_km": 12.0},
    Track.AUSTRALIA_STAGE_5_REV: {"display_name": "Stage 5 (Reverse)",          "location": Location.AUSTRALIA,   "length_km": 5.0},
    Track.AUSTRALIA_STAGE_6:     {"display_name": "Stage 6",                    "location": Location.AUSTRALIA,   "length_km": 5.0},
    Track.AUSTRALIA_STAGE_6_REV: {"display_name": "Stage 6 (Reverse)",          "location": Location.AUSTRALIA,   "length_km": 5.0},

    # Scotland — 12 IDs, named
    Track.NEWHOUSE_BRIDGE:          {"display_name": "Newhouse Bridge",             "location": Location.SCOTLAND,    "length_km": 12.9},
    Track.NEWHOUSE_BRIDGE_REV:      {"display_name": "Newhouse Bridge (Reverse)",   "location": Location.SCOTLAND,    "length_km": 12.9},
    Track.SOUTH_MORNINGSIDE:        {"display_name": "South Morningside",           "location": Location.SCOTLAND,    "length_km": 12.5},
    Track.SOUTH_MORNINGSIDE_REV:    {"display_name": "South Morningside (Reverse)", "location": Location.SCOTLAND,    "length_km": 12.5},
    Track.GLENFINNAN:               {"display_name": "Glenfinnan",                  "location": Location.SCOTLAND,    "length_km": 7.0},
    Track.GLENFINNAN_REV:           {"display_name": "Glenfinnan (Reverse)",        "location": Location.SCOTLAND,    "length_km": 7.0},
    Track.ANNBANK_STATION:          {"display_name": "Annbank Station",             "location": Location.SCOTLAND,    "length_km": 7.0},
    Track.ANNBANK_STATION_REV:      {"display_name": "Annbank Station (Reverse)",   "location": Location.SCOTLAND,    "length_km": 7.0},
    Track.OLD_BUTTERSTONE_MUIR:     {"display_name": "Old Butterstone Muir",        "location": Location.SCOTLAND,    "length_km": 7.0},
    Track.OLD_BUTTERSTONE_MUIR_REV: {"display_name": "Old Butterstone Muir (Reverse)", "location": Location.SCOTLAND, "length_km": 7.0},
    Track.ROSEBANK_FARM:            {"display_name": "Rosebank Farm",               "location": Location.SCOTLAND,    "length_km": 7.0},
    Track.ROSEBANK_FARM_REV:        {"display_name": "Rosebank Farm (Reverse)",     "location": Location.SCOTLAND,    "length_km": 7.0},

    # Spain — 11 IDs. Descenso (580) is verified in-game; the rest are from
    # community docs and still unverified.
    Track.DESCENSO_POR_CARRETERA:       {"display_name": "Descenso por carretera",          "location": Location.SPAIN,       "length_km": 7.0},
    Track.CENTENERA:                    {"display_name": "Centenera",                       "location": Location.SPAIN,       "length_km": 7.0},
    Track.CENTENERA_REV:                {"display_name": "Centenera (Reverse)",             "location": Location.SPAIN,       "length_km": 7.0},
    Track.RIBADELLES:                   {"display_name": "Ribadelles",                      "location": Location.SPAIN,       "length_km": 14.0},
    Track.RIBADELLES_REV:               {"display_name": "Ribadelles (Reverse)",            "location": Location.SPAIN,       "length_km": 14.0},
    Track.SUBIDA_POR_CARRETERA:         {"display_name": "Subida por carretera",            "location": Location.SPAIN,       "length_km": 7.0},
    Track.SUBIDA_POR_CARRETERA_REV:     {"display_name": "Subida por carretera (Reverse)",  "location": Location.SPAIN,       "length_km": 7.0},
    Track.ASCENSO_BOSQUE:               {"display_name": "Ascenso bosque",                  "location": Location.SPAIN,       "length_km": 7.0},
    Track.ASCENSO_BOSQUE_REV:           {"display_name": "Ascenso bosque (Reverse)",        "location": Location.SPAIN,       "length_km": 7.0},
    Track.CAMINO_ROCOSO:                {"display_name": "Camino rocoso",                   "location": Location.SPAIN,       "length_km": 7.0},
    Track.CAMINO_ROCOSO_REV:            {"display_name": "Camino rocoso (Reverse)",         "location": Location.SPAIN,       "length_km": 7.0},

    # Finland — 12 IDs, named
    Track.KAKARISTO:             {"display_name": "Kakaristo",                   "location": Location.FINLAND,     "length_km": 8.0},
    Track.KAKARISTO_REV:         {"display_name": "Kakaristo (Reverse)",         "location": Location.FINLAND,     "length_km": 8.0},
    Track.NOORMARKKU:            {"display_name": "Noormarkku",                  "location": Location.FINLAND,     "length_km": 7.0},
    Track.NOORMARKKU_REV:        {"display_name": "Noormarkku (Reverse)",        "location": Location.FINLAND,     "length_km": 7.0},
    Track.JYRKYSJARVI:           {"display_name": "Jyrkysjarvi",                 "location": Location.FINLAND,     "length_km": 14.0},
    Track.JYRKYSJARVI_REV:       {"display_name": "Jyrkysjarvi (Reverse)",       "location": Location.FINLAND,     "length_km": 14.0},
    Track.KAILAJARVI:            {"display_name": "Kailajarvi",                  "location": Location.FINLAND,     "length_km": 7.0},
    Track.KAILAJARVI_REV:        {"display_name": "Kailajarvi (Reverse)",        "location": Location.FINLAND,     "length_km": 7.0},
    Track.PITKAJÄRVI:            {"display_name": "Pitkajärvi",                  "location": Location.FINLAND,     "length_km": 7.0},
    Track.PITKAJÄRVI_REV:        {"display_name": "Pitkajärvi (Reverse)",        "location": Location.FINLAND,     "length_km": 7.0},
    Track.HÄMELAHTI:             {"display_name": "Hämelahti",                   "location": Location.FINLAND,     "length_km": 7.0},
    Track.HÄMELAHTI_REV:         {"display_name": "Hämelahti (Reverse)",         "location": Location.FINLAND,     "length_km": 7.0},

    # Greece — 4 IDs, generic names
    Track.GREECE_STAGE_1:        {"display_name": "Stage 1",                    "location": Location.GREECE,      "length_km": 10.4},
    Track.GREECE_STAGE_2:        {"display_name": "Stage 2",                    "location": Location.GREECE,      "length_km": 9.5},
    Track.GREECE_STAGE_3:        {"display_name": "Stage 3",                    "location": Location.GREECE,      "length_km": 7.0},
    Track.GREECE_STAGE_4:        {"display_name": "Stage 4",                    "location": Location.GREECE,      "length_km": 7.0},
}


# ---------------------------------------------------------------------------
# Vehicle classes — Requirements.Value maps to a vehicle class
# ---------------------------------------------------------------------------

class VehicleClass(IntEnum):
    """Vehicle class IDs used in challenge Requirements.

    Confirmed by in-game testing against the real EgoNet protocol.
    Invalid IDs crash the game client.
    """
    GROUP_A        = 72
    GROUP_B_4WD    = 73
    GROUP_B_RWD    = 74
    RX_SUPERCARS   = 78
    F2_KIT_CAR     = 86
    GROUP_B_RX     = 89
    RX_SUPER_1600  = 92
    R5             = 93
    CC_4WD         = 94   # 4WD <= 2000cc
    CROSS_KART     = 95
    NR4_R4         = 96
    H2_RWD         = 97
    H3_RWD         = 98
    R2             = 99
    H2_FWD         = 100
    H1_FWD         = 101
    RX2            = 102

    @property
    def label(self) -> str:
        return _VEHICLE_CLASS_LABELS[self]

    def __str__(self) -> str:
        return self.label


_VEHICLE_CLASS_LABELS: Dict[VehicleClass, str] = {
    VehicleClass.GROUP_A:       "Group A",
    VehicleClass.GROUP_B_4WD:   "Group B 4WD",
    VehicleClass.GROUP_B_RWD:   "Group B RWD",
    VehicleClass.RX_SUPERCARS:  "RX Supercars",
    VehicleClass.F2_KIT_CAR:    "F2 Kit Car",
    VehicleClass.GROUP_B_RX:    "Group B Rallycross",
    VehicleClass.RX_SUPER_1600: "RX Super 1600",
    VehicleClass.R5:            "R5",
    VehicleClass.CC_4WD:        "2000cc 4WD",
    VehicleClass.CROSS_KART:    "Cross Kart",
    VehicleClass.NR4_R4:        "NR4/R4",
    VehicleClass.H2_RWD:        "H2 RWD",
    VehicleClass.H3_RWD:        "H3 RWD",
    VehicleClass.R2:            "R2",
    VehicleClass.H2_FWD:        "H2 FWD",
    VehicleClass.H1_FWD:        "H1 FWD",
    VehicleClass.RX2:           "RX2",
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
    MG_METRO_6R4             = 401  # verified in-game 2026-04 (was 511, wrong)
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
    # NR4/R4 (closest to Rally GT - the actual Rally GT class doesn't have a confirmed ID)
    Vehicle.PORSCHE_911_RGT:  {"display_name": "Porsche 911 RGT Rally",    "vehicle_class": VehicleClass.NR4_R4, "abbrev": "99r"},
    Vehicle.ASTON_MARTIN_V8:  {"display_name": "Aston Martin V8 Vantage",  "vehicle_class": VehicleClass.NR4_R4, "abbrev": "amr"},
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
# Stage conditions — decoded from the game catalogue's four enum dimensions.
#
# The game's stage-data struct exposes four separate fields alongside the
# composite StageConditions id:
#
#   StageConditions (composite index, see decode_stage_conditions below)
#   WeatherPresetId (index into WeatherBucket)
#   TimeOfDayId     (index into TimeOfDayBucket)
#   SurfaceCondId   (index into SurfaceType)
#
# The individual dimension enums below come from the game catalogue strings:
#   GAME__CATALOGUE__SECTION__SURFACE_TYPE__{gravel,tarmac,snow,ice}
#   GAME__CATALOGUE__SECTION__PRECIPITATION_TYPE__{NoPrecipitation,Rain,Snow}
# and from frontend/configs/environment_image_mapping.xml, which collapses
# the raw time-of-day / weather variants into six buckets each.
#
# The specific integer IDs for these enums are server-assigned and not known
# yet — the member values below are ordinal placeholders that will be pinned
# during the manual-testing pass.  Upstream club captures always have
# (WeatherPresetId, TimeOfDayId, SurfaceCondId) = (1, 4, 1), i.e. clear /
# midday / gravel — confirmed by user saying ConditionsId=1 shows
# "Daytime / Clear / Dry Surface".
# ---------------------------------------------------------------------------


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
# StageConditions composite-ID decoder
# ---------------------------------------------------------------------------
# Hypothesis from the reverse-engineering notes:
#   high nibble = surface state (0 = dry, 1 = damp, 2 = wet/flooded)
#   low nibble  = (TimeOfDay × Weather) preset index within that surface state
#
# Observed values from upstream club captures (decomposed):
#   1  = (0,1)   9  = (0,9)    20 = (1,4)   40 = (2,8)
#   3  = (0,3)   11 = (0,11)   26 = (1,10)  42 = (2,10)
#   4  = (0,4)   16 = (1,0)    35 = (2,3)   47 = (2,15)
#   5  = (0,5)   17 = (1,1)    38 = (2,6)
#
# So the observed high-nibble set is {0,1,2} and the observed low-nibble set
# spans 0..15.  This is a working hypothesis only — low-nibble labels still
# need to be pinned via in-game capture.


class StageSurfaceState(IntEnum):
    """High nibble of StageConditions — wetness state of the surface."""
    DRY          = 0
    DAMP         = 1
    WET          = 2
    # 3 may exist for ice/snowpack but has not been observed in captures.

    @property
    def label(self) -> str:
        return {
            StageSurfaceState.DRY:  "Dry",
            StageSurfaceState.DAMP: "Damp",
            StageSurfaceState.WET:  "Wet",
        }[self]

    def __str__(self) -> str:
        return self.label


def decode_stage_conditions(value: int) -> Dict[str, Any]:
    """Decompose a composite StageConditions integer into its parts.

    Returns a dict with:
        surface_state:      StageSurfaceState or None if unknown
        surface_state_int:  raw high nibble (always valid)
        preset_index:       raw low nibble (time-of-day × weather index)
        label:              human-readable string, best-effort
    """
    high = (value >> 4) & 0xF
    low = value & 0xF
    try:
        state: Optional[StageSurfaceState] = StageSurfaceState(high)
        state_label = state.label
    except ValueError:
        state = None
        state_label = f"Surface#{high}"
    return {
        "surface_state":     state,
        "surface_state_int": high,
        "preset_index":      low,
        "label":              f"{state_label} / Preset #{low}",
    }


# StageConditions integer values observed in the wild (upstream club data +
# time-trial captures).  Every one of these must be resolvable by the web
# leaderboard page, even if we only know the surface-state half of the label.
OBSERVED_STAGE_CONDITIONS: List[int] = [
    1, 3, 4, 5, 9, 11, 16, 17, 20, 26, 35, 38, 39, 40, 42, 47,
]


# ---------------------------------------------------------------------------
# TimeTrial Category — meaning unconfirmed, best hypothesis below.
# ---------------------------------------------------------------------------
# Observed values: 1 and 2.  Best hypothesis from the dr2_unknowns notes:
#   1 = single-stage leaderboard
#   2 = event / cumulative leaderboard (matches SortCumulative flag nearby)
# Needs confirmation via a manual testing pass that posts a time and then
# views both the per-stage and the event leaderboards.


class TimeTrialCategory(IntEnum):
    """Category integer from TimeTrial.GetLeaderboardId / PostTime.

    Hypothesis — not yet confirmed:
      1 = stage-time (per-stage) leaderboard
      2 = cumulative / event leaderboard
    """
    STAGE = 1
    EVENT = 2

    @property
    def label(self) -> str:
        return {
            TimeTrialCategory.STAGE: "Stage",
            TimeTrialCategory.EVENT: "Event",
        }[self]

    def __str__(self) -> str:
        return self.label


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

WEATHER_PRESETS: Dict[int, str] = {int(w): w.label for w in WeatherBucket}

TIME_OF_DAY: Dict[int, str] = {int(t): t.label for t in TimeOfDayBucket}

SURFACE_TYPES: Dict[int, str] = {int(s): s.label for s in SurfaceType}

PRECIPITATION_TYPES: Dict[int, str] = {int(p): p.label for p in PrecipitationType}

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
