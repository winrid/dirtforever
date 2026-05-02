"""Discipline ID mappings for DiRT Rally 2.0."""

from __future__ import annotations

from enum import IntEnum
from typing import Dict


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
