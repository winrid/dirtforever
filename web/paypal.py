"""Minimal PayPal REST client — webhook verification for donations.

Mirrors ``dr2server/api_client.py``: stdlib ``urllib.request`` only, no
third-party deps. Its only job is to confirm that an incoming webhook really
came from PayPal (so a forged POST can't inflate the donation total) and to
pull the amount out of a verified event.

Config comes from the environment (loaded from ``.env`` by ``server.py``):
  PAYPAL_API_BASE      - https://api-m.paypal.com (live) or
                         https://api-m.sandbox.paypal.com (sandbox)
  PAYPAL_CLIENT_ID     - REST app client id
  PAYPAL_CLIENT_SECRET - REST app secret
  PAYPAL_WEBHOOK_ID    - id of the webhook subscription to verify against
"""
from __future__ import annotations

import base64
import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any, Optional

log = logging.getLogger('dirtforever.paypal')

# Required transmission headers PayPal signs each delivery with.
_SIG_HEADERS = (
    'paypal-transmission-id',
    'paypal-transmission-time',
    'paypal-cert-url',
    'paypal-auth-algo',
    'paypal-transmission-sig',
)

_DONATION_EVENTS = ('PAYMENT.SALE.COMPLETED', 'PAYMENT.CAPTURE.COMPLETED')

# OAuth token cached for the life of the process (PayPal tokens last ~9h).
_token_cache: dict[str, Any] = {'token': None, 'expires_at': 0.0}


def _config() -> dict[str, str]:
    return {
        'base': os.environ.get('PAYPAL_API_BASE', 'https://api-m.paypal.com').rstrip('/'),
        'client_id': os.environ.get('PAYPAL_CLIENT_ID', ''),
        'client_secret': os.environ.get('PAYPAL_CLIENT_SECRET', ''),
        'webhook_id': os.environ.get('PAYPAL_WEBHOOK_ID', ''),
    }


def is_configured() -> bool:
    c = _config()
    return bool(c['client_id'] and c['client_secret'] and c['webhook_id'])


def _get_access_token() -> Optional[str]:
    c = _config()
    if not (c['client_id'] and c['client_secret']):
        return None
    if _token_cache['token'] and time.time() < _token_cache['expires_at']:
        return _token_cache['token']

    auth = base64.b64encode(f"{c['client_id']}:{c['client_secret']}".encode()).decode()
    req = urllib.request.Request(
        f"{c['base']}/v1/oauth2/token",
        data=b'grant_type=client_credentials',
        method='POST',
        headers={
            'Authorization': f'Basic {auth}',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except urllib.error.URLError as exc:
        log.error('paypal token request failed: %s', getattr(exc, 'reason', exc))
        return None
    except Exception as exc:  # pragma: no cover - defensive
        log.error('paypal token unexpected error: %s', exc)
        return None

    token = data.get('access_token')
    if not token:
        return None
    # Refresh a minute early so a long-running request never uses a dead token.
    _token_cache['token'] = token
    _token_cache['expires_at'] = time.time() + max(0, int(data.get('expires_in', 0)) - 60)
    return token


def verify_webhook_signature(headers: dict, raw_body: bytes) -> bool:
    """Ask PayPal whether a webhook delivery is authentic.

    ``headers`` keys must be lowercase (the route lowercases them). Returns
    True only on ``verification_status == "SUCCESS"``. If PayPal isn't
    configured we reject — we cannot trust an unverifiable event.
    """
    c = _config()
    if not is_configured():
        log.warning('paypal webhook received but PayPal is not configured; rejecting')
        return False
    if not all(headers.get(h) for h in _SIG_HEADERS):
        log.warning('paypal webhook missing transmission headers')
        return False
    token = _get_access_token()
    if not token:
        return False
    try:
        event = json.loads(raw_body.decode('utf-8'))
    except Exception:
        return False

    payload = {
        'transmission_id': headers['paypal-transmission-id'],
        'transmission_time': headers['paypal-transmission-time'],
        'cert_url': headers['paypal-cert-url'],
        'auth_algo': headers['paypal-auth-algo'],
        'transmission_sig': headers['paypal-transmission-sig'],
        'webhook_id': c['webhook_id'],
        'webhook_event': event,
    }
    req = urllib.request.Request(
        f"{c['base']}/v1/notifications/verify-webhook-signature",
        data=json.dumps(payload).encode('utf-8'),
        method='POST',
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
    except urllib.error.URLError as exc:
        log.error('paypal verify request failed: %s', getattr(exc, 'reason', exc))
        return False
    except Exception as exc:  # pragma: no cover - defensive
        log.error('paypal verify unexpected error: %s', exc)
        return False
    return result.get('verification_status') == 'SUCCESS'


def extract_donation(event: dict) -> Optional[tuple[str, int]]:
    """From a verified webhook event, return ``(txn_id, amount_cents)`` or None.

    Handles PAYMENT.SALE.COMPLETED (``resource.amount.total``) and
    PAYMENT.CAPTURE.COMPLETED (``resource.amount.value``).
    """
    if event.get('event_type') not in _DONATION_EVENTS:
        return None
    resource = event.get('resource') or {}
    txn_id = resource.get('id')
    amount = resource.get('amount') or {}
    raw = amount.get('total', amount.get('value'))
    if not txn_id or raw is None:
        return None
    try:
        cents = int(round(float(raw) * 100))
    except (TypeError, ValueError):
        return None
    if cents <= 0:
        return None
    return txn_id, cents
