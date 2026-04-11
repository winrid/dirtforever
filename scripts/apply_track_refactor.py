"""Apply the generated Track enum refactor to dr2server/game_data.py.

Replaces the Track class and _TRACK_META block with the newly-generated
content from runtime/discovery/new_track_enum_fixed.py.
"""
from __future__ import annotations

GAME_DATA = "C:/Users/winrid/dr2server/dr2server/game_data.py"
NEW_BLOCK = "C:/Users/winrid/dr2server/runtime/discovery/new_track_enum_fixed.py"

with open(GAME_DATA, encoding="utf-8") as f:
    orig = f.read()
with open(NEW_BLOCK, encoding="utf-8") as f:
    new_block = f.read().rstrip() + "\n\n"

# Locate the old block bounds.
comment_start = orig.rfind(
    "# ---------------------------------------------------------------------------\n# Track models"
)
if comment_start < 0:
    raise SystemExit("old Track comment header not found")

end_marker = "\n# ---------------------------------------------------------------------------\n# Vehicle classes"
end = orig.find(end_marker)
if end < 0:
    raise SystemExit("VehicleClass header not found")

# Find the last '}\n' before the vehicle classes section — that's _TRACK_META's close.
end_of_meta = orig.rfind("}\n", comment_start, end) + 2

# Prepend a comment block that preserves the old section header style.
preamble = (
    "# ---------------------------------------------------------------------------\n"
    "# Track models — TrackModelId maps to a specific stage route\n"
    "# ---------------------------------------------------------------------------\n"
    "#\n"
    "# Track names and their Location attribution were verified in-game\n"
    "# 2026-04-11 via the enum-mapping discovery round (see\n"
    "# runtime/discovery/track_mapping.json).  98 tracks confirmed across\n"
    "# 15 locations.  Tracks not yet probed are not listed here.\n"
    "\n"
)

new_content = orig[:comment_start] + preamble + new_block + orig[end_of_meta:]

with open(GAME_DATA, "w", encoding="utf-8") as f:
    f.write(new_content)

print(f"rewritten: {len(orig)} -> {len(new_content)} bytes")
print(f"delta: {len(new_content) - len(orig):+d} bytes")
