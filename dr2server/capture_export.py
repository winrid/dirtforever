"""RaceNet capture sessions: proxy flags, capture folders, sanitized export.

The GUI's Advanced tab can turn one server start into a capture session.
Every EgoNet call is then forwarded to the real Codemasters backend
(``--proxy-all``) and :mod:`dr2server.httpd` records one JSON file per
call with the decoded request and the upstream reply.  That is the only
way left to learn what the real server answers for flows nobody captured
before the emulator was written (the My Team career ladder in issue #68).

:func:`export_capture_zip` packs such a folder for a bug report with the
private parts removed: the Steam auth ticket, every session id, and the
whole body of the login and account calls.  It is the reading-oriented
sibling of ``scripts/sanitize_test_captures.py``, which also re-encodes
the wire bytes so the replay tests stay byte-exact; nothing here needs
that.
"""
from __future__ import annotations

import json
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

# prod.egonet.codemasters.com.  Still answering application calls with
# X-EgoNet-Result 0 on 2026-10-30.
RACENET_UPSTREAM_IP = "159.153.126.42"
CAPTURE_DIR_PREFIX = "racenet-"
SESSION_PLACEHOLDER = "00000000000000000000000000000000"
REMOVED = "<removed: private>"
# Login.Login carries the Steam auth ticket; RaceNet.* carries the account
# sign-in.  Their request and response bodies are dropped entirely.  Note
# the trailing dot: RaceNetCareerLadder.* and RaceNetChallenges.* are the
# game data we want.
_PRIVATE_METHOD_PREFIXES = ("Login.", "RaceNet.")
_SESSION_HEADER = "x-egonet-sessionid"
_FUNCTION_HEADER = "x-egonet-function"


def racenet_server_args() -> List[str]:
    """Extra ``server.py`` arguments that make a server start a capture session."""
    return ["--upstream-ip", RACENET_UPSTREAM_IP, "--proxy-all"]


def new_capture_dir(captures_root: Path, now: Optional[float] = None) -> Path:
    """A fresh, timestamped folder under ``captures_root`` for one session."""
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now))
    return captures_root / f"{CAPTURE_DIR_PREFIX}{stamp}"


def list_capture_dirs(captures_root: Path) -> List[Path]:
    """RaceNet capture folders under ``captures_root``, newest first."""
    if not captures_root.is_dir():
        return []
    dirs = [p for p in captures_root.iterdir()
            if p.is_dir() and p.name.startswith(CAPTURE_DIR_PREFIX)]
    return sorted(dirs, key=lambda p: p.name, reverse=True)


def capture_method(data: Dict[str, Any]) -> str:
    """The EgoNet function name a capture file is for, or ''."""
    headers = data.get("headers")
    if isinstance(headers, dict):
        for key, value in headers.items():
            if str(key).lower() == _FUNCTION_HEADER:
                return str(value)
    return ""


def _scrub_session(headers: Any) -> None:
    if not isinstance(headers, dict):
        return
    for key in list(headers):
        if str(key).lower() == _SESSION_HEADER:
            headers[key] = SESSION_PLACEHOLDER


def sanitize_capture(data: Dict[str, Any]) -> Dict[str, Any]:
    """A deep copy of one capture file's JSON with the private parts removed.

    Session ids are replaced on both sides of every call.  For the login
    and account calls, and for anything carrying a ``SteamTicket``, the
    request body (raw and decoded) and the response body are dropped.
    """
    out = json.loads(json.dumps(data))
    _scrub_session(out.get("headers"))
    response = out.get("response")
    if isinstance(response, dict):
        _scrub_session(response.get("headers"))
    decoded = out.get("decoded_body")
    private = capture_method(out).startswith(_PRIVATE_METHOD_PREFIXES)
    if isinstance(decoded, dict) and "SteamTicket" in decoded:
        private = True
    if private:
        for key in ("body_text", "body_base64", "decoded_body"):
            if key in out:
                out[key] = REMOVED
        if isinstance(response, dict):
            for key in ("body", "body_raw_base64", "body_decoded"):
                if key in response:
                    response[key] = REMOVED
    return out


def export_capture_zip(capture_dir: Path, out_zip: Path) -> int:
    """Pack every capture JSON in ``capture_dir`` into ``out_zip``, sanitized.

    Returns the number of files packed.  Other files are skipped, and a
    capture that cannot be read is packed as a one-line note instead of
    aborting the export.
    """
    files = sorted(p for p in capture_dir.iterdir() if p.is_file() and p.suffix == ".json")
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                text = json.dumps(sanitize_capture(data), indent=2, ensure_ascii=False)
            except (OSError, ValueError) as exc:
                text = json.dumps({"unreadable": path.name, "error": str(exc)})
            zf.writestr(f"{capture_dir.name}/{path.name}", text)
    return len(files)
