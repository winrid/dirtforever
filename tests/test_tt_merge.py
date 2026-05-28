"""Time-trial boards merge across category into one ranking.

Boards are stored per category (`{vclass}_{track}_{conditions}_{category}.json`)
because the game posts to a category-keyed leaderboard, but category is not a
meaningful user-facing split and fragments the ranking (hiding the overall
fastest lap on a second board). The web view and game API merge them on read,
keeping each user's best time, while the per-category files stay on disk.
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


@pytest.fixture()
def server_mod(tmp_path):  # type: ignore[no-untyped-def]
    os.environ["DATA_DIR"] = str(tmp_path)
    os.environ.setdefault("SECRET_KEY", "test-secret")
    os.environ.setdefault("WTF_CSRF_ENABLED", "0")
    # There are two `server.py` (repo-root game host + web/). Force web/ to the
    # front so `import server` resolves to the web app. Importing it also pushes
    # the repo root onto sys.path, so re-front it every time.
    while str(WEB_DIR) in sys.path:
        sys.path.remove(str(WEB_DIR))
    sys.path.insert(0, str(WEB_DIR))
    sys.modules.pop("server", None)
    mod = importlib.import_module("server")
    try:
        yield mod
    finally:
        sys.modules.pop("server", None)


def test_merge_dedups_keeping_best(server_mod) -> None:  # type: ignore[no-untyped-def]
    out = server_mod._merge_tt_entries([
        [{"username": "a", "stage_time_ms": 300},
         {"username": "b", "stage_time_ms": 250}],
        [{"username": "a", "stage_time_ms": 200}],  # a is faster in 2nd board
    ])
    assert [(e["username"], e["stage_time_ms"]) for e in out] == [("a", 200), ("b", 250)]


def test_load_tt_merged_collapses_categories(server_mod) -> None:  # type: ignore[no-untyped-def]
    # Same vclass/track/conditions, different category: the fastest lives on
    # category 2 and must surface as #1 in the merged board.
    server_mod._save_tt("93_617_1_1", [{"username": "slow", "stage_time_ms": 265598}])
    server_mod._save_tt("93_617_1_2", [{"username": "fast", "stage_time_ms": 236365}])
    # Different conditions must NOT be merged in.
    server_mod._save_tt("93_617_9_1", [{"username": "other", "stage_time_ms": 1}])

    merged = server_mod._load_tt_merged("93", "617", "1")
    assert [e["username"] for e in merged] == ["fast", "slow"]
    assert all(e["username"] != "other" for e in merged)


def test_load_tt_merged_does_not_prefix_confuse_conditions(server_mod) -> None:  # type: ignore[no-untyped-def]
    # conditions=1 must not pull in conditions=11.
    server_mod._save_tt("93_617_1_1", [{"username": "cond1", "stage_time_ms": 100}])
    server_mod._save_tt("93_617_11_1", [{"username": "cond11", "stage_time_ms": 50}])

    merged = server_mod._load_tt_merged("93", "617", "1")
    assert [e["username"] for e in merged] == ["cond1"]


def test_list_tt_groups_counts_unique_users(server_mod) -> None:  # type: ignore[no-untyped-def]
    # A user present in both categories counts once.
    server_mod._save_tt("93_617_1_1", [
        {"username": "dup", "stage_time_ms": 300},
        {"username": "solo", "stage_time_ms": 320},
    ])
    server_mod._save_tt("93_617_1_2", [{"username": "dup", "stage_time_ms": 250}])

    groups = server_mod._list_tt_groups()
    grp = next(g for g in groups if (g["vclass"], g["track"], g["conditions"]) == (93, 617, 1))
    assert grp["count"] == 2  # dup + solo, not 3
