"""One-shot scrubber for tests/fixtures/captures/.

Replaces sensitive values in every capture JSON:
  - decoded_body.SteamTicket.blob_base64 -> 512 zero bytes (size preserved)
  - X-EgoNet-SessionID request and response headers -> placeholder
The body_base64 / body_text are re-encoded from the modified decoded_body
so the wire bytes stay consistent with the JSON view.

Run from project root:
    uv run python scripts/sanitize_test_captures.py
"""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

# Allow importing the dr2server package from the repo root.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dr2server.egonet import (  # noqa: E402
    Int64,
    Timestamp,
    UInt8,
    UInt16,
    UInt32,
    encode_stream,
)


SESSION_PLACEHOLDER = "00000000000000000000000000000000"
TICKET_PLACEHOLDER_BYTES = b"\x00" * 512

CAPTURES_DIR = ROOT / "tests" / "fixtures" / "captures"


def _rehydrate(value):
    """Convert JSON-serialized egonet values back to the wrapped/binary
    types that encode_stream expects.

    The capture writer in dr2server/httpd.py serializes:
      - bytes blobs as {"blob_base64": "...", "size": N}
      - typed integers (UInt32 etc.) as plain ints (their .value)
      - Timestamps as plain ints
    We can't perfectly recover the original wrapper types from JSON, but
    encode_stream's _encode_value handles plain ints/floats/strings/bools,
    so we only need to special-case the blob shape and leave numbers as-is.
    The resulting bytes won't be byte-identical to the original wire body
    (typed numerics may render differently), but they round-trip through
    decode_stream to the same dict, which is all the replay framework
    needs.
    """
    if isinstance(value, dict):
        if set(value.keys()) <= {"blob_base64", "size"} and "blob_base64" in value:
            return base64.b64decode(value["blob_base64"])
        return {k: _rehydrate(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_rehydrate(item) for item in value]
    return value


def sanitize_capture(path: Path) -> bool:
    """Sanitize one capture file. Returns True if it changed."""
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = False

    # Scrub session ID in request headers
    headers = data.get("headers") or {}
    for key in list(headers.keys()):
        if key.lower() == "x-egonet-sessionid" and headers[key] != SESSION_PLACEHOLDER:
            headers[key] = SESSION_PLACEHOLDER
            changed = True

    # Scrub session ID in response headers
    response = data.get("response")
    if isinstance(response, dict):
        resp_headers = response.get("headers") or {}
        for key in list(resp_headers.keys()):
            if key.lower() == "x-egonet-sessionid" and resp_headers[key] != SESSION_PLACEHOLDER:
                resp_headers[key] = SESSION_PLACEHOLDER
                changed = True

    # Scrub SteamTicket blob in decoded_body and re-encode the wire body.
    decoded_body = data.get("decoded_body") or {}
    has_steam_ticket = (
        isinstance(decoded_body, dict)
        and isinstance(decoded_body.get("SteamTicket"), dict)
        and "blob_base64" in decoded_body["SteamTicket"]
    )
    if has_steam_ticket:
        ticket = decoded_body["SteamTicket"]
        placeholder_b64 = base64.b64encode(TICKET_PLACEHOLDER_BYTES).decode("ascii")
        if ticket.get("blob_base64") != placeholder_b64:
            ticket["blob_base64"] = placeholder_b64
            ticket["size"] = len(TICKET_PLACEHOLDER_BYTES)
            changed = True

        # Re-encode the wire body so body_base64 reflects the scrubbed ticket.
        rehydrated = _rehydrate(decoded_body)
        re_encoded = encode_stream(rehydrated)
        new_b64 = base64.b64encode(re_encoded).decode("ascii")
        if data.get("body_base64") != new_b64:
            data["body_base64"] = new_b64
            data["body_text"] = re_encoded.decode("utf-8", errors="replace")
            # Update Content-Length so downstream replays match.
            for hk in list(headers.keys()):
                if hk.lower() == "content-length":
                    headers[hk] = str(len(re_encoded))
            changed = True

    if changed:
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return changed


def main() -> int:
    captures = sorted(CAPTURES_DIR.rglob("*.json"))
    if not captures:
        print(f"No captures found in {CAPTURES_DIR}", file=sys.stderr)
        return 1
    changed = 0
    for path in captures:
        if sanitize_capture(path):
            changed += 1
            print(f"  scrubbed {path.relative_to(CAPTURES_DIR)}")
    print(f"\nDone. {changed}/{len(captures)} files modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
