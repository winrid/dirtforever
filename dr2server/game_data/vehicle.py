"""Vehicle ID mappings for DiRT Rally 2.0."""

from __future__ import annotations

from enum import IntEnum
from typing import Dict

from .vehicle_class import VehicleClass


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
