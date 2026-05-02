"""Race status code mappings for DiRT Rally 2.0."""

from __future__ import annotations

from enum import IntEnum
from typing import Dict


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
