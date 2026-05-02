"""Track/stage route ID mappings for DiRT Rally 2.0."""

from __future__ import annotations

from enum import IntEnum
from typing import Dict

from .location import Location


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
    # METTET                                   = 000
    # TRIOS_RIVIERES                           = 000
    # LYDDEN_HILL                              = 000
    # SILVERSTONE                              = 000
    # LOHEAC                                   = 000
    # ESTERING                                 = 000
    # BIKERNIEKI                               = 000
    HELL                                     = 478
    MONTALEGRE                               = 537
    # KILLARNEY                                = 000
    BARCELONA                                = 538
    # HOLJES                                   = 000
    # YAS_MARINA                               = 000

    @property
    def display_name(self) -> str:
        return _TRACK_META[self]["display_name"]

    @property
    def location(self) -> Location:
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
    Track.LAS_JUNTAS: {"display_name": "Las Juntas", "location": Location.ARGENTINA, "length_km": 5.13},
    Track.CAMINO_A_LA_PUERTA: {"display_name": "Camino a La Puerta", "location": Location.ARGENTINA, "length_km": 5.13},
    Track.CAMINO_DE_ACANTILADOS_Y_ROCAS: {"display_name": "Camino de acantilados y rocas", "location": Location.ARGENTINA, "length_km": 3.29},
    Track.EL_RODEO: {"display_name": "El Rodeo", "location": Location.ARGENTINA, "length_km": 1.77},
    Track.LA_MERCED: {"display_name": "La Merced", "location": Location.ARGENTINA, "length_km": 1.77},
    Track.CAMINO_DE_ACANTILADOS_Y_ROCAS_INVERSO: {"display_name": "Camino de acantilados y rocas inverso", "location": Location.ARGENTINA, "length_km": 3.29},
    Track.VALLE_DE_LOS_PUENTES: {"display_name": "Valle de los puentes", "location": Location.ARGENTINA, "length_km": 4.96},
    Track.VALLE_DE_LOS_PUENTES_A_LA_INVERSA: {"display_name": "Valle de los puentes a la inversa", "location": Location.ARGENTINA, "length_km": 4.96},
    Track.MIRAFLORES: {"display_name": "Miraflores", "location": Location.ARGENTINA, "length_km": 2.08},
    Track.SAN_ISIDRO: {"display_name": "San Isidro", "location": Location.ARGENTINA, "length_km": 2.78},
    Track.CAMINO_A_CONETA: {"display_name": "Camino a Coneta", "location": Location.ARGENTINA, "length_km": 2.78},
    Track.HUILLAPRIMA: {"display_name": "Huillaprima", "location": Location.ARGENTINA, "length_km": 2.08},

    # Australia
    Track.MOUNT_KAYE_PASS: {"display_name": "Mount Kaye Pass", "location": Location.AUSTRALIA, "length_km": 7.77},
    Track.MOUNT_KAYE_PASS_REVERSE: {"display_name": "Mount Kaye Pass Reverse", "location": Location.AUSTRALIA, "length_km": 7.77},
    Track.ROCKTON_PLAINS: {"display_name": "Rockton Plains", "location": Location.AUSTRALIA, "length_km": 4.28},
    Track.YAMBULLA_MOUNTAIN_DESCENT: {"display_name": "Yambulla Mountain Descent", "location": Location.AUSTRALIA, "length_km": 4.13},
    Track.YAMBULLA_MOUNTAIN_ASCENT: {"display_name": "Yambulla Mountain Ascent", "location": Location.AUSTRALIA, "length_km": 4.13},
    Track.ROCKTON_PLAINS_REVERSE: {"display_name": "Rockton Plains Reverse", "location": Location.AUSTRALIA, "length_km": 4.28},
    Track.CHANDLERS_CREEK: {"display_name": "Chandlers Creek", "location": Location.AUSTRALIA, "length_km": 7.67},
    Track.CHANDLERS_CREEK_REVERSE: {"display_name": "Chandlers Creek Reverse", "location": Location.AUSTRALIA, "length_km": 7.67},
    Track.NOORINBEE_RIDGE_ASCENT: {"display_name": "Noorinbee Ridge Ascent", "location": Location.AUSTRALIA, "length_km": 3.28},
    Track.TAYLOR_FARM_SPRINT: {"display_name": "Taylor Farm Sprint", "location": Location.AUSTRALIA, "length_km": 4.35},
    Track.BONDI_FOREST: {"display_name": "Bondi Forest", "location": Location.AUSTRALIA, "length_km": 4.35},
    Track.NOORINBEE_RIDGE_DESCENT: {"display_name": "Noorinbee Ridge Descent", "location": Location.AUSTRALIA, "length_km": 3.28},

    # Finland
    Track.KONTINJARVI: {"display_name": "Kontinjärvi", "location": Location.FINLAND, "length_km": 9.35},
    Track.HAMELAHTI: {"display_name": "Hämelahti", "location": Location.FINLAND, "length_km": 9.30},
    Track.KAILAJARVI: {"display_name": "Kailajärvi", "location": Location.FINLAND, "length_km": 4.67},
    Track.JYRKYSJARVI: {"display_name": "Jyrkysjärvi", "location": Location.FINLAND, "length_km": 4.69},
    Track.NAARAJARVI: {"display_name": "Naarajärvi", "location": Location.FINLAND, "length_km": 4.62},
    Track.PASKURI: {"display_name": "Paskuri", "location": Location.FINLAND, "length_km": 4.56},
    Track.KAKARISTO: {"display_name": "Kakaristo", "location": Location.FINLAND, "length_km": 10.07},
    Track.PITKAJARVI: {"display_name": "Pitkajarvi", "location": Location.FINLAND, "length_km": 10.07},
    Track.ISO_OKSJARVI: {"display_name": "Iso Oksjärvi", "location": Location.FINLAND, "length_km": 5.00},
    Track.JARVENKYLA: {"display_name": "Järvenkylä", "location": Location.FINLAND, "length_km": 5.00},
    Track.KOTAJARVI: {"display_name": "Kotajarvi", "location": Location.FINLAND, "length_km": 5.03},
    Track.OKSALA: {"display_name": "Oksala", "location": Location.FINLAND, "length_km": 5.03},

    # Germany
    Track.OBERSTEIN: {"display_name": "Oberstein", "location": Location.GERMANY, "length_km": 7.25},
    Track.FRAUENBERG: {"display_name": "Frauenberg", "location": Location.GERMANY, "length_km": 7.25},
    Track.WALDAUFSTIEG: {"display_name": "Waldaufstieg", "location": Location.GERMANY, "length_km": 3.35},
    Track.KREUZUNGSRING_REVERSE: {"display_name": "Kreuzungsring Reverse", "location": Location.GERMANY, "length_km": 3.92},
    Track.KREUZUNGSRING: {"display_name": "Kreuzungsring", "location": Location.GERMANY, "length_km": 3.92},
    Track.WALDABSTIEG: {"display_name": "Waldabstieg", "location": Location.GERMANY, "length_km": 3.35},
    Track.HAMMERSTEIN: {"display_name": "Hammerstein", "location": Location.GERMANY, "length_km": 6.72},
    Track.RUSCHBERG: {"display_name": "Ruschberg", "location": Location.GERMANY, "length_km": 6.65},
    Track.VERBUNDSRING: {"display_name": "Verbundsring", "location": Location.GERMANY, "length_km": 3.64},
    Track.INNERER_FELD_SPRINT: {"display_name": "Innerer Feld-Sprint", "location": Location.GERMANY, "length_km": 3.45},
    Track.INNERER_FELD_SPRINT_UMGEKEHRT: {"display_name": "Innerer Feld-Sprint (umgekehrt)", "location": Location.GERMANY, "length_km": 3.45},
    Track.VERBUNDSRING_REVERSE: {"display_name": "Verbundsring Reverse", "location": Location.GERMANY, "length_km": 3.64},

    # Greece
    Track.ANODOU_FARMAKAS: {"display_name": "Anodou Farmakas", "location": Location.GREECE, "length_km": 5.97},
    Track.KATHODO_LEONTIOU: {"display_name": "Kathodo Leontiou", "location": Location.GREECE, "length_km": 5.97},
    Track.POMONA_EKRIXI: {"display_name": "Pomona Ekrixi", "location": Location.GREECE, "length_km": 3.16},
    Track.FOURKETA_KOURVA: {"display_name": "Fourkéta Kourva", "location": Location.GREECE, "length_km": 2.98},
    Track.KORYFI_DAFNI: {"display_name": "Koryfi Dafni", "location": Location.GREECE, "length_km": 2.80},
    Track.AMPELONAS_ORMI: {"display_name": "Ampelonas Ormi", "location": Location.GREECE, "length_km": 3.08},
    Track.PERASMA_PLATANI: {"display_name": "Perasma Platani", "location": Location.GREECE, "length_km": 6.64},
    Track.TSIRISTRA_THEA: {"display_name": "Tsiristra Théa", "location": Location.GREECE, "length_km": 6.44},
    Track.OUREA_SPEVSI: {"display_name": "Ourea Spevsi", "location": Location.GREECE, "length_km": 3.57},
    Track.PEDINES_EPIDAXI: {"display_name": "Pedines Epidaxi", "location": Location.GREECE, "length_km": 3.34},
    Track.ABIES_KOILEDA: {"display_name": "Abies Koiléda", "location": Location.GREECE, "length_km": 4.41},
    Track.YPSONA_TOU_DASOS: {"display_name": "Ypsona tou Dasos", "location": Location.GREECE, "length_km": 4.09},

    # Monaco
    Track.PRA_D_ALART: {"display_name": "Pra d'Alart", "location": Location.MONTE_CARLO, "length_km": 6.11},
    Track.COL_DE_TURINI_DEPART: {"display_name": "Col de Turini Départ", "location": Location.MONTE_CARLO, "length_km": 6.11},
    Track.GORDOLON_COURTE_MONTEE: {"display_name": "Gordolon - Courte montée", "location": Location.MONTE_CARLO, "length_km": 3.22},
    Track.COL_DE_TURINI_SPRINT_EN_DESCENTE: {"display_name": "Col de Turini - Sprint en descente", "location": Location.MONTE_CARLO, "length_km": 2.94},
    Track.COL_DE_TURINI_SPRINT_EN_MONTEE: {"display_name": "Col de Turini sprint en Montée", "location": Location.MONTE_CARLO, "length_km": 2.94},
    Track.COL_DE_TURINI_DESCENTE: {"display_name": "Col de Turini - Descente", "location": Location.MONTE_CARLO, "length_km": 3.22},
    Track.VALLEE_DESCENDANTE: {"display_name": "Vallée descendante", "location": Location.MONTE_CARLO, "length_km": 6.75},
    Track.ROUTE_DE_TURINI: {"display_name": "Route de Turini", "location": Location.MONTE_CARLO, "length_km": 6.75},
    Track.COL_DE_TURINI_DEPART_EN_DESCENTE: {"display_name": "Col de Turini - Départ en descente", "location": Location.MONTE_CARLO, "length_km": 4.25},
    Track.APPROCHE_DU_COL_DE_TURINI_MONTEE: {"display_name": "Approche du Col de Turini - Montée", "location": Location.MONTE_CARLO, "length_km": 2.46},
    Track.ROUTE_DE_TURINI_DESCENTE: {"display_name": "Route de Turini Descente", "location": Location.MONTE_CARLO, "length_km": 2.46},
    Track.ROUTE_DE_TURINI_MONTEE: {"display_name": "Route de Turini Montée", "location": Location.MONTE_CARLO, "length_km": 4.25},

    # New Zealand
    Track.TE_AWANGA_FORWARD: {"display_name": "Te Awanga Forward", "location": Location.NEW_ZEALAND, "length_km": 7.13},
    Track.OCEAN_BEACH: {"display_name": "Ocean Beach", "location": Location.NEW_ZEALAND, "length_km": 7.13},
    Track.TE_AWANGA_SPRINT_FORWARD: {"display_name": "Te Awanga Sprint Forward", "location": Location.NEW_ZEALAND, "length_km": 2.98},
    Track.OCEAN_BEACH_SPRINT_FORWARD: {"display_name": "Ocean Beach Sprint Forward", "location": Location.NEW_ZEALAND, "length_km": 4.11},
    Track.OCEAN_BEACH_SPRINT_REVERSE: {"display_name": "Ocean Beach Sprint Reverse", "location": Location.NEW_ZEALAND, "length_km": 4.11},
    Track.TE_AWANGA_SPRINT_REVERSE: {"display_name": "Te Awanga Sprint Reverse", "location": Location.NEW_ZEALAND, "length_km": 2.98},
    Track.WAIMARAMA_POINT_FORWARD: {"display_name": "Waimarama Point Forward", "location": Location.NEW_ZEALAND, "length_km": 9.98},
    Track.WAIMARAMA_POINT_REVERSE: {"display_name": "Waimarama Point Reverse", "location": Location.NEW_ZEALAND, "length_km": 9.98},
    Track.ELSTHORPE_SPRINT_FORWARD: {"display_name": "Elsthorpe Sprint Forward", "location": Location.NEW_ZEALAND, "length_km": 4.55},
    Track.WAIMARAMA_SPRINT_FORWARD: {"display_name": "Waimarama Sprint Forward", "location": Location.NEW_ZEALAND, "length_km": 5.47},
    Track.WAIMARAMA_SPRINT_REVERSE: {"display_name": "Waimarama Sprint Reverse", "location": Location.NEW_ZEALAND, "length_km": 5.47},
    Track.ELSTHORPE_SPRINT_REVERSE: {"display_name": "Elsthorpe Sprint Reverse", "location": Location.NEW_ZEALAND, "length_km": 4.55},

    # Poland
    Track.ZAROBKA: {"display_name": "Zaróbka", "location": Location.POLAND, "length_km": 10.23},
    Track.ZAGORZE: {"display_name": "Zagórze", "location": Location.POLAND, "length_km": 10.23},
    Track.KOPINA: {"display_name": "Kopina", "location": Location.POLAND, "length_km": 4.37},
    Track.MARYNKA: {"display_name": "Marynka", "location": Location.POLAND, "length_km": 5.75},
    Track.BORYSIK: {"display_name": "Borysik", "location": Location.POLAND, "length_km": 5.75},
    Track.JOZEFIN: {"display_name": "Józefin", "location": Location.POLAND, "length_km": 4.37},
    Track.JEZIORO_ROTCZE: {"display_name": "Jezioro Rotcze", "location": Location.POLAND, "length_km": 8.34},
    Track.ZIENKI: {"display_name": "Zienki", "location": Location.POLAND, "length_km": 8.34},
    Track.CZARNY_LAS: {"display_name": "Czarny Las", "location": Location.POLAND, "length_km": 4.12},
    Track.LEJNO: {"display_name": "Lejno", "location": Location.POLAND, "length_km": 4.23},
    Track.JAGODNO: {"display_name": "Jagodno", "location": Location.POLAND, "length_km": 4.23},
    Track.JEZIORO_LUKIE: {"display_name": "Jezioro Lukie", "location": Location.POLAND, "length_km": 4.12},

    # Spain
    Track.COMIENZO_DE_BELLRIU: {"display_name": "Comienzo De Bellriu", "location": Location.SPAIN, "length_km": 8.91},
    Track.FINAL_DE_BELLRIU: {"display_name": "Final de Bellriu", "location": Location.SPAIN, "length_km": 8.91},
    Track.ASCENSO_POR_VALLE_EL_GUALET: {"display_name": "Ascenso por valle el Gualet", "location": Location.SPAIN, "length_km": 4.35},
    Track.VINEDOS_DENTRO_DEL_VALLE_PARRA: {"display_name": "Viñedos dentro del valle Parra", "location": Location.SPAIN, "length_km": 4.23},
    Track.ASCENSO_BOSQUE_MONTVERD: {"display_name": "Ascenso bosque Montverd", "location": Location.SPAIN, "length_km": 4.23},
    Track.SALIDA_DESDE_MONTVERD: {"display_name": "Salida desde Montverd", "location": Location.SPAIN, "length_km": 4.35},
    Track.CENTENERA: {"display_name": "Centenera", "location": Location.SPAIN, "length_km": 6.57},
    Track.CAMINO_A_CENTENERA: {"display_name": "Camino a Centenera", "location": Location.SPAIN, "length_km": 6.57},
    Track.DESCENSO_POR_CARRETERA: {"display_name": "Descenso por carretera", "location": Location.SPAIN, "length_km": 2.85},
    Track.VINEDOS_DARDENYA: {"display_name": "Viñedos Dardenyà", "location": Location.SPAIN, "length_km": 4.07},
    Track.VINEDOS_DARDENYA_INVERSA: {"display_name": "Viñedos Dardenyà inversa", "location": Location.SPAIN, "length_km": 4.07},
    Track.SUBIDA_POR_CARRETERA: {"display_name": "Subida por carretera", "location": Location.SPAIN, "length_km": 2.85},

    # Sweden
    Track.RANSBYSATER: {"display_name": "Ransbysäter", "location": Location.SWEDEN, "length_km": 7.44},
    Track.NORRASKOGA: {"display_name": "Norraskoga", "location": Location.SWEDEN, "length_km": 7.44},
    Track.ALGSJON_SPRINT: {"display_name": "Älgsjön Sprint", "location": Location.SWEDEN, "length_km": 3.26},
    Track.STOR_JANGEN_SPRINT_REVERSE: {"display_name": "Stor-jangen Sprint Reverse", "location": Location.SWEDEN, "length_km": 4.16},
    Track.STOR_JANGEN_SPRINT: {"display_name": "Stor-jangen Sprint", "location": Location.SWEDEN, "length_km": 4.16},
    Track.SKOGSRALLYT: {"display_name": "Skogsrallyt", "location": Location.SWEDEN, "length_km": 3.26},
    Track.HAMRA: {"display_name": "Hamra", "location": Location.SWEDEN, "length_km": 7.67},
    Track.LYSVIK: {"display_name": "Lysvik", "location": Location.SWEDEN, "length_km": 7.67},
    Track.ELGSJON: {"display_name": "Elgsjön", "location": Location.SWEDEN, "length_km": 4.52},
    Track.BJORKLANGEN: {"display_name": "Björklangen", "location": Location.SWEDEN, "length_km": 3.23},
    Track.OSTRA_HINNSJON: {"display_name": "Östra Hinnsjön", "location": Location.SWEDEN, "length_km": 3.23},
    Track.ALGSJON: {"display_name": "Älgsjön", "location": Location.SWEDEN, "length_km": 4.52},

    # USA
    Track.NORTH_FORK_PASS: {"display_name": "North Fork Pass", "location": Location.NEW_ENGLAND, "length_km": 7.77},
    Track.NORTH_FORK_PASS_REVERSE: {"display_name": "North Fork Pass Reverse", "location": Location.NEW_ENGLAND, "length_km": 7.77},
    Track.HANCOCK_CREEK_BURST: {"display_name": "Hancock Creek Burst", "location": Location.NEW_ENGLAND, "length_km": 4.28},
    Track.FULLER_MOUNTAIN_DESCENT: {"display_name": "Fuller Mountain Descent", "location": Location.NEW_ENGLAND, "length_km": 4.13},
    Track.FULLER_MOUNTAIN_ASCENT: {"display_name": "Fuller Mountain Ascent", "location": Location.NEW_ENGLAND, "length_km": 4.13},
    Track.FURY_LAKE_DEPART: {"display_name": "Fury Lake Depart", "location": Location.NEW_ENGLAND, "length_km": 4.28},
    Track.BEAVER_CREEK_TRAIL_FORWARD: {"display_name": "Beaver Creek Trail Forward", "location": Location.NEW_ENGLAND, "length_km": 7.99},
    Track.BEAVER_CREEK_TRAIL_REVERSE: {"display_name": "Beaver Creek Trail Reverse", "location": Location.NEW_ENGLAND, "length_km": 7.99},
    Track.HANCOCK_HILL_SPRINT_FORWARD: {"display_name": "Hancock Hill Sprint Forward", "location": Location.NEW_ENGLAND, "length_km": 3.73},
    Track.TOLT_VALLEY_SPRINT_REVERSE: {"display_name": "Tolt Valley Sprint Reverse", "location": Location.NEW_ENGLAND, "length_km": 3.79},
    Track.TOLT_VALLEY_SPRINT_FORWARD: {"display_name": "Tolt Valley Sprint Forward", "location": Location.NEW_ENGLAND, "length_km": 3.79},
    Track.HANCOCK_HILL_SPRINT_REVERSE: {"display_name": "Hancock Hill Sprint Reverse", "location": Location.NEW_ENGLAND, "length_km": 3.73},

    # Wales
    Track.SWEET_LAMB: {"display_name": "Sweet Lamb", "location": Location.WALES, "length_km": 6.15},
    Track.GEUFRON_FOREST: {"display_name": "Geufron Forest", "location": Location.WALES, "length_km": 6.21},
    Track.PANT_MAWR: {"display_name": "Pant Mawr", "location": Location.WALES, "length_km": 2.92},
    Track.BIDNO_MOORLAND_REVERSE: {"display_name": "Bidno Moorland Reverse", "location": Location.WALES, "length_km": 2.98},
    Track.BIDNO_MOORLAND: {"display_name": "Bidno Moorland", "location": Location.WALES, "length_km": 3.04},
    Track.PANT_MAWR_REVERSE: {"display_name": "Pant Mawr Reverse", "location": Location.WALES, "length_km": 3.17},
    Track.RIVER_SEVERN_VALLEY: {"display_name": "River Severn Valley", "location": Location.WALES, "length_km": 7.08},
    Track.BRONFELEN: {"display_name": "Bronfelen", "location": Location.WALES, "length_km": 7.08},
    Track.FFERM_WYNT: {"display_name": "Fferm Wynt", "location": Location.WALES, "length_km": 3.54},
    Track.DYFFRYN_AFON_REVERSE: {"display_name": "Dyffryn Afon Reverse", "location": Location.WALES, "length_km": 3.54},
    Track.DYFFRYN_AFON: {"display_name": "Dyffryn Afon", "location": Location.WALES, "length_km": 3.54},
    Track.FFERM_WYNT_REVERSE: {"display_name": "Fferm Wynt Reverse", "location": Location.WALES, "length_km": 3.54},

    # Scotland
    Track.SOUTH_MORNINGSIDE: {"display_name": "South Morningside", "location": Location.SCOTLAND, "length_km": 7.82},
    Track.SOUTH_MORNINGSIDE_REVERSE: {"display_name": "South Morningside Reverse", "location": Location.SCOTLAND, "length_km": 7.87},
    Track.OLD_BUTTERSTONE_MUIR: {"display_name": "Old Butterstone Muir", "location": Location.SCOTLAND, "length_km": 3.62},
    Track.ROSEBANK_FARM: {"display_name": "Rosebank Farm", "location": Location.SCOTLAND, "length_km": 4.45},
    Track.ROSEBANK_FARM_REVERSE: {"display_name": "Rosebank Farm Reverse", "location": Location.SCOTLAND, "length_km": 4.33},
    Track.OLD_BUTTERSTONE_MUIR_REVERSE: {"display_name": "Old Butterstone Muir Reverse", "location": Location.SCOTLAND, "length_km": 3.52},
    Track.NEWHOUSE_BRIDGE: {"display_name": "Newhouse Bridge", "location": Location.SCOTLAND, "length_km": 7.99},
    Track.NEWHOUSE_BRIDGE_REVERSE: {"display_name": "Newhouse Bridge Reverse", "location": Location.SCOTLAND, "length_km": 8.07},
    Track.GLENCASTLE_FARM: {"display_name": "Glencastle Farm", "location": Location.SCOTLAND, "length_km": 3.26},
    Track.ANNBANK_STATION: {"display_name": "Annbank Station", "location": Location.SCOTLAND, "length_km": 4.83},
    Track.ANNBANK_STATION_REVERSE: {"display_name": "Annbank Station Reverse", "location": Location.SCOTLAND, "length_km": 4.71},
    Track.GLENCASTLE_FARM_REVERSE: {"display_name": "Glencastle Farm Reverse", "location": Location.SCOTLAND, "length_km": 3.26},

    # Rallycross
    Track.HELL: {"display_name": "Full Circuit", "location": Location.HELL, "length_km": 0.63},
    Track.MONTALEGRE: {"display_name": "Full Circuit", "location": Location.MONTALEGRE, "length_km": 0.59},
    Track.BARCELONA: {"display_name": "Circuit de Barcelona-Catalunya", "location": Location.BARCELONA, "length_km": 0.70},
}
