"""Unit tests for RpcDispatcher._cap_entries_at_stage."""
from __future__ import annotations

from dr2server.dispatcher import RpcDispatcher


def test_cutoff_zero_filters_dnf_and_sorts():
    entries = [
        {"username": "alice", "stages": [{"time_ms": 60000, "penalties_ms": 1000}]},
        {"username": "bob",   "stages": [{"time_ms": 0,     "penalties_ms": 0}]},
        {"username": "carol", "stages": [{"time_ms": 50000, "penalties_ms": 0}]},
    ]
    out = RpcDispatcher._cap_entries_at_stage(entries, 0)
    assert [e["username"] for e in out] == ["carol", "alice"]
    assert out[0]["partial_total_ms"] == 50000
    assert out[1]["partial_total_ms"] == 61000


def test_short_stages_list_excluded():
    entries = [
        {"username": "alice", "stages": [
            {"time_ms": 60000, "penalties_ms": 0},
            {"time_ms": 70000, "penalties_ms": 0},
        ]},
        {"username": "bob", "stages": [
            {"time_ms": 60000, "penalties_ms": 0},
            {"time_ms": 70000, "penalties_ms": 0},
            {"time_ms": 80000, "penalties_ms": 0},
        ]},
    ]
    out = RpcDispatcher._cap_entries_at_stage(entries, 2)
    assert [e["username"] for e in out] == ["bob"]
    assert out[0]["partial_total_ms"] == 60000 + 70000 + 80000


def test_zero_time_at_cutoff_excluded():
    entries = [
        {"username": "alice", "stages": [
            {"time_ms": 60000, "penalties_ms": 0},
            {"time_ms": 0,     "penalties_ms": 0},
        ]},
        {"username": "bob", "stages": [
            {"time_ms": 60000, "penalties_ms": 0},
            {"time_ms": 70000, "penalties_ms": 0},
        ]},
    ]
    out = RpcDispatcher._cap_entries_at_stage(entries, 1)
    assert [e["username"] for e in out] == ["bob"]


def test_penalties_summed():
    entries = [
        {"username": "alice", "stages": [
            {"time_ms": 60000, "penalties_ms": 500},
            {"time_ms": 70000, "penalties_ms": 1000},
        ]},
    ]
    out = RpcDispatcher._cap_entries_at_stage(entries, 1)
    assert len(out) == 1
    assert out[0]["partial_total_ms"] == 60000 + 500 + 70000 + 1000


def test_empty_input():
    assert RpcDispatcher._cap_entries_at_stage([], 3) == []


def test_stable_sort_ties_preserve_input_order():
    entries = [
        {"username": "alice", "stages": [{"time_ms": 60000, "penalties_ms": 0}]},
        {"username": "bob",   "stages": [{"time_ms": 60000, "penalties_ms": 0}]},
        {"username": "carol", "stages": [{"time_ms": 60000, "penalties_ms": 0}]},
    ]
    out = RpcDispatcher._cap_entries_at_stage(entries, 0)
    assert [e["username"] for e in out] == ["alice", "bob", "carol"]


def test_none_stage_excludes_entry():
    entries = [
        {"username": "alice", "stages": [
            {"time_ms": 60000, "penalties_ms": 0},
            None,
        ]},
        {"username": "bob", "stages": [
            {"time_ms": 60000, "penalties_ms": 0},
            {"time_ms": 70000, "penalties_ms": 0},
        ]},
    ]
    out = RpcDispatcher._cap_entries_at_stage(entries, 1)
    assert [e["username"] for e in out] == ["bob"]


def test_does_not_mutate_input():
    entries = [
        {"username": "alice", "stages": [{"time_ms": 60000, "penalties_ms": 0}]},
    ]
    out = RpcDispatcher._cap_entries_at_stage(entries, 0)
    assert "partial_total_ms" not in entries[0]
    assert out[0]["partial_total_ms"] == 60000


def test_start_index_totals_only_this_rally():
    # Two-rally championship: rally 1 = stages 0-1, rally 2 = stages 2-3.
    entries = [
        {"username": "alice", "stages": [
            {"time_ms": 100000, "penalties_ms": 0},
            {"time_ms": 100000, "penalties_ms": 0},
            {"time_ms": 50000,  "penalties_ms": 1000},
            {"time_ms": 60000,  "penalties_ms": 0},
        ]},
        {"username": "bob", "stages": [
            {"time_ms": 10000, "penalties_ms": 0},
            {"time_ms": 10000, "penalties_ms": 0},
            {"time_ms": 70000, "penalties_ms": 0},
            {"time_ms": 70000, "penalties_ms": 0},
        ]},
    ]
    out = RpcDispatcher._cap_entries_at_stage(entries, 3, start_stage_index=2)
    # Bob is far ahead on the championship total but alice wins rally 2.
    assert [e["username"] for e in out] == ["alice", "bob"]
    assert out[0]["partial_total_ms"] == 50000 + 1000 + 60000
    assert out[1]["partial_total_ms"] == 140000


def test_start_index_ignores_missing_earlier_rally():
    entries = [
        {"username": "alice", "stages": [
            {"time_ms": 0, "penalties_ms": 0},
            {"time_ms": 0, "penalties_ms": 0},
            {"time_ms": 50000, "penalties_ms": 0},
        ]},
    ]
    out = RpcDispatcher._cap_entries_at_stage(entries, 2, start_stage_index=2)
    assert [e["username"] for e in out] == ["alice"]
    assert out[0]["partial_total_ms"] == 50000


def test_time_in_range_sums_only_this_rally():
    completed = [
        {"stage_index": 0, "time_ms": 100},
        {"stage_index": 1, "time_ms": 200},
        {"stage_index": 2, "time_ms": 300},
        {"stage_index": 3, "time_ms": 400},
    ]
    assert RpcDispatcher._time_in_range(completed, 2, 2) == 700
    assert RpcDispatcher._time_in_range(completed, 0, 2) == 300
    assert RpcDispatcher._time_in_range(completed, 0, None) == 1000
    assert RpcDispatcher._time_in_range(completed, 4, 2) == 0
