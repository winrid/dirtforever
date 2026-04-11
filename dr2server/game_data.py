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

    Verified by in-game testing — map names are from the Event Details
    header in the Racenet Clubs UI (OCR'd via the automated discovery
    pipeline on 2026-04-11).
    """
    MONTE_CARLO     = 4   # Monte Carlo / Monaco (rally, Season 1 DLC)
    GREECE          = 2   # Greece rally
    WALES           = 3   # Wales rally
    GERMANY         = 5   # Germany rally
    LYDDEN_HILL     = 9   # Lydden Hill RX (England)
    HELL            = 10  # Hell RX (Norway)
    HOLJES          = 11  # Höljes RX (Sweden)
    FINLAND         = 13  # Finland rally
    SWEDEN          = 14  # Sweden rally
    AUSTRALIA       = 16  # Australia rally
    ARGENTINA       = 17  # Argentina rally
    LOHEAC          = 18  # Loheac RX (France)
    MONTALEGRE      = 19  # Montalegre RX (Portugal)
    BARCELONA       = 20  # Barcelona RX (Spain)
    TWIN_PEAKS      = 22  # Twin Peaks freeplay (Washington, USA)
    TROIS_RIVIERES  = 30  # Trois-Rivières RX (Canada)
    SPAIN           = 31  # Spain rally (Ribadelles)
    NEW_ZEALAND     = 34  # New Zealand rally
    POLAND          = 36  # Poland rally
    NEW_ENGLAND     = 37  # New England rally (USA)
    SILVERSTONE     = 38  # Silverstone RX (England)
    METTET          = 39  # Mettet RX (Belgium)
    ESTERING        = 40  # Estering RX (Germany)
    BIKERNIEKI      = 41  # Bikernieki / Riga RX (Latvia)
    KILLARNEY       = 42  # Killarney RX (South Africa)
    YAS_MARINA      = 43  # Yas Marina RX (Abu Dhabi, UAE)
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
    Location.MONTE_CARLO:    {"display_name": "Monte Carlo",      "country": "Monaco",       "discipline": "rally"},
    Location.GREECE:         {"display_name": "Greece",           "country": "Greece",       "discipline": "rally"},
    Location.WALES:          {"display_name": "Wales",            "country": "UK",           "discipline": "rally"},
    Location.GERMANY:        {"display_name": "Germany",          "country": "Germany",      "discipline": "rally"},
    Location.LYDDEN_HILL:    {"display_name": "Lydden Hill",      "country": "England",      "discipline": "rallycross"},
    Location.HELL:           {"display_name": "Hell",             "country": "Norway",       "discipline": "rallycross"},
    Location.HOLJES:         {"display_name": "Höljes",           "country": "Sweden",       "discipline": "rallycross"},
    Location.FINLAND:        {"display_name": "Finland",          "country": "Finland",      "discipline": "rally"},
    Location.SWEDEN:         {"display_name": "Sweden",           "country": "Sweden",       "discipline": "rally"},
    Location.AUSTRALIA:      {"display_name": "Australia",        "country": "Australia",    "discipline": "rally"},
    Location.ARGENTINA:      {"display_name": "Argentina",        "country": "Argentina",    "discipline": "rally"},
    Location.LOHEAC:         {"display_name": "Loheac",           "country": "France",       "discipline": "rallycross"},
    Location.MONTALEGRE:     {"display_name": "Montalegre",       "country": "Portugal",     "discipline": "rallycross"},
    Location.BARCELONA:      {"display_name": "Barcelona",        "country": "Spain",        "discipline": "rallycross"},
    Location.TWIN_PEAKS:     {"display_name": "Twin Peaks",       "country": "USA",          "discipline": "rally"},
    Location.TROIS_RIVIERES: {"display_name": "Trois-Rivières",   "country": "Canada",       "discipline": "rallycross"},
    Location.SPAIN:          {"display_name": "Spain",            "country": "Spain",        "discipline": "rally"},
    Location.NEW_ZEALAND:    {"display_name": "New Zealand",      "country": "New Zealand",  "discipline": "rally"},
    Location.POLAND:         {"display_name": "Poland",           "country": "Poland",       "discipline": "rally"},
    Location.NEW_ENGLAND:    {"display_name": "New England",      "country": "USA",          "discipline": "rally"},
    Location.SILVERSTONE:    {"display_name": "Silverstone",      "country": "England",      "discipline": "rallycross"},
    Location.METTET:         {"display_name": "Mettet",           "country": "Belgium",      "discipline": "rallycross"},
    Location.ESTERING:       {"display_name": "Estering",         "country": "Germany",      "discipline": "rallycross"},
    Location.BIKERNIEKI:     {"display_name": "Bikernieki",       "country": "Latvia",       "discipline": "rallycross"},
    Location.KILLARNEY:      {"display_name": "Killarney",        "country": "South Africa", "discipline": "rallycross"},
    Location.YAS_MARINA:     {"display_name": "Yas Marina",       "country": "UAE",          "discipline": "rallycross"},
    Location.SCOTLAND:       {"display_name": "Scotland",         "country": "UK",           "discipline": "rally"},
}


# ---------------------------------------------------------------------------
# Track models — TrackModelId maps to a specific stage route
# ---------------------------------------------------------------------------
#
# Track names and their Location attribution were verified in-game
# 2026-04-11 via the enum-mapping discovery round (see
# runtime/discovery/track_mapping.json).  98 tracks confirmed across
# 15 locations.  Tracks not yet probed are not listed here.

class Track(IntEnum):
    """Stage/track route IDs (TrackModelId in the EgoNet protocol).

    Verified in-game 2026-04-11 by the enum-mapping discovery round.
    Names and Location attribution come from the in-game Event Details
    panel for each TrackModelId.  See runtime/discovery/track_mapping.json
    for the raw data.
    """

    # ARGENTINA
    LAS_JUNTAS                               = 572
    VALLE_DE_LOS_PUENTES                     = 573
    CAMINO_A_LA_PUERTA                       = 604
    CAMINO_DE_ACANTILADOS_Y_ROCAS            = 605
    EL_RODEO                                 = 606
    LA_MERCED                                = 607
    CAMINO_DE_ACANTILADOS_Y_ROCAS_INVERSO    = 608
    VALLE_DE_LOS_PUENTES_A_LA_INVERSA        = 609
    MIRAFLORES                               = 610
    SAN_ISIDRO                               = 611
    CAMINO_A_CONETA                          = 612
    HUILLAPRIMA                              = 613

    # AUSTRALIA
    MOUNT_KAYE_PASS                          = 568
    CHANDLERS_CREEK                          = 569
    MOUNT_KAYE_PASS_REVERSE                  = 584
    ROCKTON_PLAINS                           = 585
    YAMBULLA_MOUNTAIN_DESCENT                = 586
    YAMBULLA_MOUNTAIN_ASCENT                 = 587
    ROCKTON_PLAINS_REVERSE                   = 588
    CHANDLERS_CREEK_REVERSE                  = 589
    NOORINBEE_RIDGE_ASCENT                   = 590
    TAYLOR_FARM_SPRINT                       = 591
    BONDI_FOREST                             = 592
    NOORINBEE_RIDGE_DESCENT                  = 593

    # BARCELONA
    FULL_CIRCUIT                             = 538

    # FINLAND
    KAKARISTO                                = 511
    PITKAJARVI                               = 512
    KOTAJARVI                                = 515
    OKSALA                                   = 516

    # GERMANY
    OBERSTEIN                                = 472
    HAMMERSTEIN                              = 480
    WALDAUFSTIEG                             = 490
    INNERER_FELD_SPRINT                      = 496

    # GREECE
    FOURKETA_KOURVA                          = 462
    AMPELONAS_ORMI                           = 464
    OUREA_SPEVSI                             = 467
    ABIES_KOILEDA                            = 469

    # HELL
    FULL_CIRCUIT_478                         = 478

    # MONTALEGRE
    FULL_CIRCUIT_537                         = 537

    # NEW_ENGLAND
    NORTH_FORK_PASS                          = 626
    NORTH_FORK_PASS_REVERSE                  = 627
    HANCOCK_CREEK_BURST                      = 628
    FULLER_MOUNTAIN_DESCENT                  = 629
    FULLER_MOUNTAIN_ASCENT                   = 630
    FURY_LAKE_DEPART                         = 631
    BEAVER_CREEK_TRAIL_FORWARD               = 632
    BEAVER_CREEK_TRAIL_REVERSE               = 633
    HANCOCK_HILL_SPRINT_FORWARD              = 634
    TOLT_VALLEY_SPRINT_REVERSE               = 635
    TOLT_VALLEY_SPRINT_FORWARD               = 636
    HANCOCK_HILL_SPRINT_REVERSE              = 637

    # NEW_ZEALAND
    TE_AWANGA_FORWARD                        = 570
    WAIMARAMA_POINT_FORWARD                  = 571
    OCEAN_BEACH                              = 594
    TE_AWANGA_SPRINT_FORWARD                 = 595
    OCEAN_BEACH_SPRINT_FORWARD               = 596
    OCEAN_BEACH_SPRINT_REVERSE               = 597
    TE_AWANGA_SPRINT_REVERSE                 = 598
    WAIMARAMA_POINT_REVERSE                  = 599
    ELSTHORPE_SPRINT_FORWARD                 = 600
    WAIMARAMA_SPRINT_FORWARD                 = 601
    WAIMARAMA_SPRINT_REVERSE                 = 602
    ELSTHORPE_SPRINT_REVERSE                 = 603

    # POLAND
    ZAROBKA                                  = 614
    ZAGORZE                                  = 615
    KOPINA                                   = 616
    MARYNKA                                  = 617
    JEZIORO_ROTCZE                           = 620
    ZIENKI                                   = 621
    CZARNY_LAS                               = 622
    LEJNO                                    = 623
    JAGODNO                                  = 624
    JEZIORO_LUKIE                            = 625

    # SCOTLAND
    OLD_BUTTERSTONE_MUIR                     = 659
    ROSEBANK_FARM_REVERSE                    = 661
    NEWHOUSE_BRIDGE                          = 663
    ANNBANK_STATION_REVERSE                  = 667

    # SPAIN
    COMIENZO_DE_BELLRIU                      = 566
    FINAL_DE_BELLRIU                         = 574
    ASCENSO_POR_VALLE_EL_GUALET              = 575
    VINEDOS_DENTRO_DEL_VALLE_PARRA           = 576
    ASCENSO_BOSQUE_MONTVERD                  = 577
    SALIDA_DESDE_MONTVERD                    = 578
    CAMINO_A_CENTENERA                       = 579
    DESCENSO_POR_CARRETERA                   = 580
    VINEDOS_DARDENYA                         = 581
    VINEDOS_DARDENYA_INVERSA                 = 582
    SUBIDA_POR_CARRETERA                     = 583

    # SWEDEN
    ALGSJON_SPRINT                           = 519
    STOR_JANGEN_SPRINT_REVERSE               = 520
    OSTRA_HINNSJON                           = 527
    ALGSJON                                  = 528

    # WALES
    SWEET_LAMB                               = 437
    PANT_MAWR                                = 439
    BIDNO_MOORLAND                           = 441
    PANT_MAWR_REVERSE                        = 442
    RIVER_SEVERN_VALLEY                      = 443
    DYFFRYN_AFON_REVERSE                     = 446
    FFERM_WYNT_REVERSE                       = 448

    @property
    def display_name(self) -> str:
        return _TRACK_META[self]["display_name"]

    @property
    def location(self) -> "Location":
        return _TRACK_META[self]["location"]

    @property
    def length_km(self) -> float:
        return _TRACK_META[self].get("length_km", 0.0)

    @property
    def discipline(self) -> str:
        return _TRACK_META[self].get("discipline", "rally")

    def __str__(self) -> str:
        return self.display_name

_TRACK_META: Dict[Track, dict] = {
    Track.LAS_JUNTAS: {"display_name": "Las Juntas", "location": Location.ARGENTINA, "length_km": 0.0},
    Track.VALLE_DE_LOS_PUENTES: {"display_name": "Valle de los puentes", "location": Location.ARGENTINA, "length_km": 0.0},
    Track.CAMINO_A_LA_PUERTA: {"display_name": "Camino a La Puerta", "location": Location.ARGENTINA, "length_km": 0.0},
    Track.CAMINO_DE_ACANTILADOS_Y_ROCAS: {"display_name": "Camino de acantilados y rocas", "location": Location.ARGENTINA, "length_km": 0.0},
    Track.EL_RODEO: {"display_name": "El Rodeo", "location": Location.ARGENTINA, "length_km": 0.0},
    Track.LA_MERCED: {"display_name": "La Merced", "location": Location.ARGENTINA, "length_km": 0.0},
    Track.CAMINO_DE_ACANTILADOS_Y_ROCAS_INVERSO: {"display_name": "Camino de acantilados y rocas inverso", "location": Location.ARGENTINA, "length_km": 0.0},
    Track.VALLE_DE_LOS_PUENTES_A_LA_INVERSA: {"display_name": "Valle de los puentes a la inversa", "location": Location.ARGENTINA, "length_km": 0.0},
    Track.MIRAFLORES: {"display_name": "Miraflores", "location": Location.ARGENTINA, "length_km": 0.0},
    Track.SAN_ISIDRO: {"display_name": "San Isidro", "location": Location.ARGENTINA, "length_km": 0.0},
    Track.CAMINO_A_CONETA: {"display_name": "Camino a Coneta", "location": Location.ARGENTINA, "length_km": 0.0},
    Track.HUILLAPRIMA: {"display_name": "Huillaprima", "location": Location.ARGENTINA, "length_km": 0.0},
    Track.MOUNT_KAYE_PASS: {"display_name": "Mount Kaye Pass", "location": Location.AUSTRALIA, "length_km": 0.0},
    Track.CHANDLERS_CREEK: {"display_name": "Chandlers Creek", "location": Location.AUSTRALIA, "length_km": 0.0},
    Track.MOUNT_KAYE_PASS_REVERSE: {"display_name": "Mount Kaye Pass Reverse", "location": Location.AUSTRALIA, "length_km": 0.0},
    Track.ROCKTON_PLAINS: {"display_name": "Rockton Plains", "location": Location.AUSTRALIA, "length_km": 0.0},
    Track.YAMBULLA_MOUNTAIN_DESCENT: {"display_name": "Yambulla Mountain Descent", "location": Location.AUSTRALIA, "length_km": 0.0},
    Track.YAMBULLA_MOUNTAIN_ASCENT: {"display_name": "Yambulla Mountain Ascent", "location": Location.AUSTRALIA, "length_km": 0.0},
    Track.ROCKTON_PLAINS_REVERSE: {"display_name": "Rockton Plains Reverse", "location": Location.AUSTRALIA, "length_km": 0.0},
    Track.CHANDLERS_CREEK_REVERSE: {"display_name": "Chandlers Creek Reverse", "location": Location.AUSTRALIA, "length_km": 0.0},
    Track.NOORINBEE_RIDGE_ASCENT: {"display_name": "Noorinbee Ridge Ascent", "location": Location.AUSTRALIA, "length_km": 0.0},
    Track.TAYLOR_FARM_SPRINT: {"display_name": "Taylor Farm Sprint", "location": Location.AUSTRALIA, "length_km": 0.0},
    Track.BONDI_FOREST: {"display_name": "Bondi Forest", "location": Location.AUSTRALIA, "length_km": 0.0},
    Track.NOORINBEE_RIDGE_DESCENT: {"display_name": "Noorinbee Ridge Descent", "location": Location.AUSTRALIA, "length_km": 0.0},
    Track.FULL_CIRCUIT: {"display_name": "Full Circuit", "location": Location.BARCELONA, "length_km": 0.0},
    Track.KAKARISTO: {"display_name": "Kakaristo", "location": Location.FINLAND, "length_km": 0.0},
    Track.PITKAJARVI: {"display_name": "Pitkajarvi", "location": Location.FINLAND, "length_km": 0.0},
    Track.KOTAJARVI: {"display_name": "Kotajarvi", "location": Location.FINLAND, "length_km": 0.0},
    Track.OKSALA: {"display_name": "Oksala", "location": Location.FINLAND, "length_km": 0.0},
    Track.OBERSTEIN: {"display_name": "Oberstein", "location": Location.GERMANY, "length_km": 0.0},
    Track.HAMMERSTEIN: {"display_name": "Hammerstein", "location": Location.GERMANY, "length_km": 0.0},
    Track.WALDAUFSTIEG: {"display_name": "Waldaufstieg", "location": Location.GERMANY, "length_km": 0.0},
    Track.INNERER_FELD_SPRINT: {"display_name": "Innerer Feld-Sprint", "location": Location.GERMANY, "length_km": 0.0},
    Track.FOURKETA_KOURVA: {"display_name": "Fourkéta Kourva", "location": Location.GREECE, "length_km": 0.0},
    Track.AMPELONAS_ORMI: {"display_name": "Ampelonas Ormi", "location": Location.GREECE, "length_km": 0.0},
    Track.OUREA_SPEVSI: {"display_name": "Ourea Spevsi", "location": Location.GREECE, "length_km": 0.0},
    Track.ABIES_KOILEDA: {"display_name": "Abies Koiléda", "location": Location.GREECE, "length_km": 0.0},
    Track.FULL_CIRCUIT_478: {"display_name": "Full Circuit", "location": Location.HELL, "length_km": 0.0},
    Track.FULL_CIRCUIT_537: {"display_name": "Full Circuit", "location": Location.MONTALEGRE, "length_km": 0.0},
    Track.NORTH_FORK_PASS: {"display_name": "North Fork Pass", "location": Location.NEW_ENGLAND, "length_km": 0.0},
    Track.NORTH_FORK_PASS_REVERSE: {"display_name": "North Fork Pass Reverse", "location": Location.NEW_ENGLAND, "length_km": 0.0},
    Track.HANCOCK_CREEK_BURST: {"display_name": "Hancock Creek Burst", "location": Location.NEW_ENGLAND, "length_km": 0.0},
    Track.FULLER_MOUNTAIN_DESCENT: {"display_name": "Fuller Mountain Descent", "location": Location.NEW_ENGLAND, "length_km": 0.0},
    Track.FULLER_MOUNTAIN_ASCENT: {"display_name": "Fuller Mountain Ascent", "location": Location.NEW_ENGLAND, "length_km": 0.0},
    Track.FURY_LAKE_DEPART: {"display_name": "Fury Lake Depart", "location": Location.NEW_ENGLAND, "length_km": 0.0},
    Track.BEAVER_CREEK_TRAIL_FORWARD: {"display_name": "Beaver Creek Trail Forward", "location": Location.NEW_ENGLAND, "length_km": 0.0},
    Track.BEAVER_CREEK_TRAIL_REVERSE: {"display_name": "Beaver Creek Trail Reverse", "location": Location.NEW_ENGLAND, "length_km": 0.0},
    Track.HANCOCK_HILL_SPRINT_FORWARD: {"display_name": "Hancock Hill Sprint Forward", "location": Location.NEW_ENGLAND, "length_km": 0.0},
    Track.TOLT_VALLEY_SPRINT_REVERSE: {"display_name": "Tolt Valley Sprint Reverse", "location": Location.NEW_ENGLAND, "length_km": 0.0},
    Track.TOLT_VALLEY_SPRINT_FORWARD: {"display_name": "Tolt Valley Sprint Forward", "location": Location.NEW_ENGLAND, "length_km": 0.0},
    Track.HANCOCK_HILL_SPRINT_REVERSE: {"display_name": "Hancock Hill Sprint Reverse", "location": Location.NEW_ENGLAND, "length_km": 0.0},
    Track.TE_AWANGA_FORWARD: {"display_name": "Te Awanga Forward", "location": Location.NEW_ZEALAND, "length_km": 0.0},
    Track.WAIMARAMA_POINT_FORWARD: {"display_name": "Waimarama Point Forward", "location": Location.NEW_ZEALAND, "length_km": 0.0},
    Track.OCEAN_BEACH: {"display_name": "Ocean Beach", "location": Location.NEW_ZEALAND, "length_km": 0.0},
    Track.TE_AWANGA_SPRINT_FORWARD: {"display_name": "Te Awanga Sprint Forward", "location": Location.NEW_ZEALAND, "length_km": 0.0},
    Track.OCEAN_BEACH_SPRINT_FORWARD: {"display_name": "Ocean Beach Sprint Forward", "location": Location.NEW_ZEALAND, "length_km": 0.0},
    Track.OCEAN_BEACH_SPRINT_REVERSE: {"display_name": "Ocean Beach Sprint Reverse", "location": Location.NEW_ZEALAND, "length_km": 0.0},
    Track.TE_AWANGA_SPRINT_REVERSE: {"display_name": "Te Awanga Sprint Reverse", "location": Location.NEW_ZEALAND, "length_km": 0.0},
    Track.WAIMARAMA_POINT_REVERSE: {"display_name": "Waimarama Point Reverse", "location": Location.NEW_ZEALAND, "length_km": 0.0},
    Track.ELSTHORPE_SPRINT_FORWARD: {"display_name": "Elsthorpe Sprint Forward", "location": Location.NEW_ZEALAND, "length_km": 0.0},
    Track.WAIMARAMA_SPRINT_FORWARD: {"display_name": "Waimarama Sprint Forward", "location": Location.NEW_ZEALAND, "length_km": 0.0},
    Track.WAIMARAMA_SPRINT_REVERSE: {"display_name": "Waimarama Sprint Reverse", "location": Location.NEW_ZEALAND, "length_km": 0.0},
    Track.ELSTHORPE_SPRINT_REVERSE: {"display_name": "Elsthorpe Sprint Reverse", "location": Location.NEW_ZEALAND, "length_km": 0.0},
    Track.ZAROBKA: {"display_name": "Zarobka", "location": Location.POLAND, "length_km": 0.0},
    Track.ZAGORZE: {"display_name": "Zagorze", "location": Location.POLAND, "length_km": 0.0},
    Track.KOPINA: {"display_name": "Kopina", "location": Location.POLAND, "length_km": 0.0},
    Track.MARYNKA: {"display_name": "Marynka", "location": Location.POLAND, "length_km": 0.0},
    Track.JEZIORO_ROTCZE: {"display_name": "Jezioro Rotcze", "location": Location.POLAND, "length_km": 0.0},
    Track.ZIENKI: {"display_name": "Zienki", "location": Location.POLAND, "length_km": 0.0},
    Track.CZARNY_LAS: {"display_name": "Czarny Las", "location": Location.POLAND, "length_km": 0.0},
    Track.LEJNO: {"display_name": "Lejno", "location": Location.POLAND, "length_km": 0.0},
    Track.JAGODNO: {"display_name": "Jagodno", "location": Location.POLAND, "length_km": 0.0},
    Track.JEZIORO_LUKIE: {"display_name": "Jezioro Lukie", "location": Location.POLAND, "length_km": 0.0},
    Track.OLD_BUTTERSTONE_MUIR: {"display_name": "Old Butterstone Muir", "location": Location.SCOTLAND, "length_km": 0.0},
    Track.ROSEBANK_FARM_REVERSE: {"display_name": "Rosebank Farm Reverse", "location": Location.SCOTLAND, "length_km": 0.0},
    Track.NEWHOUSE_BRIDGE: {"display_name": "Newhouse Bridge", "location": Location.SCOTLAND, "length_km": 0.0},
    Track.ANNBANK_STATION_REVERSE: {"display_name": "Annbank Station Reverse", "location": Location.SCOTLAND, "length_km": 0.0},
    Track.COMIENZO_DE_BELLRIU: {"display_name": "Comienzo De Bellriu", "location": Location.SPAIN, "length_km": 0.0},
    Track.FINAL_DE_BELLRIU: {"display_name": "Final de Bellriu", "location": Location.SPAIN, "length_km": 0.0},
    Track.ASCENSO_POR_VALLE_EL_GUALET: {"display_name": "Ascenso por valle el Gualet", "location": Location.SPAIN, "length_km": 0.0},
    Track.VINEDOS_DENTRO_DEL_VALLE_PARRA: {"display_name": "Vinedos dentro del valle Parra", "location": Location.SPAIN, "length_km": 0.0},
    Track.ASCENSO_BOSQUE_MONTVERD: {"display_name": "Ascenso bosque Montverd", "location": Location.SPAIN, "length_km": 0.0},
    Track.SALIDA_DESDE_MONTVERD: {"display_name": "Salida desde Montverd", "location": Location.SPAIN, "length_km": 0.0},
    Track.CAMINO_A_CENTENERA: {"display_name": "Camino a Centenera", "location": Location.SPAIN, "length_km": 0.0},
    Track.DESCENSO_POR_CARRETERA: {"display_name": "Descenso por carretera", "location": Location.SPAIN, "length_km": 0.0},
    Track.VINEDOS_DARDENYA: {"display_name": "Vinedos Dardenya", "location": Location.SPAIN, "length_km": 0.0},
    Track.VINEDOS_DARDENYA_INVERSA: {"display_name": "Vinedos Dardenya inversa", "location": Location.SPAIN, "length_km": 0.0},
    Track.SUBIDA_POR_CARRETERA: {"display_name": "Subida por carretera", "location": Location.SPAIN, "length_km": 0.0},
    Track.ALGSJON_SPRINT: {"display_name": "Algsjon Sprint", "location": Location.SWEDEN, "length_km": 0.0},
    Track.STOR_JANGEN_SPRINT_REVERSE: {"display_name": "Stor-jangen Sprint Reverse", "location": Location.SWEDEN, "length_km": 0.0},
    Track.OSTRA_HINNSJON: {"display_name": "Östra Hinnsjön", "location": Location.SWEDEN, "length_km": 0.0},
    Track.ALGSJON: {"display_name": "Algsjon", "location": Location.SWEDEN, "length_km": 0.0},
    Track.SWEET_LAMB: {"display_name": "Sweet Lamb", "location": Location.WALES, "length_km": 0.0},
    Track.PANT_MAWR: {"display_name": "Pant Mawr", "location": Location.WALES, "length_km": 0.0},
    Track.BIDNO_MOORLAND: {"display_name": "Bidno Moorland", "location": Location.WALES, "length_km": 0.0},
    Track.PANT_MAWR_REVERSE: {"display_name": "Pant Mawr Reverse", "location": Location.WALES, "length_km": 0.0},
    Track.RIVER_SEVERN_VALLEY: {"display_name": "River Severn Valley", "location": Location.WALES, "length_km": 0.0},
    Track.DYFFRYN_AFON_REVERSE: {"display_name": "Dyffryn Afon Reverse", "location": Location.WALES, "length_km": 0.0},
    Track.FFERM_WYNT_REVERSE: {"display_name": "Fferm Wynt Reverse", "location": Location.WALES, "length_km": 0.0},
}

# Generated from 99 tracks across 15 locations.
#   ARGENTINA: 12 tracks
#   AUSTRALIA: 12 tracks
#   BARCELONA: 1 tracks
#   FINLAND: 4 tracks
#   GERMANY: 4 tracks
#   GREECE: 4 tracks
#   HELL: 1 tracks
#   MONTALEGRE: 1 tracks
#   NEW_ENGLAND: 12 tracks
#   NEW_ZEALAND: 12 tracks
#   POLAND: 10 tracks
#   SCOTLAND: 4 tracks
#   SPAIN: 11 tracks
#   SWEDEN: 4 tracks
#   WALES: 7 tracks



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
