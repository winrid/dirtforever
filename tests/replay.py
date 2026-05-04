"""Capture replay engine.

Reads JSON capture files (the format dr2server/httpd.py writes), sorts them
chronologically by filename, and replays each one against a running DR2
server over real HTTP. Maintains a session-id substitution map so that the
captured X-EgoNet-SessionID is rewritten to the server's freshly minted one
after Login.Login.
"""
from __future__ import annotations

import base64
import http.client
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dr2server.egonet import decode_stream


@dataclass
class Capture:
    path: Path
    name: str
    data: Dict[str, Any]

    @property
    def egonet_function(self) -> str:
        return str(self.data.get("headers", {}).get("X-EgoNet-Function", ""))

    @property
    def request_path(self) -> str:
        return str(self.data.get("path", "/"))

    @property
    def headers(self) -> Dict[str, str]:
        return {
            str(key): str(value)
            for key, value in self.data.get("headers", {}).items()
        }

    @property
    def body_bytes(self) -> bytes:
        b64 = self.data.get("body_base64")
        if b64:
            return base64.b64decode(b64)
        text = self.data.get("body_text", "")
        return text.encode("utf-8") if isinstance(text, str) else b""


@dataclass
class ReplayResult:
    status: int
    headers: Dict[str, str]
    body_bytes: bytes
    decoded_body: Any


@dataclass
class Replayer:
    server_host: str
    server_port: int
    session_map: Dict[str, str] = field(default_factory=dict)

    @staticmethod
    def load_corpus(directory: Path) -> List[Capture]:
        files = sorted(directory.glob("*.json"))
        captures: List[Capture] = []
        for f in files:
            data = json.loads(f.read_text(encoding="utf-8"))
            captures.append(Capture(path=f, name=f.name, data=data))
        return captures

    def _prepare_headers(self, capture: Capture) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        for key, value in capture.headers.items():
            key_lower = key.lower()
            if key_lower in ("host", "content-length", "connection"):
                continue
            if key_lower == "x-egonet-sessionid":
                live = self.session_map.get(value)
                if live:
                    headers[key] = live
                    continue
            headers[key] = value
        return headers

    def _decode_response(self, body: bytes, content_type: str) -> Any:
        if not body:
            return None
        if "egonet-stream" in content_type or "text/html" in content_type:
            try:
                return decode_stream(body)
            except Exception:
                pass
        # Fall back to JSON, then to a base64 wrapper.
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {"__raw_base64": base64.b64encode(body).decode("ascii")}

    def replay(self, capture: Capture) -> ReplayResult:
        body = capture.body_bytes
        headers = self._prepare_headers(capture)
        # Always restate Content-Length to match the (possibly identical) bytes.
        headers["Content-Length"] = str(len(body))

        conn = http.client.HTTPConnection(self.server_host, self.server_port, timeout=10)
        try:
            method = str(capture.data.get("method", "GET")).upper()
            url_path = capture.request_path
            query = capture.data.get("query") or {}
            if query:
                # query is parse_qs output: dict[str, list[str]] -> rebuild querystring
                from urllib.parse import urlencode
                pairs: List[Tuple[str, str]] = []
                for key, values in query.items():
                    for value in values:
                        pairs.append((key, value))
                if pairs:
                    url_path = f"{url_path}?{urlencode(pairs)}"
            conn.request(method, url_path, body=body, headers=headers)
            resp = conn.getresponse()
            resp_body = resp.read()
            resp_headers = {key: value for key, value in resp.getheaders()}
            status = resp.status
        finally:
            conn.close()

        # Capture session ID from Login.Login responses for downstream substitution.
        if capture.egonet_function == "Login.Login":
            live_session = resp_headers.get("X-EgoNet-SessionID") or resp_headers.get("x-egonet-sessionid")
            if live_session:
                self._record_login_session(live_session, capture)

        decoded = self._decode_response(resp_body, resp_headers.get("Content-Type", ""))
        return ReplayResult(
            status=status,
            headers=resp_headers,
            body_bytes=resp_body,
            decoded_body=decoded,
        )

    def _record_login_session(
        self,
        live_session: str,
        login_capture: Capture,
    ) -> None:
        response = login_capture.data.get("response")
        if not isinstance(response, dict):
            return
        captured_response_session = response.get("headers", {}).get("X-EgoNet-SessionID")
        if captured_response_session and captured_response_session not in self.session_map:
            self.session_map[captured_response_session] = live_session

