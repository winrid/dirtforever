"""Spins up the real `web/server.py` Flask app for e2e tests.

The DR2 server's `DirtForeverClient` POSTs/GETs to dirtforever.net in
production. Tests here run the actual web app against a temp DATA_DIR
so we can exercise the full HTTP path AND assert resulting state in
the on-disk JSON 'database' (data/users, data/events, data/results,
data/time_trials).

Usage (via the `web_app` fixture in conftest.py):
    web_app.reset()                     # wipe data dirs
    web_app.seed_user("sgt", token="df_test", clubs=["test-club"])
    web_app.seed_club("test-club", members=["sgt"])
    web_app.seed_event("evt-000271a6", club_id="test-club")
    # ... run replay ...
    results = web_app.read_results("evt-000271a6")
    tt = web_app.read_time_trials()
"""
from __future__ import annotations

import importlib
import json
import os
import sys
import threading
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from werkzeug.serving import BaseWSGIServer, make_server


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = REPO_ROOT / "web"


class WebApp:
    """Wraps a running werkzeug server hosting web/server.py."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self._make_subdirs()

        # Web server.py reads DATA_DIR at module import time and creates the
        # subdirs there. We must set the env BEFORE importing.
        os.environ["DATA_DIR"] = str(data_dir)
        # Flask-WTF needs a key; use a deterministic one for tests.
        os.environ.setdefault("SECRET_KEY", "test-secret")
        # Disable CSRF for the test client; game endpoints are already
        # @csrf.exempt but other routes aren't, and we only hit the game ones.
        os.environ.setdefault("WTF_CSRF_ENABLED", "0")

        if str(WEB_DIR) not in sys.path:
            sys.path.insert(0, str(WEB_DIR))
        # Force a fresh import so module-level os.makedirs uses our DATA_DIR.
        sys.modules.pop("server", None)
        self._module = importlib.import_module("server")
        flask_app = self._module.app
        flask_app.config["TESTING"] = True
        flask_app.config["WTF_CSRF_ENABLED"] = False

        self._server: BaseWSGIServer = make_server("127.0.0.1", 0, flask_app, threaded=True)
        self.port: int = self._server.server_port
        self.url: str = f"http://127.0.0.1:{self.port}"
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def _make_subdirs(self) -> None:
        for sub in ("users", "clubs", "events", "results", "time_trials"):
            (self.data_dir / sub).mkdir(parents=True, exist_ok=True)

    def reset(self) -> None:
        """Wipe all per-test state from data/. Leaves directory structure intact."""
        for sub in ("users", "clubs", "events", "results", "time_trials"):
            d = self.data_dir / sub
            if not d.exists():
                continue
            for path in d.glob("*.json"):
                path.unlink()

    # ------------------------------------------------------------------
    # Fixture seeding
    # ------------------------------------------------------------------

    def seed_user(
        self,
        username: str,
        *,
        game_token: str,
        clubs: Optional[Iterable[str]] = None,
    ) -> None:
        """Create a minimal user record. Real password hashing is bypassed:
        game endpoints authenticate via Bearer token, not password."""
        user = {
            "username": username,
            "email": f"{username}@example.com",
            "password_hash": "0" * 64,
            "salt": "0" * 32,
            "display_name": username,
            "country": "",
            "bio": "",
            "created_at": "2026-01-01T00:00:00",
            "clubs": list(clubs or []),
            "email_verified": True,
            "verify_token": None,
            "game_token": game_token,
        }
        self._write("users", username, user)

    def seed_club(
        self,
        club_id: str,
        *,
        members: Iterable[str],
        name: Optional[str] = None,
        admins: Optional[Iterable[str]] = None,
    ) -> None:
        members_list = list(members)
        club = {
            "id": club_id,
            "name": name or club_id,
            "description": "",
            "created_by": members_list[0] if members_list else "",
            "created_at": "2026-01-01T00:00:00",
            "members": members_list,
            "admins": list(admins or []),
        }
        self._write("clubs", club_id, club)

    def seed_event(
        self,
        event_id: str,
        *,
        club_id: Optional[str] = None,
        name: Optional[str] = None,
        location: str = "Finland",
        car_class: str = "Group B (RWD)",
        stages: Optional[List[Dict[str, Any]]] = None,
        events: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Seed a championship.

        ``events`` (v2 shape: one dict per rally with its own ``location``,
        ``car_class`` and ``stages``) makes a multi-rally championship; the
        top-level ``stages`` then mirror rally 0, as the web app stores them.
        """
        if events:
            stages = list(events[0].get("stages", []) or [])
        event = {
            "id": event_id,
            "name": name or event_id,
            "type": "club" if club_id else "monthly",
            "location": location,
            "car_class": car_class,
            "surface": "Gravel",
            "conditions": "Day",
            "stages": stages or [{"name": "Stage 1", "distance_km": 10.0, "conditions": "Day"}],
            "start_time": "2026-01-01T00:00:00",
            "end_time": "2027-01-01T00:00:00",
            "active": True,
            "featured": False,
            "club_id": club_id,
            "system": False,
        }
        if events:
            event["schema_version"] = 2
            event["events"] = events
        self._write("events", event_id, event)

    def seed_results(self, event_id: str, entries: List[Dict[str, Any]]) -> None:
        """Seed a results file. Each entry needs ``username`` and ``stages``
        (flat, championship-wide ordinals); ``total_time_ms`` is derived and
        entries are stored sorted by it, as the web app keeps them."""
        out = []
        for e in entries:
            e = dict(e)
            e["total_time_ms"] = sum(
                int(s.get("time_ms", 0) or 0) + int(s.get("penalties_ms", 0) or 0)
                for s in e.get("stages", []) if s and int(s.get("time_ms", 0) or 0) > 0
            )
            e.setdefault("car", "")
            e.setdefault("attempts_used", 0)
            out.append(e)
        out.sort(key=lambda e: e["total_time_ms"])
        self._write("results", event_id, {"event_id": event_id, "entries": out})

    def _write(self, subdir: str, name: str, payload: Dict[str, Any]) -> None:
        (self.data_dir / subdir / f"{name}.json").write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # State readback for assertions / snapshotting
    # ------------------------------------------------------------------

    def read_results(self, event_id: str) -> Optional[Dict[str, Any]]:
        path = self.data_dir / "results" / f"{event_id}.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def read_time_trials(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        d = self.data_dir / "time_trials"
        for path in sorted(d.glob("*.json")):
            out[path.name] = json.loads(path.read_text(encoding="utf-8"))
        return out

    def read_db_state(self) -> Dict[str, Any]:
        """Return the mutated state (results + time_trials) for snapshotting.

        Excludes seeded fixtures (users, clubs, events) since those are
        pre-populated test inputs, not outputs.
        """
        return {
            "results": {
                path.stem: json.loads(path.read_text(encoding="utf-8"))
                for path in sorted((self.data_dir / "results").glob("*.json"))
            },
            "time_trials": self.read_time_trials(),
        }
