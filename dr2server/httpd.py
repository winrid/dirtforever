from __future__ import annotations

import argparse
import base64
import http.client
import json
import secrets
import ssl
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any, Dict, Optional, Set
from urllib.parse import parse_qs, urlparse

from .account_store import AccountStore
from .api_client import DirtForeverClient
from .dispatcher import RpcDispatcher
from .egonet import decode_stream, encode_stream


HTML_HOME = """<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <title>DR2 Community Server</title>
  </head>
  <body>
    <h1>DR2 Community Server</h1>
    <p>This is the bootstrap server for backend emulation and request capture.</p>
    <ul>
      <li><a href="/register">Register account</a></li>
      <li><a href="/login">Login test</a></li>
      <li><a href="/api/health">Health</a></li>
    </ul>
  </body>
</html>
"""

HTML_REGISTER = """<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <title>Register</title>
  </head>
  <body>
    <h1>Create Account</h1>
    <form method="post" action="/api/account/register">
      <label>Username <input name="username" /></label><br />
      <label>Email <input name="email" /></label><br />
      <label>Password <input type="password" name="password" /></label><br />
      <button type="submit">Register</button>
    </form>
  </body>
</html>
"""

HTML_LOGIN = """<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <title>Login</title>
  </head>
  <body>
    <h1>Login Test</h1>
    <form method="post" action="/api/account/login">
      <label>Username <input name="username" /></label><br />
      <label>Password <input type="password" name="password" /></label><br />
      <button type="submit">Login</button>
    </form>
  </body>
</html>
"""


class App:
    def __init__(
        self,
        data_root: Path,
        capture_root: Path,
        upstream_ip: Optional[str] = None,
        proxy_methods: Optional[Set[str]] = None,
        api_url: Optional[str] = None,
    ) -> None:
        self.account_store = AccountStore(data_root / "accounts")
        api_client: Optional[DirtForeverClient] = None
        if api_url:
            api_client = DirtForeverClient(base_url=api_url)
            print(f"[API] Connected to dirtforever API at {api_url}")
        self.dispatcher = RpcDispatcher(self.account_store, api_client=api_client)
        self.capture_root = capture_root
        self.capture_root.mkdir(parents=True, exist_ok=True)
        self.upstream_ip = upstream_ip
        self.proxy_methods: Set[str] = proxy_methods if proxy_methods is not None else set()
        # When Login.Login is proxied, the upstream session ID is stored here
        # so subsequent proxied calls can use it.
        self.upstream_session: Optional[str] = None

    @staticmethod
    def _json_default(obj: Any) -> Any:
        from .egonet import Timestamp, UInt32, UInt8, Int64
        if isinstance(obj, (Timestamp, UInt32, UInt8, Int64)):
            return obj.value
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    def capture(self, request: Dict[str, Any]) -> Path:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        path = self.capture_root / f"{stamp}-{time.time_ns()}.json"
        path.write_text(json.dumps(request, indent=2, default=self._json_default), encoding="utf-8")
        return path

    def capture_response(self, capture_path: Path, response: Dict[str, Any]) -> None:
        try:
            existing = json.loads(capture_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        existing["response"] = response
        capture_path.write_text(json.dumps(existing, indent=2, default=self._json_default), encoding="utf-8")


class RequestHandler(BaseHTTPRequestHandler):
    server_version = "DR2CommunityServer/0.1"

    @property
    def app(self) -> App:
        return self.server.app  # type: ignore[attr-defined]

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        capture_path = self.app.capture(
            {
                "method": self.command,
                "path": parsed.path,
                "query": parse_qs(parsed.query),
                "headers": dict(self.headers.items()),
                "body_text": "",
                "decoded_body": {},
            }
        )
        if parsed.path == "/":
            return self._send_html(HTML_HOME)
        if parsed.path == "/register":
            return self._send_html(HTML_REGISTER)
        if parsed.path == "/login":
            return self._send_html(HTML_LOGIN)
        if parsed.path == "/api/health":
            return self._send_json({"ok": True, "status": "healthy", "capture_file": str(capture_path)})
        self._send_json({"ok": False, "error": "not found", "capture_file": str(capture_path)}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length) if content_length else b""
        # Store raw body so the proxy handler can access it without re-reading
        self._raw_body = raw_body
        parsed_body = self._decode_body(raw_body)
        header_map = {key.lower(): value for key, value in self.headers.items()}
        egonet_function = header_map.get("x-egonet-function", "")

        capture_path = self.app.capture(
            {
                "method": self.command,
                "path": parsed.path,
                "query": parse_qs(parsed.query),
                "headers": dict(self.headers.items()),
                "body_text": raw_body.decode("utf-8", errors="replace"),
                "body_base64": base64.b64encode(raw_body).decode("ascii"),
                "decoded_body": parsed_body,
            }
        )

        if egonet_function:
            return self._handle_egonet_rpc(egonet_function, parsed_body, capture_path)

        if parsed.path == "/api/account/register":
            return self._handle_register(parsed_body, capture_path)
        if parsed.path == "/api/account/login":
            return self._handle_login(parsed_body, capture_path)
        if parsed.path == "/rpc":
            return self._handle_rpc(parsed_body, None, capture_path)
        if parsed.path.startswith("/rpc/"):
            method = parsed.path.split("/rpc/", 1)[1]
            return self._handle_rpc(parsed_body, method, capture_path)

        # Fallback for clients that post directly to a method-like path.
        method_name = parsed.path.strip("/").replace("/", ".")
        if "." in method_name:
            return self._handle_rpc(parsed_body, method_name, capture_path)

        self._send_json(
            {"ok": False, "error": "not found", "capture_file": str(capture_path)},
            status=HTTPStatus.NOT_FOUND,
        )

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress default HTTP request logging (too noisy)
        pass

    def _handle_register(self, payload: Dict[str, Any], capture_path: Path) -> None:
        try:
            account = self.app.account_store.create_account(
                username=str(payload.get("username", "")),
                password=str(payload.get("password", "")),
                email=str(payload.get("email", "")),
            )
        except ValueError as exc:
            self._send_json({"ok": False, "error": str(exc), "capture_file": str(capture_path)}, status=HTTPStatus.BAD_REQUEST)
            return

        self._send_json(
            {
                "ok": True,
                "account": {
                    "username": account.username,
                    "email": account.email,
                },
                "capture_file": str(capture_path),
            }
        )

    def _handle_login(self, payload: Dict[str, Any], capture_path: Path) -> None:
        account = self.app.account_store.authenticate(
            username=str(payload.get("username", "")),
            password=str(payload.get("password", "")),
        )
        if not account:
            self._send_json({"ok": False, "error": "invalid credentials", "capture_file": str(capture_path)}, status=HTTPStatus.UNAUTHORIZED)
            return

        self._send_json(
            {
                "ok": True,
                "username": account.username,
                "profile": account.profile,
                "capture_file": str(capture_path),
            }
        )

    def _handle_rpc(self, payload: Dict[str, Any], path_method: Optional[str], capture_path: Path) -> None:
        method = path_method or str(payload.get("method", "")).strip()
        params = payload.get("params", payload)
        if not method:
            self._send_json({"ok": False, "error": "missing method", "capture_file": str(capture_path)}, status=HTTPStatus.BAD_REQUEST)
            return
        if not isinstance(params, dict):
            params = {"value": params}

        result = self.app.dispatcher.dispatch(method, params)
        result["capture_file"] = str(capture_path)
        self._send_json(result)

    def _handle_egonet_rpc(self, method: str, payload: Dict[str, Any], capture_path: Path) -> None:
        is_proxied = self.app.upstream_ip and method in self.app.proxy_methods
        print(f"[RPC] {method}{'  [PROXY]' if is_proxied else ''}")

        # Check if this method should be proxied upstream
        if is_proxied:
            return self._handle_egonet_proxy(method, capture_path)

        if method == "Login.Login":
            return self._handle_egonet_login(payload, capture_path)

        result = self.app.dispatcher.dispatch(method, payload)

        # If dispatcher returned raw binary bytes (e.g. from upstream template),
        # send them directly without re-encoding.
        if isinstance(result, bytes):
            extra_headers: Dict[str, str] = {
                "X-EgoNet-Result": "0",
                "X-EgoNet-Catalogue-Version": "1.18.0",
            }
            # Match upstream Content-Type (text/html, not application/egonet-stream)
            self._send_bytes(
                result,
                content_type="text/html",
                extra_headers=extra_headers,
            )
            self.app.capture_response(
                capture_path,
                {"headers": extra_headers, "body": "(raw binary template)"},
            )
            return

        if result.get("stub"):
            result = {"Accepted": True}
        result = self._sanitize_egonet_value(result)
        status = str(result.get("result_code", "0" if result.get("ok") else "1"))
        if "ok" in result:
            del result["ok"]
        if "result_code" in result:
            del result["result_code"]
        extra_headers: Dict[str, str] = {
            "X-EgoNet-Result": status,
            "X-EgoNet-Catalogue-Version": "1.18.0",
        }

        body = encode_stream(result)
        # Send response FIRST, then capture
        self._send_bytes(
            body,
            content_type="text/html",
            extra_headers=extra_headers,
        )
        self.app.capture_response(
            capture_path,
            {
                "headers": extra_headers,
                "body": result,
            },
        )

    def _handle_egonet_proxy(self, method: str, capture_path: Path) -> None:
        """Forward an EgoNet request to the real upstream server and relay the response."""
        raw_body = getattr(self, "_raw_body", b"")

        # Build upstream headers from the original request
        upstream_headers: Dict[str, str] = {}
        for key, value in self.headers.items():
            key_lower = key.lower()
            # Forward all EgoNet headers and content headers
            if key_lower.startswith("x-egonet-") or key_lower in (
                "content-type", "content-length", "user-agent",
            ):
                upstream_headers[key] = value

        # If we have an upstream session from a proxied Login.Login, use it
        # instead of the local session ID
        if self.app.upstream_session and "X-EgoNet-SessionID" in upstream_headers:
            upstream_headers["X-EgoNet-SessionID"] = self.app.upstream_session

        upstream_headers["Host"] = "prod.egonet.codemasters.com"

        path = self.headers.get("X-Original-Path", "/RP17/1.18.0/STEAM/")
        # Use the path from the actual request
        parsed = urlparse(self.path)
        if parsed.path:
            path = parsed.path

        print(f"[PROXY] {method} -> {self.app.upstream_ip}:443{path}")

        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            conn = http.client.HTTPSConnection(
                self.app.upstream_ip, 443, timeout=15, context=ctx,
            )
            conn.request("POST", path, body=raw_body, headers=upstream_headers)
            resp = conn.getresponse()
            resp_body = resp.read()
            resp_headers = {key: value for key, value in resp.getheaders()}
            conn.close()
        except Exception as exc:
            print(f"[PROXY] ERROR forwarding {method}: {exc}")
            # Fall back to local handler
            result = self.app.dispatcher.dispatch(method, {})
            if result.get("stub"):
                result = {"Accepted": True}
            result = self._sanitize_egonet_value(result)
            if "ok" in result:
                del result["ok"]
            extra_headers = {"X-EgoNet-Result": "0"}
            body = encode_stream(result)
            self._send_bytes(body, content_type="application/egonet-stream", extra_headers=extra_headers)
            return

        upstream_result = resp_headers.get("X-EgoNet-Result", resp_headers.get("x-egonet-result", "?"))
        print(f"[PROXY] {method} upstream returned: status={resp.status}, X-EgoNet-Result={upstream_result}, body_len={len(resp_body)}")

        # If this was Login.Login, capture the upstream session ID
        upstream_session = resp_headers.get("X-EgoNet-SessionID", resp_headers.get("x-egonet-sessionid"))
        if method == "Login.Login" and upstream_session:
            self.app.upstream_session = upstream_session
            print(f"[PROXY] Stored upstream session: {upstream_session[:16]}...")

        # Decode upstream response for capture
        decoded_upstream = {}
        if resp_body:
            try:
                decoded_upstream = decode_stream(resp_body)
            except Exception:
                decoded_upstream = {"raw_base64": base64.b64encode(resp_body).decode("ascii")}

        # Capture the upstream response
        self.app.capture_response(
            capture_path,
            {
                "proxy": True,
                "upstream_status": resp.status,
                "headers": {key: value for key, value in resp_headers.items()},
                "body_raw_base64": base64.b64encode(resp_body).decode("ascii"),
                "body_decoded": decoded_upstream,
            },
        )

        # Relay the upstream response directly to the game
        extra_headers: Dict[str, str] = {}
        for key, value in resp_headers.items():
            key_lower = key.lower()
            if key_lower.startswith("x-egonet-") or key_lower == "content-type":
                extra_headers[key] = value

        self.send_response(HTTPStatus(resp.status) if 100 <= resp.status <= 599 else HTTPStatus.OK)
        self.send_header("Content-Type", resp_headers.get("Content-Type", resp_headers.get("content-type", "application/egonet-stream")))
        self.send_header("Content-Length", str(len(resp_body)))
        for key, value in extra_headers.items():
            if key.lower() not in ("content-type", "content-length"):
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(resp_body)

    def _handle_egonet_login(self, payload: Dict[str, Any], capture_path: Path) -> None:
        # If Login.Login is in proxy methods, it's handled by _handle_egonet_proxy
        # This path is for local-only login
        # Real upstream returns: {"AccountId": <si64>, "Flags": <ui64>}
        session_id = secrets.token_hex(16)
        # Use a large si64 AccountId like the real server
        account_id = 259912747194382660
        result = self._sanitize_egonet_value({
            "AccountId": account_id,
            "Flags": 0,
        })
        extra_headers = {
            "X-EgoNet-Result": "0",
            "X-EgoNet-SessionID": session_id,
            "X-EgoNet-Catalogue-Version": "1.18.0",
        }
        self.app.capture_response(
            capture_path,
            {
                "headers": extra_headers,
                "body": {"AccountId": account_id, "Flags": 0},
            },
        )
        body = encode_stream(result)
        self._send_bytes(
            body,
            content_type="text/html",
            extra_headers=extra_headers,
        )

    def _sanitize_egonet_value(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._sanitize_egonet_value(item) for key, item in value.items() if item is not None}
        if isinstance(value, list):
            return [self._sanitize_egonet_value(item) for item in value if item is not None]
        if isinstance(value, tuple):
            return tuple(self._sanitize_egonet_value(item) for item in value if item is not None)
        return value

    def _decode_body(self, raw_body: bytes) -> Dict[str, Any]:
        if not raw_body:
            return {}

        content_type = self.headers.get("Content-Type", "")
        text = raw_body.decode("utf-8", errors="replace")

        if "application/egonet-stream" in content_type:
            return decode_stream(raw_body)

        if "application/json" in content_type:
            try:
                data = json.loads(text)
                return data if isinstance(data, dict) else {"value": data}
            except json.JSONDecodeError:
                return {"raw": text, "decode_error": "invalid json"}

        if "application/x-www-form-urlencoded" in content_type:
            return {key: values[0] if len(values) == 1 else values for key, values in parse_qs(text).items()}

        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else {"value": data}
        except json.JSONDecodeError:
            return {"raw": text}

    def _send_html(self, html: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_json(self, payload: Dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_bytes(
        self,
        payload: bytes,
        *,
        content_type: str,
        status: HTTPStatus = HTTPStatus.OK,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(payload)
            self.wfile.flush()
        except (ConnectionResetError, BrokenPipeError, OSError) as exc:
            print(f"[SEND] FAILED to deliver {len(payload)} bytes: {exc}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DiRT Rally 2.0 community server bootstrap")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080, help="HTTP port")
    parser.add_argument("--https-port", type=int, default=443, help="HTTPS port")
    parser.add_argument("--ssl-cert")
    parser.add_argument("--ssl-key")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--capture-dir", default="captures")
    parser.add_argument("--upstream-ip", default=None,
                        help="Real upstream server IP (e.g. 159.153.126.42)")
    parser.add_argument("--proxy-method", action="append", default=[],
                        help="EgoNet method to proxy upstream (can be repeated)")
    parser.add_argument("--proxy-all", action="store_true",
                        help="Proxy ALL EgoNet methods upstream (overrides --proxy-method)")
    parser.add_argument("--api-url", default=None,
                        help="Base URL for the dirtforever.net web API "
                             "(e.g. https://dirtforever.net). "
                             "When omitted, the server uses local fallback data.")
    return parser


def create_server(host: str, port: int, app: App, ssl_context: Optional[ssl.SSLContext] = None) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), RequestHandler)
    server.app = app  # type: ignore[attr-defined]
    if ssl_context is not None:
        server.socket = ssl_context.wrap_socket(server.socket, server_side=True)
    return server


def main() -> int:
    args = build_arg_parser().parse_args()
    proxy_methods: Optional[Set[str]] = None
    if args.proxy_all:
        # Special sentinel: _handle_egonet_rpc checks membership, so we use
        # a set subclass that contains everything.
        class _AllSet(set):
            def __contains__(self, item: object) -> bool:
                return True
        proxy_methods = _AllSet()
        print("[PROXY] Proxy-all mode: ALL EgoNet methods will be forwarded upstream")
    elif args.proxy_method:
        proxy_methods = set(args.proxy_method)
        print(f"[PROXY] Proxying methods: {', '.join(sorted(proxy_methods))}")

    if args.upstream_ip and proxy_methods:
        print(f"[PROXY] Upstream: {args.upstream_ip}:443")
    elif proxy_methods and not args.upstream_ip:
        print("[PROXY] WARNING: --proxy-method specified but no --upstream-ip; proxying disabled")
        proxy_methods = None

    app = App(
        data_root=Path(args.data_dir),
        capture_root=Path(args.capture_dir),
        upstream_ip=args.upstream_ip,
        proxy_methods=proxy_methods,
        api_url=args.api_url,
    )
    servers = []

    http_server = create_server(args.host, args.port, app)
    servers.append((f"http://{args.host}:{args.port}", http_server))

    if args.ssl_cert and args.ssl_key:
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(certfile=args.ssl_cert, keyfile=args.ssl_key)
        https_server = create_server(args.host, args.https_port, app, ssl_context=ssl_context)
        servers.append((f"https://{args.host}:{args.https_port}", https_server))

    for label, server in servers:
        print(f"Listening on {label}")
        Thread(target=server.serve_forever, daemon=True).start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for _, server in servers:
            server.shutdown()
            server.server_close()
    return 0
