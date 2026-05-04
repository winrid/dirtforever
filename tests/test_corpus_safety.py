"""Guard test: ensures no real Steam tickets or session IDs are committed.

Scans every capture under tests/fixtures/captures/. Fails if it finds any
SteamTicket whose payload isn't all-zero placeholder bytes, or any
X-EgoNet-SessionID whose value isn't the canonical placeholder.

Run scripts/sanitize_test_captures.py to scrub before re-committing.
"""
from __future__ import annotations

import base64
import json
import re

from .conftest import CAPTURES_DIR

SESSION_PLACEHOLDER = "00000000000000000000000000000000"
TICKET_PLACEHOLDER_BYTES = b"\x00" * 512
TICKET_PLACEHOLDER_B64 = base64.b64encode(TICKET_PLACEHOLDER_BYTES).decode("ascii")
SESSION_HEX_PATTERN = re.compile(r"^[0-9a-fA-F]{32}$")


def test_no_real_steam_tickets_in_corpus() -> None:
    bad: list[str] = []
    for path in sorted(CAPTURES_DIR.rglob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        decoded = data.get("decoded_body") or {}
        ticket = decoded.get("SteamTicket") if isinstance(decoded, dict) else None
        if not (isinstance(ticket, dict) and "blob_base64" in ticket):
            continue
        b64 = ticket["blob_base64"]
        if b64 == TICKET_PLACEHOLDER_B64:
            continue
        try:
            raw = base64.b64decode(b64)
        except Exception:
            bad.append(f"{path.relative_to(CAPTURES_DIR)}: SteamTicket.blob_base64 is not valid base64")
            continue
        if raw != TICKET_PLACEHOLDER_BYTES:
            bad.append(
                f"{path.relative_to(CAPTURES_DIR)}: SteamTicket has {len(raw)} non-placeholder bytes "
                f"(first 8: {raw[:8].hex()}); run scripts/sanitize_test_captures.py"
            )
    assert not bad, "Real Steam tickets found in committed captures:\n  " + "\n  ".join(bad)


def test_no_real_session_ids_in_corpus() -> None:
    bad: list[str] = []
    for path in sorted(CAPTURES_DIR.rglob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))

        for source_label, headers in (
            ("request", data.get("headers") or {}),
            ("response", (data.get("response") or {}).get("headers") or {} if isinstance(data.get("response"), dict) else {}),
        ):
            if not isinstance(headers, dict):
                continue
            for key, value in headers.items():
                if key.lower() != "x-egonet-sessionid":
                    continue
                if value == SESSION_PLACEHOLDER:
                    continue
                # Anything that looks like a 32-hex token is a real session id.
                if isinstance(value, str) and SESSION_HEX_PATTERN.match(value):
                    bad.append(
                        f"{path.relative_to(CAPTURES_DIR)}: {source_label} X-EgoNet-SessionID="
                        f"{value!r} is not the placeholder; run "
                        f"scripts/sanitize_test_captures.py"
                    )
    assert not bad, "Real session IDs found in committed captures:\n  " + "\n  ".join(bad)
