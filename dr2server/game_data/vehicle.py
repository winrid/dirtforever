"""Vehicle ID mappings for DiRT Rally 2.0."""

from __future__ import annotations

from enum import IntEnum
from typing import Dict

from .vehicle_class import VehicleClass


class Vehicle(IntEnum):
    """Vehicle IDs (VehicleId in the EgoNet protocol)."""
    # H1 FWD
    MINI_COOPER_S        = 469
    CITROEN_DS_21        = 470
    LANCIA_FULVIA_HF     = 468

    # H2 FWD
    VW_GOLF_GTI_16V      = 471
    # PEUGEOT_205_GTI = 000

    # H2 RWD
    FORD_ESCORT_MK2      = 478
    ALPINE_A110_1600S    = 480
    # FIAT_131_ABARTH_RALLY = 000
    # OPEL_KADETT_C_GTE = 000

    # H3 RWD
    # BMW_E30_M3_EVO_RALLY = 000
    # OPEL_ASCONA_400 = 000
    # LANCIA_STRATOS = 000
    # DATSUN_240Z = 000
    # RENAULT_5_TURBO       = 000
    # FORD_SIERRA_COSWORTH_RS500 = 000

    # F2 Kit Car
    # PEUGEOT_306_MAXI      = 000
    # SEAT_IBIZA_KIT_CAR    = 000
    # VW_GOLF_KIT_CAR = 000

    # Group B RWD
    # LANCIA_037_EVO2 = 000
    # OPEL_MANTA_400 = 000
    # BMW_M1_PROCAR_RALLY = 000
    # PORSCHE_911_SC_RS = 000

    # Group B 4WD
    AUDI_SPORT_QUATTRO_S1_E2 = 513
    # PEUGOT_205_T16_EVO2       = 000
    # LANCIA_DELTA_S4 = 000
    # FORD_RS200 = 000
    MG_METRO_6R4             = 401

    # R2
    # FORD_FIESTA_R2 = 000
    # OPEL_ADAM_R2 = 000
    # PEUGEOT_208_R2 = 000

    # Group A
    MITSUBISHI_LANCER_EVO6   = 529
    # SUBARU_IMPREZA_1995 = 000
    # SUBARU_LEGACY_RS = 000
    # LANCIA_DELTA_HF_INTEGRALE = 000
    # FORD_ESCORT_RS_COSWORTH = 000

    # NR4/R4
    # SUBARU_WRX_STI_NR4 = 000
    # MITSUBISHI_LANCER_EVOX = 000

    # 2000cc 4WD
    # SKODA_FABIA_RALLY = 000
    # CITROEN_C4_RALLY = 000
    # FORD_FOCUS_RS_RALLY_2001 = 000
    SUBARU_IMPREZA_S4     = 395
    SUBARU_IMPREZA_2001   = 382
    # FORD_FOCUS_RS_RALLY_2007 = 000
    # SUBARU_IMPREZA = 000
    # PEUGEOT_206_RALLY = 000

    # R5
    FORD_FIESTA_R5        = 555
    # PEUGEOT_208_R5_T16 = 000
    VW_POLO_R5            = 559
    MITSUBISHI_SPACE_STAR_R5 = 557
    SKODA_FABIA_R5        = 556
    CITROEN_C3_R5         = 558
    # FORD_FIESTA_R5_MK2 = 000

    # Rally GT
    # BMW_M2_COMPETITION = 000
    # CHEVROLET_CAMARO_GT4_R = 000
    PORSCHE_911_RGT       = 547
    ASTON_MARTIN_V8       = 548
    # FORD_MUSTANG_GT4 = 000

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
