"""Vehicle class ID mappings for DiRT Rally 2.0."""

from __future__ import annotations

from enum import IntEnum
from typing import Dict


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
    # VehicleClass.RGT:           "Rally GT",

    # Rallycross
    VehicleClass.RX_SUPER_1600: "RX Super 1600",
    VehicleClass.CROSS_KART:    "Cross Kart",
    VehicleClass.GROUP_B_RX:    "Group B Rallycross",
    VehicleClass.RX2:           "RX2",
    VehicleClass.RX_SUPERCARS:  "RX Supercars",
    # VehicleClass.RX_SUPERCARS_2019: "RX Supercars 2019",
}
