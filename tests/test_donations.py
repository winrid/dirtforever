"""Donation tracker: status endpoint, donate page, and webhook recording.

Drives the real Flask app (the session-scoped ``web_app`` fixture) over HTTP.
The webhook normally calls PayPal to verify each delivery's signature; we
monkeypatch that verification because the app runs in-process, in the same
interpreter as the test, so patching ``paypal.verify_webhook_signature`` is
visible to the request handler.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from .web_app import WebApp


def _get(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, resp.read().decode()


def _post_json(url: str, payload: dict) -> tuple[int, str]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def _clear_store(web_app: WebApp) -> None:
    """Start each test from an empty donations store (recreated on demand)."""
    path = web_app.data_dir / "donations.json"
    if path.exists():
        path.unlink()


def _sale_event(txn_id: str, dollars: str) -> dict:
    return {
        "event_type": "PAYMENT.SALE.COMPLETED",
        "resource": {"id": txn_id, "amount": {"total": dollars, "currency": "USD"}},
    }


def test_donate_page_renders(web_app: WebApp) -> None:
    _clear_store(web_app)
    status, body = _get(f"{web_app.url}/donate")
    assert status == 200
    assert "FUEL THE" in body
    assert "BUDGET COVERAGE" in body


def test_status_defaults(web_app: WebApp) -> None:
    _clear_store(web_app)
    status, body = _get(f"{web_app.url}/api/donations/status")
    assert status == 200
    data = json.loads(body)
    assert data["goal_cents"] == 10000
    assert data["raised_cents"] == 0
    assert data["percent"] == 0
    assert data["history"] == []


def test_webhook_records_and_dedupes(
    web_app: WebApp, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_store(web_app)
    monkeypatch.setattr("paypal.verify_webhook_signature", lambda headers, raw: True)

    wh = f"{web_app.url}/api/paypal/webhook"
    status_url = f"{web_app.url}/api/donations/status"

    # First donation of $25 → 25% of the $100 goal.
    code, _ = _post_json(wh, _sale_event("TXN1", "25.00"))
    assert code == 200
    data = json.loads(_get(status_url)[1])
    assert data["raised_cents"] == 2500
    assert data["percent"] == 25

    # Same txn id redelivered → not double-counted (webhooks can repeat).
    code, _ = _post_json(wh, _sale_event("TXN1", "25.00"))
    assert code == 200
    assert json.loads(_get(status_url)[1])["raised_cents"] == 2500

    # A second donation pushes coverage past the goal; percent caps at 100.
    code, _ = _post_json(wh, _sale_event("TXN2", "100.00"))
    assert code == 200
    data = json.loads(_get(status_url)[1])
    assert data["raised_cents"] == 12500
    assert data["percent"] == 100


def test_webhook_rejects_unverified(
    web_app: WebApp, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_store(web_app)
    monkeypatch.setattr("paypal.verify_webhook_signature", lambda headers, raw: False)

    code, _ = _post_json(
        f"{web_app.url}/api/paypal/webhook", _sale_event("TXNX", "50.00")
    )
    assert code == 400
    data = json.loads(_get(f"{web_app.url}/api/donations/status")[1])
    assert data["raised_cents"] == 0
