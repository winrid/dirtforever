"""Replays bundled DR2 session capture corpora end-to-end.

Each corpus (a directory under tests/fixtures/captures/) is replayed in its
own test against a fresh DR2 server + fake upstream. Captures are sent over
real HTTP byte-for-byte from `body_base64` (with the live X-EgoNet-SessionID
substituted in once Login.Login establishes one). Per capture we snapshot
the response and the upstream calls it triggered.

We also assert per-capture that times round-trip correctly:
  - TimeTrial.PostTime decoded `StageTime` in seconds reaches the upstream
    POST as `stage_time_ms = int(StageTime * 1000)`.
  - RaceNetChallenges.StageComplete with RaceStatus=0 likewise reaches the
    upstream POST with `time_ms = int(StageTime * 1000)`.
"""
from __future__ import annotations

import base64
from typing import Any, Dict, List

import pytest

from dr2server.httpd import App

from .conftest import CORPORA, Corpus
from .fake_upstream import FakeUpstream
from .normalize import normalize_decoded_body, normalize_response_headers
from .replay import Capture, Replayer
from .snapshot import assert_snapshot


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


def _build_snapshot(
    capture: Capture,
    status: int,
    headers: Dict[str, str],
    decoded_body: Any,
    upstream_calls: List[Dict[str, Any]],
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
        "upstream_calls": upstream_calls,
    }


@pytest.mark.parametrize("corpus", CORPORA, ids=[c.name for c in CORPORA])
def test_replay_corpus(
    corpus: Corpus,
    dr2_server,
    fake_upstream: FakeUpstream,
) -> None:
    host, port, app, _ = dr2_server
    replayer = Replayer(server_host=host, server_port=port)

    for chal_id, event_id in corpus.seeded_challenge_ids.items():
        app.dispatcher._challenge_event_map[chal_id] = event_id

    captures = Replayer.load_corpus(corpus.captures_dir)
    assert captures, f"No captures found in {corpus.captures_dir}"

    fake_upstream.reset()

    seen_post_time = False
    seen_stage_complete = False

    for capture in captures:
        result = replayer.replay(capture)
        assert result.status == 200, (
            f"[{corpus.name}] {capture.name}: expected 200, got {result.status}\n"
            f"body={result.body_bytes[:200]!r}"
        )

        new_calls = fake_upstream.take_calls()
        upstream_calls = [
            {"method": call.method, "path": call.path, "payload": call.payload}
            for call in new_calls
        ]

        snapshot = _build_snapshot(
            capture,
            result.status,
            result.headers,
            result.decoded_body,
            upstream_calls,
        )
        assert_snapshot(capture.name, snapshot, corpus.snapshots_dir)

        if capture.egonet_function == "TimeTrial.PostTime":
            seen_post_time = True
            stage_time = float(capture.data["decoded_body"]["StageTime"])
            expected_ms = int(stage_time * 1000)
            tt_posts = [
                call for call in new_calls
                if call.method == "POST" and call.path == "/api/game/time-trial-submit"
            ]
            assert len(tt_posts) == 1, (
                f"[{corpus.name}] {capture.name}: expected exactly one POST "
                f"/api/game/time-trial-submit, saw {len(tt_posts)}: {tt_posts!r}"
            )
            assert tt_posts[0].payload["stage_time_ms"] == expected_ms, (
                f"[{corpus.name}] {capture.name}: stage_time_ms round-trip failed. "
                f"StageTime={stage_time}s expected_ms={expected_ms} "
                f"actual={tt_posts[0].payload.get('stage_time_ms')}"
            )

        if capture.egonet_function == "RaceNetChallenges.StageComplete":
            body = capture.data["decoded_body"]
            stage_time = float(body["StageTime"])
            race_status = body.get("RaceStatus", 0) or 0
            sc_posts = [
                call for call in new_calls
                if call.method == "POST" and call.path == "/api/game/stage-complete"
            ]
            if race_status == 0:
                seen_stage_complete = True
                expected_ms = int(stage_time * 1000)
                assert len(sc_posts) == 1, (
                    f"[{corpus.name}] {capture.name}: expected one POST "
                    f"/api/game/stage-complete on clean finish, saw {len(sc_posts)}"
                )
                assert sc_posts[0].payload["time_ms"] == expected_ms, (
                    f"[{corpus.name}] {capture.name}: time_ms round-trip failed. "
                    f"StageTime={stage_time}s expected_ms={expected_ms} "
                    f"actual={sc_posts[0].payload.get('time_ms')}"
                )
            else:
                assert sc_posts == [], (
                    f"[{corpus.name}] {capture.name}: race_status={race_status} "
                    f"should not POST stage-complete, but saw {sc_posts}"
                )

    assert seen_post_time or seen_stage_complete, (
        f"[{corpus.name}]: corpus contained neither TimeTrial.PostTime nor "
        f"RaceNetChallenges.StageComplete - round-trip checks all skipped"
    )
