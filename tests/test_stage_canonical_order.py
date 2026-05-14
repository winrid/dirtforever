"""Guard: web's STAGES order must match dr2server's dispatcher order.

The dispatcher (dr2server/dispatcher.py) assigns track IDs to stages
positionally — ``track_ids[stage_index]`` — using
``get_tracks_for_location(loc_id)``.  The website then displays the i-th
entry of ``STAGES[location_name]`` as "S(i+1)".  Drift between these two
lists causes submitted stage times to be attributed to the wrong stage
name, which is the bug this fix exists to prevent.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("SECRET_KEY", "test")

from dr2server.game_data import Track, get_tracks_for_location  # noqa: E402
from web.server import STAGES, _RALLY_LOCATIONS  # type: ignore  # noqa: E402


@pytest.mark.parametrize("web_name,location", sorted(_RALLY_LOCATIONS.items()))
def test_stages_match_canonical_track_order(web_name: str, location) -> None:
    track_ids = get_tracks_for_location(int(location))
    canonical_names = [Track(tid).display_name for tid in track_ids]
    web_names = [name for name, _dist in STAGES[web_name]]
    assert web_names == canonical_names, (
        f"STAGES[{web_name!r}] is out of sync with "
        f"dr2server tracks_for_location({int(location)}). "
        f"Expected order: {canonical_names}; got: {web_names}."
    )
