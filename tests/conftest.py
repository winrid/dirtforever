"""Pytest fixtures for the e2e replay framework.

Spins up the real `web/server.py` Flask app on loopback and points the
DR2 server's DirtForeverClient at it. Each corpus runs against a fresh
DR2 server with a wiped+reseeded web data directory, so we can both
exercise the real HTTP path and read the resulting on-disk JSON state
to assert what got persisted.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, List, Tuple

import pytest

from dr2server.httpd import App, create_server

from .replay import Replayer
from .web_app import WebApp


TESTS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
CAPTURES_DIR = FIXTURES_DIR / "captures"
SNAPSHOTS_DIR = TESTS_DIR / "snapshots"

GAME_TOKEN = "df_test"
GAME_USER = "sgt"


@dataclass(frozen=True)
class CorpusEvent:
    event_id: str          # the on-disk event id (the file under data/events)
    challenge_id: int      # what dispatcher._stable_int_id() of event_id resolves to
    location: str = "Finland"
    car_class: str = "Group B (RWD)"


@dataclass(frozen=True)
class Corpus:
    name: str
    captures_dir: Path
    snapshots_dir: Path
    # Every event the dispatcher needs to resolve while replaying this
    # corpus. event_id values are picked so dispatcher._stable_int_id(event_id)
    # equals the ChallengeId baked into the captures.
    events: List[CorpusEvent] = field(default_factory=list)


CORPORA: List[Corpus] = [
    Corpus(
        name="full-session",
        captures_dir=CAPTURES_DIR / "full-session",
        snapshots_dir=SNAPSHOTS_DIR / "full-session",
        events=[CorpusEvent(event_id="evt-000271a6", challenge_id=240681)],
    ),
    Corpus(
        name="events-repairs-quit",
        captures_dir=CAPTURES_DIR / "events-repairs-quit",
        snapshots_dir=SNAPSHOTS_DIR / "events-repairs-quit",
        events=[CorpusEvent(event_id="evt-00008b42", challenge_id=262345)],
    ),
    Corpus(
        name="single-event",
        captures_dir=CAPTURES_DIR / "single-event",
        snapshots_dir=SNAPSHOTS_DIR / "single-event",
        events=[CorpusEvent(event_id="evt-00008b42", challenge_id=262345)],
    ),
]


@pytest.fixture(scope="session")
def web_app(tmp_path_factory: pytest.TempPathFactory) -> Iterator[WebApp]:
    """One real Flask web server per test session, hosting on loopback.

    The data directory is cleared and reseeded per corpus by `dr2_server`.
    """
    data_dir = tmp_path_factory.mktemp("web-data")
    app = WebApp(data_dir=data_dir)
    app.start()
    try:
        yield app
    finally:
        app.stop()


@pytest.fixture
def dr2_server(
    tmp_path: Path,
    web_app: WebApp,
    request: pytest.FixtureRequest,
) -> Iterator[Tuple[str, int, App, WebApp]]:
    """Fresh DR2 server per test against a freshly-seeded web data dir.

    The fixture reads the active `corpus` parametrize value (if any) and
    seeds the web app's user/club/events to match what that corpus's
    captures expect; otherwise just creates the test user.
    """
    corpus: Corpus = request.node.callspec.params.get("corpus") if hasattr(request.node, "callspec") else None  # type: ignore[union-attr]
    web_app.reset()
    web_app.seed_user(GAME_USER, game_token=GAME_TOKEN, clubs=["test-club"])
    web_app.seed_club("test-club", members=[GAME_USER])
    if corpus is not None:
        for evt in corpus.events:
            web_app.seed_event(
                evt.event_id,
                club_id="test-club",
                location=evt.location,
                car_class=evt.car_class,
            )

    app = App(
        data_root=tmp_path / "data",
        capture_root=tmp_path / "replay_captures",
        api_url=web_app.url,
        api_token=GAME_TOKEN,
    )
    server = create_server("127.0.0.1", 0, app)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "127.0.0.1", port, app, web_app
    finally:
        server.shutdown()
        server.server_close()
