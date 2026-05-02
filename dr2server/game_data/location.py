"""Location ID mappings for DiRT Rally 2.0."""

from __future__ import annotations

from enum import IntEnum
from typing import Dict


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
