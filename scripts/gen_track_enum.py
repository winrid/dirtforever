"""Generate new Track enum + _TRACK_META code from track_mapping.json.

Outputs Python source to stdout that can replace the existing Track/_TRACK_META
block in dr2server/game_data.py.
"""
from __future__ import annotations

import json
import re
import sys
from typing import Dict, List, Tuple

MAPPING = "C:/Users/winrid/dr2server/runtime/discovery/track_mapping.json"


def slug(name: str) -> str:
    """Turn a stage name into a valid uppercase Python identifier."""
    # Strip common OCR noise / diacritics
    translit = {
        "Ä": "A", "ä": "a", "Ö": "O", "ö": "o", "Å": "A", "å": "a",
        "é": "e", "è": "e", "ä": "a", "ü": "u", "ñ": "n", "Ñ": "N",
        "á": "a", "í": "i", "ó": "o", "ú": "u", "â": "a", "ê": "e",
        "î": "i", "ô": "o", "û": "u", "ý": "y", "ç": "c",
    }
    for k, v in translit.items():
        name = name.replace(k, v)
    # Replace non-word with underscore
    out = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").upper()
    # Python can't start with digit
    if out and out[0].isdigit():
        out = "T_" + out
    return out or "UNNAMED"


def clean_name(raw: str) -> str:
    """Clean up OCR artifacts in a stage name string."""
    # Apply specific whole-word fixes first.
    fixes = {
        "Fourk\ufffdta":       "Fourketa",
        "Fourk\xefta":         "Fourketa",
        "Koil\ufffdda":        "Koilada",
        "Koil\xefda":          "Koilada",
        "Algsj\ufffdn Sprint": "Algsjon Sprint",
        "Algsjn":              "Algsjon",
        "Ostra Hinnsj\ufffdn": "Ostra Hinnsjon",
        "Ostra Hinnsjn":       "Ostra Hinnsjon",
        "Vifiedos":            "Vinedos",
        "Viiedos":             "Vinedos",
        "Vi\ufffdedos":        "Vinedos",
        "Annhank":             "Annbank",
        "Cleat":               "Clear",
        "\ufffdlgsj\ufffdn":   "Algsjon",
        "\u00c4lgsj\u00f6n":   "Algsjon",
    }
    for bad, good in fixes.items():
        raw = raw.replace(bad, good)
    # Replace any remaining replacement chars.
    raw = raw.replace("\ufffd", "")
    return raw.strip()


def main() -> None:
    with open(MAPPING, encoding="utf-8") as f:
        master: Dict[str, dict] = json.load(f)

    # Group by location
    by_loc: Dict[str, List[Tuple[int, str]]] = {}
    for tid_str, info in master.items():
        tid = int(tid_str)
        loc = info.get("real_location")
        if not loc:
            continue
        name = clean_name(info["name"])
        # Skip probes where OCR clearly failed (name is stats text)
        if name.lower().startswith(("length", "elevation", "service", "conditions", "surface")):
            continue
        by_loc.setdefault(loc, []).append((tid, name))

    # Print new Track enum
    print("class Track(IntEnum):")
    print('    """Stage/track route IDs (TrackModelId in the EgoNet protocol).\n')
    print('    Verified in-game 2026-04-11 by the enum-mapping discovery round.')
    print('    Names and Location attribution come from the in-game Event Details')
    print('    panel for each TrackModelId.  See runtime/discovery/track_mapping.json')
    print('    for the raw data.')
    print('    """')

    # Track unique identifiers
    used_names: Dict[str, int] = {}
    enum_lines: List[Tuple[str, int, str]] = []  # (ident, track_id, display_name)
    for loc in sorted(by_loc.keys()):
        tracks = sorted(by_loc[loc])
        print(f"\n    # {loc}")
        for tid, name in tracks:
            ident = slug(name)
            # Deduplicate
            if ident in used_names:
                ident = f"{ident}_{tid}"
            used_names[ident] = tid
            print(f"    {ident:40} = {tid}")
            enum_lines.append((ident, tid, name))

    print("\n    @property")
    print("    def display_name(self) -> str:")
    print("        return _TRACK_META[self][\"display_name\"]")
    print()
    print("    @property")
    print("    def location(self) -> \"Location\":")
    print("        return _TRACK_META[self][\"location\"]")
    print()
    print("    def __str__(self) -> str:")
    print("        return self.display_name")

    # Print _TRACK_META
    print()
    print("_TRACK_META: Dict[Track, dict] = {")
    for loc in sorted(by_loc.keys()):
        tracks = sorted(by_loc[loc])
        for tid, name in tracks:
            ident = None
            for ln_ident, ln_tid, _ in enum_lines:
                if ln_tid == tid:
                    ident = ln_ident
                    break
            if ident is None:
                continue
            # Escape quotes in display name
            safe_name = name.replace('"', '\\"')
            print(f'    Track.{ident}: {{"display_name": "{safe_name}", "location": Location.{loc}}},')
    print("}")

    print()
    print(f"# Generated from {len(enum_lines)} tracks across {len(by_loc)} locations.")
    for loc in sorted(by_loc.keys()):
        print(f"#   {loc}: {len(by_loc[loc])} tracks")


if __name__ == "__main__":
    main()
