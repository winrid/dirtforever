"""Stage conditions must be valid for the location they are served at.

Regression test for official/club events loading with a broken skybox: the
generator picked StageConditions from one global list regardless of location,
so ~42% of (location, conditions) pairs asked for lighting the location does
not ship — e.g. id 38 (Daytime / Overcast / Dry) at Germany, which only Poland
and Argentina have. RaceNet never validated this, so the game client is the
only check and the server has to get it right.
"""
from __future__ import annotations

import pytest

from dr2server.game_data import (
    Location,
    STAGE_CONDITIONS_BY_LOCATION,
    STAGE_CONDITIONS_LABELS,
    default_stage_conditions_for_location,
    stage_conditions_for_location,
    stage_conditions_options_for_location,
)

# Every location the game lets you pick in Freeplay -> Create Championship was
# swept in-game; Twin Peaks is not selectable there, so it has no verified set.
UNSWEPT = {Location.TWIN_PEAKS}
SWEPT = [loc for loc in Location if loc not in UNSWEPT]


@pytest.mark.parametrize('loc', SWEPT, ids=lambda l: l.name)
def test_every_selectable_location_has_verified_conditions(loc: Location) -> None:
    assert stage_conditions_for_location(loc), (
        f'{loc.name} has no verified StageConditions; events there would have '
        f'nothing valid to serve'
    )


@pytest.mark.parametrize('loc', SWEPT, ids=lambda l: l.name)
def test_default_is_one_of_the_locations_own_options(loc: Location) -> None:
    # The point of the change: the default is per-location, never a global id.
    ids = stage_conditions_for_location(loc)
    assert default_stage_conditions_for_location(loc) == ids[0]


def test_no_universal_default_exists() -> None:
    """Guards the reason there is no global fallback.

    Varmland offers snow conditions only -- it has no "Daytime / Clear / Dry" --
    so id 1 is not safe everywhere and neither is any other single id.
    """
    common = set.intersection(
        *(set(ids) for ids in STAGE_CONDITIONS_BY_LOCATION.values())
    )
    assert not common, (
        f'ids {sorted(common)} appear at every location; if that is genuinely '
        f'true the no-global-default rule could be revisited'
    )
    assert 1 not in stage_conditions_for_location(Location.SWEDEN)


def test_every_served_id_has_a_label() -> None:
    for loc, ids in STAGE_CONDITIONS_BY_LOCATION.items():
        for cid in ids:
            assert cid in STAGE_CONDITIONS_LABELS, (
                f'{loc.name} serves id {cid}, which has no verified label'
            )


def test_no_location_serves_both_halves_of_a_twin_pair() -> None:
    """Three labels are each shared by two ids that select different lighting.

    A location ships one file or the other, so offering both would guarantee
    one of them renders a torn sky -- exactly the bug this table prevents.
    """
    import collections
    by_label = collections.defaultdict(list)
    for cid, lbl in STAGE_CONDITIONS_LABELS.items():
        by_label[lbl].append(cid)
    twins = {frozenset(ids) for ids in by_label.values() if len(ids) > 1}
    for loc, ids in STAGE_CONDITIONS_BY_LOCATION.items():
        for pair in twins:
            assert not pair.issubset(set(ids)), (
                f'{loc.name} offers both of {sorted(pair)}, which render the '
                f'same label -- at most one can be right for a location'
            )


def test_germany_excludes_the_id_that_broke_it() -> None:
    # 38 = "Daytime / Overcast / Dry"; Germany ships no midday_overcast
    # lighting, and its in-game list offers 6 options that do not include it.
    assert 38 not in stage_conditions_for_location(Location.GERMANY)
    assert 38 in stage_conditions_for_location(Location.POLAND)


def test_every_in_game_option_has_an_id() -> None:
    """The table must cover every option the game actually offers.

    The sweep recorded each location's in-game list; serving fewer ids than it
    has options would silently narrow what players can be given.
    """
    import json
    from pathlib import Path

    sweep = json.loads(
        (Path(__file__).resolve().parents[1]
         / 'data/verified/conditions_by_location.json').read_text(encoding='utf-8'))
    offered = {name: len(opts) for name, opts in sweep.items() if opts}
    served = sum(len(ids) for ids in STAGE_CONDITIONS_BY_LOCATION.values())
    assert served == sum(offered.values()), (
        f'{served} ids served for {sum(offered.values())} in-game options'
    )


def test_options_pair_ids_with_labels() -> None:
    opts = stage_conditions_options_for_location(Location.GERMANY)
    assert opts and all(isinstance(cid, int) and label for cid, label in opts)
    assert [cid for cid, _ in opts] == stage_conditions_for_location(Location.GERMANY)


def test_unknown_location_yields_nothing_rather_than_a_guess() -> None:
    assert stage_conditions_for_location('Atlantis') == []
    assert default_stage_conditions_for_location('Atlantis') is None
