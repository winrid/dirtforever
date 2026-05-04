"""Replays bundled DR2 session capture corpora end-to-end.

Each corpus replays through:
  [replayer] -- HTTP --> [DR2 server] -- HTTP --> [real web app]

The web app persists state to JSON files under a per-test temp data dir.
After replay we read the resulting `results/<event_id>.json` and
`time_trials/*.json` and assert that StageTime values from the captures
landed there as `int(StageTime * 1000)` ms.

Per-capture response snapshots live under tests/snapshots/<corpus>/.
A separate end-of-corpus DB-state snapshot lives at
tests/snapshots/<corpus>/_db_state.json.
"""
from __future__ import annotations

import base64
import re
from typing import Any, Dict

import pytest

from .conftest import CORPORA, Corpus
from .normalize import normalize_decoded_body, normalize_response_headers
from .replay import Capture, Replayer
from .snapshot import assert_snapshot
from .web_app import WebApp


def _serialize_decoded_body(body: Any) -> Any:
    """Make egonet-decoded structures JSON-friendly for snapshotting."""
    from dr2server.egonet import Int64, Timestamp, UInt8, UInt16, UInt32

    if isinstance(body, (UInt32, UInt16, UInt8, Int64, Timestamp)):
        return body.value
    if isinstance(body, bytes):
        return {"__bytes_b64": base64.b64encode(body).decode("ascii"), "size": len(body)}
    if isinstance(body, dict):
        return {key: _serialize_decoded_body(value) for key, value in body.items()}
    if isinstance(body, (list, tuple)):
        return [_serialize_decoded_body(item) for item in body]
    return body


def _build_response_snapshot(
    capture: Capture,
    status: int,
    headers: Dict[str, str],
    decoded_body: Any,
) -> Dict[str, Any]:
    return {
        "request_summary": {
            "egonet_function": capture.egonet_function,
            "method": capture.data.get("method"),
            "path": capture.request_path,
        },
        "response": {
            "status": status,
            "headers": normalize_response_headers(headers),
            "decoded_body": normalize_decoded_body(_serialize_decoded_body(decoded_body)),
        },
    }


_TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?")


def _normalize_db(value: Any) -> Any:
    """Strip non-deterministic fields (timestamps, ghost data) from the
    persisted state before snapshotting."""
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for key, item in value.items():
            if key in ("submitted_at", "created_at"):
                out[key] = "<TIMESTAMP>" if item else item
            elif key == "ghost_data_b64":
                out[key] = f"<GHOST_DATA len={len(item) if isinstance(item, str) else 0}>"
            else:
                out[key] = _normalize_db(item)
        return out
    if isinstance(value, list):
        return [_normalize_db(item) for item in value]
    if isinstance(value, str) and _TIMESTAMP_RE.fullmatch(value):
        return "<TIMESTAMP>"
    return value


@pytest.mark.parametrize("corpus", CORPORA, ids=[c.name for c in CORPORA])
def test_replay_corpus(corpus: Corpus, dr2_server) -> None:
    host, port, app, web_app = dr2_server  # type: ignore[misc]
    replayer = Replayer(server_host=host, server_port=port)

    captures = Replayer.load_corpus(corpus.captures_dir)
    assert captures, f"No captures found in {corpus.captures_dir}"

    seen_post_time = False
    seen_stage_complete = False

    for capture in captures:
        result = replayer.replay(capture)
        assert result.status == 200, (
            f"[{corpus.name}] {capture.name}: expected 200, got {result.status}\n"
            f"body={result.body_bytes[:200]!r}"
        )
        snapshot = _build_response_snapshot(
            capture, result.status, result.headers, result.decoded_body
        )
        assert_snapshot(capture.name, snapshot, corpus.snapshots_dir)

        if capture.egonet_function == "TimeTrial.PostTime":
            seen_post_time = True
        if capture.egonet_function == "RaceNetChallenges.StageComplete":
            body = capture.data["decoded_body"]
            if (body.get("RaceStatus", 0) or 0) == 0:
                seen_stage_complete = True

    # End-of-corpus DB-state snapshot: only the mutated dirs.
    db_state = web_app.read_db_state()
    assert_snapshot("_db_state", _normalize_db(db_state), corpus.snapshots_dir)

    # Round-trip checks: every captured StageTime must appear in the DB
    # exactly as int(StageTime * 1000).
    expected_tt_times: list[int] = []
    expected_stage_times: list[tuple[str, int]] = []
    for capture in captures:
        body = capture.data.get("decoded_body") or {}
        if capture.egonet_function == "TimeTrial.PostTime":
            expected_tt_times.append(int(float(body["StageTime"]) * 1000))
        elif capture.egonet_function == "RaceNetChallenges.StageComplete":
            if (body.get("RaceStatus", 0) or 0) != 0:
                continue
            for evt in corpus.events:
                if int(body.get("ChallengeId") or body.get("ChallengeID") or 0) == evt.challenge_id:
                    expected_stage_times.append(
                        (evt.event_id, int(float(body["StageTime"]) * 1000))
                    )
                    break

    if expected_tt_times:
        all_tt_times: list[int] = []
        for entries in db_state["time_trials"].values():
            for entry in entries:
                all_tt_times.append(int(entry["stage_time_ms"]))
        for ms in expected_tt_times:
            assert ms in all_tt_times, (
                f"[{corpus.name}] expected stage_time_ms={ms} in time_trials, "
                f"got {sorted(all_tt_times)}"
            )

    for event_id, ms in expected_stage_times:
        results = db_state["results"].get(event_id)
        assert results is not None, (
            f"[{corpus.name}] expected results/{event_id}.json to exist"
        )
        all_stage_times: list[int] = []
        for entry in results.get("entries", []):
            for stage in entry.get("stages", []):
                if stage.get("time_ms"):
                    all_stage_times.append(int(stage["time_ms"]))
        assert ms in all_stage_times, (
            f"[{corpus.name}] expected stage time_ms={ms} in results/{event_id}.json, "
            f"got {sorted(all_stage_times)}"
        )

    assert seen_post_time or seen_stage_complete, (
        f"[{corpus.name}]: corpus had no time-bearing RPC; round-trip checks skipped"
    )
