"""Pytest fixtures for the e2e replay framework."""
from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Tuple

import pytest

from dr2server.httpd import App, create_server

from .fake_upstream import FakeUpstream
from .replay import Replayer


TESTS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
CAPTURES_DIR = FIXTURES_DIR / "captures"
SNAPSHOTS_DIR = TESTS_DIR / "snapshots"
SEED_FILE = FIXTURES_DIR / "upstream_responses.json"


@dataclass(frozen=True)
class Corpus:
    name: str
    captures_dir: Path
    snapshots_dir: Path
    # Challenge IDs the captured session was inside; the dispatcher normally
    # learns these via Clubs.GetClubs against real upstream data, which we
    # don't have in fixtures. Seeding lets the StageComplete handler resolve
    # to a stable event_id so it actually POSTs upstream.
    seeded_challenge_ids: Dict[int, str]


CORPORA: List[Corpus] = [
    Corpus(
        name="full-session",
        captures_dir=CAPTURES_DIR / "full-session",
        snapshots_dir=SNAPSHOTS_DIR / "full-session",
        seeded_challenge_ids={240681: "test-event-240681"},
    ),
    Corpus(
        name="events-repairs-quit",
        captures_dir=CAPTURES_DIR / "events-repairs-quit",
        snapshots_dir=SNAPSHOTS_DIR / "events-repairs-quit",
        seeded_challenge_ids={262345: "test-event-262345"},
    ),
    Corpus(
        name="single-event",
        captures_dir=CAPTURES_DIR / "single-event",
        snapshots_dir=SNAPSHOTS_DIR / "single-event",
        seeded_challenge_ids={262345: "test-event-262345"},
    ),
]


@pytest.fixture(scope="session")
def fake_upstream() -> Iterator[FakeUpstream]:
    server = FakeUpstream()
    server.start()
    server.load_seed(SEED_FILE)
    yield server
    server.stop()


@pytest.fixture
def dr2_server(
    tmp_path: Path,
    fake_upstream: FakeUpstream,
) -> Iterator[Tuple[str, int, App, FakeUpstream]]:
    """Fresh DR2 server per test, so each corpus replays against clean state.

    Each capture corpus represents an independent gameplay session; reusing
    the dispatcher across corpora would carry over `_challenge_event_map`,
    `_my_username`, etc., and pollute later snapshots.
    """
    fake_upstream.reset()
    app = App(
        data_root=tmp_path / "data",
        capture_root=tmp_path / "replay_captures",
        api_url=fake_upstream.url,
        api_token="df_test",
    )
    server = create_server("127.0.0.1", 0, app)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "127.0.0.1", port, app, fake_upstream
    finally:
        server.shutdown()
        server.server_close()
