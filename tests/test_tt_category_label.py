"""TimeTrial category ids get distinct human-readable labels.

Regression test: the leaderboard variant picker labelled boards with only
the conditions, so two boards that shared conditions but differed by category
(e.g. 93_617_1_1 vs 93_617_1_2) rendered as identical buttons.
"""
from __future__ import annotations

from dr2server.game_data import time_trial_category_label


def test_known_categories() -> None:
    assert time_trial_category_label(1) == "Stage"
    assert time_trial_category_label(2) == "Event"


def test_unknown_category_falls_back() -> None:
    assert time_trial_category_label(7) == "Category 7"


def test_distinct_labels_per_category() -> None:
    # Same conditions, different category must produce different labels.
    cond = "Daytime / Clear / Dry"
    a = f"{cond} ({time_trial_category_label(1)})"
    b = f"{cond} ({time_trial_category_label(2)})"
    assert a != b
