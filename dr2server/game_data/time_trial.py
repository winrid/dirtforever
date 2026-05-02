"""TimeTrial category ID mappings for DiRT Rally 2.0."""

from __future__ import annotations

from enum import IntEnum


class TimeTrialCategory(IntEnum):
    """Category integer from TimeTrial.GetLeaderboardId / PostTime.

    Hypothesis — not yet confirmed:
      1 = stage-time (per-stage) leaderboard
      2 = cumulative / event leaderboard
    """
    # Observed values: 1 and 2.  Best hypothesis from the dr2_unknowns notes:
    #   1 = single-stage leaderboard
    #   2 = event / cumulative leaderboard (matches SortCumulative flag nearby)
    # Needs confirmation via a manual testing pass that posts a time and then
    # views both the per-stage and the event leaderboards.
    STAGE = 1
    EVENT = 2

    @property
    def label(self) -> str:
        return {
            TimeTrialCategory.STAGE: "Stage",
            TimeTrialCategory.EVENT: "Event",
        }[self]

    def __str__(self) -> str:
        return self.label
