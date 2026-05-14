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
