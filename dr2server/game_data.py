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
    HAMMERSTEIN                              = 480
    FRAUENBERG                               = 489
    WALDAUFSTIEG                             = 490
    KREUZUNGSRING_REVERSE                    = 491
    KREUZUNGSRING                            = 492
    WALDABSTIEG                              = 493
    RUSCHBERG                                = 494
    VERBUNDSRING                             = 495
    INNERER_FELD_SPRINT                      = 496
    INNERER_FELD_SPRINT_UMGEKEHRT            = 497
    VERBUNDSRING_REVERSE                     = 498

    # GREECE
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
    ANODOU_FARMAKAS                          = 471

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
    BORYSIK                                  = 618
    JOZEFIN                                  = 619
    JEZIORO_ROTCZE                           = 620
    ZIENKI                                   = 621
    CZARNY_LAS                               = 622
    LEJNO                                    = 623
    JAGODNO                                  = 624
    JEZIORO_LUKIE                            = 625

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

    # SPAIN
    COMIENZO_DE_BELLRIU                      = 566
    CENTENERA                                = 567
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
    RAMSHYTTAN                               = 517
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
    Track.KONTINJARVI: {"display_name": "Kontinjärvi", "location": Location.FINLAND, "length_km": 0.0},
    Track.HAMELAHTI: {"display_name": "Hämelahti", "location": Location.FINLAND, "length_km": 0.0},
    Track.KAILAJARVI: {"display_name": "Kailajärvi", "location": Location.FINLAND, "length_km": 0.0},
    Track.JYRKYSJARVI: {"display_name": "Jyrkysjärvi", "location": Location.FINLAND, "length_km": 0.0},
    Track.NAARAJARVI: {"display_name": "Naarajärvi", "location": Location.FINLAND, "length_km": 0.0},
    Track.PASKURI: {"display_name": "Paskuri", "location": Location.FINLAND, "length_km": 0.0},
    Track.KAKARISTO: {"display_name": "Kakaristo", "location": Location.FINLAND, "length_km": 0.0},
    Track.PITKAJARVI: {"display_name": "Pitkajarvi", "location": Location.FINLAND, "length_km": 0.0},
    Track.ISO_OKSJARVI: {"display_name": "Iso Oksjärvi", "location": Location.FINLAND, "length_km": 0.0},
    Track.JARVENKYLA: {"display_name": "Järvenkylä", "location": Location.FINLAND, "length_km": 0.0},
    Track.KOTAJARVI: {"display_name": "Kotajarvi", "location": Location.FINLAND, "length_km": 0.0},
    Track.OKSALA: {"display_name": "Oksala", "location": Location.FINLAND, "length_km": 0.0},
    Track.OBERSTEIN: {"display_name": "Oberstein", "location": Location.GERMANY, "length_km": 0.0},
    Track.HAMMERSTEIN: {"display_name": "Hammerstein", "location": Location.GERMANY, "length_km": 0.0},
    Track.FRAUENBERG: {"display_name": "Frauenberg", "location": Location.GERMANY, "length_km": 0.0},
    Track.WALDAUFSTIEG: {"display_name": "Waldaufstieg", "location": Location.GERMANY, "length_km": 0.0},
    Track.KREUZUNGSRING_REVERSE: {"display_name": "Kreuzungsring Reverse", "location": Location.GERMANY, "length_km": 0.0},
    Track.KREUZUNGSRING: {"display_name": "Kreuzungsring", "location": Location.GERMANY, "length_km": 0.0},
    Track.WALDABSTIEG: {"display_name": "Waldabstieg", "location": Location.GERMANY, "length_km": 0.0},
    Track.RUSCHBERG: {"display_name": "Ruschberg", "location": Location.GERMANY, "length_km": 0.0},
    Track.VERBUNDSRING: {"display_name": "Verbundsring", "location": Location.GERMANY, "length_km": 0.0},
    Track.INNERER_FELD_SPRINT: {"display_name": "Innerer Feld-Sprint", "location": Location.GERMANY, "length_km": 0.0},
    Track.INNERER_FELD_SPRINT_UMGEKEHRT: {"display_name": "Innerer Feld-Sprint (umgekehrt)", "location": Location.GERMANY, "length_km": 0.0},
    Track.VERBUNDSRING_REVERSE: {"display_name": "Verbundsring Reverse", "location": Location.GERMANY, "length_km": 0.0},
    Track.KATHODO_LEONTIOU: {"display_name": "Kathodo Leontiou", "location": Location.GREECE, "length_km": 0.0},
    Track.POMONA_EKRIXI: {"display_name": "Pomona Ekrixi", "location": Location.GREECE, "length_km": 0.0},
    Track.FOURKETA_KOURVA: {"display_name": "Fourkéta Kourva", "location": Location.GREECE, "length_km": 0.0},
    Track.KORYFI_DAFNI: {"display_name": "Koryfi Dafni", "location": Location.GREECE, "length_km": 0.0},
    Track.AMPELONAS_ORMI: {"display_name": "Ampelonas Ormi", "location": Location.GREECE, "length_km": 0.0},
    Track.PERASMA_PLATANI: {"display_name": "Perasma Platani", "location": Location.GREECE, "length_km": 0.0},
    Track.TSIRISTRA_THEA: {"display_name": "Tsiristra Théa", "location": Location.GREECE, "length_km": 0.0},
    Track.OUREA_SPEVSI: {"display_name": "Ourea Spevsi", "location": Location.GREECE, "length_km": 0.0},
    Track.PEDINES_EPIDAXI: {"display_name": "Pedines Epidaxi", "location": Location.GREECE, "length_km": 0.0},
    Track.ABIES_KOILEDA: {"display_name": "Abies Koiléda", "location": Location.GREECE, "length_km": 0.0},
    Track.YPSONA_TOU_DASOS: {"display_name": "Ypsona tou Dasos", "location": Location.GREECE, "length_km": 0.0},
    Track.ANODOU_FARMAKAS: {"display_name": "Anodou Farmakas", "location": Location.GREECE, "length_km": 0.0},
    Track.PRA_D_ALART: {"display_name": "Pra d'Alart", "location": Location.MONTE_CARLO, "length_km": 0.0},
    Track.COL_DE_TURINI_DEPART: {"display_name": "Col de Turini Départ", "location": Location.MONTE_CARLO, "length_km": 0.0},
    Track.GORDOLON_COURTE_MONTEE: {"display_name": "Gordolon - Courte montée", "location": Location.MONTE_CARLO, "length_km": 0.0},
    Track.COL_DE_TURINI_SPRINT_EN_DESCENTE: {"display_name": "Col de Turini - Sprint en descente", "location": Location.MONTE_CARLO, "length_km": 0.0},
    Track.COL_DE_TURINI_SPRINT_EN_MONTEE: {"display_name": "Col de Turini sprint en Montée", "location": Location.MONTE_CARLO, "length_km": 0.0},
    Track.COL_DE_TURINI_DESCENTE: {"display_name": "Col de Turini - Descente", "location": Location.MONTE_CARLO, "length_km": 0.0},
    Track.VALLEE_DESCENDANTE: {"display_name": "Vallée descendante", "location": Location.MONTE_CARLO, "length_km": 0.0},
    Track.ROUTE_DE_TURINI: {"display_name": "Route de Turini", "location": Location.MONTE_CARLO, "length_km": 0.0},
    Track.COL_DE_TURINI_DEPART_EN_DESCENTE: {"display_name": "Col de Turini - Départ en descente", "location": Location.MONTE_CARLO, "length_km": 0.0},
    Track.APPROCHE_DU_COL_DE_TURINI_MONTEE: {"display_name": "Approche du Col de Turini - Montée", "location": Location.MONTE_CARLO, "length_km": 0.0},
    Track.ROUTE_DE_TURINI_DESCENTE: {"display_name": "Route de Turini Descente", "location": Location.MONTE_CARLO, "length_km": 0.0},
    Track.ROUTE_DE_TURINI_MONTEE: {"display_name": "Route de Turini Montée", "location": Location.MONTE_CARLO, "length_km": 0.0},
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
    Track.BORYSIK: {"display_name": "Borysik", "location": Location.POLAND, "length_km": 0.0},
    Track.JOZEFIN: {"display_name": "Józefin", "location": Location.POLAND, "length_km": 0.0},
    Track.JEZIORO_ROTCZE: {"display_name": "Jezioro Rotcze", "location": Location.POLAND, "length_km": 0.0},
    Track.ZIENKI: {"display_name": "Zienki", "location": Location.POLAND, "length_km": 0.0},
    Track.CZARNY_LAS: {"display_name": "Czarny Las", "location": Location.POLAND, "length_km": 0.0},
    Track.LEJNO: {"display_name": "Lejno", "location": Location.POLAND, "length_km": 0.0},
    Track.JAGODNO: {"display_name": "Jagodno", "location": Location.POLAND, "length_km": 0.0},
    Track.JEZIORO_LUKIE: {"display_name": "Jezioro Lukie", "location": Location.POLAND, "length_km": 0.0},
    Track.SOUTH_MORNINGSIDE: {"display_name": "South Morningside", "location": Location.SCOTLAND, "length_km": 0.0},
    Track.SOUTH_MORNINGSIDE_REVERSE: {"display_name": "South Morningside Reverse", "location": Location.SCOTLAND, "length_km": 0.0},
    Track.OLD_BUTTERSTONE_MUIR: {"display_name": "Old Butterstone Muir", "location": Location.SCOTLAND, "length_km": 0.0},
    Track.ROSEBANK_FARM: {"display_name": "Rosebank Farm", "location": Location.SCOTLAND, "length_km": 0.0},
    Track.ROSEBANK_FARM_REVERSE: {"display_name": "Rosebank Farm Reverse", "location": Location.SCOTLAND, "length_km": 0.0},
    Track.OLD_BUTTERSTONE_MUIR_REVERSE: {"display_name": "Old Butterstone Muir Reverse", "location": Location.SCOTLAND, "length_km": 0.0},
    Track.NEWHOUSE_BRIDGE: {"display_name": "Newhouse Bridge", "location": Location.SCOTLAND, "length_km": 0.0},
    Track.NEWHOUSE_BRIDGE_REVERSE: {"display_name": "Newhouse Bridge Reverse", "location": Location.SCOTLAND, "length_km": 0.0},
    Track.GLENCASTLE_FARM: {"display_name": "Glencastle Farm", "location": Location.SCOTLAND, "length_km": 0.0},
    Track.ANNBANK_STATION: {"display_name": "Annbank Station", "location": Location.SCOTLAND, "length_km": 0.0},
    Track.ANNBANK_STATION_REVERSE: {"display_name": "Annbank Station Reverse", "location": Location.SCOTLAND, "length_km": 0.0},
    Track.GLENCASTLE_FARM_REVERSE: {"display_name": "Glencastle Farm Reverse", "location": Location.SCOTLAND, "length_km": 0.0},
    Track.COMIENZO_DE_BELLRIU: {"display_name": "Comienzo De Bellriu", "location": Location.SPAIN, "length_km": 0.0},
    Track.CENTENERA: {"display_name": "Centenera", "location": Location.SPAIN, "length_km": 0.0},
    Track.FINAL_DE_BELLRIU: {"display_name": "Final de Bellriu", "location": Location.SPAIN, "length_km": 0.0},
    Track.ASCENSO_POR_VALLE_EL_GUALET: {"display_name": "Ascenso por valle el Gualet", "location": Location.SPAIN, "length_km": 0.0},
    Track.VINEDOS_DENTRO_DEL_VALLE_PARRA: {"display_name": "Viñedos dentro del valle Parra", "location": Location.SPAIN, "length_km": 0.0},
    Track.ASCENSO_BOSQUE_MONTVERD: {"display_name": "Ascenso bosque Montverd", "location": Location.SPAIN, "length_km": 0.0},
    Track.SALIDA_DESDE_MONTVERD: {"display_name": "Salida desde Montverd", "location": Location.SPAIN, "length_km": 0.0},
    Track.CAMINO_A_CENTENERA: {"display_name": "Camino a Centenera", "location": Location.SPAIN, "length_km": 0.0},
    Track.DESCENSO_POR_CARRETERA: {"display_name": "Descenso por carretera", "location": Location.SPAIN, "length_km": 0.0},
    Track.VINEDOS_DARDENYA: {"display_name": "Viñedos Dardenya", "location": Location.SPAIN, "length_km": 0.0},
    Track.VINEDOS_DARDENYA_INVERSA: {"display_name": "Viñedos Dardenya inversa", "location": Location.SPAIN, "length_km": 0.0},
    Track.SUBIDA_POR_CARRETERA: {"display_name": "Subida por carretera", "location": Location.SPAIN, "length_km": 0.0},
    Track.RAMSHYTTAN: {"display_name": "Rämshyttan", "location": Location.SWEDEN, "length_km": 0.0},
    Track.NORRASKOGA: {"display_name": "Norraskoga", "location": Location.SWEDEN, "length_km": 0.0},
    Track.ALGSJON_SPRINT: {"display_name": "Älgsjön Sprint", "location": Location.SWEDEN, "length_km": 0.0},
    Track.STOR_JANGEN_SPRINT_REVERSE: {"display_name": "Stor-jangen Sprint Reverse", "location": Location.SWEDEN, "length_km": 0.0},
    Track.STOR_JANGEN_SPRINT: {"display_name": "Stor-jangen Sprint", "location": Location.SWEDEN, "length_km": 0.0},
    Track.SKOGSRALLYT: {"display_name": "Skogsrallyt", "location": Location.SWEDEN, "length_km": 0.0},
    Track.HAMRA: {"display_name": "Hamra", "location": Location.SWEDEN, "length_km": 0.0},
    Track.LYSVIK: {"display_name": "Lysvik", "location": Location.SWEDEN, "length_km": 0.0},
    Track.ELGSJON: {"display_name": "Elgsjön", "location": Location.SWEDEN, "length_km": 0.0},
    Track.BJORKLANGEN: {"display_name": "Björklangen", "location": Location.SWEDEN, "length_km": 0.0},
    Track.OSTRA_HINNSJON: {"display_name": "Östra Hinnsjön", "location": Location.SWEDEN, "length_km": 0.0},
    Track.ALGSJON: {"display_name": "Älgsjön", "location": Location.SWEDEN, "length_km": 0.0},
    Track.SWEET_LAMB: {"display_name": "Sweet Lamb", "location": Location.WALES, "length_km": 0.0},
    Track.GEUFRON_FOREST: {"display_name": "Geufron Forest", "location": Location.WALES, "length_km": 0.0},
    Track.PANT_MAWR: {"display_name": "Pant Mawr", "location": Location.WALES, "length_km": 0.0},
    Track.BIDNO_MOORLAND_REVERSE: {"display_name": "Bidno Moorland Reverse", "location": Location.WALES, "length_km": 0.0},
    Track.BIDNO_MOORLAND: {"display_name": "Bidno Moorland", "location": Location.WALES, "length_km": 0.0},
    Track.PANT_MAWR_REVERSE: {"display_name": "Pant Mawr Reverse", "location": Location.WALES, "length_km": 0.0},
    Track.RIVER_SEVERN_VALLEY: {"display_name": "River Severn Valley", "location": Location.WALES, "length_km": 0.0},
    Track.BRONFELEN: {"display_name": "Bronfelen", "location": Location.WALES, "length_km": 0.0},
    Track.FFERM_WYNT: {"display_name": "Fferm Wynt", "location": Location.WALES, "length_km": 0.0},
    Track.DYFFRYN_AFON_REVERSE: {"display_name": "Dyffryn Afon Reverse", "location": Location.WALES, "length_km": 0.0},
    Track.DYFFRYN_AFON: {"display_name": "Dyffryn Afon", "location": Location.WALES, "length_km": 0.0},
    Track.FFERM_WYNT_REVERSE: {"display_name": "Fferm Wynt Reverse", "location": Location.WALES, "length_km": 0.0},
}

# 159 tracks across 16 locations (13 rally × 12 stages + 3 rallycross).
#   Rally: ARGENTINA, AUSTRALIA, FINLAND, GERMANY, GREECE, MONTE_CARLO,
#     NEW_ENGLAND, NEW_ZEALAND, POLAND, SCOTLAND, SPAIN, SWEDEN, WALES — 12 each.
#   Rallycross: BARCELONA (1), HELL (1), MONTALEGRE (1).



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
    RX_SUPER_1600  = 92
    CROSS_KART     = 95
    GROUP_B_RX     = 89
    RX2            = 102
    RX_SUPERCARS   = 78
    # RX_SUPERCARS_2019   = 000

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
    # VehicleClass.RX_SUPERCARS_2019: "RX Supercars 2019",
}


# ---------------------------------------------------------------------------
# Vehicles — VehicleId maps to car metadata
# ---------------------------------------------------------------------------

class Vehicle(IntEnum):
    """Vehicle IDs (VehicleId in the EgoNet protocol)."""
    # H1 FWD
    MINI_COOPER_S              = 385
    CITROEN_DS_21              = 572
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
    SKODA_FABIA_R5             = 556
    CITROEN_C3_R5              = 561
    VW_POLO_R5                 = 562
    FORD_FIESTA_R5_MK2         = 600

    # Rally GT
    BMW_M2_COMPETITION         = 563
    CHEVROLET_CAMARO_GT4_R     = 564
    PORSCHE_911_RGT            = 565
    FORD_MUSTANG_GT4           = 556
    ASTON_MARTIN_V8            = 554

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
    Vehicle.LANCIA_FULVIA_HF:           {"display_name": "Lancia Fulvia HF",              "vehicle_class": VehicleClass.H1_FWD,      "abbrev": "ful"},
    Vehicle.MINI_COOPER_S:              {"display_name": "Mini Cooper S",                 "vehicle_class": VehicleClass.H1_FWD,      "abbrev": "mcs"},
    Vehicle.CITROEN_DS_21:              {"display_name": "Citroen DS 21",                 "vehicle_class": VehicleClass.H1_FWD,      "abbrev": "cds"},

    # H2 FWD
    Vehicle.VW_GOLF_GTI_16V:            {"display_name": "Volkswagen Golf GTI 16V",       "vehicle_class": VehicleClass.H2_FWD,      "abbrev": "gti"},
    Vehicle.PEUGEOT_205_GTI:            {"display_name": "Peugeot 205 GTI",               "vehicle_class": VehicleClass.H2_FWD,      "abbrev": "p5g"},

    # H2 RWD
    Vehicle.FORD_ESCORT_MK2:            {"display_name": "Ford Escort Mk II",             "vehicle_class": VehicleClass.H2_RWD,      "abbrev": "mr5"},
    Vehicle.ALPINE_A110_1600S:          {"display_name": "Alpine A110 1600 S",            "vehicle_class": VehicleClass.H2_RWD,      "abbrev": "alp"},
    Vehicle.FIAT_131_ABARTH_RALLY:      {"display_name": "Fiat 131 Abarth Rally",         "vehicle_class": VehicleClass.H2_RWD,      "abbrev": "131"},
    Vehicle.OPEL_KADETT_C_GTE:          {"display_name": "Opel Kadett C GT/E",            "vehicle_class": VehicleClass.H2_RWD,      "abbrev": "kad"},

    # H3 RWD
    Vehicle.BMW_E30_M3_EVO_RALLY:       {"display_name": "BMW E30 M3 Evo Rally",          "vehicle_class": VehicleClass.H3_RWD,      "abbrev": "e30"},
    Vehicle.OPEL_ASCONA_400:            {"display_name": "Opel Ascona 400",               "vehicle_class": VehicleClass.H3_RWD,      "abbrev": "asc"},
    Vehicle.LANCIA_STRATOS:             {"display_name": "Lancia Stratos",                "vehicle_class": VehicleClass.H3_RWD,      "abbrev": "str"},
    Vehicle.DATSUN_240Z:                {"display_name": "Datsun 240Z",                   "vehicle_class": VehicleClass.H3_RWD,      "abbrev": "240"},
    Vehicle.RENAULT_5_TURBO:            {"display_name": "Renault 5 Turbo",               "vehicle_class": VehicleClass.H3_RWD,      "abbrev": "r5t"},
    Vehicle.FORD_SIERRA_COSWORTH_RS500: {"display_name": "Ford Sierra Cosworth RS500",    "vehicle_class": VehicleClass.H3_RWD,      "abbrev": "rs5"},

    # F2 Kit Car
    Vehicle.PEUGEOT_306_MAXI:           {"display_name": "Peugeot 306 Maxi",              "vehicle_class": VehicleClass.F2_KIT_CAR,  "abbrev": "306"},
    Vehicle.SEAT_IBIZA_KIT_CAR:         {"display_name": "Seat Ibiza Kit Car",            "vehicle_class": VehicleClass.F2_KIT_CAR,  "abbrev": "ibz"},
    Vehicle.VW_GOLF_KIT_CAR:            {"display_name": "Volkswagen Golf Kit Car",       "vehicle_class": VehicleClass.F2_KIT_CAR,  "abbrev": "gkc"},

    # Group B RWD
    Vehicle.LANCIA_037_EVO2:            {"display_name": "Lancia 037 Evo 2",              "vehicle_class": VehicleClass.GROUP_B_RWD, "abbrev": "037"},
    Vehicle.OPEL_MANTA_400:             {"display_name": "Opel Manta 400",                "vehicle_class": VehicleClass.GROUP_B_RWD, "abbrev": "mnt"},
    Vehicle.BMW_M1_PROCAR_RALLY:        {"display_name": "BMW M1 Procar Rally",           "vehicle_class": VehicleClass.GROUP_B_RWD, "abbrev": "m1p"},
    Vehicle.PORSCHE_911_SC_RS:          {"display_name": "Porsche 911 SC RS",             "vehicle_class": VehicleClass.GROUP_B_RWD, "abbrev": "911"},

    # Group B 4WD
    Vehicle.AUDI_SPORT_QUATTRO_S1_E2:   {"display_name": "Audi Sport Quattro S1 E2",      "vehicle_class": VehicleClass.GROUP_B_4WD, "abbrev": "aqe"},
    Vehicle.PEUGOT_205_T16_EVO2:        {"display_name": "Peugeot 205 T16 Evo 2",         "vehicle_class": VehicleClass.GROUP_B_4WD, "abbrev": "t16"},
    Vehicle.LANCIA_DELTA_S4:            {"display_name": "Lancia Delta S4",               "vehicle_class": VehicleClass.GROUP_B_4WD, "abbrev": "s4"},
    Vehicle.FORD_RS200:                 {"display_name": "Ford RS200",                    "vehicle_class": VehicleClass.GROUP_B_4WD, "abbrev": "rs2"},
    Vehicle.MG_METRO_6R4:               {"display_name": "MG Metro 6R4",                  "vehicle_class": VehicleClass.GROUP_B_4WD, "abbrev": "6r4"},

    # R2
    Vehicle.FORD_FIESTA_R2:             {"display_name": "Ford Fiesta R2",                "vehicle_class": VehicleClass.R2,          "abbrev": "fr2"},
    Vehicle.OPEL_ADAM_R2:               {"display_name": "Opel Adam R2",                  "vehicle_class": VehicleClass.R2,          "abbrev": "ar2"},
    Vehicle.PEUGEOT_208_R2:             {"display_name": "Peugeot 208 R2",                "vehicle_class": VehicleClass.R2,          "abbrev": "p2r"},

    # Group A
    Vehicle.MITSUBISHI_LANCER_EVO6:     {"display_name": "Mitsubishi Lancer Evo VI",      "vehicle_class": VehicleClass.GROUP_A,     "abbrev": "ev6"},
    Vehicle.SUBARU_IMPREZA_1995:        {"display_name": "Subaru Impreza 1995",           "vehicle_class": VehicleClass.GROUP_A,     "abbrev": "s95"},
    Vehicle.SUBARU_LEGACY_RS:           {"display_name": "Subaru Legacy RS",              "vehicle_class": VehicleClass.GROUP_A,     "abbrev": "lrs"},
    Vehicle.LANCIA_DELTA_HF_INTEGRALE:  {"display_name": "Lancia Delta HF Integrale",     "vehicle_class": VehicleClass.GROUP_A,     "abbrev": "dhi"},
    Vehicle.FORD_ESCORT_RS_COSWORTH:    {"display_name": "Ford Escort RS Cosworth",       "vehicle_class": VehicleClass.GROUP_A,     "abbrev": "erc"},

    # NR4/R4
    Vehicle.SUBARU_WRX_STI_NR4:         {"display_name": "Subaru WRX STI NR4",            "vehicle_class": VehicleClass.NR4_R4,      "abbrev": "swr"},
    Vehicle.MITSUBISHI_LANCER_EVOX:     {"display_name": "Mitsubishi Lancer Evo X",       "vehicle_class": VehicleClass.NR4_R4,      "abbrev": "evx"},

    # 2000cc 4WD
    Vehicle.FORD_FOCUS_RS_RALLY_2001:   {"display_name": "Ford Focus RS Rally 2001",      "vehicle_class": VehicleClass.CC_4WD,      "abbrev": "ffr"},
    Vehicle.CITROEN_C4_RALLY:           {"display_name": "Citroen C4 Rally",              "vehicle_class": VehicleClass.CC_4WD,      "abbrev": "c4r"},
    Vehicle.SKODA_FABIA_RALLY:          {"display_name": "Skoda Fabia Rally",             "vehicle_class": VehicleClass.CC_4WD,      "abbrev": "sfr"},
    Vehicle.SUBARU_IMPREZA_S4:          {"display_name": "Subaru Impreza S4 Rally",       "vehicle_class": VehicleClass.CC_4WD,      "abbrev": "srs_05"},
    Vehicle.SUBARU_IMPREZA_2001:        {"display_name": "Subaru Impreza 2001",           "vehicle_class": VehicleClass.CC_4WD,      "abbrev": "srs"},
    Vehicle.FORD_FOCUS_RS_RALLY_2007:   {"display_name": "Ford Focus RS Rally 2007",      "vehicle_class": VehicleClass.CC_4WD,      "abbrev": "ffr_07"},
    Vehicle.SUBARU_IMPREZA:             {"display_name": "Subaru Impreza",                "vehicle_class": VehicleClass.CC_4WD,      "abbrev": "sri"},
    Vehicle.PEUGEOT_206_RALLY:          {"display_name": "Peugeot 206 Rally",             "vehicle_class": VehicleClass.CC_4WD,      "abbrev": "pgr"},

    # R5
    Vehicle.FORD_FIESTA_R5:             {"display_name": "Ford Fiesta R5",                "vehicle_class": VehicleClass.R5,          "abbrev": "fr5"},
    Vehicle.PEUGEOT_208_R5_T16:         {"display_name": "Peugeot 208 R5 T16",            "vehicle_class": VehicleClass.R5,          "abbrev": "p5t"},
    Vehicle.MITSUBISHI_SPACE_STAR_R5:   {"display_name": "Mitsubishi Space Star R5",      "vehicle_class": VehicleClass.R5,          "abbrev": "msr"},
    Vehicle.SKODA_FABIA_R5:             {"display_name": "Skoda Fabia R5",                "vehicle_class": VehicleClass.R5,          "abbrev": "sr5"},
    Vehicle.CITROEN_C3_R5:              {"display_name": "Citroen C3 R5",                 "vehicle_class": VehicleClass.R5,          "abbrev": "c3r"},
    Vehicle.VW_POLO_R5:                 {"display_name": "Volkswagen Polo R5",            "vehicle_class": VehicleClass.R5,          "abbrev": "pr5"},
    Vehicle.FORD_FIESTA_R5_MK2:         {"display_name": "Ford Fiesta R5 Mk2",            "vehicle_class": VehicleClass.R5,          "abbrev": "fr5m"},

    # Rally GT
    Vehicle.BMW_M2_COMPETITION:         {"display_name": "BMW M2 Competition",            "vehicle_class": VehicleClass.RGT,         "abbrev": "m2c"},
    Vehicle.CHEVROLET_CAMARO_GT4_R:     {"display_name": "Chevrolet Camaro GT4.R",        "vehicle_class": VehicleClass.RGT,         "abbrev": "ccg"},
    Vehicle.PORSCHE_911_RGT:            {"display_name": "Porsche 911 RGT Rally",         "vehicle_class": VehicleClass.NR4_R4,      "abbrev": "99r"},
    Vehicle.FORD_MUSTANG_GT4:           {"display_name": "Ford Mustang GT4",              "vehicle_class": VehicleClass.RGT,         "abbrev": "fmg"},
    Vehicle.ASTON_MARTIN_V8:            {"display_name": "Aston Martin V8 Vantage",       "vehicle_class": VehicleClass.NR4_R4,      "abbrev": "amr"},
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
