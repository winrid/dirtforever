"""In-process HTTP server impersonating dirtforever.net for tests.

The DR2 server's `DirtForeverClient` (api_client.py) POSTs/GETs against this
server when its `base_url` is pointed at us. We:
  - record every request (method, path, payload) on `received_calls`
  - return canned responses loaded from a JSON seed map

Tests call `take_calls()` to drain the buffer between replayed captures.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Call:
    method: str
    path: str
    payload: Optional[Dict[str, Any]] = None


@dataclass
class FakeUpstreamState:
    received_calls: List[Call] = field(default_factory=list)
    seed_responses: Dict[Tuple[str, str], Dict[str, Any]] = field(default_factory=dict)
    default_responses: Dict[str, Dict[str, Any]] = field(default_factory=dict)


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return

    @property
    def state(self) -> FakeUpstreamState:
        return self.server.state  # type: ignore[attr-defined]

    def _read_payload(self) -> Optional[Dict[str, Any]]:
        length = int(self.headers.get("Content-Length", "0"))
        if not length:
            return None
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {"__raw_base64": raw.hex()}

    def _send(self, body: Dict[str, Any], status: int = 200) -> None:
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _resolve_response(self, method: str, path: str) -> Dict[str, Any]:
        if (method, path) in self.state.seed_responses:
            return self.state.seed_responses[(method, path)]
        # Fall back to a default keyed by path-prefix or exact match.
        for key, body in self.state.default_responses.items():
            if path == key or path.startswith(key + "/") or path.startswith(key + "?"):
                return body
        return {"ok": True}

    def do_GET(self) -> None:
        self.state.received_calls.append(Call(method="GET", path=self.path))
        body = self._resolve_response("GET", self.path)
        self._send(body)

    def do_POST(self) -> None:
        payload = self._read_payload()
        self.state.received_calls.append(Call(method="POST", path=self.path, payload=payload))
        body = self._resolve_response("POST", self.path)
        self._send(body)


class FakeUpstream:
    def __init__(self) -> None:
        self.state = FakeUpstreamState()
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self.url: str = ""

    def start(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        server.state = self.state  # type: ignore[attr-defined]
        port = server.server_address[1]
        self._server = server
        self._thread = threading.Thread(target=server.serve_forever, daemon=True)
        self._thread.start()
        self.url = f"http://127.0.0.1:{port}"

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

    def reset(self) -> None:
        self.state.received_calls.clear()

    def load_seed(self, path: Path) -> None:
        """Load canned responses from a JSON file.

        File schema:
            {
              "GET /api/game/clubs": {"ok": true, "clubs": [...], "events": [...]},
              "POST /api/game/stage-complete": {"ok": true},
              "_defaults": {
                "/api/game/leaderboard": {"ok": true, "entries": []}
              }
            }
        """
        if not path.exists():
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        defaults = data.pop("_defaults", {})
        for key, body in data.items():
            method, request_path = key.split(" ", 1)
            self.state.seed_responses[(method.upper(), request_path)] = body
        self.state.default_responses.update(defaults)

    def take_calls(self) -> List[Call]:
        """Drain and return all calls received since last reset/take."""
        calls = list(self.state.received_calls)
        self.state.received_calls.clear()
        return calls
