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
from typing import Any, Dict, List, Optional


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
    # Rally
    ARGENTINA       = 17  # Argentina rally
    AUSTRALIA       = 16  # Australia rally
    FINLAND         = 13  # Finland rally
    GERMANY         = 5   # Germany rally
    GREECE          = 2   # Greece rally
    MONTE_CARLO     = 4   # Monte Carlo / Monaco (rally, Season 1 DLC)
    NEW_ZEALAND     = 34  # New Zealand rally
    POLAND          = 36  # Poland rally
    SPAIN           = 31  # Spain rally (Ribadelles)
    SWEDEN          = 14  # Sweden rally
    NEW_ENGLAND     = 37  # New England rally (USA)
    WALES           = 3   # Wales rally
    SCOTLAND        = 46  # Scotland rally

    # Rallycross
    METTET          = 39  # Mettet RX (Belgium)
    TROIS_RIVIERES  = 30  # Trois-Rivières RX (Canada)
    LYDDEN_HILL     = 9   # Lydden Hill RX (England)
    SILVERSTONE     = 38  # Silverstone RX (England)
    LOHEAC          = 18  # Loheac RX (France)
    ESTERING        = 40  # Estering RX (Germany)
    BIKERNIEKI      = 41  # Bikernieki / Riga RX (Latvia)
    HELL            = 10  # Hell RX (Norway)
    MONTALEGRE      = 19  # Montalegre RX (Portugal)
    KILLARNEY       = 42  # Killarney RX (South Africa)
    BARCELONA       = 20  # Barcelona RX (Spain)
    HOLJES          = 11  # Höljes RX (Sweden)
    YAS_MARINA      = 43  # Yas Marina RX (Abu Dhabi, UAE)
    
    # Freeplay
    TWIN_PEAKS      = 22  # Twin Peaks freeplay (Washington, USA)

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
    Location.ARGENTINA:      {"display_name": "Argentina",        "country": "Argentina",    "discipline": "rally"},
    Location.AUSTRALIA:      {"display_name": "Australia",        "country": "Australia",    "discipline": "rally"},
    Location.FINLAND:        {"display_name": "Finland",          "country": "Finland",      "discipline": "rally"},
    Location.GERMANY:        {"display_name": "Germany",          "country": "Germany",      "discipline": "rally"},
    Location.GREECE:         {"display_name": "Greece",           "country": "Greece",       "discipline": "rally"},
    Location.MONTE_CARLO:    {"display_name": "Monte Carlo",      "country": "Monaco",       "discipline": "rally"},
    Location.NEW_ZEALAND:    {"display_name": "New Zealand",      "country": "New Zealand",  "discipline": "rally"},
    Location.POLAND:         {"display_name": "Poland",           "country": "Poland",       "discipline": "rally"},
    Location.SPAIN:          {"display_name": "Spain",            "country": "Spain",        "discipline": "rally"},
    Location.SWEDEN:         {"display_name": "Sweden",           "country": "Sweden",       "discipline": "rally"},
    Location.NEW_ENGLAND:    {"display_name": "New England",      "country": "USA",          "discipline": "rally"},
    Location.WALES:          {"display_name": "Wales",            "country": "UK",           "discipline": "rally"},
    Location.SCOTLAND:       {"display_name": "Scotland",         "country": "UK",           "discipline": "rally"},
    Location.METTET:         {"display_name": "Mettet",           "country": "Belgium",      "discipline": "rallycross"},
    Location.TROIS_RIVIERES: {"display_name": "Trois-Rivières",   "country": "Canada",       "discipline": "rallycross"},
    Location.LYDDEN_HILL:    {"display_name": "Lydden Hill",      "country": "England",      "discipline": "rallycross"},
    Location.SILVERSTONE:    {"display_name": "Silverstone",      "country": "England",      "discipline": "rallycross"},
    Location.LOHEAC:         {"display_name": "Loheac",           "country": "France",       "discipline": "rallycross"},
    Location.ESTERING:       {"display_name": "Estering",         "country": "Germany",      "discipline": "rallycross"},
    Location.BIKERNIEKI:     {"display_name": "Bikernieki",       "country": "Latvia",       "discipline": "rallycross"},
    Location.HELL:           {"display_name": "Hell",             "country": "Norway",       "discipline": "rallycross"},
    Location.MONTALEGRE:     {"display_name": "Montalegre",       "country": "Portugal",     "discipline": "rallycross"},
    Location.KILLARNEY:      {"display_name": "Killarney",        "country": "South Africa", "discipline": "rallycross"},
    Location.BARCELONA:      {"display_name": "Barcelona",        "country": "Spain",        "discipline": "rallycross"},
    Location.HOLJES:         {"display_name": "Höljes",           "country": "Sweden",       "discipline": "rallycross"},
    Location.YAS_MARINA:     {"display_name": "Yas Marina",       "country": "UAE",          "discipline": "rallycross"},
    Location.TWIN_PEAKS:     {"display_name": "Twin Peaks",       "country": "USA",          "discipline": "rally"},
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
    CAMINO_A_LA_PUERTA                       = 604
    CAMINO_DE_ACANTILADOS_Y_ROCAS            = 605
    EL_RODEO                                 = 606
    LA_MERCED                                = 607
    CAMINO_DE_ACANTILADOS_Y_ROCAS_INVERSO    = 608
    VALLE_DE_LOS_PUENTES                     = 573
    VALLE_DE_LOS_PUENTES_A_LA_INVERSA        = 609
    MIRAFLORES                               = 610
    SAN_ISIDRO                               = 611
    CAMINO_A_CONETA                          = 612
    HUILLAPRIMA                              = 613

    # AUSTRALIA
    MOUNT_KAYE_PASS                          = 568
    MOUNT_KAYE_PASS_REVERSE                  = 584
    ROCKTON_PLAINS                           = 585
    YAMBULLA_MOUNTAIN_DESCENT                = 586
    YAMBULLA_MOUNTAIN_ASCENT                 = 587
    ROCKTON_PLAINS_REVERSE                   = 588
    CHANDLERS_CREEK                          = 569
    CHANDLERS_CREEK_REVERSE                  = 589
    NOORINBEE_RIDGE_ASCENT                   = 590
    TAYLOR_FARM_SPRINT                       = 591
    BONDI_FOREST                             = 592
    NOORINBEE_RIDGE_DESCENT                  = 593

    # FINLAND
    KONTINJARVI                              = 505
    HAMELAHTI                                = 506
    KAILAJARVI                               = 507
    JYRKYSJARVI                              = 508
    NAARAJARVI                               = 509
    PASKURI                                  = 510
    KAKARISTO                                = 511
    PITKAJARVI                               = 512
    ISO_OKSJARVI                             = 513
    JARVENKYLA                               = 514
    KOTAJARVI                                = 515
    OKSALA                                   = 516

    # GERMANY
    OBERSTEIN                                = 472
    FRAUENBERG                               = 489
    WALDAUFSTIEG                             = 490
    KREUZUNGSRING_REVERSE                    = 491
    KREUZUNGSRING                            = 492
    WALDABSTIEG                              = 493
    HAMMERSTEIN                              = 480
    RUSCHBERG                                = 494
    VERBUNDSRING                             = 495
    INNERER_FELD_SPRINT                      = 496
    INNERER_FELD_SPRINT_UMGEKEHRT            = 497
    VERBUNDSRING_REVERSE                     = 498

    # GREECE
    ANODOU_FARMAKAS                          = 471
    KATHODO_LEONTIOU                         = 460
    POMONA_EKRIXI                            = 461
    FOURKETA_KOURVA                          = 462
    KORYFI_DAFNI                             = 463
    AMPELONAS_ORMI                           = 464
    PERASMA_PLATANI                          = 465
    TSIRISTRA_THEA                           = 466
    OUREA_SPEVSI                             = 467
    PEDINES_EPIDAXI                          = 468
    ABIES_KOILEDA                            = 469
    YPSONA_TOU_DASOS                         = 470

    # MONTE_CARLO
    PRA_D_ALART                              = 435
    COL_DE_TURINI_DEPART                     = 449
    GORDOLON_COURTE_MONTEE                   = 450
    COL_DE_TURINI_SPRINT_EN_DESCENTE         = 451
    COL_DE_TURINI_SPRINT_EN_MONTEE           = 452
    COL_DE_TURINI_DESCENTE                   = 453
    VALLEE_DESCENDANTE                       = 454
    ROUTE_DE_TURINI                          = 455
    COL_DE_TURINI_DEPART_EN_DESCENTE         = 456
    APPROCHE_DU_COL_DE_TURINI_MONTEE         = 457
    ROUTE_DE_TURINI_DESCENTE                 = 458
    ROUTE_DE_TURINI_MONTEE                   = 459

    # NEW_ZEALAND
    TE_AWANGA_FORWARD                        = 570
    OCEAN_BEACH                              = 594
    TE_AWANGA_SPRINT_FORWARD                 = 595
    OCEAN_BEACH_SPRINT_FORWARD               = 596
    OCEAN_BEACH_SPRINT_REVERSE               = 597
    TE_AWANGA_SPRINT_REVERSE                 = 598
    WAIMARAMA_POINT_FORWARD                  = 571
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
    BORYSIK                                  = 618
    JOZEFIN                                  = 619
    JEZIORO_ROTCZE                           = 620
    ZIENKI                                   = 621
    CZARNY_LAS                               = 622
    LEJNO                                    = 623
    JAGODNO                                  = 624
    JEZIORO_LUKIE                            = 625

    # SPAIN
    COMIENZO_DE_BELLRIU                      = 566
    FINAL_DE_BELLRIU                         = 574
    ASCENSO_POR_VALLE_EL_GUALET              = 575
    VINEDOS_DENTRO_DEL_VALLE_PARRA           = 576
    ASCENSO_BOSQUE_MONTVERD                  = 577
    SALIDA_DESDE_MONTVERD                    = 578
    CENTENERA                                = 567
    CAMINO_A_CENTENERA                       = 579
    DESCENSO_POR_CARRETERA                   = 580
    VINEDOS_DARDENYA                         = 581
    VINEDOS_DARDENYA_INVERSA                 = 582
    SUBIDA_POR_CARRETERA                     = 583

    # SWEDEN
    RANSBYSATER                              = 517
    NORRASKOGA                               = 518
    ALGSJON_SPRINT                           = 519
    STOR_JANGEN_SPRINT_REVERSE               = 520
    STOR_JANGEN_SPRINT                       = 521
    SKOGSRALLYT                              = 522
    HAMRA                                    = 523
    LYSVIK                                   = 524
    ELGSJON                                  = 525
    BJORKLANGEN                              = 526
    OSTRA_HINNSJON                           = 527
    ALGSJON                                  = 528

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

    # WALES
    SWEET_LAMB                               = 437
    GEUFRON_FOREST                           = 438
    PANT_MAWR                                = 439
    BIDNO_MOORLAND_REVERSE                   = 440
    BIDNO_MOORLAND                           = 441
    PANT_MAWR_REVERSE                        = 442
    RIVER_SEVERN_VALLEY                      = 443
    BRONFELEN                                = 444
    FFERM_WYNT                               = 445
    DYFFRYN_AFON_REVERSE                     = 446
    DYFFRYN_AFON                             = 447
    FFERM_WYNT_REVERSE                       = 448

    # SCOTLAND
    SOUTH_MORNINGSIDE                        = 657
    SOUTH_MORNINGSIDE_REVERSE                = 658
    OLD_BUTTERSTONE_MUIR                     = 659
    ROSEBANK_FARM                            = 660
    ROSEBANK_FARM_REVERSE                    = 661
    OLD_BUTTERSTONE_MUIR_REVERSE             = 662
    NEWHOUSE_BRIDGE                          = 663
    NEWHOUSE_BRIDGE_REVERSE                  = 664
    GLENCASTLE_FARM                          = 665
    ANNBANK_STATION                          = 666
    ANNBANK_STATION_REVERSE                  = 667
    GLENCASTLE_FARM_REVERSE                  = 668

    # RALLYCROSS
    METTET                                   = 172
    TROIS_RIVIERES                           = 158
    LYDDEN_HILL                              = 131
    SILVERSTONE                              = 171
    LOHEAC                                   = 152
    ESTERING                                 = 173
    BIKERNIEKI                               = 174
    HELL                                     = 142
    MONTALEGRE                               = 153
    KILLARNEY                                = 175
    BARCELONA                                = 154
    HOLJES                                   = 141
    YAS_MARINA                               = 176

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
    # Argentina
    Track.LAS_JUNTAS: {"display_name": "Las Juntas", "location": Location.ARGENTINA, "length_km": 8.25},
    Track.CAMINO_A_LA_PUERTA: {"display_name": "Camino a La Puerta", "location": Location.ARGENTINA, "length_km": 8.25},
    Track.CAMINO_DE_ACANTILADOS_Y_ROCAS: {"display_name": "Camino de acantilados y rocas", "location": Location.ARGENTINA, "length_km": 5.30},
    Track.EL_RODEO: {"display_name": "El Rodeo", "location": Location.ARGENTINA, "length_km": 2.84},
    Track.LA_MERCED: {"display_name": "La Merced", "location": Location.ARGENTINA, "length_km": 2.84},
    Track.CAMINO_DE_ACANTILADOS_Y_ROCAS_INVERSO: {"display_name": "Camino de acantilados y rocas inverso", "location": Location.ARGENTINA, "length_km": 5.30},
    Track.VALLE_DE_LOS_PUENTES: {"display_name": "Valle de los puentes", "location": Location.ARGENTINA, "length_km": 7.98},
    Track.VALLE_DE_LOS_PUENTES_A_LA_INVERSA: {"display_name": "Valle de los puentes a la inversa", "location": Location.ARGENTINA, "length_km": 7.98},
    Track.MIRAFLORES: {"display_name": "Miraflores", "location": Location.ARGENTINA, "length_km": 3.35},
    Track.SAN_ISIDRO: {"display_name": "San Isidro", "location": Location.ARGENTINA, "length_km": 4.48},
    Track.CAMINO_A_CONETA: {"display_name": "Camino a Coneta", "location": Location.ARGENTINA, "length_km": 4.48},
    Track.HUILLAPRIMA: {"display_name": "Huillaprima", "location": Location.ARGENTINA, "length_km": 3.35},

    # Australia
    Track.MOUNT_KAYE_PASS: {"display_name": "Mount Kaye Pass", "location": Location.AUSTRALIA, "length_km": 12.50},
    Track.MOUNT_KAYE_PASS_REVERSE: {"display_name": "Mount Kaye Pass Reverse", "location": Location.AUSTRALIA, "length_km": 12.50},
    Track.ROCKTON_PLAINS: {"display_name": "Rockton Plains", "location": Location.AUSTRALIA, "length_km": 6.89},
    Track.YAMBULLA_MOUNTAIN_DESCENT: {"display_name": "Yambulla Mountain Descent", "location": Location.AUSTRALIA, "length_km": 6.64},
    Track.YAMBULLA_MOUNTAIN_ASCENT: {"display_name": "Yambulla Mountain Ascent", "location": Location.AUSTRALIA, "length_km": 6.64},
    Track.ROCKTON_PLAINS_REVERSE: {"display_name": "Rockton Plains Reverse", "location": Location.AUSTRALIA, "length_km": 6.89},
    Track.CHANDLERS_CREEK: {"display_name": "Chandlers Creek", "location": Location.AUSTRALIA, "length_km": 12.34},
    Track.CHANDLERS_CREEK_REVERSE: {"display_name": "Chandlers Creek Reverse", "location": Location.AUSTRALIA, "length_km": 12.34},
    Track.NOORINBEE_RIDGE_ASCENT: {"display_name": "Noorinbee Ridge Ascent", "location": Location.AUSTRALIA, "length_km": 5.28},
    Track.TAYLOR_FARM_SPRINT: {"display_name": "Taylor Farm Sprint", "location": Location.AUSTRALIA, "length_km": 7.01},
    Track.BONDI_FOREST: {"display_name": "Bondi Forest", "location": Location.AUSTRALIA, "length_km": 7.01},
    Track.NOORINBEE_RIDGE_DESCENT: {"display_name": "Noorinbee Ridge Descent", "location": Location.AUSTRALIA, "length_km": 5.28},

    # Finland
    Track.KONTINJARVI: {"display_name": "Kontinjärvi", "location": Location.FINLAND, "length_km": 15.05},
    Track.HAMELAHTI: {"display_name": "Hämelahti", "location": Location.FINLAND, "length_km": 14.96},
    Track.KAILAJARVI: {"display_name": "Kailajärvi", "location": Location.FINLAND, "length_km": 7.51},
    Track.JYRKYSJARVI: {"display_name": "Jyrkysjärvi", "location": Location.FINLAND, "length_km": 7.55},
    Track.NAARAJARVI: {"display_name": "Naarajärvi", "location": Location.FINLAND, "length_km": 7.43},
    Track.PASKURI: {"display_name": "Paskuri", "location": Location.FINLAND, "length_km": 7.34},
    Track.KAKARISTO: {"display_name": "Kakaristo", "location": Location.FINLAND, "length_km": 16.20},
    Track.PITKAJARVI: {"display_name": "Pitkäjärvi", "location": Location.FINLAND, "length_km": 16.20},
    Track.ISO_OKSJARVI: {"display_name": "Iso Oksjärvi", "location": Location.FINLAND, "length_km": 8.04},
    Track.JARVENKYLA: {"display_name": "Järvenkylä", "location": Location.FINLAND, "length_km": 8.05},
    Track.KOTAJARVI: {"display_name": "Kotajärvi", "location": Location.FINLAND, "length_km": 8.10},
    Track.OKSALA: {"display_name": "Oksala", "location": Location.FINLAND, "length_km": 8.10},

    # Germany
    Track.OBERSTEIN: {"display_name": "Oberstein", "location": Location.GERMANY, "length_km": 11.67},
    Track.FRAUENBERG: {"display_name": "Frauenberg", "location": Location.GERMANY, "length_km": 11.67},
    Track.WALDAUFSTIEG: {"display_name": "Waldaufstieg", "location": Location.GERMANY, "length_km": 5.39},
    Track.KREUZUNGSRING_REVERSE: {"display_name": "Kreuzungsring Reverse", "location": Location.GERMANY, "length_km": 6.31},
    Track.KREUZUNGSRING: {"display_name": "Kreuzungsring", "location": Location.GERMANY, "length_km": 6.31},
    Track.WALDABSTIEG: {"display_name": "Waldabstieg", "location": Location.GERMANY, "length_km": 5.39},
    Track.HAMMERSTEIN: {"display_name": "Hammerstein", "location": Location.GERMANY, "length_km": 10.81},
    Track.RUSCHBERG: {"display_name": "Ruschberg", "location": Location.GERMANY, "length_km": 10.70},
    Track.VERBUNDSRING: {"display_name": "Verbundsring", "location": Location.GERMANY, "length_km": 5.85},
    Track.INNERER_FELD_SPRINT: {"display_name": "Innerer Feld-Sprint", "location": Location.GERMANY, "length_km": 5.56},
    Track.INNERER_FELD_SPRINT_UMGEKEHRT: {"display_name": "Innerer Feld-Sprint (umgekehrt)", "location": Location.GERMANY, "length_km": 5.56},
    Track.VERBUNDSRING_REVERSE: {"display_name": "Verbundsring Reverse", "location": Location.GERMANY, "length_km": 5.85},

    # Greece
    Track.ANODOU_FARMAKAS: {"display_name": "Anodou Farmakas", "location": Location.GREECE, "length_km": 9.60},
    Track.KATHODO_LEONTIOU: {"display_name": "Kathodo Leontiou", "location": Location.GREECE, "length_km": 9.60},
    Track.POMONA_EKRIXI: {"display_name": "Pomona Ekrixi", "location": Location.GREECE, "length_km": 5.09},
    Track.FOURKETA_KOURVA: {"display_name": "Fourkéta Kourva", "location": Location.GREECE, "length_km": 4.80},
    Track.KORYFI_DAFNI: {"display_name": "Koryfi Dafni", "location": Location.GREECE, "length_km": 4.50},
    Track.AMPELONAS_ORMI: {"display_name": "Ampelonas Ormi", "location": Location.GREECE, "length_km": 4.95},
    Track.PERASMA_PLATANI: {"display_name": "Perasma Platani", "location": Location.GREECE, "length_km": 10.69},
    Track.TSIRISTRA_THEA: {"display_name": "Tsiristra Théa", "location": Location.GREECE, "length_km": 10.36},
    Track.OUREA_SPEVSI: {"display_name": "Ourea Spevsi", "location": Location.GREECE, "length_km": 5.74},
    Track.PEDINES_EPIDAXI: {"display_name": "Pedines Epidaxi", "location": Location.GREECE, "length_km": 5.38},
    Track.ABIES_KOILEDA: {"display_name": "Abies Koiléda", "location": Location.GREECE, "length_km": 7.09},
    Track.YPSONA_TOU_DASOS: {"display_name": "Ypsona tou Dasos", "location": Location.GREECE, "length_km": 6.59},

    # Monaco
    Track.PRA_D_ALART: {"display_name": "Pra d'Alart", "location": Location.MONTE_CARLO, "length_km": 9.83},
    Track.COL_DE_TURINI_DEPART: {"display_name": "Col de Turini Départ", "location": Location.MONTE_CARLO, "length_km": 9.83},
    Track.GORDOLON_COURTE_MONTEE: {"display_name": "Gordolon - Courte montée", "location": Location.MONTE_CARLO, "length_km": 5.17},
    Track.COL_DE_TURINI_SPRINT_EN_DESCENTE: {"display_name": "Col de Turini - Sprint en descente", "location": Location.MONTE_CARLO, "length_km": 4.73},
    Track.COL_DE_TURINI_SPRINT_EN_MONTEE: {"display_name": "Col de Turini sprint en Montée", "location": Location.MONTE_CARLO, "length_km": 4.73},
    Track.COL_DE_TURINI_DESCENTE: {"display_name": "Col de Turini - Descente", "location": Location.MONTE_CARLO, "length_km": 5.17},
    Track.VALLEE_DESCENDANTE: {"display_name": "Vallée descendante", "location": Location.MONTE_CARLO, "length_km": 10.87},
    Track.ROUTE_DE_TURINI: {"display_name": "Route de Turini", "location": Location.MONTE_CARLO, "length_km": 10.87},
    Track.COL_DE_TURINI_DEPART_EN_DESCENTE: {"display_name": "Col de Turini - Départ en descente", "location": Location.MONTE_CARLO, "length_km": 6.85},
    Track.APPROCHE_DU_COL_DE_TURINI_MONTEE: {"display_name": "Approche du Col de Turini - Montée", "location": Location.MONTE_CARLO, "length_km": 3.95},
    Track.ROUTE_DE_TURINI_DESCENTE: {"display_name": "Route de Turini Descente", "location": Location.MONTE_CARLO, "length_km": 3.95},
    Track.ROUTE_DE_TURINI_MONTEE: {"display_name": "Route de Turini Montée", "location": Location.MONTE_CARLO, "length_km": 6.84},

    # New Zealand
    Track.TE_AWANGA_FORWARD: {"display_name": "Te Awanga Forward", "location": Location.NEW_ZEALAND, "length_km": 11.48},
    Track.OCEAN_BEACH: {"display_name": "Ocean Beach", "location": Location.NEW_ZEALAND, "length_km": 11.48},
    Track.TE_AWANGA_SPRINT_FORWARD: {"display_name": "Te Awanga Sprint Forward", "location": Location.NEW_ZEALAND, "length_km": 4.79},
    Track.OCEAN_BEACH_SPRINT_FORWARD: {"display_name": "Ocean Beach Sprint Forward", "location": Location.NEW_ZEALAND, "length_km": 6.61},
    Track.OCEAN_BEACH_SPRINT_REVERSE: {"display_name": "Ocean Beach Sprint Reverse", "location": Location.NEW_ZEALAND, "length_km": 6.61},
    Track.TE_AWANGA_SPRINT_REVERSE: {"display_name": "Te Awanga Sprint Reverse", "location": Location.NEW_ZEALAND, "length_km": 4.79},
    Track.WAIMARAMA_POINT_FORWARD: {"display_name": "Waimarama Point Forward", "location": Location.NEW_ZEALAND, "length_km": 16.06},
    Track.WAIMARAMA_POINT_REVERSE: {"display_name": "Waimarama Point Reverse", "location": Location.NEW_ZEALAND, "length_km": 16.06},
    Track.ELSTHORPE_SPRINT_FORWARD: {"display_name": "Elsthorpe Sprint Forward", "location": Location.NEW_ZEALAND, "length_km": 7.32},
    Track.WAIMARAMA_SPRINT_FORWARD: {"display_name": "Waimarama Sprint Forward", "location": Location.NEW_ZEALAND, "length_km": 8.81},
    Track.WAIMARAMA_SPRINT_REVERSE: {"display_name": "Waimarama Sprint Reverse", "location": Location.NEW_ZEALAND, "length_km": 8.81},
    Track.ELSTHORPE_SPRINT_REVERSE: {"display_name": "Elsthorpe Sprint Reverse", "location": Location.NEW_ZEALAND, "length_km": 7.32},

    # Poland
    Track.ZAROBKA: {"display_name": "Zaróbka", "location": Location.POLAND, "length_km": 16.46},
    Track.ZAGORZE: {"display_name": "Zagórze", "location": Location.POLAND, "length_km": 16.46},
    Track.KOPINA: {"display_name": "Kopina", "location": Location.POLAND, "length_km": 7.03},
    Track.MARYNKA: {"display_name": "Marynka", "location": Location.POLAND, "length_km": 9.25},
    Track.BORYSIK: {"display_name": "Borysik", "location": Location.POLAND, "length_km": 9.25},
    Track.JOZEFIN: {"display_name": "Józefin", "location": Location.POLAND, "length_km": 7.03},
    Track.JEZIORO_ROTCZE: {"display_name": "Jezioro Rotcze", "location": Location.POLAND, "length_km": 13.42},
    Track.ZIENKI: {"display_name": "Zienki", "location": Location.POLAND, "length_km": 13.42},
    Track.CZARNY_LAS: {"display_name": "Czarny Las", "location": Location.POLAND, "length_km": 6.62},
    Track.LEJNO: {"display_name": "Lejno", "location": Location.POLAND, "length_km": 6.82},
    Track.JAGODNO: {"display_name": "Jagodno", "location": Location.POLAND, "length_km": 6.82},
    Track.JEZIORO_LUKIE: {"display_name": "Jezioro Lukie", "location": Location.POLAND, "length_km": 6.62},

    # Spain
    Track.COMIENZO_DE_BELLRIU: {"display_name": "Comienzo De Bellriu", "location": Location.SPAIN, "length_km": 14.34},
    Track.FINAL_DE_BELLRIU: {"display_name": "Final de Bellriu", "location": Location.SPAIN, "length_km": 14.34},
    Track.ASCENSO_POR_VALLE_EL_GUALET: {"display_name": "Ascenso por valle el Gualet", "location": Location.SPAIN, "length_km": 7.00},
    Track.VINEDOS_DENTRO_DEL_VALLE_PARRA: {"display_name": "Viñedos dentro del valle Parra", "location": Location.SPAIN, "length_km": 6.81},
    Track.ASCENSO_BOSQUE_MONTVERD: {"display_name": "Ascenso bosque Montverd", "location": Location.SPAIN, "length_km": 6.81},
    Track.SALIDA_DESDE_MONTVERD: {"display_name": "Salida desde Montverd", "location": Location.SPAIN, "length_km": 7.00},
    Track.CENTENERA: {"display_name": "Centenera", "location": Location.SPAIN, "length_km": 10.57},
    Track.CAMINO_A_CENTENERA: {"display_name": "Camino a Centenera", "location": Location.SPAIN, "length_km": 10.57},
    Track.DESCENSO_POR_CARRETERA: {"display_name": "Descenso por carretera", "location": Location.SPAIN, "length_km": 4.58},
    Track.VINEDOS_DARDENYA: {"display_name": "Viñedos Dardenyà", "location": Location.SPAIN, "length_km": 6.55},
    Track.VINEDOS_DARDENYA_INVERSA: {"display_name": "Viñedos Dardenyà inversa", "location": Location.SPAIN, "length_km": 6.55},
    Track.SUBIDA_POR_CARRETERA: {"display_name": "Subida por carretera", "location": Location.SPAIN, "length_km": 4.58},

    # Sweden
    Track.RANSBYSATER: {"display_name": "Ransbysäter", "location": Location.SWEDEN, "length_km": 11.98},
    Track.NORRASKOGA: {"display_name": "Norraskoga", "location": Location.SWEDEN, "length_km": 11.98},
    Track.ALGSJON_SPRINT: {"display_name": "Älgsjön Sprint", "location": Location.SWEDEN, "length_km": 5.25},
    Track.STOR_JANGEN_SPRINT_REVERSE: {"display_name": "Stor-jangen Sprint Reverse", "location": Location.SWEDEN, "length_km": 6.69},
    Track.STOR_JANGEN_SPRINT: {"display_name": "Stor-jangen Sprint", "location": Location.SWEDEN, "length_km": 6.69},
    Track.SKOGSRALLYT: {"display_name": "Skogsrallyt", "location": Location.SWEDEN, "length_km": 5.25},
    Track.HAMRA: {"display_name": "Hamra", "location": Location.SWEDEN, "length_km": 12.34},
    Track.LYSVIK: {"display_name": "Lysvik", "location": Location.SWEDEN, "length_km": 12.34},
    Track.ELGSJON: {"display_name": "Elgsjön", "location": Location.SWEDEN, "length_km": 7.28},
    Track.BJORKLANGEN: {"display_name": "Björklangen", "location": Location.SWEDEN, "length_km": 5.19},
    Track.OSTRA_HINNSJON: {"display_name": "Östra Hinnsjön", "location": Location.SWEDEN, "length_km": 5.19},
    Track.ALGSJON: {"display_name": "Älgsjön", "location": Location.SWEDEN, "length_km": 7.28},

    # USA
    Track.NORTH_FORK_PASS: {"display_name": "North Fork Pass", "location": Location.NEW_ENGLAND, "length_km": 12.50},
    Track.NORTH_FORK_PASS_REVERSE: {"display_name": "North Fork Pass Reverse", "location": Location.NEW_ENGLAND, "length_km": 12.50},
    Track.HANCOCK_CREEK_BURST: {"display_name": "Hancock Creek Burst", "location": Location.NEW_ENGLAND, "length_km": 6.89},
    Track.FULLER_MOUNTAIN_DESCENT: {"display_name": "Fuller Mountain Descent", "location": Location.NEW_ENGLAND, "length_km": 6.64},
    Track.FULLER_MOUNTAIN_ASCENT: {"display_name": "Fuller Mountain Ascent", "location": Location.NEW_ENGLAND, "length_km": 6.64},
    Track.FURY_LAKE_DEPART: {"display_name": "Fury Lake Depart", "location": Location.NEW_ENGLAND, "length_km": 6.89},
    Track.BEAVER_CREEK_TRAIL_FORWARD: {"display_name": "Beaver Creek Trail Forward", "location": Location.NEW_ENGLAND, "length_km": 12.86},
    Track.BEAVER_CREEK_TRAIL_REVERSE: {"display_name": "Beaver Creek Trail Reverse", "location": Location.NEW_ENGLAND, "length_km": 12.86},
    Track.HANCOCK_HILL_SPRINT_FORWARD: {"display_name": "Hancock Hill Sprint Forward", "location": Location.NEW_ENGLAND, "length_km": 6.01},
    Track.TOLT_VALLEY_SPRINT_REVERSE: {"display_name": "Tolt Valley Sprint Reverse", "location": Location.NEW_ENGLAND, "length_km": 6.10},
    Track.TOLT_VALLEY_SPRINT_FORWARD: {"display_name": "Tolt Valley Sprint Forward", "location": Location.NEW_ENGLAND, "length_km": 6.10},
    Track.HANCOCK_HILL_SPRINT_REVERSE: {"display_name": "Hancock Hill Sprint Reverse", "location": Location.NEW_ENGLAND, "length_km": 6.01},

    # Wales
    Track.SWEET_LAMB: {"display_name": "Sweet Lamb", "location": Location.WALES, "length_km": 9.90},
    Track.GEUFRON_FOREST: {"display_name": "Geufron Forest", "location": Location.WALES, "length_km": 10.00},
    Track.PANT_MAWR: {"display_name": "Pant Mawr", "location": Location.WALES, "length_km": 4.70},
    Track.BIDNO_MOORLAND_REVERSE: {"display_name": "Bidno Moorland Reverse", "location": Location.WALES, "length_km": 4.80},
    Track.BIDNO_MOORLAND: {"display_name": "Bidno Moorland", "location": Location.WALES, "length_km": 4.90},
    Track.PANT_MAWR_REVERSE: {"display_name": "Pant Mawr Reverse", "location": Location.WALES, "length_km": 5.10},
    Track.RIVER_SEVERN_VALLEY: {"display_name": "River Severn Valley", "location": Location.WALES, "length_km": 11.40},
    Track.BRONFELEN: {"display_name": "Bronfelen", "location": Location.WALES, "length_km": 11.40},
    Track.FFERM_WYNT: {"display_name": "Fferm Wynt", "location": Location.WALES, "length_km": 5.70},
    Track.DYFFRYN_AFON_REVERSE: {"display_name": "Dyffryn Afon Reverse", "location": Location.WALES, "length_km": 5.70},
    Track.DYFFRYN_AFON: {"display_name": "Dyffryn Afon", "location": Location.WALES, "length_km": 5.70},
    Track.FFERM_WYNT_REVERSE: {"display_name": "Fferm Wynt Reverse", "location": Location.WALES, "length_km": 5.70},

    # Scotland
    Track.SOUTH_MORNINGSIDE: {"display_name": "South Morningside", "location": Location.SCOTLAND, "length_km": 12.58},
    Track.SOUTH_MORNINGSIDE_REVERSE: {"display_name": "South Morningside Reverse", "location": Location.SCOTLAND, "length_km": 12.66},
    Track.OLD_BUTTERSTONE_MUIR: {"display_name": "Old Butterstone Muir", "location": Location.SCOTLAND, "length_km": 5.82},
    Track.ROSEBANK_FARM: {"display_name": "Rosebank Farm", "location": Location.SCOTLAND, "length_km": 7.16},
    Track.ROSEBANK_FARM_REVERSE: {"display_name": "Rosebank Farm Reverse", "location": Location.SCOTLAND, "length_km": 6.96},
    Track.OLD_BUTTERSTONE_MUIR_REVERSE: {"display_name": "Old Butterstone Muir Reverse", "location": Location.SCOTLAND, "length_km": 5.66},
    Track.NEWHOUSE_BRIDGE: {"display_name": "Newhouse Bridge", "location": Location.SCOTLAND, "length_km": 12.86},
    Track.NEWHOUSE_BRIDGE_REVERSE: {"display_name": "Newhouse Bridge Reverse", "location": Location.SCOTLAND, "length_km": 12.98},
    Track.GLENCASTLE_FARM: {"display_name": "Glencastle Farm", "location": Location.SCOTLAND, "length_km": 5.25},
    Track.ANNBANK_STATION: {"display_name": "Annbank Station", "location": Location.SCOTLAND, "length_km": 7.77},
    Track.ANNBANK_STATION_REVERSE: {"display_name": "Annbank Station Reverse", "location": Location.SCOTLAND, "length_km": 7.59},
    Track.GLENCASTLE_FARM_REVERSE: {"display_name": "Glencastle Farm Reverse", "location": Location.SCOTLAND, "length_km": 5.24},

    # Rallycross
    Track.METTET: {"display_name": "Mettet", "location": Location.METTET, "length_km": 1.15, "discipline": "rallycross"},
    Track.TROIS_RIVIERES: {"display_name": "Trois-Rivières", "location": Location.TROIS_RIVIERES, "length_km": 1.35, "discipline": "rallycross"},
    Track.LYDDEN_HILL: {"display_name": "Lydden Hill", "location": Location.LYDDEN_HILL, "length_km": 1.40, "discipline": "rallycross"},
    Track.SILVERSTONE: {"display_name": "Silverstone", "location": Location.SILVERSTONE, "length_km": 0.97, "discipline": "rallycross"},
    Track.LOHEAC: {"display_name": "Lohéac Bretagne", "location": Location.LOHEAC, "length_km": 1.09, "discipline": "rallycross"},
    Track.ESTERING: {"display_name": "Estering", "location": Location.ESTERING, "length_km": 0.95, "discipline": "rallycross"},
    Track.BIKERNIEKI: {"display_name": "Bikernieki", "location": Location.BIKERNIEKI, "length_km": 1.29, "discipline": "rallycross"},
    Track.HELL: {"display_name": "Hell", "location": Location.HELL, "length_km": 1.02, "discipline": "rallycross"},
    Track.MONTALEGRE: {"display_name": "Montalegre", "location": Location.MONTALEGRE, "length_km": 0.95, "discipline": "rallycross"},
    Track.KILLARNEY: {"display_name": "Killarney International Raceway", "location": Location.KILLARNEY, "length_km": 1.07, "discipline": "rallycross"},
    Track.BARCELONA: {"display_name": "Circuit de Barcelona-Catalunya", "location": Location.BARCELONA, "length_km": 1.13, "discipline": "rallycross"},
    Track.HOLJES: {"display_name": "Höljes", "location": Location.HOLJES, "length_km": 1.21, "discipline": "rallycross"},
    Track.YAS_MARINA: {"display_name": "Yas Marina Circuit", "location": Location.YAS_MARINA, "length_km": 1.00, "discipline": "rallycross"},
}


# ---------------------------------------------------------------------------
# Vehicle classes — Requirements.Value maps to a vehicle class
# ---------------------------------------------------------------------------

class VehicleClass(IntEnum):
    """Vehicle class IDs used in challenge Requirements.

    Confirmed by in-game testing against the real EgoNet protocol.
    Invalid IDs crash the game client.
    """
    # Rally
    H1_FWD         = 101
    H2_FWD         = 100
    H2_RWD         = 97
    H3_RWD         = 98
    F2_KIT_CAR     = 86
    GROUP_B_RWD    = 74
    GROUP_B_4WD    = 73
    R2             = 99
    GROUP_A        = 72
    NR4_R4         = 96
    CC_4WD         = 94
    R5             = 93
    RGT            = 107

    # Rallycross
    RX_SUPER_1600     = 92
    CROSS_KART        = 95
    GROUP_B_RX        = 89
    RX2               = 102
    RX_SUPERCARS      = 78
    RX_SUPERCARS_2019 = 108

    @property
    def label(self) -> str:
        return _VEHICLE_CLASS_LABELS[self]

    def __str__(self) -> str:
        return self.label


_VEHICLE_CLASS_LABELS: Dict[VehicleClass, str] = {
    # Rally
    VehicleClass.H1_FWD:        "H1 FWD",
    VehicleClass.H2_FWD:        "H2 FWD",
    VehicleClass.H2_RWD:        "H2 RWD",
    VehicleClass.H3_RWD:        "H3 RWD",
    VehicleClass.F2_KIT_CAR:    "F2 Kit Car",
    VehicleClass.GROUP_B_RWD:   "Group B RWD",
    VehicleClass.GROUP_B_4WD:   "Group B 4WD",
    VehicleClass.R2:            "R2",
    VehicleClass.GROUP_A:       "Group A",
    VehicleClass.NR4_R4:        "NR4/R4",
    VehicleClass.CC_4WD:        "2000cc 4WD",
    VehicleClass.R5:            "R5",
    VehicleClass.RGT:           "Rally GT",

    # Rallycross
    VehicleClass.RX_SUPER_1600: "RX Super 1600",
    VehicleClass.CROSS_KART:    "Cross Kart",
    VehicleClass.GROUP_B_RX:    "Group B Rallycross",
    VehicleClass.RX2:           "RX2",
    VehicleClass.RX_SUPERCARS:  "RX Supercars",
    VehicleClass.RX_SUPERCARS_2019: "RX Supercars 2019",
}


# ---------------------------------------------------------------------------
# Canonical car-class label resolution
# ---------------------------------------------------------------------------
#
# Single source of truth shared by the web UI (event creation + validation)
# and the game server (challenge building), so the set of resolvable labels
# can never drift from the confirmed IDs.

# Every VehicleClass member is confirmed in-game.  An ID outside this set — or
# a missing/empty Requirement — crashes the game client, so callers must never
# emit one.
CONFIRMED_VEHICLE_CLASS_IDS: frozenset = frozenset(int(vc) for vc in VehicleClass)

# label (lower-cased) -> confirmed VehicleClassId.  Seeded from the enum labels,
# then extended with alternate spellings used by the web UI / seed data.  Each
# alias is an exact synonym for a confirmed class — NOT a fallback.
_VCLASS_LABEL_TO_ID: Dict[str, int] = {vc.label.lower(): int(vc) for vc in VehicleClass}
_VCLASS_LABEL_TO_ID.update({
    "h1 (fwd)":           int(VehicleClass.H1_FWD),
    "h2 (fwd)":           int(VehicleClass.H2_FWD),
    "h2 (rwd)":           int(VehicleClass.H2_RWD),
    "h3 (rwd)":           int(VehicleClass.H3_RWD),
    "group b (4wd)":      int(VehicleClass.GROUP_B_4WD),
    "group b (awd)":      int(VehicleClass.GROUP_B_4WD),
    "group b (rwd)":      int(VehicleClass.GROUP_B_RWD),
    "group b rallycross": int(VehicleClass.GROUP_B_RX),
    "f2 kit cars":        int(VehicleClass.F2_KIT_CAR),
    "rally gt":           int(VehicleClass.NR4_R4),  # no confirmed Rally GT ID
    "2000cc":             int(VehicleClass.CC_4WD),  # web UI label for 2000cc 4WD
    "2000cc 4wd":         int(VehicleClass.CC_4WD),
    "4wd <= 2000cc":      int(VehicleClass.CC_4WD),
    "cross kart":         int(VehicleClass.CROSS_KART),
})


def vehicle_class_id_for_label(label: str) -> Optional[int]:
    """Resolve a car-class label to a confirmed VehicleClassId, or None.

    Returns None when the label doesn't correspond to a class the game client
    can enforce.  Callers MUST treat None as "do not serve this event" — never
    substitute a default class, since that would silently change the event's
    rules and an invalid/empty requirement crashes the game.
    """
    return _VCLASS_LABEL_TO_ID.get(label.strip().lower())


# ---------------------------------------------------------------------------
# Vehicles — VehicleId maps to car metadata
# ---------------------------------------------------------------------------

class Vehicle(IntEnum):
    """Vehicle IDs (VehicleId in the EgoNet protocol)."""
    # H1 FWD
    MINI_COOPER_S              = 385
    DS_DS_21                   = 572
    LANCIA_FULVIA_HF           = 468

    # H2 FWD
    VW_GOLF_GTI_16V            = 558
    PEUGEOT_205_GTI            = 534

    # H2 RWD
    FORD_ESCORT_MK2            = 555
    ALPINE_A110_1600S          = 469
    FIAT_131_ABARTH_RALLY      = 471
    OPEL_KADETT_C_GTE          = 399

    # H3 RWD
    BMW_E30_M3_EVO_RALLY       = 396
    OPEL_ASCONA_400            = 538
    LANCIA_STRATOS             = 470
    DATSUN_240Z                = 559
    RENAULT_5_TURBO            = 472
    FORD_SIERRA_COSWORTH_RS500 = 394

    # F2 Kit Car
    PEUGEOT_306_MAXI           = 483
    SEAT_IBIZA_KIT_CAR         = 484
    VW_GOLF_KIT_CAR            = 582

    # Group B RWD
    LANCIA_037_EVO2            = 480
    OPEL_MANTA_400             = 400
    BMW_M1_PROCAR_RALLY        = 575
    PORSCHE_911_SC_RS          = 577

    # Group B 4WD
    AUDI_SPORT_QUATTRO_S1_E2   = 537
    PEUGOT_205_T16_EVO2        = 479
    LANCIA_DELTA_S4            = 478
    FORD_RS200                 = 393
    MG_METRO_6R4               = 401

    # R2
    FORD_FIESTA_R2             = 532
    OPEL_ADAM_R2               = 533
    PEUGEOT_208_R2             = 557

    # Group A
    MITSUBISHI_LANCER_EVO6     = 536
    SUBARU_IMPREZA_1995        = 382
    SUBARU_LEGACY_RS           = 597
    LANCIA_DELTA_HF_INTEGRALE  = 477
    FORD_ESCORT_RS_COSWORTH    = 389

    # NR4/R4
    SUBARU_WRX_STI_NR4         = 531
    MITSUBISHI_LANCER_EVOX     = 482

    # 2000cc 4WD
    FORD_FOCUS_RS_RALLY_2001   = 485
    CITROEN_C4_RALLY           = 573
    SKODA_FABIA_RALLY          = 574
    SUBARU_IMPREZA_S4          = 593
    SUBARU_IMPREZA_2001        = 490
    FORD_FOCUS_RS_RALLY_2007   = 395
    SUBARU_IMPREZA             = 576
    PEUGEOT_206_RALLY          = 578

    # R5
    FORD_FIESTA_R5             = 529
    PEUGEOT_208_R5_T16         = 530
    MITSUBISHI_SPACE_STAR_R5   = 527
    SKODA_FABIA_R5             = 560
    CITROEN_C3_R5              = 561
    VW_POLO_R5                 = 562
    FORD_FIESTA_R5_MK2         = 600

    # Rally GT
    BMW_M2_COMPETITION         = 563
    CHEVROLET_CAMARO_GT4_R     = 564
    PORSCHE_911_RGT            = 565
    FORD_MUSTANG_GT4           = 556
    ASTON_MARTIN_V8            = 554

    # RX Super 1600
    VW_POLO_S1600              = 543
    RENAULT_CLIO_RS_S1600      = 514
    OPEL_CORSA_SUPER_1600      = 513

    # Cross Kart
    SPEEDCAR_XTREM             = 535

    # Group B Rallycross
    LANCIA_DELTA_S4_RX         = 548
    FORD_RS200_EVO             = 550
    PEUGEOT_205_T16_RX         = 511
    MG_METRO_6R4_RX            = 547

    # RX2
    FORD_FIESTA_OMSE_SUPERCAR_LITES = 541

    # RX Supercars
    VW_POLO_R_SUPERCAR         = 570
    AUDI_S1_EKS_RX_QUATTRO     = 566
    PEUGEOT_208_WRX            = 502
    RENAULT_MEGANE_RS_RX       = 569
    FORD_FIESTA_RX_MK8         = 567
    FORD_FIESTA_RX_MK7         = 504
    SUBARU_WRX_STI_RX          = 571

    # RX Supercars 2019
    RENAULT_MEGANE_RS_RX_2019   = 579
    PEUGEOT_208_WRX_2019        = 580
    AUDI_S1_EKS_RX_QUATTRO_2019 = 581
    RENAULT_CLIO_RS_RX_2019     = 585
    FORD_FIESTA_RXS_EVO_5_2019  = 586
    FORD_FIESTA_RX_MK8_2019     = 587
    MINI_COOPER_SX1_2019        = 588
    FORD_FIESTA_RX_STARD_2019   = 589
    SEAT_IBIOZA_RX_2019         = 590

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
    Vehicle.MINI_COOPER_S:              {"display_name": "Mini Cooper S",                 "vehicle_class": VehicleClass.H1_FWD,      "abbrev": "h1_mini"},
    Vehicle.DS_DS_21:                   {"display_name": "DS Automobiles DS 21",          "vehicle_class": VehicleClass.H1_FWD,      "abbrev": "h1_ds"},
    Vehicle.LANCIA_FULVIA_HF:           {"display_name": "Lancia Fulvia HF",              "vehicle_class": VehicleClass.H1_FWD,      "abbrev": "h1_fulvia"},

    # H2 FWD
    Vehicle.VW_GOLF_GTI_16V:            {"display_name": "Volkswagen Golf GTI 16V",       "vehicle_class": VehicleClass.H2_FWD,      "abbrev": "h2f_golf"},
    Vehicle.PEUGEOT_205_GTI:            {"display_name": "Peugeot 205 GTI",               "vehicle_class": VehicleClass.H2_FWD,      "abbrev": "h2f_205"},

    # H2 RWD
    Vehicle.FORD_ESCORT_MK2:            {"display_name": "Ford Escort Mk II",             "vehicle_class": VehicleClass.H2_RWD,      "abbrev": "h2r_escort"},
    Vehicle.ALPINE_A110_1600S:          {"display_name": "Alpine A110 1600 S",            "vehicle_class": VehicleClass.H2_RWD,      "abbrev": "h2r_a110"},
    Vehicle.FIAT_131_ABARTH_RALLY:      {"display_name": "Fiat 131 Abarth Rally",         "vehicle_class": VehicleClass.H2_RWD,      "abbrev": "h2r_131"},
    Vehicle.OPEL_KADETT_C_GTE:          {"display_name": "Opel Kadett C GT/E",            "vehicle_class": VehicleClass.H2_RWD,      "abbrev": "h2r_kadett"},

    # H3 RWD
    Vehicle.BMW_E30_M3_EVO_RALLY:       {"display_name": "BMW E30 M3 Evo Rally",          "vehicle_class": VehicleClass.H3_RWD,      "abbrev": "h3r_e30"},
    Vehicle.OPEL_ASCONA_400:            {"display_name": "Opel Ascona 400",               "vehicle_class": VehicleClass.H3_RWD,      "abbrev": "h3r_ascona"},
    Vehicle.LANCIA_STRATOS:             {"display_name": "Lancia Stratos",                "vehicle_class": VehicleClass.H3_RWD,      "abbrev": "h3r_stratos"},
    Vehicle.DATSUN_240Z:                {"display_name": "Datsun 240Z",                   "vehicle_class": VehicleClass.H3_RWD,      "abbrev": "h3r_240z"},
    Vehicle.RENAULT_5_TURBO:            {"display_name": "Renault 5 Turbo",               "vehicle_class": VehicleClass.H3_RWD,      "abbrev": "h3r_5"},
    Vehicle.FORD_SIERRA_COSWORTH_RS500: {"display_name": "Ford Sierra Cosworth RS500",    "vehicle_class": VehicleClass.H3_RWD,      "abbrev": "h3r_sierra"},

    # F2 Kit Car
    Vehicle.PEUGEOT_306_MAXI:           {"display_name": "Peugeot 306 Maxi",              "vehicle_class": VehicleClass.F2_KIT_CAR,  "abbrev": "f2_306"},
    Vehicle.SEAT_IBIZA_KIT_CAR:         {"display_name": "Seat Ibiza Kit Car",            "vehicle_class": VehicleClass.F2_KIT_CAR,  "abbrev": "f2_ibiza"},
    Vehicle.VW_GOLF_KIT_CAR:            {"display_name": "Volkswagen Golf KitCar",        "vehicle_class": VehicleClass.F2_KIT_CAR,  "abbrev": "f2_golf"},

    # Group B RWD
    Vehicle.LANCIA_037_EVO2:            {"display_name": "Lancia 037 Evo 2",              "vehicle_class": VehicleClass.GROUP_B_RWD, "abbrev": "gbr_037"},
    Vehicle.OPEL_MANTA_400:             {"display_name": "Opel Manta 400",                "vehicle_class": VehicleClass.GROUP_B_RWD, "abbrev": "gbr_manta"},
    Vehicle.BMW_M1_PROCAR_RALLY:        {"display_name": "BMW M1 Procar Rally",           "vehicle_class": VehicleClass.GROUP_B_RWD, "abbrev": "gbr_m1"},
    Vehicle.PORSCHE_911_SC_RS:          {"display_name": "Porsche 911 SC RS",             "vehicle_class": VehicleClass.GROUP_B_RWD, "abbrev": "gbr_911"},

    # Group B 4WD
    Vehicle.AUDI_SPORT_QUATTRO_S1_E2:   {"display_name": "Audi Sport Quattro S1 E2",      "vehicle_class": VehicleClass.GROUP_B_4WD, "abbrev": "gb4_quattro"},
    Vehicle.PEUGOT_205_T16_EVO2:        {"display_name": "Peugeot 205 T16 Evo 2",         "vehicle_class": VehicleClass.GROUP_B_4WD, "abbrev": "gb4_205"},
    Vehicle.LANCIA_DELTA_S4:            {"display_name": "Lancia Delta S4",               "vehicle_class": VehicleClass.GROUP_B_4WD, "abbrev": "gb4_delta"},
    Vehicle.FORD_RS200:                 {"display_name": "Ford RS200",                    "vehicle_class": VehicleClass.GROUP_B_4WD, "abbrev": "gb4_rs200"},
    Vehicle.MG_METRO_6R4:               {"display_name": "MG Metro 6R4",                  "vehicle_class": VehicleClass.GROUP_B_4WD, "abbrev": "gb4_metro"},

    # R2
    Vehicle.FORD_FIESTA_R2:             {"display_name": "Ford Fiesta R2",                "vehicle_class": VehicleClass.R2,          "abbrev": "r2_fiesta"},
    Vehicle.OPEL_ADAM_R2:               {"display_name": "Opel Adam R2",                  "vehicle_class": VehicleClass.R2,          "abbrev": "r2_adam"},
    Vehicle.PEUGEOT_208_R2:             {"display_name": "Peugeot 208 R2",                "vehicle_class": VehicleClass.R2,          "abbrev": "r2_208"},

    # Group A
    Vehicle.MITSUBISHI_LANCER_EVO6:     {"display_name": "Mitsubishi Lancer Evolution VI", "vehicle_class": VehicleClass.GROUP_A,     "abbrev": "ga_evo6"},
    Vehicle.SUBARU_IMPREZA_1995:        {"display_name": "Subaru Impreza 1995",           "vehicle_class": VehicleClass.GROUP_A,     "abbrev": "ga_imprez"},
    Vehicle.SUBARU_LEGACY_RS:           {"display_name": "Subaru Legacy RS",              "vehicle_class": VehicleClass.GROUP_A,     "abbrev": "ga_legacy"},
    Vehicle.LANCIA_DELTA_HF_INTEGRALE:  {"display_name": "Lancia Delta HF Integrale",     "vehicle_class": VehicleClass.GROUP_A,     "abbrev": "ga_delta"},
    Vehicle.FORD_ESCORT_RS_COSWORTH:    {"display_name": "Ford Escort RS Cosworth",       "vehicle_class": VehicleClass.GROUP_A,     "abbrev": "ga_escort"},

    # NR4/R4
    Vehicle.SUBARU_WRX_STI_NR4:         {"display_name": "Subaru WRX STI NR4",            "vehicle_class": VehicleClass.NR4_R4,      "abbrev": "nr4_wrx"},
    Vehicle.MITSUBISHI_LANCER_EVOX:     {"display_name": "Mitsubishi Lancer Evolution X", "vehicle_class": VehicleClass.NR4_R4,      "abbrev": "nr4_evo"},

    # 2000cc 4WD
    Vehicle.FORD_FOCUS_RS_RALLY_2001:   {"display_name": "Ford Focus RS Rally 2001",      "vehicle_class": VehicleClass.CC_4WD,      "abbrev": "2k_f01"},
    Vehicle.CITROEN_C4_RALLY:           {"display_name": "Citroen C4 Rally",              "vehicle_class": VehicleClass.CC_4WD,      "abbrev": "2k_c4"},
    Vehicle.SKODA_FABIA_RALLY:          {"display_name": "Skoda Fabia Rally",             "vehicle_class": VehicleClass.CC_4WD,      "abbrev": "2k_fab"},
    Vehicle.SUBARU_IMPREZA_S4:          {"display_name": "Subaru Impreza S4 Rally",       "vehicle_class": VehicleClass.CC_4WD,      "abbrev": "2k_imps4"},
    Vehicle.SUBARU_IMPREZA_2001:        {"display_name": "Subaru Impreza (2001)",         "vehicle_class": VehicleClass.CC_4WD,      "abbrev": "2k_imp01"},
    Vehicle.FORD_FOCUS_RS_RALLY_2007:   {"display_name": "Ford Focus RS Rally 2007",      "vehicle_class": VehicleClass.CC_4WD,      "abbrev": "2k_f07"},
    Vehicle.SUBARU_IMPREZA:             {"display_name": "Subaru Impreza",                "vehicle_class": VehicleClass.CC_4WD,      "abbrev": "2k_imp"},
    Vehicle.PEUGEOT_206_RALLY:          {"display_name": "Peugeot 206 Rally",             "vehicle_class": VehicleClass.CC_4WD,      "abbrev": "2k_206"},

    # R5
    Vehicle.FORD_FIESTA_R5:             {"display_name": "Ford Fiesta R5",                "vehicle_class": VehicleClass.R5,          "abbrev": "r5_fiesta"},
    Vehicle.PEUGEOT_208_R5_T16:         {"display_name": "Peugeot 208 R5 T16",            "vehicle_class": VehicleClass.R5,          "abbrev": "r5_208"},
    Vehicle.MITSUBISHI_SPACE_STAR_R5:   {"display_name": "Mitsubishi Space Star R5",      "vehicle_class": VehicleClass.R5,          "abbrev": "r5_star"},
    Vehicle.SKODA_FABIA_R5:             {"display_name": "Skoda Fabia R5",                "vehicle_class": VehicleClass.R5,          "abbrev": "r5_fab"},
    Vehicle.CITROEN_C3_R5:              {"display_name": "Citroen C3 R5",                 "vehicle_class": VehicleClass.R5,          "abbrev": "r5_c3"},
    Vehicle.VW_POLO_R5:                 {"display_name": "Volkswagen Polo GTI R5",        "vehicle_class": VehicleClass.R5,          "abbrev": "r5_polo"},
    Vehicle.FORD_FIESTA_R5_MK2:         {"display_name": "Ford Fiesta R5 MkII",           "vehicle_class": VehicleClass.R5,          "abbrev": "r5_fiesta2"},

    # Rally GT
    Vehicle.BMW_M2_COMPETITION:         {"display_name": "BMW M2 Competition",            "vehicle_class": VehicleClass.RGT,         "abbrev": "rgt_m2"},
    Vehicle.CHEVROLET_CAMARO_GT4_R:     {"display_name": "Chevrolet Camaro GT4.R",        "vehicle_class": VehicleClass.RGT,         "abbrev": "rgt_cam"},
    Vehicle.PORSCHE_911_RGT:            {"display_name": "Porsche 911 RGT Rally Spec",    "vehicle_class": VehicleClass.RGT,         "abbrev": "rgt_911"},
    Vehicle.FORD_MUSTANG_GT4:           {"display_name": "Ford Mustang GT4",              "vehicle_class": VehicleClass.RGT,         "abbrev": "rgt_stang"},
    Vehicle.ASTON_MARTIN_V8:            {"display_name": "Aston Martin V8 Vantage GT4",   "vehicle_class": VehicleClass.RGT,         "abbrev": "rgt_vantage"},

    # RX Super 1600
    Vehicle.VW_POLO_S1600:              {"display_name": "Volkswagen Polo S1600",         "vehicle_class": VehicleClass.RX_SUPER_1600, "abbrev": "rx16_polo"},
    Vehicle.RENAULT_CLIO_RS_S1600:      {"display_name": "Renault Sport Clio R.S. S1600", "vehicle_class": VehicleClass.RX_SUPER_1600, "abbrev": "rx16_clio"},
    Vehicle.OPEL_CORSA_SUPER_1600:      {"display_name": "Opel Corsa Super 1600",         "vehicle_class": VehicleClass.RX_SUPER_1600, "abbrev": "rx16_corsa"},

    # Cross Kart
    Vehicle.SPEEDCAR_XTREM:            {"display_name": "SpeedCar Xtrem",                 "vehicle_class": VehicleClass.CROSS_KART, "abbrev": "kart"},

    # Group B Rallycross
    Vehicle.LANCIA_DELTA_S4_RX:       {"display_name": "Lancia Delta S4 Rallycross",      "vehicle_class": VehicleClass.GROUP_B_RX, "abbrev": "gbrx_delta"},
    Vehicle.FORD_RS200_EVO:           {"display_name": "Ford RS200 Evolution",            "vehicle_class": VehicleClass.GROUP_B_RX, "abbrev": "gbrx_rs200"},
    Vehicle.PEUGEOT_205_T16_RX:       {"display_name": "Peugeot 205 T16 Rallycross",      "vehicle_class": VehicleClass.GROUP_B_RX, "abbrev": "gbrx_205"},
    Vehicle.MG_METRO_6R4_RX:          {"display_name": "MG Metro 6R4 Rallycross",         "vehicle_class": VehicleClass.GROUP_B_RX, "abbrev": "gbrx_metro"},

    # RX2
    Vehicle.FORD_FIESTA_OMSE_SUPERCAR_LITES: {"display_name": "Ford Fiesta OMSE Supercar Lites", "vehicle_class": VehicleClass.RX2, "abbrev": "rx2_fiesta"},

    # RX Supercars
    Vehicle.VW_POLO_R_SUPERCAR:       {"display_name": "Volkswagen Polo R Supercar",      "vehicle_class": VehicleClass.RX_SUPERCARS, "abbrev": "rx_polo"},
    Vehicle.AUDI_S1_EKS_RX_QUATTRO:   {"display_name": "Audi S1 EKS RX Quattro",          "vehicle_class": VehicleClass.RX_SUPERCARS, "abbrev": "rx_s1"},
    Vehicle.PEUGEOT_208_WRX:          {"display_name": "Peugeot 208 WRX",                 "vehicle_class": VehicleClass.RX_SUPERCARS, "abbrev": "rx_208"},
    Vehicle.RENAULT_MEGANE_RS_RX:     {"display_name": "Renault Megane RS RX",            "vehicle_class": VehicleClass.RX_SUPERCARS, "abbrev": "rx_megane"},
    Vehicle.FORD_FIESTA_RX_MK8:       {"display_name": "Ford Fiesta Rallycross Mk8",      "vehicle_class": VehicleClass.RX_SUPERCARS, "abbrev": "rx_fiesta8"},
    Vehicle.FORD_FIESTA_RX_MK7:       {"display_name": "Ford Fiesta Rallycross Mk7",      "vehicle_class": VehicleClass.RX_SUPERCARS, "abbrev": "rx_fiesta7"},
    Vehicle.SUBARU_WRX_STI_RX:        {"display_name": "Subaru WRX STI Rallycross",       "vehicle_class": VehicleClass.RX_SUPERCARS, "abbrev": "rx_wrx"},

    # RX Supercars 2019
    Vehicle.RENAULT_MEGANE_RS_RX_2019:   {"display_name": "Renault Megane R.S. RX",         "vehicle_class": VehicleClass.RX_SUPERCARS_2019, "abbrev": "rx19_megane"},
    Vehicle.PEUGEOT_208_WRX_2019:        {"display_name": "Peugeot 208 WRX",                "vehicle_class": VehicleClass.RX_SUPERCARS_2019, "abbrev": "rx19_208"},
    Vehicle.AUDI_S1_EKS_RX_QUATTRO_2019: {"display_name": "Audi S1 EKS RX Quattro",         "vehicle_class": VehicleClass.RX_SUPERCARS_2019, "abbrev": "rx19_s1"},
    Vehicle.RENAULT_CLIO_RS_RX_2019:     {"display_name": "Renault Clio R.S. RX",           "vehicle_class": VehicleClass.RX_SUPERCARS_2019, "abbrev": "rx19_clio"},
    Vehicle.FORD_FIESTA_RXS_EVO_5_2019:  {"display_name": "Ford Fiesta RXS Evo 5",          "vehicle_class": VehicleClass.RX_SUPERCARS_2019, "abbrev": "rx19_fiesta5"},
    Vehicle.FORD_FIESTA_RX_MK8_2019:     {"display_name": "Ford Fiesta RX (Mk8)",           "vehicle_class": VehicleClass.RX_SUPERCARS_2019, "abbrev": "rx19_fiesta8"},
    Vehicle.MINI_COOPER_SX1_2019:        {"display_name": "Mini Cooper SX1",                "vehicle_class": VehicleClass.RX_SUPERCARS_2019, "abbrev": "rx19_mini"},
    Vehicle.FORD_FIESTA_RX_STARD_2019:   {"display_name": "Ford Fiesta Rallycross (Stard)", "vehicle_class": VehicleClass.RX_SUPERCARS_2019, "abbrev": "rx19_fiesta"},
    Vehicle.SEAT_IBIOZA_RX_2019:         {"display_name": "Seat Ibioza RX",                 "vehicle_class": VehicleClass.RX_SUPERCARS_2019, "abbrev": "rx19_ibiza"},
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
    16: "Sunset / Cloudy / Dry",   # verified via RaceNet club builder 2026-07-07
    17: "Sunset / Overcast / Dry",
    20: "Sunset / Cloudy / Wet",   # in-game OCR variant; RaceNet builder emits 34 for this label
    26: "Daytime / Showers / Wet",
    32: "Daytime / Rain / Wet",    # verified via RaceNet club builder 2026-07-07 (distinct from 9 "Heavy Rain")
    34: "Sunset / Cloudy / Wet",   # verified via RaceNet club builder 2026-07-07 (builder-canonical; cf. 20)
    35: "Sunset / Light Showers / Wet",
    38: "Daytime / Overcast / Dry",
    39: "Sunset / Light Rain / Wet",
    40: "Dusk / Showers / Wet",
    47: "Sunset / Clear / Dry",
}
# NOTE: id 42 ("Sunset / Cloudy / Dry") was a hypothesised duplicate of 16 and is
# NOT reachable from the RaceNet builder — its single "Sunset / Cloudy / Dry"
# option emits 16 (proxy-captured 2026-07-07).  Removed as a dead guess.


def stage_conditions_label(value: int) -> str:
    """Return the human-readable label for a StageConditions / ConditionsId.

    Falls back to ``"Conditions #N"`` for unknown values so the web leaderboard
    can display something until the ID is mapped in-game.
    """
    return STAGE_CONDITIONS_LABELS.get(int(value), f"Conditions #{int(value)}")


_STAGE_LABEL_TO_ID: Dict[str, int] = {
    label: value for value, label in STAGE_CONDITIONS_LABELS.items()
}

# NOTE: there is deliberately no global "web label -> StageConditions" mapping
# and no global default any more.  Conditions are per-location (see
# STAGE_CONDITIONS_BY_LOCATION below): a fixed label list would keep offering
# ids at locations that ship no lighting for them, which loads the stage with a
# broken sky, and no single id — id 1 included — is valid everywhere.


# StageConditions integer values observed in the wild (upstream club data +
# time-trial captures).  Kept as a sorted list for UI dropdowns.
OBSERVED_STAGE_CONDITIONS: List[int] = sorted(STAGE_CONDITIONS_LABELS.keys())

# StageConditions ids the RaceNet club builder itself emits, verified 2026-07-07
# by proxy-capturing Clubs.GetClubs from a championship built on real RaceNet.
# When two ids render as the same in-game label (e.g. 20 and 34 both read
# "Sunset / Cloudy / Wet"), the builder canonically uses the id listed here.
RACENET_BUILDER_CONDITION_IDS: frozenset[int] = frozenset({1, 3, 4, 11, 16, 17, 26, 32, 34})


def _build_stage_conditions_options() -> List[tuple[int, str]]:
    """(composite_id, label) pairs for the championship-builder "Time of Day /
    Conditions" dropdown — one row per distinct label.

    Where several ids share a label, the RaceNet-builder-canonical id
    (:data:`RACENET_BUILDER_CONDITION_IDS`) wins, so the builder writes the same
    StageConditions int RaceNet's own builder would and the stage loads correctly
    in-game.
    """
    by_label: Dict[str, int] = {}
    for cid, label in sorted(STAGE_CONDITIONS_LABELS.items()):
        current = by_label.get(label)
        if current is None:
            by_label[label] = cid
        elif cid in RACENET_BUILDER_CONDITION_IDS and current not in RACENET_BUILDER_CONDITION_IDS:
            by_label[label] = cid
    return sorted((cid, label) for label, cid in by_label.items())


# (composite_id, label) pairs for every distinct confirmed conditions label.
# NOT a dropdown source: which of these a location can actually load varies per
# location (see STAGE_CONDITIONS_BY_LOCATION below), so UIs must offer the
# per-location set instead -- offering this list is what shipped stages with
# lighting their location had no assets for.
STAGE_CONDITIONS_OPTIONS: List[tuple[int, str]] = _build_stage_conditions_options()


# ---------------------------------------------------------------------------
# Per-location StageConditions  (VERIFIED in-game 2026-08-19)
# ---------------------------------------------------------------------------
# StageConditions is a GLOBAL enum -- id 9 reads "Daytime / Heavy Rain / Wet"
# everywhere -- but a location only ships lighting assets for a subset of it.
# Serving an id a location lacks does not error: RaceNet accepted any id for
# any track, and the stage simply loads with a broken sky/lighting setup.  The
# game client is the only validator, so the allowed set has to live here.
#
# Enumerated from Freeplay -> Custom -> Create Championship, whose per-stage
# "Stage Conditions" selector (rally) and "Weather" row (rallycross) list
# exactly what each location supports.  Raw sweep of all 26 selectable
# locations: data/verified/conditions_by_location.json, collected by
# scripts/probe_all_conditions.py and turned into this table by
# scripts/_build_conditions_table.py.
#
# Ids appear in the order the game lists them, so entry 0 is the location's own
# first option -- that is what callers pre-select.  There is deliberately no
# global default: Varmland offers no "Daytime / Clear / Dry" at all, so id 1 is
# not safe everywhere and no single id is.
#
# Labels the game offers whose id we have not confirmed are listed as "--" and
# omitted rather than guessed; they only cost variety, never correctness.
STAGE_CONDITIONS_BY_LOCATION: Dict[Location, tuple[int, ...]] = {
    Location.ARGENTINA: (1, 38, 16, 4, 3,),
        #  1 Daytime / Clear / Dry
        # 38 Daytime / Overcast / Dry
        # 16 Sunset / Cloudy / Dry
        #  4 Dusk / Cloudy / Dry
        #  3 Night / Clear / Dry
        # -- Daytime / Light Showers / Wet  (offered in-game; id not yet known)
        # -- Daytime / Light Rain / Wet  (offered in-game; id not yet known)
        # -- Dusk / Heavy Rain / Wet  (offered in-game; id not yet known)
    Location.AUSTRALIA: (1, 11, 26, 32, 16, 17, 20, 4, 3,),
        #  1 Daytime / Clear / Dry
        # 11 Daytime / Cloudy / Wet
        # 26 Daytime / Showers / Wet
        # 32 Daytime / Rain / Wet
        # 16 Sunset / Cloudy / Dry
        # 17 Sunset / Overcast / Dry
        # 20 Sunset / Cloudy / Wet
        #  4 Dusk / Cloudy / Dry
        #  3 Night / Clear / Dry
    Location.FINLAND: (1, 38, 9, 16, 5, 3,),
        #  1 Daytime / Clear / Dry
        # 38 Daytime / Overcast / Dry
        #  9 Daytime / Heavy Rain / Wet
        # 16 Sunset / Cloudy / Dry
        #  5 Dusk / Overcast / Dry
        #  3 Night / Clear / Dry
        # -- Dusk / Cloudy / Wet  (offered in-game; id not yet known)
        # -- Dusk / Heavy Rain / Wet  (offered in-game; id not yet known)
    Location.GERMANY: (1, 9, 16, 4, 3,),
        #  1 Daytime / Clear / Dry
        #  9 Daytime / Heavy Rain / Wet
        # 16 Sunset / Cloudy / Dry
        #  4 Dusk / Cloudy / Dry
        #  3 Night / Clear / Dry
        # -- Sunset / Heavy Rain / Wet  (offered in-game; id not yet known)
    Location.GREECE: (1, 38, 16, 4, 3,),
        #  1 Daytime / Clear / Dry
        # 38 Daytime / Overcast / Dry
        # 16 Sunset / Cloudy / Dry
        #  4 Dusk / Cloudy / Dry
        #  3 Night / Clear / Dry
        # -- Sunset / Heavy Rain / Wet  (offered in-game; id not yet known)
    Location.MONTE_CARLO: (1, 16, 4, 3,),
        #  1 Daytime / Clear / Dry
        # 16 Sunset / Cloudy / Dry
        #  4 Dusk / Cloudy / Dry
        #  3 Night / Clear / Dry
        # -- Sunset / Light Snow / Dry  (offered in-game; id not yet known)
        # -- Night / Light Snow / Dry  (offered in-game; id not yet known)
    Location.NEW_ZEALAND: (1, 11, 26, 16, 3,),
        #  1 Daytime / Clear / Dry
        # 11 Daytime / Cloudy / Wet
        # 26 Daytime / Showers / Wet
        # 16 Sunset / Cloudy / Dry
        #  3 Night / Clear / Dry
        # -- Dusk / Heavy Rain / Wet  (offered in-game; id not yet known)
        # -- Dusk / Light Rain / Wet  (offered in-game; id not yet known)
        # -- Night / Cloudy / Wet  (offered in-game; id not yet known)
        # -- Night / Light Showers / Wet  (offered in-game; id not yet known)
    Location.POLAND: (1, 9, 38, 20, 35, 16, 4, 3,),
        #  1 Daytime / Clear / Dry
        #  9 Daytime / Heavy Rain / Wet
        # 38 Daytime / Overcast / Dry
        # 20 Sunset / Cloudy / Wet
        # 35 Sunset / Light Showers / Wet
        # 16 Sunset / Cloudy / Dry
        #  4 Dusk / Cloudy / Dry
        #  3 Night / Clear / Dry
        # -- Night / Heavy Rain / Wet  (offered in-game; id not yet known)
        # -- Night / Cloudy / Dry  (offered in-game; id not yet known)
    Location.SPAIN: (1, 11, 26, 17, 20, 39, 4, 40, 3,),
        #  1 Daytime / Clear / Dry
        # 11 Daytime / Cloudy / Wet
        # 26 Daytime / Showers / Wet
        # 17 Sunset / Overcast / Dry
        # 20 Sunset / Cloudy / Wet
        # 39 Sunset / Light Rain / Wet
        #  4 Dusk / Cloudy / Dry
        # 40 Dusk / Showers / Wet
        #  3 Night / Clear / Dry
        # -- Dusk / Cloudy / Wet  (offered in-game; id not yet known)
    Location.SWEDEN: (52,),
        # 52 -- label unconfirmed.  The game itself sent ConditionsId 52 for 11
        #    different Varmland routes in TimeTrial.GetLeaderboardId captures,
        #    so the id is verified for this location even though its label is
        #    not.  Varmland's 7 in-game options are all snow and none of them
        #    map to a confirmed id yet:
        # -- Daytime / Cloudy / Snow
        # -- Daytime / Heavy Snow / Snow
        # -- Sunset / Partly Cloudy / Snow
        # -- Sunset / Heavy Snow / Snow
        # -- Dusk / Cloudy / Snow
        # -- Night / Cloudy / Snow
        # -- Night / Heavy Snow / Snow
    Location.NEW_ENGLAND: (1, 11, 26, 20, 35, 4, 3,),
        #  1 Daytime / Clear / Dry
        # 11 Daytime / Cloudy / Wet
        # 26 Daytime / Showers / Wet
        # 20 Sunset / Cloudy / Wet
        # 35 Sunset / Light Showers / Wet
        #  4 Dusk / Cloudy / Dry
        #  3 Night / Clear / Dry
        # -- Night / Heavy Rain / Wet  (offered in-game; id not yet known)
        # -- Night / Showers / Wet  (offered in-game; id not yet known)
        # -- Night / Cloudy / Dry  (offered in-game; id not yet known)
    Location.WALES: (1, 9, 16, 20, 3,),
        #  1 Daytime / Clear / Dry
        #  9 Daytime / Heavy Rain / Wet
        # 16 Sunset / Cloudy / Dry
        # 20 Sunset / Cloudy / Wet
        #  3 Night / Clear / Dry
        # -- Night / Heavy Rain / Wet  (offered in-game; id not yet known)
    Location.SCOTLAND: (1, 9, 11, 47, 3,),
        #  1 Daytime / Clear / Dry
        #  9 Daytime / Heavy Rain / Wet
        # 11 Daytime / Cloudy / Wet
        # 47 Sunset / Clear / Dry
        #  3 Night / Clear / Dry
        # -- Sunset / Heavy Rain / Wet  (offered in-game; id not yet known)
        # -- Dusk / Heavy Rain / Wet  (offered in-game; id not yet known)
        # -- Night / Heavy Rain / Wet  (offered in-game; id not yet known)
    Location.METTET: (1, 11, 9, 16, 20,),
        #  1 Daytime / Clear / Dry
        # 11 Daytime / Cloudy / Wet
        #  9 Daytime / Heavy Rain / Wet
        # 16 Sunset / Cloudy / Dry
        # 20 Sunset / Cloudy / Wet
        # -- Sunset / Heavy Rain / Wet  (offered in-game; id not yet known)
    Location.TROIS_RIVIERES: (1, 11, 9, 16, 20,),
        #  1 Daytime / Clear / Dry
        # 11 Daytime / Cloudy / Wet
        #  9 Daytime / Heavy Rain / Wet
        # 16 Sunset / Cloudy / Dry
        # 20 Sunset / Cloudy / Wet
        # -- Sunset / Heavy Rain / Wet  (offered in-game; id not yet known)
    Location.LYDDEN_HILL: (1, 11, 9, 16, 20,),
        #  1 Daytime / Clear / Dry
        # 11 Daytime / Cloudy / Wet
        #  9 Daytime / Heavy Rain / Wet
        # 16 Sunset / Cloudy / Dry
        # 20 Sunset / Cloudy / Wet
        # -- Sunset / Heavy Rain / Wet  (offered in-game; id not yet known)
    Location.SILVERSTONE: (1, 11, 9, 16, 20,),
        #  1 Daytime / Clear / Dry
        # 11 Daytime / Cloudy / Wet
        #  9 Daytime / Heavy Rain / Wet
        # 16 Sunset / Cloudy / Dry
        # 20 Sunset / Cloudy / Wet
        # -- Sunset / Heavy Rain / Wet  (offered in-game; id not yet known)
    Location.LOHEAC: (1, 11, 9, 16, 20,),
        #  1 Daytime / Clear / Dry
        # 11 Daytime / Cloudy / Wet
        #  9 Daytime / Heavy Rain / Wet
        # 16 Sunset / Cloudy / Dry
        # 20 Sunset / Cloudy / Wet
        # -- Sunset / Heavy Rain / Wet  (offered in-game; id not yet known)
    Location.ESTERING: (1, 11, 9, 16, 20,),
        #  1 Daytime / Clear / Dry
        # 11 Daytime / Cloudy / Wet
        #  9 Daytime / Heavy Rain / Wet
        # 16 Sunset / Cloudy / Dry
        # 20 Sunset / Cloudy / Wet
        # -- Sunset / Heavy Rain / Wet  (offered in-game; id not yet known)
    Location.BIKERNIEKI: (1, 11, 9, 16, 20,),
        #  1 Daytime / Clear / Dry
        # 11 Daytime / Cloudy / Wet
        #  9 Daytime / Heavy Rain / Wet
        # 16 Sunset / Cloudy / Dry
        # 20 Sunset / Cloudy / Wet
        # -- Sunset / Heavy Rain / Wet  (offered in-game; id not yet known)
    Location.HELL: (1, 11, 9, 16, 20,),
        #  1 Daytime / Clear / Dry
        # 11 Daytime / Cloudy / Wet
        #  9 Daytime / Heavy Rain / Wet
        # 16 Sunset / Cloudy / Dry
        # 20 Sunset / Cloudy / Wet
        # -- Sunset / Heavy Rain / Wet  (offered in-game; id not yet known)
    Location.MONTALEGRE: (1, 11, 9, 16, 20,),
        #  1 Daytime / Clear / Dry
        # 11 Daytime / Cloudy / Wet
        #  9 Daytime / Heavy Rain / Wet
        # 16 Sunset / Cloudy / Dry
        # 20 Sunset / Cloudy / Wet
        # -- Sunset / Heavy Rain / Wet  (offered in-game; id not yet known)
    Location.KILLARNEY: (1, 11, 9, 16, 20,),
        #  1 Daytime / Clear / Dry
        # 11 Daytime / Cloudy / Wet
        #  9 Daytime / Heavy Rain / Wet
        # 16 Sunset / Cloudy / Dry
        # 20 Sunset / Cloudy / Wet
        # -- Sunset / Heavy Rain / Wet  (offered in-game; id not yet known)
    Location.BARCELONA: (1, 11, 9, 16, 20,),
        #  1 Daytime / Clear / Dry
        # 11 Daytime / Cloudy / Wet
        #  9 Daytime / Heavy Rain / Wet
        # 16 Sunset / Cloudy / Dry
        # 20 Sunset / Cloudy / Wet
        # -- Sunset / Heavy Rain / Wet  (offered in-game; id not yet known)
    Location.HOLJES: (1, 11, 9, 16, 20,),
        #  1 Daytime / Clear / Dry
        # 11 Daytime / Cloudy / Wet
        #  9 Daytime / Heavy Rain / Wet
        # 16 Sunset / Cloudy / Dry
        # 20 Sunset / Cloudy / Wet
        # -- Sunset / Heavy Rain / Wet  (offered in-game; id not yet known)
    Location.YAS_MARINA: (1, 11, 20, 47, 4,),
        #  1 Daytime / Clear / Dry
        # 11 Daytime / Cloudy / Wet
        # 20 Sunset / Cloudy / Wet
        # 47 Sunset / Clear / Dry
        #  4 Dusk / Cloudy / Dry
        # -- Dusk / Cloudy / Wet  (offered in-game; id not yet known)
}


def _resolve_location(location: object) -> Optional[Location]:
    """Accept a Location, its int id, or its display name."""
    if isinstance(location, Location):
        return location
    if isinstance(location, int):
        try:
            return Location(location)
        except ValueError:
            return None
    if isinstance(location, str):
        want = location.strip().lower()
        for loc in Location:
            if want in (loc.display_name.lower(), loc.name.lower()):
                return loc
    return None


def stage_conditions_for_location(location: object) -> List[int]:
    """StageConditions ids this location actually ships lighting for.

    Empty when the location has not been swept, which callers must treat as
    "cannot offer conditions here" rather than falling back to a global value.
    """
    loc = _resolve_location(location)
    if loc is None:
        return []
    return list(STAGE_CONDITIONS_BY_LOCATION.get(loc, ()))


def default_stage_conditions_for_location(location: object) -> Optional[int]:
    """The location's own first option, or None if we have no verified set."""
    ids = stage_conditions_for_location(location)
    return ids[0] if ids else None


def stage_conditions_options_for_location(location: object) -> List[tuple[int, str]]:
    """(id, label) pairs to populate a conditions dropdown for one location."""
    return [(cid, stage_conditions_label(cid))
            for cid in stage_conditions_for_location(location)]


# ---------------------------------------------------------------------------
# Surface degradation levels  (VERIFIED via RaceNet club builder 2026-07-07)
# ---------------------------------------------------------------------------
# RaceNet's championship builder exposes a per-stage "Surface Deg" dropdown
# (None / Low / Medium / High / Max).  The game field is the raw float
# Stage.surface_degrad (0.0-1.0, default 0.25).  Proxy-captured Clubs.GetClubs
# ground truth confirmed the full label->float mapping below exactly.
SURFACE_DEGRAD_LEVELS: List[tuple[str, float]] = [
    ("None",   0.0),
    ("Low",    0.25),   # == Stage.surface_degrad default (upstream-observed)
    ("Medium", 0.5),
    ("High",   0.75),
    ("Max",    1.0),
]

_SURFACE_DEGRAD_BY_LABEL: Dict[str, float] = {lbl: val for lbl, val in SURFACE_DEGRAD_LEVELS}


def surface_degrad_for_level(label: str) -> float:
    """Resolve a Surface Deg label to a ``Stage.surface_degrad`` float.

    Unknown labels fall back to 0.25 (the engine default / "Low").
    """
    return _SURFACE_DEGRAD_BY_LABEL.get(label, 0.25)


# ---------------------------------------------------------------------------
# Service area levels  (VERIFIED via RaceNet club builder 2026-07-07)
# ---------------------------------------------------------------------------
# RaceNet exposes a per-stage "Service Area" dropdown: None / Short / Medium /
# Long.  Maps to Stage.has_service_area (bool) + Stage.svc_settings_id (int).
# Proxy-captured Clubs.GetClubs ground truth: the ordinals are 0=off, 2=Short,
# 3=Medium, 4=Long — svc_settings_id 1 is never emitted (an unexposed gap), and
# the previously-observed default of 2 is "Short", NOT "Medium" as once assumed.
SERVICE_AREA_LEVELS: List[tuple[str, bool, int]] = [
    ("None",   False, 0),
    ("Short",  True,  2),   # == Stage.svc_settings_id default (upstream-observed)
    ("Medium", True,  3),
    ("Long",   True,  4),
]

_SERVICE_AREA_BY_LABEL: Dict[str, tuple[bool, int]] = {
    lbl: (has_area, sid) for lbl, has_area, sid in SERVICE_AREA_LEVELS
}


def service_area_for_level(label: str) -> tuple[bool, int]:
    """Resolve a Service Area label to ``(has_service_area, svc_settings_id)``.

    Unknown labels fall back to ``(True, 2)`` (the upstream-observed default,
    which is "Short").
    """
    return _SERVICE_AREA_BY_LABEL.get(label, (True, 2))


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
# Reward source codes (from EventReward.Reason.Source / ChampReward.Reason.Source)
# ---------------------------------------------------------------------------

class RewardSource(IntEnum):
    """Source codes observed in EgoNet Reward.Reason.Source.

    Names are placeholders — real meaning is unknown until we capture more
    upstream traffic. Echoing the observed value verbatim is required for
    the game client to accept the response.
    """
    UNKNOWN_4 = 4  # observed in mid-event StageComplete responses


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

VERIFIED_TRACK_IDS = (
    # Argentina
    572, 604, 605, 606, 607, 608, 573, 609, 610, 611, 612, 613,

    # Australia
    568, 584, 585, 586, 587, 588, 569, 589, 590, 591, 592, 593,

    # Finland
    505, 506, 507, 508, 509, 510, 511, 512, 513, 514, 515, 516,

    # Germany
    472, 489, 490, 491, 492, 493, 480, 494, 495, 496, 497, 498,

    # Greece
    471, 460, 461, 462, 463, 464, 465, 466, 467, 468, 469, 470,

    # Monte Carlo
    435, 449, 450, 451, 452, 453, 454, 455, 456, 457, 458, 459,

    # New Zealand
    570, 594, 595, 596, 597, 598, 571, 599, 600, 601, 602, 603,

    # Poland
    614, 615, 616, 617, 618, 619, 620, 621, 622, 623, 624, 625,

    # Spain
    566, 574, 575, 576, 577, 578, 567, 579, 580, 581, 582, 583,

    # Sweden
    517, 518, 519, 520, 521, 522, 523, 524, 525, 526, 527, 528,

    # New England
    626, 627, 628, 629, 630, 631, 632, 633, 634, 635, 636, 637,

    # Wales
    437, 438, 439, 440, 441, 442, 443, 444, 445, 446, 447, 448,

    # Scotland
    657, 658, 659, 660, 661, 662, 663, 664, 665, 666, 667, 668,

    # Rallycross, one circuit per location.  These route IDs come from the
    # track enum rather than an in-game capture, so they're less certain than
    # the rally routes above.  They're listed here anyway because leaving them
    # out made every rallycross club championship unservable: the dispatcher
    # resolves zero tracks for the location and drops the challenge, so the
    # site showed the event as live while the game showed the club with no
    # championship active.  Auto-generated official events must NOT land on
    # these circuits, but that exclusion is by discipline now (see RX_LOCATIONS
    # in web/server.py), not by omission from this list.
    172, 158, 131, 171, 152, 173, 174, 142, 153, 175, 154, 141, 176,
)


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


def get_verified_routes_for_location(location_id: int) -> List[tuple[int, str, float]]:
    """Return ``(track_id, display_name, length_km)`` for a location's verified routes.

    Only tracks in ``VERIFIED_TRACK_IDS`` are returned (same filter as
    :func:`get_tracks_for_location`), because an unverified route loads the
    wrong stage in-game.  This is the source for the championship-builder ROUTE
    dropdown: the caller stores the ``track_id`` (canonical, locale-independent)
    and shows ``display_name`` + ``length_km``.
    """
    loc = Location(location_id)
    return [
        (int(t), _TRACK_META[t]["display_name"], _TRACK_META[t].get("length_km", 0.0))
        for t in Track
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
