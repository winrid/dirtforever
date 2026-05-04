"""Replace volatile values in a snapshot payload with stable sentinels.

The DR2 server stamps fresh values on each run (session IDs, account IDs
derived from a token-resolved username, the local capture-file path it
returns). We swap those out with placeholders before snapshot comparison
so equality is deterministic.
"""
from __future__ import annotations

from typing import Any, Dict


SESSION_ID_PLACEHOLDER = "<SESSION_ID>"
ACCOUNT_ID_PLACEHOLDER = "<ACCOUNT_ID>"
ENTRY_ID_PLACEHOLDER = "<ENTRY_ID>"
EPOCH_PLACEHOLDER = "<EPOCH>"
CAPTURE_PATH_PLACEHOLDER = "<CAPTURE_PATH>"

_VOLATILE_HEADER_KEYS = {"x-egonet-sessionid"}
_VOLATILE_DECODED_BODY_KEYS = {
    "AccountId": ACCOUNT_ID_PLACEHOLDER,
    "EntryId": ENTRY_ID_PLACEHOLDER,
}
# Nested keys whose entire value is volatile (clock-derived). These appear
# under e.g. EntryWindow inside Challenges responses; the dispatcher builds
# them from int(time.time()) so they drift per run.
_VOLATILE_NESTED_KEYS = {"Start", "End", "Visible", "LastEntry"}
_VOLATILE_RESPONSE_HEADER_KEYS_LOWER = {"date", "server"}


def normalize_response_headers(headers: Dict[str, str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for key, value in headers.items():
        key_lower = key.lower()
        if key_lower in _VOLATILE_RESPONSE_HEADER_KEYS_LOWER:
            continue
        if key_lower in _VOLATILE_HEADER_KEYS:
            out[key] = SESSION_ID_PLACEHOLDER
            continue
        out[key] = value
    return out


def normalize_decoded_body(body: Any) -> Any:
    if isinstance(body, dict):
        out: Dict[str, Any] = {}
        for key, value in body.items():
            if key in _VOLATILE_DECODED_BODY_KEYS:
                out[key] = _VOLATILE_DECODED_BODY_KEYS[key]
            elif key in _VOLATILE_NESTED_KEYS:
                out[key] = EPOCH_PLACEHOLDER
            else:
                out[key] = normalize_decoded_body(value)
        return out
    if isinstance(body, list):
        return [normalize_decoded_body(item) for item in body]
    return body
