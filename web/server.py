from __future__ import annotations

import os
import re
import sys
import json
import fcntl
import hashlib
import hmac
import logging
import secrets
import smtplib
import uuid
import random
from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime, timedelta
from email.message import EmailMessage
from functools import wraps
from typing import Any

logging.basicConfig(
    stream=sys.stderr,
    level=getattr(logging, os.environ.get('LOG_LEVEL', 'INFO').upper(), logging.INFO),
    format='[%(asctime)s] %(levelname)s: %(message)s',
    force=True,
)
log = logging.getLogger('dirtforever')
log.info('dirtforever server module loading')

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, abort, jsonify,
)
from werkzeug.wrappers import Response
from flask_wtf.csrf import CSRFProtect

# Make the sibling dr2server package importable so we can reuse its
# LocationId / TrackModelId / VehicleClassId tables instead of duplicating
# them here. The package is stdlib-only, so this adds no runtime deps.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dr2server.game_data import (  # noqa: E402
    Location,
    Track,
    LOCATIONS as GAME_LOCATIONS,
    TRACKS as GAME_TRACKS,
    VEHICLE_CLASSES as GAME_VEHICLE_CLASSES,
    VEHICLES as GAME_VEHICLES,
    stage_conditions_label,
    stage_conditions_for_location,
    stage_conditions_options_for_location,
    stage_conditions_sibling_for_location,
    get_tracks_for_location,
    get_verified_routes_for_location,
    vehicle_class_id_for_label,
    CONFIRMED_VEHICLE_CLASS_IDS,
    STAGE_CONDITIONS_LABELS,
    SURFACE_DEGRAD_LEVELS,
    SERVICE_AREA_LEVELS,
)


def _load_dotenv(path: str) -> None:
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, val = line.split('=', 1)
            os.environ.setdefault(key.strip(), val.strip())


_load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'))

app = Flask(__name__)
app.secret_key = os.environ['SECRET_KEY']
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'

csrf = CSRFProtect(app)

SMTP_HOST = os.environ.get('EMAIL_HOST', '')
SMTP_PORT = int(os.environ.get('EMAIL_PORT', '587'))
SMTP_USER = os.environ.get('EMAIL_HOST_USER', '')
SMTP_PASS = os.environ.get('EMAIL_HOST_PASSWORD', '')
SMTP_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'true').lower() == 'true'
MAIL_FROM = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@dirtforever.com')
SITE_URL = os.environ.get('SITE_URL', 'http://localhost:5001')
CRON_API_KEY = os.environ.get('CRON_API_KEY', '')

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.environ.get('DATA_DIR', os.path.join(BASE, 'data'))
USERS_DIR  = os.path.join(DATA_DIR, 'users')
CLUBS_DIR  = os.path.join(DATA_DIR, 'clubs')
EVENTS_DIR = os.path.join(DATA_DIR, 'events')
RESULTS_DIR = os.path.join(DATA_DIR, 'results')
TIME_TRIALS_DIR = os.path.join(DATA_DIR, 'time_trials')
# Championship builder drafts live in their OWN directory so they never leak
# into get_all_events() (which would serve them to the game and the /events
# list before the user has submitted).
CHAMP_DRAFTS_DIR = os.path.join(DATA_DIR, 'championship_drafts')

for d in (USERS_DIR, CLUBS_DIR, EVENTS_DIR, RESULTS_DIR, TIME_TRIALS_DIR, CHAMP_DRAFTS_DIR):
    os.makedirs(d, exist_ok=True)


# ── ID validation ───────────────────────────────────────

_SAFE_ID_RE = re.compile(r'^[a-zA-Z0-9_-]+$')


def _validate_id(value: str) -> str:
    if not value or not _SAFE_ID_RE.match(value):
        abort(400)
    return value


# ── File helpers ─────────────────────────────────────────

def _load(path: str) -> Any:
    with open(path) as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        try:
            return json.load(f)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _save(path: str, data: Any) -> None:
    with open(path, 'w') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            json.dump(data, f, indent=2)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


@contextmanager
def _atomic_update(path: str) -> Any:
    """Hold LOCK_EX across read+mutate+write to close the load-modify-save race.

    Yields the parsed JSON. On context exit, whatever the caller mutated is
    written back under the same lock. Two concurrent callers on the same path
    serialize: the second one sees the first's writes before reading.

    Critically we flush+fsync BEFORE releasing the lock — otherwise another
    waiter can acquire the lock and read a half-written file because Python's
    buffered write hasn't reached the kernel yet.
    """
    with open(path, 'r+') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            data = json.load(f)
            yield data
            f.seek(0)
            f.truncate()
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _user_path(username: str) -> str:
    _validate_id(username)
    return os.path.join(USERS_DIR, f'{username}.json')


def _club_path(cid: str) -> str:
    _validate_id(cid)
    return os.path.join(CLUBS_DIR, f'{cid}.json')


def _list_json(directory: str) -> list[Any]:
    out: list[Any] = []
    if os.path.isdir(directory):
        for fn in sorted(os.listdir(directory)):
            if fn.endswith('.json'):
                out.append(_load(os.path.join(directory, fn)))
    return out


# ── User ops ─────────────────────────────────────────────

def get_user(username: str) -> dict[str, Any] | None:
    _validate_id(username)
    p = os.path.join(USERS_DIR, f'{username}.json')
    return _load(p) if os.path.exists(p) else None


def save_user(u: dict[str, Any]) -> None:
    _validate_id(u['username'])
    _save(os.path.join(USERS_DIR, f"{u['username']}.json"), u)


def get_all_users() -> list[Any]:
    # Yes I know this is bad, we'll switch to a real database with indexes if anyone ends up using this
    return _list_json(USERS_DIR)


def create_user(username: str, email: str, password: str, display_name: str | None = None,
                country: str = '', bio: str = '',
                email_verified: bool = False) -> dict[str, Any]:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 120_000)
    verify_token = secrets.token_urlsafe(32) if not email_verified else None
    u = {
        'username': username,
        'email': email,
        'password_hash': dk.hex(),
        'salt': salt.hex(),
        'display_name': display_name or username,
        'country': country,
        'bio': bio,
        'created_at': datetime.now().isoformat(),
        'clubs': [],
        'email_verified': email_verified,
        'verify_token': verify_token,
    }
    save_user(u)
    return u


def check_password(password: str, user: dict[str, Any]) -> bool:
    salt = bytes.fromhex(user['salt'])
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 120_000)
    return hmac.compare_digest(dk.hex(), user['password_hash'])


# ── Email ───────────────────────────────────────────────

def _send_email(to: str, subject: str, body: str) -> bool:
    log.info('Sending email to=%s subject=%r host=%s port=%s',
                    to, subject, SMTP_HOST or '(not set)', SMTP_PORT)
    if not SMTP_HOST:
        log.warning('EMAIL_HOST not configured — email not sent')
        return False
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = MAIL_FROM
    msg['To'] = to
    msg.set_content(body)
    try:
        log.debug('Connecting to %s:%s (TLS=%s)', SMTP_HOST, SMTP_PORT, SMTP_USE_TLS)
        if SMTP_USE_TLS:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
            server.starttls()
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
        if SMTP_USER:
            log.debug('Authenticating as %s', SMTP_USER)
            server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        log.info('Email sent to %s', to)
        return True
    except Exception:
        log.exception('Failed to send email to %s', to)
        return False


def send_verification_email(user: dict[str, Any]) -> bool:
    log.info('Sending verification email to user=%s email=%s',
                    user['username'], user['email'])
    link = f'{SITE_URL}/verify/{user["verify_token"]}'
    body = (
        f'Hi {user["display_name"]},\n\n'
        f'Welcome to DirtForever! Please verify your email address by visiting:\n\n'
        f'{link}\n\n'
        f'If you did not create this account, ignore this email.\n\n'
        f'- DirtForever'
    )
    return _send_email(user['email'], 'Verify your DirtForever account', body)


def send_reset_email(user: dict[str, Any]) -> bool:
    log.info('Sending password reset email to user=%s email=%s',
                    user['username'], user['email'])
    link = f'{SITE_URL}/reset/{user["reset_token"]}'
    body = (
        f'Hi {user["display_name"]},\n\n'
        f'We received a request to reset your DirtForever password. '
        f'Visit the link below to choose a new password:\n\n'
        f'{link}\n\n'
        f'This link expires in 1 hour. If you did not request this, ignore this email.\n\n'
        f'- DirtForever'
    )
    return _send_email(user['email'], 'Reset your DirtForever password', body)


def _send_join_request_email(owner: dict[str, Any], requester: dict[str, Any],
                             club: dict[str, Any]) -> bool:
    if not owner.get('email'):
        return False
    link = f'{SITE_URL}/clubs/{club["id"]}'
    body = (
        f'Hi {owner.get("display_name") or owner["username"]},\n\n'
        f'{requester.get("display_name") or requester["username"]} has requested '
        f'to join your club "{club["name"]}".\n\n'
        f'Review and approve or deny the request here:\n{link}\n\n'
        f'- DirtForever'
    )
    return _send_email(owner['email'], f'Join request for {club["name"]}', body)


def _send_join_approved_email(user: dict[str, Any], club: dict[str, Any]) -> bool:
    if not user.get('email'):
        return False
    link = f'{SITE_URL}/clubs/{club["id"]}'
    body = (
        f'Hi {user.get("display_name") or user["username"]},\n\n'
        f'Your request to join "{club["name"]}" was approved. You can now '
        f'submit times to its events.\n\n{link}\n\n- DirtForever'
    )
    return _send_email(user['email'], f'You joined {club["name"]}', body)


def _send_join_denied_email(user: dict[str, Any], club: dict[str, Any]) -> bool:
    if not user.get('email'):
        return False
    body = (
        f'Hi {user.get("display_name") or user["username"]},\n\n'
        f'Your request to join "{club["name"]}" was declined.\n\n'
        f'- DirtForever'
    )
    return _send_email(user['email'], f'Join request for {club["name"]} declined', body)


def _send_invite_email(invitee: dict[str, Any], inviter: dict[str, Any],
                       club: dict[str, Any]) -> bool:
    if not invitee.get('email'):
        return False
    link = f'{SITE_URL}/clubs/{club["id"]}'
    body = (
        f'Hi {invitee.get("display_name") or invitee["username"]},\n\n'
        f'{inviter.get("display_name") or inviter["username"]} invited you to '
        f'join their club "{club["name"]}" on DirtForever.\n\n'
        f'View the club and accept here:\n{link}\n\n'
        f'- DirtForever'
    )
    return _send_email(invitee['email'], f'Invitation to join {club["name"]}', body)


# ── Notifications ────────────────────────────────────────

# Per-user notification cap. Once exceeded, oldest read entries are dropped
# first; if all are unread we drop oldest unread to keep the list bounded.
MAX_NOTIFICATIONS = 200

# Cooldown windows for re-requesting club membership after a self-cancel or
# owner-deny. Keeps the request/cancel/request loop from spamming the owner.
COOLDOWN_AFTER_CANCEL = timedelta(minutes=10)
COOLDOWN_AFTER_DENY = timedelta(hours=1)


def _trim_notifications(notifs: list[dict[str, Any]]) -> None:
    """In-place trim of notifs to MAX_NOTIFICATIONS, dropping read entries
    first (oldest first), then oldest unread if still over."""
    while len(notifs) > MAX_NOTIFICATIONS:
        idx = next((i for i, n in enumerate(notifs) if n.get('read')), 0)
        del notifs[idx]


def add_notification(username: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Append a notification to the user under an exclusive lock.

    Returns the new notification, or None if it was suppressed (de-duped).
    For ``club_join_request``, an existing unread notification from the same
    requester for the same club suppresses re-add — this stops the request /
    cancel / request loop from spamming the owner inbox.
    """
    path = _user_path(username)
    if not os.path.exists(path):
        return None
    with _atomic_update(path) as user:
        notifs = user.setdefault('notifications', [])
        if payload.get('type') == 'club_join_request':
            for n in notifs:
                if (n.get('type') == 'club_join_request'
                        and n.get('club_id') == payload.get('club_id')
                        and n.get('from_username') == payload.get('from_username')
                        and not n.get('read')):
                    return None
        notif = {
            'id': f'ntf-{secrets.token_hex(8)}',
            'created_at': datetime.now().isoformat(),
            'read': False,
            **payload,
        }
        notifs.append(notif)
        _trim_notifications(notifs)
        return notif


def mark_notification_read(username: str, ntf_id: str) -> bool:
    path = _user_path(username)
    if not os.path.exists(path):
        return False
    with _atomic_update(path) as user:
        for n in user.get('notifications', []) or []:
            if n.get('id') == ntf_id and not n.get('read'):
                n['read'] = True
                return True
    return False


def mark_all_notifications_read(username: str) -> int:
    path = _user_path(username)
    if not os.path.exists(path):
        return 0
    count = 0
    with _atomic_update(path) as user:
        for n in user.get('notifications', []) or []:
            if not n.get('read'):
                n['read'] = True
                count += 1
    return count


def unread_notification_count(user: dict[str, Any] | None) -> int:
    if not user:
        return 0
    return sum(1 for n in (user.get('notifications') or []) if not n.get('read'))


def clear_join_request_notification(owner_username: str, club_id: str,
                                    requester_username: str) -> None:
    """Remove an owner's pending join_request notification when the underlying
    request is resolved (canceled / approved / denied). We drop it entirely
    rather than mark-read so the inbox doesn't carry a stale row that points at
    a request that no longer exists."""
    path = _user_path(owner_username)
    if not os.path.exists(path):
        return
    with _atomic_update(path) as owner:
        notifs = owner.get('notifications') or []
        kept = [
            n for n in notifs
            if not (
                n.get('type') == 'club_join_request'
                and n.get('club_id') == club_id
                and n.get('from_username') == requester_username
            )
        ]
        if len(kept) != len(notifs):
            owner['notifications'] = kept


# ── Club ops ─────────────────────────────────────────────

def get_club(cid: str) -> dict[str, Any] | None:
    _validate_id(cid)
    p = os.path.join(CLUBS_DIR, f'{cid}.json')
    return _load(p) if os.path.exists(p) else None


def save_club(c: dict[str, Any]) -> None:
    _validate_id(c['id'])
    _save(os.path.join(CLUBS_DIR, f"{c['id']}.json"), c)


def get_all_clubs() -> list[Any]:
    # Yes I know this is bad, we'll switch to a real database with indexes if anyone ends up using this
    return _list_json(CLUBS_DIR)


def club_visibility(club: dict[str, Any]) -> str:
    return club.get('visibility') or 'public'


def club_join_policy(club: dict[str, Any]) -> str:
    return club.get('join_policy') or 'open'


def user_is_member(club: dict[str, Any], username: str | None) -> bool:
    if not username:
        return False
    return username in (club.get('members') or [])


def user_is_owner(club: dict[str, Any], username: str | None) -> bool:
    return bool(username) and club.get('created_by') == username


def club_is_visible_to(club: dict[str, Any], user: dict[str, Any] | None) -> bool:
    if club_visibility(club) == 'public':
        return True
    uname = user.get('username') if user else None
    return (
        user_is_owner(club, uname)
        or user_is_member(club, uname)
        or user_has_invite(club, uname)
    )


def user_has_pending_request(club: dict[str, Any], username: str | None) -> bool:
    if not username:
        return False
    return any(r.get('username') == username for r in (club.get('pending_requests') or []))


def user_has_invite(club: dict[str, Any], username: str | None) -> bool:
    if not username:
        return False
    return any(i.get('username') == username for i in (club.get('invites') or []))


def find_invite_link(club: dict[str, Any], token: str) -> dict[str, Any] | None:
    if not token:
        return None
    links: list[dict[str, Any]] = club.get('invite_links') or []
    for link in links:
        if link.get('token') == token and not link.get('revoked'):
            return link
    return None


# ── Event ops ────────────────────────────────────────────

def get_event(eid: str) -> dict[str, Any] | None:
    _validate_id(eid)
    p = os.path.join(EVENTS_DIR, f'{eid}.json')
    return _load(p) if os.path.exists(p) else None


def save_event(e: dict[str, Any]) -> None:
    _validate_id(e['id'])
    _save(os.path.join(EVENTS_DIR, f"{e['id']}.json"), e)


def get_all_events() -> list[Any]:
    # Yes I know this is bad, we'll switch to a real database with indexes if anyone ends up using this
    return _list_json(EVENTS_DIR)


def get_events_by_type(t: str) -> list[Any]:
    return [e for e in get_all_events() if e.get('type') == t]


def event_is_active(e: dict[str, Any], now: datetime | None = None) -> bool:
    if not e.get('active'):
        return False
    now = now or datetime.now()
    # Start gate: a scheduled/future championship isn't live until its start
    # time passes, so it isn't served to the game (or shown as active) early.
    raw_start = e.get('start_time')
    if raw_start:
        try:
            if datetime.fromisoformat(raw_start) > now:
                return False
        except ValueError:
            pass
    raw = e.get('end_time')
    if not raw:
        return True
    try:
        end = datetime.fromisoformat(raw)
    except ValueError:
        return True
    return end > now


def event_is_upcoming(e: dict[str, Any], now: datetime | None = None) -> bool:
    """True when the event is scheduled but hasn't started yet.

    An upcoming event is deliberately not served to the game (see
    ``event_is_active``), so every listing has to label it, otherwise it looks
    identical to a live one on the site and reads as "the game lost my event".
    """
    if not e.get('active'):
        return False
    raw = e.get('start_time')
    if not raw:
        return False
    try:
        return datetime.fromisoformat(raw) > (now or datetime.now())
    except ValueError:
        return False


def event_sort_key(e: dict[str, Any],
                   now: datetime | None = None) -> tuple[int, float, str]:
    """Listing order for one event: live first, then upcoming, then ended.

    Within a bucket, live events run soonest-ending first, upcoming ones
    soonest-starting first, and ended ones most-recently-finished first, so
    what a driver can still enter is always at the top. The event id is the
    last tiebreak, which keeps the order from wobbling between requests when
    two events share a timestamp or carry none at all.
    """
    now = now or datetime.now()

    def _ts(raw: Any) -> float | None:
        try:
            return datetime.fromisoformat(raw).timestamp()
        except (TypeError, ValueError):
            return None

    eid = str(e.get('id', ''))
    # A missing/unparseable timestamp sorts last inside its bucket rather than
    # first, so a malformed event can never head a listing.
    if event_is_upcoming(e, now):
        start = _ts(e.get('start_time'))
        return (1, start if start is not None else float('inf'), eid)
    if event_is_active(e, now):
        end = _ts(e.get('end_time'))
        return (0, end if end is not None else float('inf'), eid)
    end = _ts(e.get('end_time'))
    return (2, -end if end is not None else float('inf'), eid)


def sort_events(events: list[Any], now: datetime | None = None) -> list[Any]:
    """Order any event listing by ``event_sort_key``."""
    now = now or datetime.now()
    return sorted(events, key=lambda e: event_sort_key(e, now))


def event_window(e: dict[str, Any]) -> tuple[datetime, datetime] | None:
    """Parse an event's ``[start, end)`` window; None when unusable."""
    try:
        start = datetime.fromisoformat(e['start_time'])
        end = datetime.fromisoformat(e['end_time'])
    except (KeyError, TypeError, ValueError):
        return None
    return (start, end) if end > start else None


def club_event_conflict(club_id: str, start: datetime,
                        end: datetime) -> dict[str, Any] | None:
    """Return a club event whose window overlaps ``[start, end)``, if any.

    A club carries a single ``AmountOfEvents``/``EventIndex`` cursor in the game
    and RaceNet only ever serves the current event's Challenge
    (notes/protocol_notes.md), so two championships live at once leaves one of
    them unreachable in game.  Back-to-back windows are fine (that's the model
    the game expects), so only real overlaps are rejected.
    """
    for raw in get_all_events():
        e: dict[str, Any] = raw
        if e.get('club_id') != club_id or not e.get('active'):
            continue
        w = event_window(e)
        if w and w[0] < end and start < w[1]:
            return e
    return None


def club_busy_until(club_id: str, now: datetime | None = None) -> datetime | None:
    """When the club's schedule frees up, or None if nothing is running.

    The latest end time across the club's events that haven't finished yet, so
    the next championship can be scheduled to pick up where they leave off.
    """
    now = now or datetime.now()
    ends: list[datetime] = []
    for e in get_all_events():
        if e.get('club_id') != club_id or not e.get('active'):
            continue
        w = event_window(e)
        if w and w[1] > now:
            ends.append(w[1])
    return max(ends) if ends else None


# ── Result ops ───────────────────────────────────────────

def get_results(eid: str) -> dict[str, Any]:
    _validate_id(eid)
    p = os.path.join(RESULTS_DIR, f'{eid}.json')
    if os.path.exists(p):
        return _load(p)  # type: ignore[no-any-return]
    return {'event_id': eid, 'entries': []}


def save_results(eid: str, data: dict[str, Any]) -> None:
    _validate_id(eid)
    _save(os.path.join(RESULTS_DIR, f'{eid}.json'), data)


# ── Auth decorator ───────────────────────────────────────

def login_required(f: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if 'username' not in session or not current_user():
            flash('Please sign in to continue.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper


def verified_required(f: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(f)
    @login_required
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        user = current_user()
        if not user or not user.get('email_verified'):
            flash('Please verify your email address first.', 'warning')
            return redirect(url_for('verify_prompt'))
        return f(*args, **kwargs)
    return wrapper


def current_user() -> dict[str, Any] | None:
    if 'username' in session:
        user = get_user(session['username'])
        if not user:
            session.pop('username', None)
        return user
    return None


# ── Context & filters ────────────────────────────────────

@app.context_processor
def inject_globals() -> dict[str, Any]:
    user = current_user()
    return dict(
        current_user=user,
        unread_notifications=unread_notification_count(user),
    )


@app.template_filter('rally_time')
def rally_time_filter(ms: int | None) -> str:
    if ms is None:
        return '--:--.---'
    ms = int(ms)
    minutes = ms // 60000
    seconds = (ms % 60000) // 1000
    millis = ms % 1000
    return f'{minutes:02d}:{seconds:02d}.{millis:03d}'


@app.template_filter('time_diff')
def time_diff_filter(ms: int | None) -> str:
    if ms is None or ms == 0:
        return ''
    sign = '+' if ms > 0 else '-'
    a = abs(int(ms))
    s = a // 1000
    m = a % 1000
    if s >= 60:
        return f'{sign}{s // 60}:{s % 60:02d}.{m:03d}'
    return f'{sign}{s}.{m:03d}'


@app.template_filter('timeago')
def timeago_filter(dt_str: str) -> str:
    try:
        dt = datetime.fromisoformat(dt_str)
        diff = datetime.now() - dt
        if diff.days > 30:
            return f'{diff.days // 30}mo ago'
        if diff.days > 0:
            return f'{diff.days}d ago'
        h = diff.seconds // 3600
        if h > 0:
            return f'{h}h ago'
        m = diff.seconds // 60
        return f'{m}m ago' if m > 0 else 'just now'
    except Exception:
        return dt_str


@app.template_filter('countdown')
def countdown_filter(dt_str: str) -> str:
    try:
        dt = datetime.fromisoformat(dt_str)
        diff = dt - datetime.now()
        if diff.total_seconds() <= 0:
            return 'Ended'
        d = diff.days
        h = diff.seconds // 3600
        m = (diff.seconds % 3600) // 60
        if d > 0:
            return f'{d}d {h}h'
        if h > 0:
            return f'{h}h {m}m'
        return f'{m}m'
    except Exception:
        return dt_str


@app.template_filter('is_upcoming')
def is_upcoming_filter(e: dict[str, Any]) -> bool:
    """Template-side ``event_is_upcoming`` so listings can label scheduled events."""
    return event_is_upcoming(e)


@app.template_filter('country_flag')
def country_flag_filter(country: str) -> str:
    if not country:
        return ''
    return COUNTRIES.get(country, '')


@app.template_filter('user_flag')
def user_flag_filter(username: str) -> str:
    if not username:
        return ''
    user = get_user(username)
    if not user:
        return ''
    return COUNTRIES.get(user.get('country', ''), '')


# ── Seed data ────────────────────────────────────────────

STAGES: dict[str, list[tuple[str, float]]] = {
    loc.display_name: [
        (t.display_name, t.length_km)
        for t in Track
        if t.location is loc
    ]
    for loc in Location
    if any(t.location is loc for t in Track)
}

RX_LOCATIONS: frozenset[str] = frozenset(
    loc.display_name for loc in Location if loc.discipline == 'rallycross'
)

# Number of *verified* track routes the game can actually deliver per location.
# 0 means no in-game routes are confirmed yet; such events won't appear in-game
# until their routes are verified, so the auto-generator skips those locations.
# Every location currently has at least one route (the rallycross circuits were
# added in the "rallycross clubs" change), but keep the 0 handling: it's what
# stops a future unmapped location from silently producing dead events.
VERIFIED_STAGE_COUNTS: dict[str, int] = {
    loc.display_name: len(get_tracks_for_location(int(loc)))
    for loc in Location
    if loc.display_name in STAGES
}

# Max distinct stages the create-event form allows.  The game assigns one
# verified route per stage; asking for more just repeats routes, so cap at the
# verified count.  Locations with no verified tracks are NOT blocked from the
# form — they fall back to their full enum count (the event simply won't appear
# in-game until routes are verified).
STAGE_CAPS: dict[str, int] = {
    name: (count or len(STAGES[name]))
    for name, count in VERIFIED_STAGE_COUNTS.items()
}

# Per-location VERIFIED routes for the championship-builder ROUTE dropdown:
# {location_display_name: [(track_id, route_name, length_km), ...]}.  Unlike
# STAGES (which lists every route), this is filtered to routes the game can
# actually deliver, because an unverified track_id loads the wrong stage.
# Locations with no verified routes map to an empty list (the editor shows a
# hint and such a championship won't appear in-game until routes are verified).
STAGE_ROUTES: dict[str, list[tuple[int, str, float]]] = {
    loc.display_name: get_verified_routes_for_location(int(loc))
    for loc in Location
    if loc.display_name in STAGES
}

# Ordered label lists for the per-stage Surface Deg / Service Area dropdowns.
SURFACE_DEG_OPTIONS: list[str] = [label for label, _ in SURFACE_DEGRAD_LEVELS]
SERVICE_AREA_OPTIONS: list[str] = [label for label, _has, _sid in SERVICE_AREA_LEVELS]

CAR_CLASSES = {
    'H1 (FWD)': [
        'Mini Cooper S', 'DS Automobiles DS 21', 'Lancia Fulvia HF',
    ],
    'H2 (FWD)': [
        'Volkswagen Golf GTI 16V', 'Peugeot 205 GTI',
    ],
    'H3 (RWD)': [
        'BMW E30 M3 Evo Rally', 'Opel Ascona 400', 'Lancia Stratos',
        'Datsun 240Z', 'Renault 5 Turbo', 'Ford Sierra Cosworth RS500',
    ],
    'R2': [
        'Ford Fiesta R2', 'Opel Adam R2', 'Peugeot 208 R2',
    ],
    'Group A': [
        'Subaru Impreza 1995', 'Mitsubishi Lancer Evo VI',
        'Ford Escort RS Cosworth', 'Subaru Legacy RS',
    ],
    'Group B (4WD)': [
        'Audi Sport quattro S1 E2', 'Peugeot 205 T16 Evo 2',
        'Lancia Delta S4', 'Ford RS200', 'MG Metro 6R4',
    ],
    'Group B (RWD)': [
        'Lancia 037 Evo 2', 'Opel Manta 400', 'BMW M1 Procar Rally',
    ],
    'R5': [
        'Ford Fiesta R5', 'Volkswagen Polo GTI R5',
        'Citroen C3 R5', 'Skoda Fabia R5',
        'Peugeot 208 T16 R5',
    ],
    'NR4/R4': [
        'Subaru WRX STI NR4', 'Mitsubishi Lancer Evo X',
    ],
    'H2 (RWD)': [
        'Porsche 911 SC RS', 'Fiat 131 Abarth Rally',
        'Opel Kadett C GT/E',
    ],
    'Rally GT': [
        'Porsche 911 RGT Rally Spec', 'BMW M2 Competition',
        'Chevrolet Camaro GT4.R', 'Aston Martin V8 Vantage GT4',
    ],
    'F2 Kit Car': [
        'Peugeot 306 Maxi', 'Seat Ibiza Kit Car',
        'Volkswagen Golf Kitcar',
    ],
    '2000cc': [
        'Citroen C4 Rally', 'Skoda Fabia Rally',
        'Ford Focus RS Rally 2007', 'Subaru Impreza 2008',
    ],
}

# Conditions offered per location, as (StageConditions id, label).  There is no
# global list: each location only ships lighting assets for a subset of the
# enum, and offering an id outside its set loads the stage with a broken sky.
# Ordered as the game orders them, so entry 0 is the location's own default.
CONDITIONS_BY_LOCATION: dict[str, list[tuple[int, str]]] = {
    loc: stage_conditions_options_for_location(loc) for loc in STAGES
}

COUNTRIES: dict[str, str] = {
    'Argentina':      '\U0001F1E6\U0001F1F7',
    'Australia':      '\U0001F1E6\U0001F1FA',
    'Austria':        '\U0001F1E6\U0001F1F9',
    'Belgium':        '\U0001F1E7\U0001F1EA',
    'Brazil':         '\U0001F1E7\U0001F1F7',
    'Bulgaria':       '\U0001F1E7\U0001F1EC',
    'Canada':         '\U0001F1E8\U0001F1E6',
    'Chile':          '\U0001F1E8\U0001F1F1',
    'China':          '\U0001F1E8\U0001F1F3',
    'Colombia':       '\U0001F1E8\U0001F1F4',
    'Croatia':        '\U0001F1ED\U0001F1F7',
    'Czech Republic': '\U0001F1E8\U0001F1FF',
    'Denmark':        '\U0001F1E9\U0001F1F0',
    'England':        '\U0001F3F4\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067\U000E007F',
    'Estonia':        '\U0001F1EA\U0001F1EA',
    'Finland':        '\U0001F1EB\U0001F1EE',
    'France':         '\U0001F1EB\U0001F1F7',
    'Germany':        '\U0001F1E9\U0001F1EA',
    'Greece':         '\U0001F1EC\U0001F1F7',
    'Hungary':        '\U0001F1ED\U0001F1FA',
    'Iceland':        '\U0001F1EE\U0001F1F8',
    'India':          '\U0001F1EE\U0001F1F3',
    'Indonesia':      '\U0001F1EE\U0001F1E9',
    'Ireland':        '\U0001F1EE\U0001F1EA',
    'Israel':         '\U0001F1EE\U0001F1F1',
    'Italy':          '\U0001F1EE\U0001F1F9',
    'Japan':          '\U0001F1EF\U0001F1F5',
    'Kenya':          '\U0001F1F0\U0001F1EA',
    'Latvia':         '\U0001F1F1\U0001F1FB',
    'Lithuania':      '\U0001F1F1\U0001F1F9',
    'Luxembourg':     '\U0001F1F1\U0001F1FA',
    'Malaysia':       '\U0001F1F2\U0001F1FE',
    'Mexico':         '\U0001F1F2\U0001F1FD',
    'Monaco':         '\U0001F1F2\U0001F1E8',
    'Netherlands':    '\U0001F1F3\U0001F1F1',
    'New Zealand':    '\U0001F1F3\U0001F1FF',
    'Northern Ireland': '\U0001F1EC\U0001F1E7',
    'Norway':         '\U0001F1F3\U0001F1F4',
    'Peru':           '\U0001F1F5\U0001F1EA',
    'Philippines':    '\U0001F1F5\U0001F1ED',
    'Poland':         '\U0001F1F5\U0001F1F1',
    'Portugal':       '\U0001F1F5\U0001F1F9',
    'Romania':        '\U0001F1F7\U0001F1F4',
    'Russia':         '\U0001F1F7\U0001F1FA',
    'Scotland':       '\U0001F3F4\U000E0067\U000E0062\U000E0073\U000E0063\U000E0074\U000E007F',
    'Serbia':         '\U0001F1F7\U0001F1F8',
    'Singapore':      '\U0001F1F8\U0001F1EC',
    'Slovakia':       '\U0001F1F8\U0001F1F0',
    'Slovenia':       '\U0001F1F8\U0001F1EE',
    'South Africa':   '\U0001F1FF\U0001F1E6',
    'South Korea':    '\U0001F1F0\U0001F1F7',
    'Spain':          '\U0001F1EA\U0001F1F8',
    'Sweden':         '\U0001F1F8\U0001F1EA',
    'Switzerland':    '\U0001F1E8\U0001F1ED',
    'Thailand':       '\U0001F1F9\U0001F1ED',
    'Turkey':         '\U0001F1F9\U0001F1F7',
    'Ukraine':        '\U0001F1FA\U0001F1E6',
    'United Arab Emirates': '\U0001F1E6\U0001F1EA',
    'United Kingdom': '\U0001F1EC\U0001F1E7',
    'United States':  '\U0001F1FA\U0001F1F8',
    'Uruguay':        '\U0001F1FA\U0001F1FE',
    'Vietnam':        '\U0001F1FB\U0001F1F3',
    'Wales':          '\U0001F3F4\U000E0067\U000E0062\U000E0077\U000E006C\U000E0073\U000E007F',
}

LOCATION_SURFACE = {
    'Monte Carlo': 'Tarmac',
    'Spain': 'Tarmac',
    # Rallycross circuits — mix of tarmac and gravel in-game.
    'Barcelona':      'Tarmac/Gravel',
    'Hell':           'Tarmac/Gravel',
    'Höljes':         'Tarmac/Gravel',
    'Loheac':         'Tarmac/Gravel',
    'Lydden Hill':    'Tarmac/Gravel',
    'Mettet':         'Tarmac/Gravel',
    'Montalegre':     'Tarmac/Gravel',
    'Estering':       'Tarmac/Gravel',
    'Bikernieki':     'Tarmac/Gravel',
    'Killarney':      'Tarmac/Gravel',
    'Silverstone':    'Tarmac',
    'Trois-Rivières': 'Tarmac/Gravel',
    'Yas Marina':     'Tarmac',
}

DURATION_OPTIONS = {
    '24h': ('daily', timedelta(hours=24)),
    '1week': ('weekly', timedelta(weeks=1)),
    '1month': ('monthly', timedelta(days=30)),
}


# ── Championship schema helpers ──────────────────────────

# Longest a single rally (one championship event) may run.  Two weeks covers a
# club that wants a rally open across a couple of weekends.
MAX_EVENT_DAYS = 14

# Total championship duration bounds (sum of all per-event durations).  The
# ceiling has to clear MAX_CHAMP_EVENTS * MAX_EVENT_DAYS (12 * 14 = 168 days),
# otherwise the builder could offer a combination that submit then rejects.
MIN_CHAMP_DURATION = timedelta(hours=1)
MAX_CHAMP_DURATION = timedelta(days=180)

# Defaults for the four championship-wide advanced toggles.  force_cockpit is
# stored as its own boolean; the dispatcher inverts it into Challenge.exterior_cams.
DEFAULT_CHAMP_SETTINGS: dict[str, bool] = {
    'hardcore_damage': True,
    'force_cockpit_camera': False,
    'allow_assists': True,
    'unexpected_moments': True,
}


def _event_timedelta(d: dict[str, Any]) -> timedelta:
    """Return the timedelta for a per-event ``{days, hours, mins}`` dict."""
    try:
        days = int(d.get('days', 0) or 0)
        hours = int(d.get('hours', 0) or 0)
        mins = int(d.get('mins', 0) or 0)
    except (TypeError, ValueError):
        return timedelta(0)
    return timedelta(days=days, hours=hours, minutes=mins)


def championship_duration(events: list[dict[str, Any]]) -> timedelta:
    """Sum every event's duration into the total championship length."""
    total = timedelta(0)
    for ev in events:
        total += _event_timedelta(ev.get('duration', {}))
    return total


def _validate_duration(d: dict[str, Any]) -> list[str]:
    """Validate one event's ``{days, hours, mins}``; return error strings."""
    errors: list[str] = []
    for key in ('days', 'hours', 'mins'):
        try:
            v = int(d.get(key, 0) or 0)
        except (TypeError, ValueError):
            errors.append(f'Invalid {key} in event duration.')
            continue
        if v < 0:
            errors.append(f'Event {key} cannot be negative.')
        if key == 'days' and v > MAX_EVENT_DAYS:
            errors.append(f'An event can run at most {MAX_EVENT_DAYS} days.')
    return errors


def bucket_for_duration(total: timedelta) -> str:
    """Map a total championship duration to a daily/weekly/monthly bucket.

    Used only for the ``/events`` list filter and badges.
    """
    if total <= timedelta(hours=24):
        return 'daily'
    if total <= timedelta(days=7):
        return 'weekly'
    return 'monthly'


def _duration_for_type(event_type: str) -> dict[str, int]:
    """Legacy adapter: map an old daily/weekly/monthly ``type`` to a duration dict."""
    key = {'daily': '24h', 'weekly': '1week', 'monthly': '1month'}.get(event_type, '1week')
    _t, delta = DURATION_OPTIONS[key]
    total_min = int(delta.total_seconds() // 60)
    days, rem = divmod(total_min, 24 * 60)
    hours, mins = divmod(rem, 60)
    return {'days': days, 'hours': hours, 'mins': mins}


def normalize_championship(raw: dict[str, Any]) -> dict[str, Any]:
    """Return a canonical v2 championship dict (``events[]`` + ``settings``).

    Accepts both the new multi-event shape and the legacy single-event shape
    (no ``events`` key) so every consumer — chiefly the game dispatcher — can
    treat all stored events uniformly.  Never mutates the input.

    Stage fields are passed through untouched.  This reshapes; it never
    converts values — stored data is brought up to date by web/migrations at
    deploy time, so readers can trust what is on disk.
    """
    champ = dict(raw)

    settings = dict(DEFAULT_CHAMP_SETTINGS)
    settings.update(champ.get('settings') or {})
    champ['settings'] = settings

    events = champ.get('events')
    if not events:
        events = [{
            'location': champ.get('location', ''),
            'car_class': champ.get('car_class', ''),
            'surface': champ.get('surface', 'Gravel'),
            'duration': _duration_for_type(champ.get('type', 'weekly')),
            'stages': champ.get('stages', []),
        }]

    norm_events: list[dict[str, Any]] = []
    for ev in events:
        ev = dict(ev)
        ev.setdefault('surface', 'Gravel')
        ev.setdefault('duration', {'days': 0, 'hours': 0, 'mins': 0})
        stages: list[dict[str, Any]] = []
        for s in ev.get('stages', []):
            s = dict(s)
            stages.append(s)
        ev['stages'] = stages
        norm_events.append(ev)
    champ['events'] = norm_events
    return champ


def _champ_stage_layout(event: dict[str, Any]) -> list[int]:
    """Stage counts per sub-event; ``[len(stages)]`` for legacy single events."""
    evs = event.get('events')
    if evs:
        return [len(ev.get('stages', []) or []) for ev in evs]
    return [len(event.get('stages', []) or [])]


def _global_stage_index(event: dict[str, Any], event_index: int, stage_index: int) -> int:
    """Map a per-event ``(event_index, stage_index)`` to a flat championship-wide
    stage ordinal so results for different sub-events don't collide.

    For ``event_index == 0`` this is exactly ``stage_index``, so single-event
    championships (every event today) store results identically to before.
    """
    if event_index <= 0:
        return stage_index
    layout = _champ_stage_layout(event)
    return sum(layout[:event_index]) + stage_index


# ── Championship builder: drafts & form parsing ──────────

# Upstream RaceNet clubs run up to 12 events in one championship (Ray Charles
# Race was captured at AmountOfEvents=12), so the builder matches that.
MAX_CHAMP_EVENTS = 12
MAX_STAGES_PER_EVENT = 12


def _draft_path(draft_id: str) -> str:
    _validate_id(draft_id)
    return os.path.join(CHAMP_DRAFTS_DIR, f'{draft_id}.json')


def get_draft(draft_id: str) -> dict[str, Any] | None:
    p = _draft_path(draft_id)
    return _load(p) if os.path.exists(p) else None


def save_draft(d: dict[str, Any]) -> None:
    _save(_draft_path(d['id']), d)


def delete_draft(draft_id: str) -> None:
    p = _draft_path(draft_id)
    if os.path.exists(p):
        os.remove(p)


def _service_area_for_pos(pos: int) -> str:
    """Default service area: Medium every 2 stages (indices 0, 2, 4, ...)."""
    return 'Medium' if pos % 2 == 0 else 'None'


def _blank_stage(pos: int = 0) -> dict[str, Any]:
    return {'track_id': None, 'conditions_id': None,
            'surface_deg': 'Medium', 'service_area': _service_area_for_pos(pos)}


def _blank_event(num_stages: int = 1) -> dict[str, Any]:
    return {
        'location': '',
        'car_class': '',
        'duration': {'days': 2, 'hours': 0, 'mins': 0},
        'stages': [_blank_stage(i) for i in range(max(1, num_stages))],
    }


# Surface-degradation spread for the semi-random generated fill — skips
# "None"/"Low" so a freshly-generated rally reads like RaceNet's Medium/High/Max.
_RANDOM_SURFACE_DEG = ['Medium', 'High', 'Max']


def _condition_weight(label: str) -> float:
    """Weight a "Time / Weather / Surface" conditions label, biased toward
    Daytime and Dry so a generated rally leans clear-and-bright (like RaceNet)
    while still occasionally rolling dusk/sunset/wet stages for variety."""
    parts = [p.strip() for p in label.split('/')]
    tod = parts[0] if parts else ''
    wet = parts[2] if len(parts) > 2 else ''
    weight = 1.0
    if tod == 'Daytime':
        weight *= 4.0
    elif tod in ('Sunset', 'Dusk'):
        weight *= 1.5
    # Night keeps the base weight.
    if wet == 'Dry':
        weight *= 3.0
    return weight


def _random_condition_for(rng: random.Random, location: str) -> int | None:
    """Pick a conditions id ``location`` supports, Daytime/Dry favoured.

    Drawn from the location's verified set, so a generated draft never seeds a
    stage with conditions that location has no lighting for.
    """
    ids = stage_conditions_for_location(location)
    if not ids:
        return None
    weights = [_condition_weight(stage_conditions_label(cid)) for cid in ids]
    return rng.choices(ids, weights=weights, k=1)[0]


def _random_championship_events(num_events: int, num_stages: int) -> list[dict[str, Any]]:
    """Build a semi-randomly filled set of events (RaceNet-style) so the editor
    opens pre-populated instead of blank.

    Picks ONE confirmed vehicle class for the whole championship (the game
    applies one class per championship) and a distinct verified location per
    event, then fills each stage with a real verified route, a random confirmed
    conditions preset, a surface-deg level, and the Medium-every-2-stages
    service-area pattern.
    """
    rng = random.Random()
    # Rally locations only: the class pool below is rally-only, so seeding a
    # draft with a rallycross circuit would pair an RX track with a rally car.
    # An owner can still pick an RX circuit by hand in the editor.
    loc_pool = [
        l for l in STAGES
        if VERIFIED_STAGE_COUNTS.get(l, 0) > 0 and l not in RX_LOCATIONS
    ]
    class_pool = [
        c for c in CAR_CLASSES
        if (vehicle_class_id_for_label(c) or 0) in CONFIRMED_VEHICLE_CLASS_IDS
    ]
    car_class = rng.choice(class_pool) if class_pool else ''

    used_locs: set[str] = set()
    events: list[dict[str, Any]] = []
    for _ in range(num_events):
        avail = [l for l in loc_pool if l not in used_locs] or loc_pool
        # Prefer a location with enough verified routes to fill every stage.
        rich = [l for l in avail if VERIFIED_STAGE_COUNTS.get(l, 0) >= num_stages]
        location = rng.choice(rich or avail) if avail else ''
        used_locs.add(location)

        routes = list(STAGE_ROUTES.get(location, []))
        rng.shuffle(routes)
        picked = routes[:num_stages]
        stages = [
            {
                'track_id': tid,
                'conditions_id': _random_condition_for(rng, location),
                'surface_deg': rng.choice(_RANDOM_SURFACE_DEG),
                'service_area': _service_area_for_pos(i),
            }
            for i, (tid, _name, _km) in enumerate(picked)
        ] or [_blank_stage(i) for i in range(num_stages)]

        events.append({
            'location': location,
            'car_class': car_class,
            'duration': {'days': 2, 'hours': 0, 'mins': 0},
            'stages': stages,
        })
    return events


def _to_int_or_none(v: Any) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _to_int_or_zero(v: Any) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


_CHAMP_FIELD_RE = re.compile(r'^events\[(\d+)\](?:\[stages\]\[(\d+)\])?\[(\w+)\]$')


def parse_championship_form(form: Any) -> dict[str, Any]:
    """Reconstruct ``{name, events:[{location,car_class,duration,stages:[...]}]}``
    from bracketed indexed form fields.

    Sparse indices left by client-side deletes are compacted to 0..N-1 (submit
    order is ascending), so the server never has to trust the raw indices.
    """
    events: dict[int, dict[str, Any]] = {}
    for key in form.keys():
        m = _CHAMP_FIELD_RE.match(key)
        if not m:
            continue
        ei = int(m.group(1))
        sj = m.group(2)
        field = m.group(3)
        ev = events.setdefault(ei, {'fields': {}, 'stages': {}})
        if sj is None:
            ev['fields'][field] = form.get(key, '')
        else:
            ev['stages'].setdefault(int(sj), {})[field] = form.get(key, '')

    out_events: list[dict[str, Any]] = []
    for ei in sorted(events):
        raw = events[ei]
        f = raw['fields']
        location = (f.get('location') or '').strip()
        # Conditions are per-location, so a submitted id is only kept when this
        # location ships lighting for it; anything else takes the location's own
        # first option. Guards hand-crafted posts and a stale select left over
        # from a location change.
        valid_conds = stage_conditions_for_location(location)
        stages_out: list[dict[str, Any]] = []
        for sj in sorted(raw['stages']):
            s = raw['stages'][sj]
            cond_id = _to_int_or_none(s.get('conditions'))
            if valid_conds and cond_id not in valid_conds:
                # Keep the weather that was picked where the location can
                # render it under a different id (the twin pairs), and only
                # then fall back to its first option. An unresolvable pick is
                # left for _validate_championship to reject at publish rather
                # than being quietly corrected here.
                cond_id = (stage_conditions_sibling_for_location(location, cond_id)
                           or valid_conds[0])
            stages_out.append({
                'track_id': _to_int_or_none(s.get('route')),
                'conditions_id': cond_id,
                'surface_deg': (s.get('surface_deg') or 'Medium').strip(),
                'service_area': (s.get('service_area') or 'Medium').strip(),
            })
        out_events.append({
            'location': location,
            'car_class': (f.get('car_class') or '').strip(),
            'duration': {
                'days': _to_int_or_zero(f.get('duration_days')),
                'hours': _to_int_or_zero(f.get('duration_hours')),
                'mins': _to_int_or_zero(f.get('duration_mins')),
            },
            'stages': stages_out or [_blank_stage()],
        })
    return {'name': (form.get('name') or '').strip(), 'events': out_events}


def _seed_users() -> list[dict[str, Any]]:
    profiles = [
        ('GravelKing',     'Finland',      'Scandinavian gravel specialist'),
        ('McRaeFan95',     'Scotland',     'If in doubt, flat out'),
        ('TarmacTerror',   'Spain',        'Tarmac is the only true surface'),
        ('DirtDemon',      'Australia',    'Red dust runs through my veins'),
        ('SidewaysSteve',  'Wales',        'Powerslide enthusiast'),
        ('RallyRat',       'Poland',       'Living life one stage at a time'),
        ('CoDriverCarl',   'Monaco',       'Five left tightens into three right'),
        ('SendItSarah',    'New Zealand',  'Full send, no regrets'),
        ('FlatOutFrank',   'Sweden',       'Scandinavian flick specialist'),
        ('PaceNotePete',   'Greece',       'Precision over speed'),
        ('HandbrakeHero',  'Argentina',    'Hairpins are my specialty'),
        ('MudSlinger',     'USA',          'The muddier the better'),
    ]
    users = []
    for username, country, bio in profiles:
        u = create_user(
            username=username,
            email=f'{username.lower()}@dirtforever.local',
            password='rally2025',
            display_name=username,
            country=country,
            bio=bio,
            email_verified=True,
        )
        users.append(u)
    return users


def _seed_clubs(users: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clubs_data = [
        {
            'id': 'club-scandinavian',
            'name': 'Scandinavian Sideways',
            'description': 'Nordic rally enthusiasts who live for gravel, snow, and the Scandinavian flick.',
            'created_by': 'GravelKing',
            'created_at': (datetime.now() - timedelta(days=45)).isoformat(),
            'members': ['GravelKing', 'FlatOutFrank', 'McRaeFan95', 'SidewaysSteve', 'SendItSarah'],
        },
        {
            'id': 'club-tarmac',
            'name': 'Tarmac Titans',
            'description': 'Asphalt specialists. Clean lines, late braking, maximum precision.',
            'created_by': 'TarmacTerror',
            'created_at': (datetime.now() - timedelta(days=30)).isoformat(),
            'members': ['TarmacTerror', 'CoDriverCarl', 'PaceNotePete', 'RallyRat'],
        },
        {
            'id': 'club-fullsend',
            'name': 'Full Send Racing',
            'description': 'No half measures. Flat out or nothing.',
            'created_by': 'SendItSarah',
            'created_at': (datetime.now() - timedelta(days=20)).isoformat(),
            'members': ['SendItSarah', 'DirtDemon', 'HandbrakeHero', 'MudSlinger', 'FlatOutFrank', 'McRaeFan95'],
        },
        {
            'id': 'club-weekend',
            'name': 'Weekend Warriors',
            'description': 'Casual rally fans. Fun first, times second.',
            'created_by': 'MudSlinger',
            'created_at': (datetime.now() - timedelta(days=15)).isoformat(),
            'members': ['MudSlinger', 'RallyRat', 'SidewaysSteve', 'HandbrakeHero'],
        },
    ]
    for c in clubs_data:
        save_club(c)
        for uname in c['members']:
            u = get_user(uname)
            if u and c['id'] not in u.get('clubs', []):
                u.setdefault('clubs', []).append(c['id'])
                save_user(u)
    return clubs_data


def _gen_time(base_km: float, rng: random.Random) -> int:
    """Generate a plausible stage time in ms given stage length in km."""
    pace = rng.uniform(5.8, 7.5)  # minutes per km
    base_ms = int(base_km * pace * 60 * 1000)
    variance = rng.uniform(-0.04, 0.08)
    return int(base_ms * (1 + variance))


# The short weather words the seed specs use, mapped to the full labels the
# game renders. Same bridge web/migrations 0001 applies to pre-id stored files.
_SEED_CONDITION_LABELS = {
    'Clear':      'Daytime / Clear / Dry',
    'Overcast':   'Daytime / Overcast / Dry',
    'Light Rain': 'Daytime / Showers / Wet',
    'Heavy Rain': 'Daytime / Heavy Rain / Wet',
    'Dusk':       'Dusk / Cloudy / Dry',
    'Night':      'Night / Clear / Dry',
}


def _conditions_id_for_seed(location: str, word: str) -> int | None:
    """Resolve a seed spec's weather word to an id ``location`` can load."""
    valid = stage_conditions_for_location(location)
    if not valid:
        return None
    wanted = _SEED_CONDITION_LABELS.get(word, word)
    for cid in valid:
        if stage_conditions_label(cid) == wanted:
            return cid
    return valid[0]


def _seed_events_and_results(users: list[dict[str, Any]]) -> None:
    rng = random.Random(42)
    now = datetime.now()
    usernames = [u['username'] for u in users]

    events_spec: list[dict[str, Any]] = [
        {
            'id': 'evt-daily-argentina',
            'name': 'Argentina Sprint',
            'type': 'daily',
            'location': 'Argentina',
            'car_class': 'Group A',
            'surface': 'Gravel',
            'conditions': 'Clear',
            'stage_indices': [0, 2, 4],
            'start': now - timedelta(hours=6),
            'end': now + timedelta(hours=18),
            'featured': True,
            'club_id': None,
        },
        {
            'id': 'evt-daily-finland',
            'name': 'Finland Night Rally',
            'type': 'daily',
            'location': 'Finland',
            'car_class': 'R5',
            'surface': 'Gravel',
            'conditions': 'Night',
            'stage_indices': [3, 4],
            'start': now - timedelta(hours=2),
            'end': now + timedelta(hours=22),
            'featured': False,
            'club_id': None,
        },
        {
            'id': 'evt-weekly-wales',
            'name': 'Wales Classic',
            'type': 'weekly',
            'location': 'Wales',
            'car_class': 'Group B (4WD)',
            'surface': 'Gravel',
            'conditions': 'Overcast',
            'stage_indices': [0, 1, 2, 3],
            'start': now - timedelta(days=3),
            'end': now + timedelta(days=4),
            'featured': False,
            'club_id': 'club-scandinavian',
        },
        {
            'id': 'evt-weekly-greece',
            'name': 'Greece Gravel Grind',
            'type': 'weekly',
            'location': 'Greece',
            'car_class': 'NR4/R4',
            'surface': 'Gravel',
            'conditions': 'Clear',
            'stage_indices': [0, 1, 4],
            'start': now - timedelta(days=2),
            'end': now + timedelta(days=5),
            'featured': False,
            'club_id': 'club-tarmac',
        },
        {
            'id': 'evt-monthly-monaco',
            'name': 'Monte Carlo Championship',
            'type': 'monthly',
            'location': 'Monte Carlo',
            'car_class': 'R5',
            'surface': 'Tarmac',
            'conditions': 'Light Rain',
            'stage_indices': [0, 1, 2, 3, 4, 5],
            'start': now - timedelta(days=10),
            'end': now + timedelta(days=20),
            'featured': False,
            'club_id': None,
        },
        {
            'id': 'evt-monthly-australia',
            'name': 'Australia Endurance',
            'type': 'monthly',
            'location': 'Australia',
            'car_class': 'Group A',
            'surface': 'Gravel',
            'conditions': 'Dusk',
            'stage_indices': [0, 1, 2, 3, 4],
            'start': now - timedelta(days=8),
            'end': now + timedelta(days=22),
            'featured': False,
            'club_id': 'club-fullsend',
        },
    ]

    for spec in events_spec:
        loc = spec['location']
        all_stages = STAGES[loc]
        # Seed with an id this location can actually load, not a bare label:
        # seeding runs after migrations, so label-only stages would leave a
        # fresh dev store holding exactly the shape the migration exists to
        # repair -- and reachable by nothing until the next deploy.
        cond_id = _conditions_id_for_seed(loc, spec['conditions'])
        cond_label = stage_conditions_label(cond_id) if cond_id is not None else ''
        stages = []
        for si in spec['stage_indices']:
            name, km = all_stages[si]
            stages.append({'name': name, 'distance_km': km,
                           'conditions_id': cond_id, 'conditions': cond_label})

        event = {
            'id': spec['id'],
            'name': spec['name'],
            'type': spec['type'],
            'location': spec['location'],
            'car_class': spec['car_class'],
            'surface': spec['surface'],
            'conditions': cond_label,
            'stages': stages,
            'start_time': spec['start'].isoformat(),
            'end_time': spec['end'].isoformat(),
            'active': True,
            'featured': spec['featured'],
            'club_id': spec.get('club_id'),
        }
        save_event(event)

        cars = CAR_CLASSES.get(spec['car_class'], ['Unknown Car'])
        participants = rng.sample(usernames, k=min(rng.randint(6, 10), len(usernames)))
        entries = []
        for uname in participants:
            car = rng.choice(cars)
            stage_times = []
            total = 0
            for stage in stages:
                t = _gen_time(stage['distance_km'], rng)
                penalty = rng.choice([0, 0, 0, 0, 0, 5000, 10000, 15000])
                stage_times.append({
                    'time_ms': t,
                    'penalties_ms': penalty,
                    'submitted_at': (spec['start'] + timedelta(
                        hours=rng.uniform(1, max(1.1, (spec['end'] - spec['start']).total_seconds() / 7200))
                    )).isoformat(),
                })
                total += t + penalty
            entries.append({
                'username': uname,
                'car': car,
                'stages': stage_times,
                'total_time_ms': total,
            })
        entries.sort(key=lambda e: e['total_time_ms'])
        save_results(spec['id'], {'event_id': spec['id'], 'entries': entries})


def seed_data() -> None:
    if os.listdir(USERS_DIR):
        return
    users = _seed_users()
    _seed_clubs(users)
    _seed_events_and_results(users)


# ── Routes: pages ────────────────────────────────────────

@app.route('/')
def home() -> str:
    users  = get_all_users()
    clubs  = get_all_clubs()
    events = sort_events(get_all_events())
    all_results = [get_results(e['id']) for e in events]
    total_entries = sum(len(r.get('entries', [])) for r in all_results)

    stats = {
        'total_drivers': len(users),
        'total_clubs':   len(clubs),
        'active_events': len([e for e in events if e.get('active')]),
        'total_entries': total_entries,
    }
    featured = next((e for e in events if e.get('featured')), events[0] if events else None)

    recent = []
    for r in all_results:
        evt = get_event(r['event_id'])
        if not evt:
            continue
        for entry in r.get('entries', []):
            pos = r['entries'].index(entry) + 1
            recent.append({
                'username': entry['username'],
                'event_name': evt['name'],
                'event_id': evt['id'],
                'total_time_ms': entry['total_time_ms'],
                'car': entry['car'],
                'position': pos,
                'submitted_at': entry['stages'][-1]['submitted_at'] if entry['stages'] else evt['start_time'],
            })
    recent.sort(key=lambda x: x['submitted_at'], reverse=True)

    return render_template('home.html', stats=stats, featured_event=featured, recent=recent[:8])


@app.route('/login', methods=['GET'])
def login() -> str | Response:
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def login_post() -> Response:
    identifier = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    user = None
    if identifier:
        try:
            user = get_user(identifier)
        except Exception:
            user = None
        if not user and '@' in identifier:
            user = next((u for u in get_all_users()
                         if u.get('email', '').lower() == identifier.lower()), None)
    if not user or not check_password(password, user):
        flash('Invalid username or password.', 'error')
        return redirect(url_for('login'))
    session['username'] = user['username']
    flash(f'Welcome back, {user["display_name"]}!', 'success')
    return redirect(url_for('dashboard'))


@app.route('/register', methods=['GET'])
def register() -> str | Response:
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('register.html', countries=COUNTRIES)


@app.route('/register', methods=['POST'])
def register_post() -> Response:
    if request.form.get('website', ''):
        return redirect(url_for('home'))

    username = request.form.get('username', '').strip()
    email    = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    confirm  = request.form.get('confirm', '')
    country  = request.form.get('country', '').strip()

    if not username or not email or not password:
        flash('All fields are required.', 'error')
        return redirect(url_for('register'))
    if len(username) < 3 or len(username) > 24:
        flash('Username must be 3-24 characters.', 'error')
        return redirect(url_for('register'))
    if not _SAFE_ID_RE.match(username):
        flash('Username may only contain letters, numbers, hyphens, and underscores.', 'error')
        return redirect(url_for('register'))
    if password != confirm:
        flash('Passwords do not match.', 'error')
        return redirect(url_for('register'))
    if len(password) < 6:
        flash('Password must be at least 6 characters.', 'error')
        return redirect(url_for('register'))
    if get_user(username):
        flash('Username already taken.', 'error')
        return redirect(url_for('register'))
    if country and country not in COUNTRIES:
        flash('Invalid country selection.', 'error')
        return redirect(url_for('register'))

    user = create_user(username, email, password, country=country)
    send_verification_email(user)
    session['username'] = username
    flash('Account created! Check your email to verify your address.', 'success')
    return redirect(url_for('verify_prompt'))


@app.route('/verify/resend', methods=['POST'])
@login_required
def resend_verification() -> Response:
    user = current_user()
    assert user is not None
    if user.get('email_verified'):
        return redirect(url_for('dashboard'))
    if not user.get('verify_token'):
        user['verify_token'] = secrets.token_urlsafe(32)
        save_user(user)
    send_verification_email(user)
    flash('Verification email sent.', 'success')
    return redirect(url_for('verify_prompt'))


@app.route('/verify/pending')
@login_required
def verify_prompt() -> str | Response:
    user = current_user()
    assert user is not None
    if user.get('email_verified'):
        return redirect(url_for('dashboard'))
    return render_template('verify_email.html', user=user)


@app.route('/verify/<token>')
def verify_email(token: str) -> Response:
    if not token or not _SAFE_ID_RE.match(token.replace('-', '').replace('_', '')):
        abort(400)
    for u in get_all_users():
        if u.get('verify_token') == token:
            u['email_verified'] = True
            u['verify_token'] = None
            save_user(u)
            session['username'] = u['username']
            flash('Email verified! Welcome to DirtForever.', 'success')
            return redirect(url_for('dashboard'))
    flash('Invalid or expired verification link.', 'error')
    return redirect(url_for('login'))


@app.route('/forgot', methods=['GET'])
def forgot_password() -> str:
    return render_template('forgot_password.html')


@app.route('/forgot', methods=['POST'])
def forgot_password_post() -> Response:
    email = request.form.get('email', '').strip()
    log.info('Forgot password request for email=%s', email)
    if not email:
        flash('Please enter your email address.', 'error')
        return redirect(url_for('forgot_password'))

    user = next((u for u in get_all_users() if u.get('email') == email), None)
    # Always show the same message to prevent email enumeration
    flash('If an account with that email exists, we sent a password reset link.', 'info')
    if not user:
        log.info('No user found for email=%s', email)
        return redirect(url_for('forgot_password'))

    # If the user never verified their email, resend verification too
    if not user.get('email_verified'):
        if not user.get('verify_token'):
            user['verify_token'] = secrets.token_urlsafe(32)
        send_verification_email(user)

    user['reset_token'] = secrets.token_urlsafe(32)
    user['reset_token_expires'] = (datetime.now() + timedelta(hours=1)).isoformat()
    save_user(user)
    send_reset_email(user)
    return redirect(url_for('forgot_password'))


@app.route('/reset/<token>', methods=['GET'])
def reset_password(token: str) -> str | Response:
    if not token or not _SAFE_ID_RE.match(token.replace('-', '').replace('_', '')):
        abort(400)
    user = next((u for u in get_all_users()
                 if u.get('reset_token') == token), None)
    if not user:
        flash('Invalid or expired reset link.', 'error')
        return redirect(url_for('forgot_password'))
    expires = user.get('reset_token_expires', '')
    if expires and datetime.fromisoformat(expires) < datetime.now():
        flash('This reset link has expired. Please request a new one.', 'error')
        return redirect(url_for('forgot_password'))
    return render_template('reset_password.html', token=token)


@app.route('/reset/<token>', methods=['POST'])
def reset_password_post(token: str) -> Response:
    if not token or not _SAFE_ID_RE.match(token.replace('-', '').replace('_', '')):
        abort(400)
    user = next((u for u in get_all_users()
                 if u.get('reset_token') == token), None)
    if not user:
        flash('Invalid or expired reset link.', 'error')
        return redirect(url_for('forgot_password'))
    expires = user.get('reset_token_expires', '')
    if expires and datetime.fromisoformat(expires) < datetime.now():
        flash('This reset link has expired. Please request a new one.', 'error')
        return redirect(url_for('forgot_password'))

    password = request.form.get('password', '')
    confirm = request.form.get('confirm', '')
    if len(password) < 6:
        flash('Password must be at least 6 characters.', 'error')
        return redirect(url_for('reset_password', token=token))
    if password != confirm:
        flash('Passwords do not match.', 'error')
        return redirect(url_for('reset_password', token=token))

    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 120_000)
    user['password_hash'] = dk.hex()
    user['salt'] = salt.hex()
    user['reset_token'] = None
    user['reset_token_expires'] = None
    save_user(user)

    session['username'] = user['username']
    flash('Password updated.', 'success')
    return redirect(url_for('dashboard'))


@app.route('/logout', methods=['POST'])
def logout() -> Response:
    session.pop('username', None)
    flash('Signed out.', 'info')
    return redirect(url_for('home'))


@app.route('/dashboard')
@login_required
def dashboard() -> str:
    user = current_user()
    assert user is not None
    my_clubs = [get_club(cid) for cid in user.get('clubs', []) if get_club(cid)]
    events = get_all_events()
    active = sort_events([e for e in events if e.get('active')])

    my_results = []
    for evt in events:
        res = get_results(evt['id'])
        for i, entry in enumerate(res.get('entries', [])):
            if entry['username'] == user['username']:
                my_results.append({
                    'event': evt,
                    'entry': entry,
                    'position': i + 1,
                    'total_entries': len(res['entries']),
                })
    my_results.sort(
        key=lambda x: x['entry']['stages'][-1]['submitted_at'] if x['entry']['stages'] else '',
        reverse=True,
    )

    new_token = session.pop('new_game_token', None)
    game_token = user.get('game_token', '')
    token_masked = f'df_****...{game_token[-8:]}' if game_token else ''

    return render_template(
        'dashboard.html', user=user, my_clubs=my_clubs,
        active_events=active, my_results=my_results[:10],
        new_token=new_token, token_masked=token_masked,
        has_token=bool(game_token),
    )


NOTIFICATIONS_PAGE_SIZE = 50


@app.route('/notifications')
@login_required
def notifications_inbox() -> str:
    user = current_user()
    assert user is not None
    notifs = list(user.get('notifications', []) or [])
    notifs.sort(key=lambda n: n.get('created_at', ''), reverse=True)
    total = len(notifs)
    total_pages = max(1, (total + NOTIFICATIONS_PAGE_SIZE - 1) // NOTIFICATIONS_PAGE_SIZE)
    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        page = 1
    page = max(1, min(page, total_pages))
    start = (page - 1) * NOTIFICATIONS_PAGE_SIZE
    window = notifs[start:start + NOTIFICATIONS_PAGE_SIZE]
    rows = []
    for n in window:
        cid = n.get('club_id') or ''
        club = get_club(cid) if cid else None
        from_user = get_user(n.get('from_username', '')) if n.get('from_username') else None
        rows.append({'notif': n, 'club': club, 'from_user': from_user})
    return render_template(
        'notifications.html', rows=rows,
        page=page, total_pages=total_pages, total=total,
        page_size=NOTIFICATIONS_PAGE_SIZE,
    )


@app.route('/notifications/<ntf_id>/read', methods=['POST'])
@login_required
def notifications_mark_read(ntf_id: str) -> Response:
    user = current_user()
    assert user is not None
    mark_notification_read(user['username'], ntf_id)
    return redirect(url_for('notifications_inbox'))


@app.route('/notifications/read-all', methods=['POST'])
@login_required
def notifications_mark_all_read() -> Response:
    user = current_user()
    assert user is not None
    n = mark_all_notifications_read(user['username'])
    if n:
        flash(f'Marked {n} notification(s) as read.', 'info')
    return redirect(url_for('notifications_inbox'))


@app.route('/leaderboards')
def leaderboards() -> str | Response:
    tab = request.args.get('tab', 'events')
    if tab not in ('events', 'tt'):
        tab = 'events'

    ctx: dict[str, Any] = {'tab': tab}

    if tab == 'events':
        events = sort_events(get_all_events())
        event_id = request.args.get('event')
        stage_idx = request.args.get('stage', type=int)

        selected_event = None
        entries: list[dict[str, Any]] = []
        leader_time = None

        if event_id:
            selected_event = get_event(event_id)
            if selected_event:
                res = get_results(event_id)
                raw = res.get('entries', [])
                if stage_idx is not None and selected_event.get('stages'):
                    filtered = []
                    for e in raw:
                        if stage_idx < len(e.get('stages', [])):
                            st = e['stages'][stage_idx]
                            filtered.append({
                                'username': e['username'],
                                'car': e['car'],
                                'time_ms': st['time_ms'] + st['penalties_ms'],
                                'penalties_ms': st['penalties_ms'],
                            })
                    filtered.sort(key=lambda x: x['time_ms'])
                    entries = filtered
                else:
                    entries = [
                        {
                            'username': e['username'],
                            'car': e['car'],
                            'time_ms': e['total_time_ms'],
                            'penalties_ms': sum(s.get('penalties_ms', 0) for s in e.get('stages', [])),
                        }
                        for e in raw
                    ]
                if entries:
                    leader_time = entries[0]['time_ms']
        elif events:
            return redirect(url_for('leaderboards', tab='events', event=events[0]['id']))

        ctx.update(
            events=events,
            selected_event=selected_event,
            entries=entries,
            leader_time=leader_time,
            stage_idx=stage_idx,
        )

    else:
        # ── Time Trial tab ──────────────────────────────
        # Boards are grouped by (vclass, track, conditions); the per-category
        # split is merged away here (see _list_tt_groups / _merge_tt_entries).
        boards = _list_tt_groups()

        # Collect all tracks that have at least one board, decorated with
        # human-readable names from the game_data tables.
        track_ids = sorted({b['track'] for b in boards})
        tt_tracks: list[dict[str, Any]] = []
        for tid in track_ids:
            meta = GAME_TRACKS.get(tid)
            if meta:
                loc_meta = GAME_LOCATIONS.get(meta['location_id'])
                loc_name = loc_meta['display_name'] if loc_meta else f'Location {meta["location_id"]}'
                tt_tracks.append({
                    'track_id': tid,
                    'name': meta['name'],
                    'location': loc_name,
                    'location_id': meta['location_id'],
                    'length_km': meta.get('length_km', 0.0),
                })
            else:
                tt_tracks.append({
                    'track_id': tid,
                    'name': f'Track {tid}',
                    'location': 'Unknown',
                    'location_id': 0,
                    'length_km': 0.0,
                })
        tt_tracks.sort(key=lambda t: (t['location'], t['name']))

        # Select a track — from query param or first available.
        selected_track_id = request.args.get('track', type=int)
        if selected_track_id is None or not any(t['track_id'] == selected_track_id for t in tt_tracks):
            selected_track_id = tt_tracks[0]['track_id'] if tt_tracks else None

        # Classes that have boards for this track.
        track_boards = [b for b in boards if b['track'] == selected_track_id]
        vclass_options: list[dict[str, Any]] = []
        seen_vc: set[int] = set()
        for b in track_boards:
            if b['vclass'] in seen_vc:
                continue
            seen_vc.add(b['vclass'])
            total = sum(x['count'] for x in track_boards if x['vclass'] == b['vclass'])
            vclass_options.append({
                'id': b['vclass'],
                'label': GAME_VEHICLE_CLASSES.get(b['vclass'], f'Class {b["vclass"]}'),
                'count': total,
            })
        vclass_options.sort(key=lambda v: v['label'])

        selected_vclass = request.args.get('vclass', type=int)
        if selected_vclass is None or not any(v['id'] == selected_vclass for v in vclass_options):
            selected_vclass = vclass_options[0]['id'] if vclass_options else None

        # Conditions variants that exist for this (track, class). Category is
        # merged away, so a variant is just a conditions value.
        variant_boards = [b for b in track_boards if b['vclass'] == selected_vclass]

        selected_cond = request.args.get('cond', type=int)
        selected_variant = next(
            (b for b in variant_boards if b['conditions'] == selected_cond),
            None,
        )
        if selected_variant is None and variant_boards:
            selected_variant = variant_boards[0]
            selected_cond = selected_variant['conditions']

        # Only expose a variant picker when there's more than one.
        variant_options: list[dict[str, Any]] = []
        if len(variant_boards) > 1:
            for b in variant_boards:
                variant_options.append({
                    'conditions': b['conditions'],
                    'label': stage_conditions_label(b['conditions']),
                    'count': b['count'],
                    'active': (b['conditions'] == selected_cond),
                })

        # Load entries for the selected board (merged across categories).
        tt_entries: list[dict[str, Any]] = []
        tt_leader_time: int | None = None
        if selected_variant is not None and selected_vclass is not None and selected_track_id is not None:
            raw = _load_tt_merged(
                str(selected_vclass), str(selected_track_id), str(selected_cond),
            )
            for i, e in enumerate(raw):
                vid = e.get('vehicle_id', 0)
                vmeta = GAME_VEHICLES.get(vid)
                tt_entries.append({
                    'rank': i + 1,
                    'username': e['username'],
                    'time_ms': e['stage_time_ms'],
                    'vehicle_name': vmeta['name'] if vmeta else f'Vehicle {vid}',
                    'using_wheel': e.get('using_wheel', False),
                    'using_assists': e.get('using_assists', False),
                    'submitted_at': e.get('submitted_at', ''),
                })
            if tt_entries:
                tt_leader_time = tt_entries[0]['time_ms']

        selected_track = next(
            (t for t in tt_tracks if t['track_id'] == selected_track_id), None,
        )

        ctx.update(
            tt_tracks=tt_tracks,
            tt_selected_track=selected_track,
            tt_vclass_options=vclass_options,
            tt_selected_vclass=selected_vclass,
            tt_variant_options=variant_options,
            tt_selected_cond=selected_cond,
            tt_entries=tt_entries,
            tt_leader_time=tt_leader_time,
        )

    return render_template('leaderboards.html', **ctx)


@app.route('/clubs')
def clubs() -> str:
    user = current_user()
    all_clubs = [c for c in get_all_clubs() if club_is_visible_to(c, user)]
    query = request.args.get('q', '').strip()
    if query:
        q = query.lower()
        all_clubs = [c for c in all_clubs if q in c['name'].lower() or q in c.get('description', '').lower()]
    return render_template('clubs.html', clubs=all_clubs, query=query)


@app.route('/clubs', methods=['POST'])
@verified_required
def create_club() -> Response:
    name = request.form.get('name', '').strip()
    desc = request.form.get('description', '').strip()
    visibility = request.form.get('visibility', 'public').strip().lower()
    join_policy = request.form.get('join_policy', 'open').strip().lower()
    if visibility not in ('public', 'private'):
        visibility = 'public'
    if join_policy not in ('open', 'approval'):
        join_policy = 'open'
    if not name:
        flash('Club name is required.', 'error')
        return redirect(url_for('clubs'))
    if len(name) > 40:
        flash('Club name must be under 40 characters.', 'error')
        return redirect(url_for('clubs'))

    user = current_user()
    assert user is not None
    cid = f'club-{uuid.uuid4().hex[:8]}'
    club = {
        'id': cid,
        'name': name,
        'description': desc,
        'created_by': user['username'],
        'created_at': datetime.now().isoformat(),
        'members': [user['username']],
        'visibility': visibility,
        'join_policy': join_policy,
        'pending_requests': [],
    }
    save_club(club)
    user.setdefault('clubs', []).append(cid)
    save_user(user)
    flash(f'Club "{name}" created!', 'success')
    return redirect(url_for('club_detail', club_id=cid))


@app.route('/clubs/<club_id>/edit', methods=['POST'])
@verified_required
def edit_club(club_id: str) -> Response:
    """Owner edits the club name, description, visibility, and join policy."""
    me = current_user()
    assert me is not None
    name = (request.form.get('name') or '').strip()
    desc = (request.form.get('description') or '').strip()
    visibility = (request.form.get('visibility') or 'public').strip().lower()
    join_policy = (request.form.get('join_policy') or 'open').strip().lower()
    if visibility not in ('public', 'private'):
        visibility = 'public'
    if join_policy not in ('open', 'approval'):
        join_policy = 'open'
    if not name:
        flash('Club name is required.', 'error')
        return redirect(url_for('club_detail', club_id=club_id))
    if len(name) > 40:
        flash('Club name must be under 40 characters.', 'error')
        return redirect(url_for('club_detail', club_id=club_id))

    path = _club_path(club_id)
    if not os.path.exists(path):
        abort(404)
    with _atomic_update(path) as club:
        if not user_is_owner(club, me['username']):
            abort(403)
        club['name'] = name
        club['description'] = desc
        club['visibility'] = visibility
        club['join_policy'] = join_policy
    flash('Club updated.', 'success')
    return redirect(url_for('club_detail', club_id=club_id))


@app.route('/clubs/<club_id>')
def club_detail(club_id: str) -> str:
    club = get_club(club_id)
    if not club:
        abort(404)
    user = current_user()
    if not club_is_visible_to(club, user):
        abort(404)
    members = [get_user(m) for m in club.get('members', []) if get_user(m)]
    events = sort_events([e for e in get_all_events() if e.get('club_id') == club_id])
    # The game surfaces one championship per club, so the owner needs to see
    # what's occupying the slot before trying to create another one.
    live_event = next((e for e in events if event_is_active(e)), None)
    uname = user['username'] if user else None
    pending_users = []
    if user_is_owner(club, uname):
        for r in club.get('pending_requests', []) or []:
            pu = get_user(r.get('username', ''))
            if pu:
                pending_users.append({'user': pu, 'requested_at': r.get('requested_at', '')})
    pending_invites = []
    if user_is_owner(club, uname):
        for inv in club.get('invites', []) or []:
            iu = get_user(inv.get('username', ''))
            if iu:
                pending_invites.append({'user': iu, 'created_at': inv.get('created_at', '')})
    invite_links = []
    if user_is_owner(club, uname):
        for link in (club.get('invite_links') or []):
            if link.get('revoked'):
                continue
            invite_links.append(link)
    return render_template(
        'club_detail.html', club=club, members=members, events=events,
        rally_locs=sorted(loc for loc in STAGES if loc not in RX_LOCATIONS),
        rx_locs=sorted(loc for loc in STAGES if loc in RX_LOCATIONS),
        stages=STAGES, car_classes=CAR_CLASSES,
        conditions_by_location=CONDITIONS_BY_LOCATION,
        stage_caps=STAGE_CAPS,
        live_event=live_event,
        is_owner=user_is_owner(club, uname),
        is_member=user_is_member(club, uname),
        has_pending_request=user_has_pending_request(club, uname),
        has_pending_invite=user_has_invite(club, uname),
        pending_users=pending_users,
        pending_invites=pending_invites,
        invite_links=invite_links,
        visibility=club_visibility(club),
        join_policy=club_join_policy(club),
        site_url=SITE_URL,
    )


# Sentinel results from atomic-update club mutators so the route handler can
# pick the right flash message and decide whether to fire emails / notifs.
_REQ_OK = 'requested'
_REQ_ALREADY_MEMBER = 'already_member'
_REQ_ALREADY_PENDING = 'already_pending'
_REQ_COOLDOWN = 'cooldown'


def _now_iso() -> str:
    return datetime.now().isoformat()


def _cooldown_remaining(club: dict[str, Any], username: str) -> timedelta | None:
    raw = (club.get('cooldowns') or {}).get(username)
    if not raw:
        return None
    try:
        until = datetime.fromisoformat(raw)
    except ValueError:
        return None
    delta = until - datetime.now()
    return delta if delta.total_seconds() > 0 else None


def _set_cooldown(club: dict[str, Any], username: str, window: timedelta) -> None:
    cd = club.setdefault('cooldowns', {})
    cd[username] = (datetime.now() + window).isoformat()


def _clear_cooldown(club: dict[str, Any], username: str) -> None:
    cd = club.get('cooldowns') or {}
    if username in cd:
        del cd[username]


@app.route('/clubs/<club_id>/join', methods=['POST'])
@verified_required
def join_club(club_id: str) -> Response:
    user = current_user()
    assert user is not None
    path = _club_path(club_id)
    if not os.path.exists(path):
        abort(404)
    outcome: str = ''
    club_name = ''
    with _atomic_update(path) as club:
        if not club_is_visible_to(club, user):
            abort(404)
        club_name = club['name']
        if (club_join_policy(club) == 'approval'
                and not user_is_owner(club, user['username'])):
            outcome = _enqueue_request(club, user['username'])
        else:
            if user['username'] not in (club.get('members') or []):
                club.setdefault('members', []).append(user['username'])
                outcome = 'joined'
            else:
                outcome = 'already_member'
    if outcome == 'joined':
        with _atomic_update(_user_path(user['username'])) as u:
            if club_id not in (u.get('clubs') or []):
                u.setdefault('clubs', []).append(club_id)
        flash(f'Joined {club_name}!', 'success')
    elif outcome == _REQ_OK:
        _post_request_notify(club_id, user['username'], club_name)
        flash(f'Requested to join {club_name}. The owner will review your request.', 'success')
    elif outcome == _REQ_ALREADY_MEMBER or outcome == 'already_member':
        flash('You are already a member of this club.', 'info')
    elif outcome == _REQ_ALREADY_PENDING:
        flash('Your request is already pending approval.', 'info')
    elif outcome == _REQ_COOLDOWN:
        flash('Please wait before requesting to join again.', 'warning')
    return redirect(url_for('club_detail', club_id=club_id))


def _enqueue_request(club: dict[str, Any], username: str) -> str:
    """Mutates ``club`` in place to add a pending request. Caller must hold the
    club's atomic lock. Returns one of the _REQ_* sentinels."""
    if username in (club.get('members') or []):
        return _REQ_ALREADY_MEMBER
    pending = club.setdefault('pending_requests', [])
    if any(r.get('username') == username for r in pending):
        return _REQ_ALREADY_PENDING
    if _cooldown_remaining(club, username):
        return _REQ_COOLDOWN
    pending.append({'username': username, 'requested_at': _now_iso()})
    return _REQ_OK


def _post_request_notify(club_id: str, requester_username: str,
                         club_name: str) -> None:
    """After a request was successfully enqueued, notify + email the owner.
    Email is only sent when add_notification actually wrote a fresh row, so a
    request/cancel/request loop produces at most one alert per cycle."""
    club = get_club(club_id)
    if not club:
        return
    owner_username = club.get('created_by', '')
    if not owner_username:
        return
    notif = add_notification(owner_username, {
        'type': 'club_join_request',
        'club_id': club_id,
        'from_username': requester_username,
    })
    if notif is None:
        return  # de-duped — owner already has an unread alert for this requester
    owner = get_user(owner_username)
    requester = get_user(requester_username)
    if not owner or not requester:
        return
    try:
        _send_join_request_email(owner, requester, {'id': club_id, 'name': club_name})
    except Exception:
        log.exception('failed to send join-request email')


@app.route('/clubs/<club_id>/request', methods=['POST'])
@verified_required
def request_join_club(club_id: str) -> Response:
    user = current_user()
    assert user is not None
    path = _club_path(club_id)
    if not os.path.exists(path):
        abort(404)
    outcome = ''
    club_name = ''
    with _atomic_update(path) as club:
        if not club_is_visible_to(club, user):
            abort(404)
        if user_is_owner(club, user['username']):
            flash('You already own this club.', 'info')
            return redirect(url_for('club_detail', club_id=club_id))
        club_name = club['name']
        outcome = _enqueue_request(club, user['username'])
    if outcome == _REQ_OK:
        _post_request_notify(club_id, user['username'], club_name)
        flash(f'Requested to join {club_name}. The owner will review your request.', 'success')
    elif outcome == _REQ_ALREADY_MEMBER:
        flash('You are already a member of this club.', 'info')
    elif outcome == _REQ_ALREADY_PENDING:
        flash('Your request is already pending approval.', 'info')
    elif outcome == _REQ_COOLDOWN:
        flash('Please wait before requesting to join again.', 'warning')
    return redirect(url_for('club_detail', club_id=club_id))


@app.route('/clubs/<club_id>/request/cancel', methods=['POST'])
@verified_required
def cancel_join_request(club_id: str) -> Response:
    user = current_user()
    assert user is not None
    path = _club_path(club_id)
    if not os.path.exists(path):
        abort(404)
    canceled = False
    owner_username = ''
    with _atomic_update(path) as club:
        owner_username = club.get('created_by', '') or ''
        pending = club.get('pending_requests', []) or []
        new_pending = [r for r in pending if r.get('username') != user['username']]
        if len(new_pending) != len(pending):
            club['pending_requests'] = new_pending
            _set_cooldown(club, user['username'], COOLDOWN_AFTER_CANCEL)
            canceled = True
    if canceled:
        if owner_username:
            clear_join_request_notification(owner_username, club_id, user['username'])
        flash('Join request canceled.', 'info')
    return redirect(url_for('club_detail', club_id=club_id))


@app.route('/clubs/<club_id>/requests/<username>/approve', methods=['POST'])
@verified_required
def approve_join_request(club_id: str, username: str) -> Response:
    me = current_user()
    assert me is not None
    try:
        _validate_id(username)
    except Exception:
        abort(400)
    path = _club_path(club_id)
    if not os.path.exists(path):
        abort(404)
    approved = False
    club_name = ''
    with _atomic_update(path) as club:
        if not user_is_owner(club, me['username']):
            abort(403)
        club_name = club['name']
        pending = club.get('pending_requests', []) or []
        if not any(r.get('username') == username for r in pending):
            flash('No pending request from that user.', 'warning')
            return redirect(url_for('club_detail', club_id=club_id))
        club['pending_requests'] = [r for r in pending if r.get('username') != username]
        if username not in (club.get('members') or []):
            club.setdefault('members', []).append(username)
        _clear_cooldown(club, username)
        approved = True
    if approved:
        requester_path = _user_path(username)
        if os.path.exists(requester_path):
            with _atomic_update(requester_path) as requester:
                if club_id not in (requester.get('clubs') or []):
                    requester.setdefault('clubs', []).append(club_id)
            add_notification(username, {
                'type': 'club_join_approved',
                'club_id': club_id,
            })
            requester_obj = get_user(username)
            if requester_obj:
                try:
                    _send_join_approved_email(requester_obj, {'id': club_id, 'name': club_name})
                except Exception:
                    log.exception('failed to send join-approved email')
        clear_join_request_notification(me['username'], club_id, username)
        flash(f'Approved {username}.', 'success')
    return redirect(url_for('club_detail', club_id=club_id))


@app.route('/clubs/<club_id>/requests/<username>/deny', methods=['POST'])
@verified_required
def deny_join_request(club_id: str, username: str) -> Response:
    me = current_user()
    assert me is not None
    try:
        _validate_id(username)
    except Exception:
        abort(400)
    path = _club_path(club_id)
    if not os.path.exists(path):
        abort(404)
    denied = False
    club_name = ''
    with _atomic_update(path) as club:
        if not user_is_owner(club, me['username']):
            abort(403)
        club_name = club['name']
        pending = club.get('pending_requests', []) or []
        if not any(r.get('username') == username for r in pending):
            flash('No pending request from that user.', 'warning')
            return redirect(url_for('club_detail', club_id=club_id))
        club['pending_requests'] = [r for r in pending if r.get('username') != username]
        _set_cooldown(club, username, COOLDOWN_AFTER_DENY)
        denied = True
    if denied:
        add_notification(username, {
            'type': 'club_join_denied',
            'club_id': club_id,
        })
        requester = get_user(username)
        if requester:
            try:
                _send_join_denied_email(requester, {'id': club_id, 'name': club_name})
            except Exception:
                log.exception('failed to send join-denied email')
        clear_join_request_notification(me['username'], club_id, username)
        flash(f'Denied request from {username}.', 'info')
    return redirect(url_for('club_detail', club_id=club_id))


@app.route('/clubs/<club_id>/leave', methods=['POST'])
@verified_required
def leave_club(club_id: str) -> Response:
    user = current_user()
    assert user is not None
    path = _club_path(club_id)
    if not os.path.exists(path):
        abort(404)
    left = False
    club_name = ''
    is_owner_attempt = False
    with _atomic_update(path) as club:
        club_name = club['name']
        if user_is_owner(club, user['username']):
            # An owner leaving would orphan the club. Block it; we don't have
            # an ownership-transfer or delete flow yet.
            is_owner_attempt = True
        else:
            members = club.get('members') or []
            if user['username'] in members:
                members.remove(user['username'])
                club['members'] = members
                left = True
    if is_owner_attempt:
        flash("You can't leave a club you own.", 'warning')
    elif left:
        with _atomic_update(_user_path(user['username'])) as u:
            if club_id in (u.get('clubs') or []):
                u['clubs'].remove(club_id)
        flash(f'Left {club_name}.', 'info')
    return redirect(url_for('club_detail', club_id=club_id))


# ── Club invites (direct + shareable link) ──────────────

@app.route('/clubs/<club_id>/invite', methods=['POST'])
@verified_required
def invite_to_club(club_id: str) -> Response:
    """Owner invites a specific user by username."""
    me = current_user()
    assert me is not None
    invitee_name = (request.form.get('username') or '').strip()
    if not invitee_name:
        flash('Username is required.', 'error')
        return redirect(url_for('club_detail', club_id=club_id))
    try:
        _validate_id(invitee_name)
    except Exception:
        flash('Invalid username.', 'error')
        return redirect(url_for('club_detail', club_id=club_id))
    invitee = get_user(invitee_name)
    if not invitee:
        flash(f'No user named {invitee_name}.', 'error')
        return redirect(url_for('club_detail', club_id=club_id))

    path = _club_path(club_id)
    if not os.path.exists(path):
        abort(404)
    outcome = ''
    club_name = ''
    with _atomic_update(path) as club:
        if not user_is_owner(club, me['username']):
            abort(403)
        club_name = club['name']
        if invitee_name == me['username']:
            outcome = 'self'
        elif invitee_name in (club.get('members') or []):
            outcome = 'already_member'
        elif user_has_invite(club, invitee_name):
            outcome = 'already_invited'
        else:
            club.setdefault('invites', []).append({
                'username': invitee_name,
                'invited_by': me['username'],
                'created_at': _now_iso(),
            })
            # An invite is owner-driven, so any prior cooldown the user had
            # (from a self-cancel or deny) is moot — clear it so the invitee
            # can act on the invite immediately.
            _clear_cooldown(club, invitee_name)
            outcome = 'invited'
    if outcome == 'invited':
        notif = add_notification(invitee_name, {
            'type': 'club_invite',
            'club_id': club_id,
            'from_username': me['username'],
        })
        if notif is not None:
            try:
                _send_invite_email(invitee, me, {'id': club_id, 'name': club_name})
            except Exception:
                log.exception('failed to send invite email')
        flash(f'Invited {invitee_name}.', 'success')
    elif outcome == 'self':
        flash('You cannot invite yourself.', 'warning')
    elif outcome == 'already_member':
        flash(f'{invitee_name} is already a member.', 'info')
    elif outcome == 'already_invited':
        flash(f'{invitee_name} has already been invited.', 'info')
    return redirect(url_for('club_detail', club_id=club_id))


def _clear_invite_notification(invitee_username: str, club_id: str) -> None:
    """Drop the invitee's `club_invite` notification when the invite is no
    longer pending (canceled, accepted, or declined)."""
    path = _user_path(invitee_username)
    if not os.path.exists(path):
        return
    with _atomic_update(path) as user:
        notifs = user.get('notifications') or []
        kept = [
            n for n in notifs
            if not (n.get('type') == 'club_invite' and n.get('club_id') == club_id)
        ]
        if len(kept) != len(notifs):
            user['notifications'] = kept


@app.route('/clubs/<club_id>/invites/<username>/cancel', methods=['POST'])
@verified_required
def cancel_invite(club_id: str, username: str) -> Response:
    """Owner withdraws a pending invite."""
    me = current_user()
    assert me is not None
    try:
        _validate_id(username)
    except Exception:
        abort(400)
    path = _club_path(club_id)
    if not os.path.exists(path):
        abort(404)
    canceled = False
    with _atomic_update(path) as club:
        if not user_is_owner(club, me['username']):
            abort(403)
        invites = club.get('invites') or []
        new_invites = [i for i in invites if i.get('username') != username]
        if len(new_invites) != len(invites):
            club['invites'] = new_invites
            canceled = True
    if canceled:
        _clear_invite_notification(username, club_id)
        flash(f'Invite to {username} canceled.', 'info')
    return redirect(url_for('club_detail', club_id=club_id))


@app.route('/clubs/<club_id>/invite/accept', methods=['POST'])
@verified_required
def accept_invite(club_id: str) -> Response:
    """Invitee accepts the invitation and is added to the club."""
    me = current_user()
    assert me is not None
    path = _club_path(club_id)
    if not os.path.exists(path):
        abort(404)
    accepted = False
    club_name = ''
    with _atomic_update(path) as club:
        if not user_has_invite(club, me['username']):
            flash('You do not have a pending invite to this club.', 'warning')
            return redirect(url_for('club_detail', club_id=club_id))
        club_name = club['name']
        club['invites'] = [
            i for i in (club.get('invites') or [])
            if i.get('username') != me['username']
        ]
        # If the user previously requested to join, drop that too.
        club['pending_requests'] = [
            r for r in (club.get('pending_requests') or [])
            if r.get('username') != me['username']
        ]
        _clear_cooldown(club, me['username'])
        if me['username'] not in (club.get('members') or []):
            club.setdefault('members', []).append(me['username'])
        accepted = True
    if accepted:
        with _atomic_update(_user_path(me['username'])) as u:
            if club_id not in (u.get('clubs') or []):
                u.setdefault('clubs', []).append(club_id)
        _clear_invite_notification(me['username'], club_id)
        flash(f'Joined {club_name}.', 'success')
    return redirect(url_for('club_detail', club_id=club_id))


@app.route('/clubs/<club_id>/invite/decline', methods=['POST'])
@verified_required
def decline_invite(club_id: str) -> Response:
    """Invitee declines the invitation."""
    me = current_user()
    assert me is not None
    path = _club_path(club_id)
    if not os.path.exists(path):
        abort(404)
    declined = False
    with _atomic_update(path) as club:
        invites = club.get('invites') or []
        new_invites = [i for i in invites if i.get('username') != me['username']]
        if len(new_invites) != len(invites):
            club['invites'] = new_invites
            declined = True
    if declined:
        _clear_invite_notification(me['username'], club_id)
        flash('Invite declined.', 'info')
    return redirect(url_for('clubs'))


@app.route('/clubs/<club_id>/invite-link', methods=['POST'])
@verified_required
def create_invite_link(club_id: str) -> Response:
    """Owner generates a new shareable invite link."""
    me = current_user()
    assert me is not None
    path = _club_path(club_id)
    if not os.path.exists(path):
        abort(404)
    token = secrets.token_urlsafe(24)
    with _atomic_update(path) as club:
        if not user_is_owner(club, me['username']):
            abort(403)
        club.setdefault('invite_links', []).append({
            'token': token,
            'created_by': me['username'],
            'created_at': _now_iso(),
            'revoked': False,
        })
    flash('Invite link created.', 'success')
    return redirect(url_for('club_detail', club_id=club_id))


@app.route('/clubs/<club_id>/invite-link/<token>/revoke', methods=['POST'])
@verified_required
def revoke_invite_link(club_id: str, token: str) -> Response:
    """Owner revokes an invite link. We mark it revoked rather than dropping
    the row so the audit history (who created it, when) is preserved."""
    me = current_user()
    assert me is not None
    path = _club_path(club_id)
    if not os.path.exists(path):
        abort(404)
    revoked = False
    with _atomic_update(path) as club:
        if not user_is_owner(club, me['username']):
            abort(403)
        for link in (club.get('invite_links') or []):
            if link.get('token') == token and not link.get('revoked'):
                link['revoked'] = True
                link['revoked_at'] = _now_iso()
                revoked = True
                break
    if revoked:
        flash('Invite link revoked.', 'info')
    return redirect(url_for('club_detail', club_id=club_id))


@app.route('/clubs/<club_id>/join/<token>', methods=['GET', 'POST'])
def join_via_invite_link(club_id: str, token: str) -> Any:
    """Public landing for a shareable invite link.

    GET renders a simple "you've been invited to <name>" page so the recipient
    can see the club name even when the club is private. POST accepts and
    joins. Login is required to actually join (we redirect to /login first if
    they're not logged in)."""
    club = get_club(club_id)
    if not club:
        abort(404)
    link = find_invite_link(club, token)
    if not link:
        abort(404)
    user = current_user()
    if request.method == 'GET':
        return render_template(
            'club_invite_landing.html', club=club, token=token,
            current_user_obj=user,
            visibility=club_visibility(club),
        )
    # POST: accept
    if not user:
        flash('Please sign in to accept the invite.', 'warning')
        return redirect(url_for('login'))
    if not user.get('email_verified'):
        flash('Please verify your email before joining clubs.', 'warning')
        return redirect(url_for('verify_prompt'))
    path = _club_path(club_id)
    joined = False
    club_name = ''
    with _atomic_update(path) as cl:
        link2 = find_invite_link(cl, token)
        if not link2:
            abort(404)
        club_name = cl['name']
        if user['username'] not in (cl.get('members') or []):
            cl.setdefault('members', []).append(user['username'])
            joined = True
        # An accepted token-link join supersedes any prior request/cooldown.
        cl['pending_requests'] = [
            r for r in (cl.get('pending_requests') or [])
            if r.get('username') != user['username']
        ]
        cl['invites'] = [
            i for i in (cl.get('invites') or [])
            if i.get('username') != user['username']
        ]
        _clear_cooldown(cl, user['username'])
    if joined:
        with _atomic_update(_user_path(user['username'])) as u:
            if club_id not in (u.get('clubs') or []):
                u.setdefault('clubs', []).append(club_id)
        flash(f'Joined {club_name}.', 'success')
    else:
        flash('You are already a member of this club.', 'info')
    return redirect(url_for('club_detail', club_id=club_id))


@app.route('/clubs/<club_id>/events', methods=['POST'])
@verified_required
def create_club_event(club_id: str) -> Response:
    club = get_club(club_id)
    if not club:
        abort(404)
    user = current_user()
    assert user is not None
    if club['created_by'] != user['username']:
        abort(403)

    name = request.form.get('name', '').strip()
    location = request.form.get('location', '').strip()
    car_class = request.form.get('car_class', '').strip()
    cond_raw = request.form.get('conditions', '').strip()
    duration = request.form.get('duration', '').strip()
    try:
        num_stages = int(request.form.get('num_stages', '0'))
    except ValueError:
        num_stages = 0

    errors: list[str] = []
    if not name:
        errors.append('Event name is required.')
    elif len(name) > 60:
        errors.append('Event name must be under 60 characters.')
    if location not in STAGES:
        errors.append('Invalid location.')
    # The class must map to a confirmed game vehicle class, otherwise the game
    # server can't build a valid challenge and would have to drop the event.
    vclass_id = vehicle_class_id_for_label(car_class)
    if car_class not in CAR_CLASSES or vclass_id is None \
            or vclass_id not in CONFIRMED_VEHICLE_CLASS_IDS:
        errors.append('Invalid or unsupported vehicle class.')
    # Conditions are per-location: only the ids this location ships lighting
    # for are accepted, since anything else loads the stage with a broken sky.
    try:
        cond_id: int | None = int(cond_raw)
    except ValueError:
        cond_id = None
    allowed_conds = stage_conditions_for_location(location)
    if not allowed_conds:
        errors.append('No verified conditions for this location yet.')
    elif cond_id not in allowed_conds:
        errors.append('Invalid conditions for this location.')
    if duration not in DURATION_OPTIONS:
        errors.append('Invalid duration.')
    available = STAGE_CAPS.get(location, len(STAGES.get(location, [])))
    if num_stages < 1 or (available and num_stages > available):
        errors.append(f'Stage count must be between 1 and {available}.')

    if errors:
        for e in errors:
            flash(e, 'error')
        return redirect(url_for('club_detail', club_id=club_id))

    event_type, delta = DURATION_OPTIONS[duration]
    now = datetime.now()
    # A Quick Event starts immediately, so it can only go out when the club's
    # championship slot is free: the game shows one per club at a time.
    clash = club_event_conflict(club_id, now, now + delta)
    if clash:
        flash(f'"{clash.get("name", "Another event")}" is still running in this '
              f'club ({countdown_filter(clash.get("end_time", ""))} left). The game '
              'only shows one championship per club, so use + Create Championship '
              'to schedule one for after it finishes.', 'error')
        return redirect(url_for('club_detail', club_id=club_id))
    surface = LOCATION_SURFACE.get(location, 'Gravel')

    cond_label = stage_conditions_label(cond_id) if cond_id is not None else ''
    stage_list = [
        {'name': sname, 'distance_km': dist,
         'conditions_id': cond_id, 'conditions': cond_label}
        for sname, dist in STAGES[location][:num_stages]
    ]

    event = {
        'id': f'evt-{uuid.uuid4().hex[:8]}',
        'name': name,
        'type': event_type,
        'location': location,
        'car_class': car_class,
        'surface': surface,
        'conditions': cond_label,
        'stages': stage_list,
        'start_time': now.isoformat(),
        'end_time': (now + delta).isoformat(),
        'active': True,
        'featured': False,
        'club_id': club_id,
    }

    save_event(event)
    flash(f'Event "{name}" created!', 'success')
    return redirect(url_for('club_detail', club_id=club_id))


# ── Championship builder (RaceNet-style multi-event) ─────

def _require_club_owner(club_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load the club and current user, enforcing 404/403; returns (club, user)."""
    club = get_club(club_id)
    if not club:
        abort(404)
    user = current_user()
    assert user is not None
    if club['created_by'] != user['username']:
        abort(403)
    return club, user


def _require_draft(club_id: str, draft_id: str, user: dict[str, Any]) -> dict[str, Any]:
    draft = get_draft(draft_id)
    if not draft or draft.get('club_id') != club_id or draft.get('owner') != user['username']:
        abort(404)
    return draft


def _championship_edit_context(club: dict[str, Any], draft: dict[str, Any]) -> dict[str, Any]:
    return dict(
        club=club, draft=draft,
        rally_locs=sorted(loc for loc in STAGES if loc not in RX_LOCATIONS),
        rx_locs=sorted(loc for loc in STAGES if loc in RX_LOCATIONS),
        car_classes=list(CAR_CLASSES.keys()),
        conditions_by_location=CONDITIONS_BY_LOCATION,
        surface_deg_options=SURFACE_DEG_OPTIONS,
        service_area_options=SERVICE_AREA_OPTIONS,
        stage_routes=STAGE_ROUTES, stage_caps=STAGE_CAPS,
        blank_stage=_blank_stage(),
        max_events=MAX_CHAMP_EVENTS, max_stages=MAX_STAGES_PER_EVENT,
        max_event_days=MAX_EVENT_DAYS,
    )


@app.route('/clubs/<club_id>/championship/new', methods=['GET'])
@verified_required
def championship_new(club_id: str) -> str:
    club, _user = _require_club_owner(club_id)
    return render_template('championship_new.html', club=club,
                           max_events=MAX_CHAMP_EVENTS, max_stages=MAX_STAGES_PER_EVENT)


@app.route('/clubs/<club_id>/championship/new', methods=['POST'])
@verified_required
def championship_generate(club_id: str) -> Response:
    club, user = _require_club_owner(club_id)
    num_events = _to_int_or_zero(request.form.get('num_events'))
    num_stages = _to_int_or_zero(request.form.get('num_stages'))
    errors: list[str] = []
    if not (1 <= num_events <= MAX_CHAMP_EVENTS):
        errors.append(f'Number of events must be between 1 and {MAX_CHAMP_EVENTS}.')
    if not (1 <= num_stages <= MAX_STAGES_PER_EVENT):
        errors.append(f'Number of stages must be between 1 and {MAX_STAGES_PER_EVENT}.')
    if errors:
        for e in errors:
            flash(e, 'error')
        return redirect(url_for('championship_new', club_id=club_id))

    draft = {
        'id': f'champ-draft-{uuid.uuid4().hex[:8]}',
        'club_id': club_id,
        'owner': user['username'],
        'created_at': datetime.now().isoformat(),
        'name': '',
        'start_at': '',
        'settings': dict(DEFAULT_CHAMP_SETTINGS),
        'events': _random_championship_events(num_events, num_stages),
    }
    save_draft(draft)
    return redirect(url_for('championship_edit', club_id=club_id, draft_id=draft['id']))


@app.route('/clubs/<club_id>/championship/<draft_id>', methods=['GET'])
@verified_required
def championship_edit(club_id: str, draft_id: str) -> str:
    club, user = _require_club_owner(club_id)
    draft = _require_draft(club_id, draft_id, user)
    return render_template('championship_edit.html',
                           **_championship_edit_context(club, draft))


@app.route('/clubs/<club_id>/championship/<draft_id>', methods=['POST'])
@verified_required
def championship_action(club_id: str, draft_id: str) -> Response:
    _club, user = _require_club_owner(club_id)
    draft = _require_draft(club_id, draft_id, user)

    # Always persist the whole editor form first so nothing is lost on a bounce.
    parsed = parse_championship_form(request.form)
    draft['name'] = parsed['name']
    draft['events'] = parsed['events'] or [_blank_event()]

    action = request.form.get('action', 'save')
    anchor = ''
    if action == 'add_event':
        if len(draft['events']) < MAX_CHAMP_EVENTS:
            draft['events'].append(_blank_event(1))
            anchor = f"#event-{len(draft['events']) - 1}"
        else:
            flash(f'A championship can have at most {MAX_CHAMP_EVENTS} events.', 'error')
    elif action.startswith('delete_event:'):
        i = _to_int_or_zero(action.split(':', 1)[1])
        if len(draft['events']) > 1 and 0 <= i < len(draft['events']):
            draft['events'].pop(i)
    elif action.startswith('add_stage:'):
        i = _to_int_or_zero(action.split(':', 1)[1])
        if 0 <= i < len(draft['events']):
            stages_i = draft['events'][i]['stages']
            if len(stages_i) < MAX_STAGES_PER_EVENT:
                stages_i.append(_blank_stage(len(stages_i)))
            else:
                flash(f'An event can have at most {MAX_STAGES_PER_EVENT} stages.', 'error')
            anchor = f"#event-{i}"
    elif action.startswith('delete_stage:'):
        parts = action.split(':')
        i = _to_int_or_zero(parts[1]) if len(parts) > 1 else 0
        j = _to_int_or_zero(parts[2]) if len(parts) > 2 else 0
        if 0 <= i < len(draft['events']):
            st = draft['events'][i]['stages']
            if len(st) > 1 and 0 <= j < len(st):
                st.pop(j)
            anchor = f"#event-{i}"

    save_draft(draft)
    if action == 'preview':
        return redirect(url_for('championship_preview', club_id=club_id, draft_id=draft_id))
    return redirect(url_for('championship_edit', club_id=club_id, draft_id=draft_id) + anchor)


def _duration_label(d: dict[str, Any]) -> str:
    """Human label for a {days, hours, mins} duration, e.g. "2 Days 6 Hours"."""
    d = d or {}
    parts = []
    if d.get('days'):
        parts.append(f"{d['days']} Day" + ('s' if d['days'] != 1 else ''))
    if d.get('hours'):
        parts.append(f"{d['hours']} Hour" + ('s' if d['hours'] != 1 else ''))
    if d.get('mins'):
        parts.append(f"{d['mins']} Min" + ('s' if d['mins'] != 1 else ''))
    return ' '.join(parts) if parts else '0 Mins'


def _championship_summary(draft: dict[str, Any]) -> dict[str, Any]:
    """Per-event summary rows + computed end time for the preview screen."""
    rows = [
        {
            'location': ev.get('location') or '(none)',
            'stages': len(ev.get('stages', [])),
            'duration_label': _duration_label(ev.get('duration', {})),
        }
        for ev in draft.get('events', [])
    ]
    return {'rows': rows, 'total': championship_duration(draft.get('events', []))}


def _championship_view(event: dict[str, Any]) -> list[dict[str, Any]]:
    """Per-rally view of a championship for the detail pages: one entry per
    sub-event with its stages and the flat stage-ordinal offset/count so the
    per-rally leaderboard can slice the flat results array."""
    champ = normalize_championship(event)
    out: list[dict[str, Any]] = []
    offset = 0
    for ei, ev in enumerate(champ['events']):
        stages = ev.get('stages', []) or []
        out.append({
            'index': ei,
            'location': ev.get('location', ''),
            'car_class': ev.get('car_class', ''),
            'surface': ev.get('surface', ''),
            'duration_label': _duration_label(ev.get('duration', {})),
            'stages': stages,
            'offset': offset,
            'count': len(stages),
        })
        offset += len(stages)
    return out


def _rally_standings(entries: list[dict[str, Any]], offset: int, count: int) -> list[dict[str, Any]]:
    """Per-rally leaderboard: slice each entry's flat stages to this rally's
    range and keep only drivers who finished every stage of it, sorted by the
    rally subtotal."""
    rows: list[dict[str, Any]] = []
    for e in entries:
        seg = (e.get('stages', []) or [])[offset:offset + count]
        if len(seg) < count:
            continue
        subtotal = 0
        complete = True
        for s in seg:
            t = int((s or {}).get('time_ms', 0) or 0)
            if t <= 0:
                complete = False
                break
            subtotal += t + int((s or {}).get('penalties_ms', 0) or 0)
        if not complete:
            continue
        rows.append({
            'username': e.get('username', ''),
            'car': e.get('car', ''),
            'stages': seg,
            'total_time_ms': subtotal,
        })
    rows.sort(key=lambda r: r['total_time_ms'])
    return rows


# Points awarded for each rally of a championship, by finishing position.
# This is the real-world stage-rally scale (FIA World Rally Championship,
# top ten score): P1 25, P2 18, P3 15, P4 12, P5 10, P6 8, P7 6, P8 4, P9 2,
# P10 1. Everyone else scores 0 for that rally.
RALLY_POINTS = (25, 18, 15, 12, 10, 8, 6, 4, 2, 1)


def _championship_points(event: dict[str, Any],
                         entries: list[dict[str, Any]]) -> dict[str, int]:
    """Championship points per username.

    Each rally of the championship is scored on its own finishing order
    (``_rally_standings``: drivers who completed every stage of that rally,
    fastest first) using ``RALLY_POINTS``, and a driver's total is the sum
    across rallies. A driver who did not complete a rally scores nothing for
    it but keeps the points from the others. Every driver in ``entries`` is
    present in the result, with 0 if they scored nothing.
    """
    points: dict[str, int] = {e.get('username', ''): 0 for e in entries}
    for rally in _championship_view(event):
        standings = _rally_standings(entries, rally['offset'], rally['count'])
        for pos, row in enumerate(standings[:len(RALLY_POINTS)]):
            name = row['username']
            points[name] = points.get(name, 0) + RALLY_POINTS[pos]
    return points


@app.route('/clubs/<club_id>/championship/<draft_id>/preview', methods=['GET'])
@verified_required
def championship_preview(club_id: str, draft_id: str) -> str:
    club, user = _require_club_owner(club_id)
    draft = _require_draft(club_id, draft_id, user)
    summary = _championship_summary(draft)
    now = datetime.now()
    # Only one championship per club can be live at a time, so the earliest a
    # new one may start is when whatever is running now finishes.
    busy_until = club_busy_until(club_id, now)
    earliest = max(now, busy_until) if busy_until else now
    start_ref = earliest
    if draft.get('start_at'):
        try:
            start_ref = datetime.fromisoformat(draft['start_at'])
        except ValueError:
            start_ref = earliest
    end_display = ''
    if summary['total'].total_seconds() > 0:
        end_display = (start_ref + summary['total']).strftime('%a %d %b %Y, %H:%M')
    # Times are stored naive in the server's own zone. The date picker is read
    # in the *viewer's* zone, so hand the browser real instants (epoch seconds)
    # and let enhance.js render/submit them in local time.
    return render_template(
        'championship_preview.html', club=club, draft=draft,
        summary_rows=summary['rows'], end_display=end_display,
        total_seconds=int(summary['total'].total_seconds()),
        busy_for=countdown_filter(busy_until.isoformat()) if busy_until else '',
        min_iso=earliest.strftime('%Y-%m-%dT%H:%M'),
        min_epoch=int(earliest.timestamp()),
        start_epoch=int(start_ref.timestamp()),
    )


def _enrich_stage(location: str, s: dict[str, Any]) -> dict[str, Any]:
    routes = {tid: (name, km) for tid, name, km in STAGE_ROUTES.get(location, [])}
    tid = s.get('track_id')
    name, km = routes.get(tid, ('', 0.0)) if tid is not None else ('', 0.0)
    cid = s.get('conditions_id')
    label = STAGE_CONDITIONS_LABELS.get(cid, '') if cid is not None else ''
    return {
        'name': name, 'track_id': tid, 'distance_km': km,
        'conditions_id': cid, 'conditions': label,
        'surface_deg': s.get('surface_deg', 'Medium'),
        'service_area': s.get('service_area', 'Medium'),
    }


def _validate_championship(events: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    if not events:
        return ['A championship needs at least one event.']
    classes = set()
    for i, ev in enumerate(events, start=1):
        loc = ev.get('location', '')
        cls = ev.get('car_class', '')
        classes.add(cls)
        if loc not in STAGES:
            errors.append(f'Event {i}: invalid location.')
        vclass_id = vehicle_class_id_for_label(cls)
        if cls not in CAR_CLASSES or vclass_id is None \
                or vclass_id not in CONFIRMED_VEHICLE_CLASS_IDS:
            errors.append(f'Event {i}: invalid or unsupported vehicle class.')
        errors.extend(f'Event {i}: {e}' for e in _validate_duration(ev.get('duration', {})))
        stages = ev.get('stages', [])
        cap = STAGE_CAPS.get(loc, len(STAGES.get(loc, [])))
        if not (1 <= len(stages) <= MAX_STAGES_PER_EVENT):
            errors.append(f'Event {i}: must have 1-{MAX_STAGES_PER_EVENT} stages.')
        if loc in STAGES and cap and len(stages) > cap:
            errors.append(f'Event {i}: {loc} supports at most {cap} stages.')
        valid_track_ids = {tid for tid, _n, _km in STAGE_ROUTES.get(loc, [])}
        # Conditions are per-location like routes are: a globally-known id the
        # location ships no lighting for loads the stage with a broken sky.
        valid_conditions = stage_conditions_for_location(loc)
        for sj, s in enumerate(stages, start=1):
            tid = s.get('track_id')
            if tid is None or tid not in valid_track_ids:
                errors.append(f'Event {i} stage {sj}: pick a route.')
            cid = s.get('conditions_id')
            if cid is None or cid not in valid_conditions:
                errors.append(f'Event {i} stage {sj}: pick conditions.')
            if s.get('surface_deg') not in SURFACE_DEG_OPTIONS:
                errors.append(f'Event {i} stage {sj}: invalid surface degradation.')
            if s.get('service_area') not in SERVICE_AREA_OPTIONS:
                errors.append(f'Event {i} stage {sj}: invalid service area.')
    if len(classes) > 1:
        errors.append('All events must use the same vehicle class '
                      '(the game applies one class per championship).')
    return errors


@app.route('/clubs/<club_id>/championship/<draft_id>/submit', methods=['POST'])
@verified_required
def championship_submit(club_id: str, draft_id: str) -> Response:
    club, user = _require_club_owner(club_id)
    draft = _require_draft(club_id, draft_id, user)

    name = (request.form.get('name') or draft.get('name') or '').strip()
    start_at = (request.form.get('start_at') or '').strip()
    # enhance.js posts the picked instant as epoch seconds so the viewer's
    # timezone survives the trip; fall back to the raw (server-zone) field
    # when JS is unavailable.
    start_epoch = (request.form.get('start_at_epoch') or '').strip()
    if start_epoch:
        try:
            start_at = datetime.fromtimestamp(
                float(start_epoch)).strftime('%Y-%m-%dT%H:%M')
        except (ValueError, OSError, OverflowError):
            pass
    settings = {
        'hardcore_damage': request.form.get('adv_hardcore_damage') == '1',
        'unexpected_moments': request.form.get('adv_unexpected_moments') == '1',
        'force_cockpit_camera': request.form.get('adv_force_cockpit') == '1',
        'allow_assists': request.form.get('adv_allow_assists') == '1',
    }
    draft['start_at'] = start_at
    draft['settings'] = settings
    save_draft(draft)

    events = draft.get('events', [])
    errors = _validate_championship(events)
    if not name:
        errors.insert(0, 'Championship name is required.')
    elif len(name) > 60:
        errors.insert(0, 'Championship name must be under 60 characters.')

    now = datetime.now()
    start_dt = now
    if start_at:
        try:
            start_dt = datetime.fromisoformat(start_at)
        except ValueError:
            errors.append('Invalid start date/time.')
    if start_dt < now - timedelta(minutes=5):
        errors.append('Start time cannot be in the past.')
    total = championship_duration(events)
    if total.total_seconds() <= 0:
        errors.append('Total championship duration must be greater than zero.')
    if total > MAX_CHAMP_DURATION:
        errors.append('Total championship duration is too long.')

    # One championship per club at a time: the game has a single event cursor
    # per club, so an overlapping one would be unreachable in game.
    if total.total_seconds() > 0:
        clash = club_event_conflict(club_id, start_dt, start_dt + total)
        if clash:
            errors.append(
                f'"{clash.get("name", "Another event")}" is running in this club '
                f'until it ends in {countdown_filter(clash.get("end_time", ""))}. '
                'The game only shows one championship per club, so start this '
                'one after that.')

    if errors:
        for e in errors:
            flash(e, 'error')
        return redirect(url_for('championship_preview', club_id=club_id, draft_id=draft_id))

    end_dt = start_dt + total
    v2_events = [
        {
            'location': ev['location'],
            'car_class': ev['car_class'],
            'surface': LOCATION_SURFACE.get(ev['location'], 'Gravel'),
            'duration': ev.get('duration', {}),
            'stages': [_enrich_stage(ev['location'], s) for s in ev.get('stages', [])],
        }
        for ev in events
    ]
    first = v2_events[0]
    event = {
        'id': f'evt-{uuid.uuid4().hex[:8]}',
        'schema_version': 2,
        'name': name,
        'type': bucket_for_duration(total),
        'club_id': club_id,
        'start_time': start_dt.isoformat(),
        'end_time': end_dt.isoformat(),
        'active': True,
        'featured': False,
        'settings': settings,
        # Top-level mirrors of events[0] so legacy readers/templates keep working.
        'location': first['location'],
        'car_class': first['car_class'],
        'surface': first['surface'],
        'conditions': first['stages'][0]['conditions'] if first['stages'] else '',
        'stages': first['stages'],
        'events': v2_events,
    }
    save_event(event)
    delete_draft(draft_id)
    flash(f'Championship "{name}" created!', 'success')
    return redirect(url_for('club_detail', club_id=club_id))


@app.route('/events')
def events() -> str:
    t = request.args.get('type', 'daily')
    all_events = get_all_events()
    filtered = sort_events([e for e in all_events if e.get('type') == t])
    counts: dict[str, int] = {}
    for e in all_events:
        counts[e['type']] = counts.get(e['type'], 0) + 1
    return render_template('events.html', events=filtered, event_type=t, counts=counts)


@app.route('/events/<event_id>')
def event_detail(event_id: str) -> str:
    """Championship overview: its rallies (each clickable) + overall standings."""
    event = get_event(event_id)
    if not event:
        abort(404)
    results = get_results(event_id)
    entries = results.get('entries', [])
    club = get_club(event['club_id']) if event.get('club_id') else None
    rallies = _championship_view(event)
    return render_template('event_detail.html', event=event, entries=entries,
                           club=club, rallies=rallies)


@app.route('/events/<event_id>/rally/<int:rally_index>')
def rally_detail(event_id: str, rally_index: int) -> str:
    """A single rally within a championship: its stages + per-rally standings."""
    event = get_event(event_id)
    if not event:
        abort(404)
    rallies = _championship_view(event)
    if rally_index < 0 or rally_index >= len(rallies):
        abort(404)
    rally = rallies[rally_index]
    results = get_results(event_id)
    standings = _rally_standings(results.get('entries', []),
                                 rally['offset'], rally['count'])
    club = get_club(event['club_id']) if event.get('club_id') else None
    return render_template('rally_detail.html', event=event, rally=rally,
                           standings=standings, club=club, rally_count=len(rallies))


@app.route('/profile/<username>')
def profile(username: str) -> str:
    user = get_user(username)
    if not user:
        abort(404)

    user_clubs = [get_club(cid) for cid in user.get('clubs', []) if get_club(cid)]
    events = get_all_events()
    results_list = []
    total_stages = 0
    best_positions = []
    for evt in events:
        res = get_results(evt['id'])
        for i, entry in enumerate(res.get('entries', [])):
            if entry['username'] == username:
                pos = i + 1
                best_positions.append(pos)
                total_stages += len(entry.get('stages', []))
                latest = max(
                    (s.get('submitted_at') or '' for s in entry.get('stages', [])),
                    default='',
                )
                results_list.append({
                    'event': evt,
                    'entry': entry,
                    'position': pos,
                    'total_entries': len(res['entries']),
                    '_sort_key': latest or evt.get('start_time', ''),
                })

    results_list.sort(key=lambda r: r['_sort_key'], reverse=True)

    stats = {
        'total_events': len(results_list),
        'total_stages': total_stages,
        'wins': best_positions.count(1),
        'podiums': sum(1 for p in best_positions if p <= 3),
        'avg_position': round(sum(best_positions) / len(best_positions), 1) if best_positions else 0,
    }

    return render_template(
        'profile.html', profile_user=user, user_clubs=user_clubs,
        results=results_list, stats=stats,
    )


@app.route('/account', methods=['GET'])
@login_required
def account() -> str:
    user = current_user()
    assert user is not None
    return render_template('account.html', user=user, countries=COUNTRIES)


@app.route('/account', methods=['POST'])
@login_required
def account_post() -> Response:
    user = current_user()
    assert user is not None

    display_name = request.form.get('display_name', '').strip()
    country      = request.form.get('country', '').strip()
    bio          = request.form.get('bio', '').strip()

    if display_name:
        if len(display_name) > 40:
            flash('Display name must be under 40 characters.', 'error')
            return redirect(url_for('account'))
        user['display_name'] = display_name

    if country and country not in COUNTRIES:
        flash('Invalid country selection.', 'error')
        return redirect(url_for('account'))
    user['country'] = country

    if len(bio) > 280:
        flash('Bio must be under 280 characters.', 'error')
        return redirect(url_for('account'))
    user['bio'] = bio

    save_user(user)
    flash('Account updated.', 'success')
    return redirect(url_for('account'))


@app.route('/install')
def install() -> str:
    return render_template('install.html')


@app.route('/about')
def about() -> str:
    return render_template('about.html')


@app.route('/streaming')
def streaming() -> str:
    return render_template('streaming.html')


# ── Error pages ──────────────────────────────────────────

@app.errorhandler(404)
def not_found(e: Exception) -> tuple[str, int]:
    return render_template('base.html', error='Page not found'), 404


# ── Game API ─────────────────────────────────────────────
# Called by the local game server (dr2server) to sync data.
# No CSRF tokens — the game server is a trusted backend process.


def _api_error(msg: str, status: int = 400) -> tuple[Response, int]:
    return jsonify({'ok': False, 'error': msg}), status


# ── Game token auth ──────────────────────────────────────

from flask import g

def _find_user_by_token(token: str | None) -> dict[str, Any] | None:
    """Look up the user who owns a game token."""
    if not token or not token.startswith('df_'):
        return None
    for u in get_all_users():
        if u.get('game_token') == token:
            return u  # type: ignore[no-any-return]
    return None


def game_auth_required(f: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator: validate Bearer token, set g.game_user."""
    @wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return jsonify({'ok': False, 'error': 'Missing game token'}), 401
        token = auth[7:]
        user = _find_user_by_token(token)
        if not user:
            return jsonify({'ok': False, 'error': 'Invalid game token'}), 401
        g.game_user = user['username']
        return f(*args, **kwargs)
    return wrapper


@app.route('/api/token/generate', methods=['POST'])
@login_required
def api_token_generate() -> Response:
    user = current_user()
    assert user is not None
    token = 'df_' + secrets.token_hex(16)
    user['game_token'] = token
    save_user(user)
    session['new_game_token'] = token
    return redirect(url_for('dashboard'))


@app.route('/api/token/revoke', methods=['POST'])
@login_required
def api_token_revoke() -> Response:
    user = current_user()
    assert user is not None
    user.pop('game_token', None)
    save_user(user)
    flash('Game token revoked.', 'info')
    return redirect(url_for('dashboard'))


@app.route('/api/game/token-test')
@csrf.exempt  # type: ignore[untyped-decorator]
@game_auth_required
def api_game_token_test() -> Response:
    """Verify a game token is valid. Returns the linked username."""
    return jsonify({'ok': True, 'username': g.game_user})


@app.route('/api/game/clubs')
@csrf.exempt  # type: ignore[untyped-decorator]
@game_auth_required
def api_game_clubs() -> Response:
    """Return the authenticated user's clubs and their active events.

    Only clubs the caller is a member of are returned, along with active events
    owned by those clubs. This prevents leaking other users' (especially
    private) clubs to the game client.
    """
    user = get_user(g.game_user) or {}
    my_club_ids = list(user.get('clubs', []) or [])
    # Direct lookup by ID — O(member_clubs) instead of scanning every club file.
    clubs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for cid in my_club_ids:
        if cid in seen:
            continue
        seen.add(cid)
        c = get_club(cid)
        if c:
            clubs.append(c)
    if not seen:
        return jsonify({'ok': True, 'clubs': [], 'events': []})
    # Events still need a directory scan — there's no club->events index yet.
    # When the project moves to a real DB, add an index on event.club_id.
    # Filter on event_is_active() (which checks end_time), not the raw `active`
    # flag: expired events keep active=True until the cron sweep runs, and we
    # must never serve a finished event to the game even if that sweep lags.
    events = [
        normalize_championship(e)
        for e in sort_events(get_all_events())
        if event_is_active(e) and e.get('club_id') in seen
    ]
    return jsonify({'ok': True, 'clubs': clubs, 'events': events})


@app.route('/api/game/challenges')
@csrf.exempt  # type: ignore[untyped-decorator]
@game_auth_required
def api_game_challenges() -> Response:
    """Return active official (non-club) events for the game's Events page.

    Serves RaceNetChallenges.GetChallenges: the daily/weekly/monthly events
    the generator creates (plus any admin-created event without a club).
    Club events are excluded — those are served via /api/game/clubs.
    Same event_is_active() filter as the clubs endpoint: never serve a
    finished or not-yet-started event even if the expiry cron sweep lags.
    """
    events = [
        normalize_championship(e)
        for e in sort_events(get_all_events())
        if event_is_active(e) and not e.get('club_id')
    ]
    return jsonify({'ok': True, 'events': events})


@app.route('/api/game/profile')
@csrf.exempt  # type: ignore[untyped-decorator]
@game_auth_required
def api_game_profile() -> Response | tuple[Response, int]:
    """Return the authenticated user's game profile for the game server."""
    username = g.game_user
    user = get_user(username)
    if not user:
        return jsonify({'ok': False, 'error': 'user not found'}), 404

    # Initialize game profile fields on first game login if absent
    changed = False
    if 'soft_currency' not in user:
        user['soft_currency'] = 500000
        changed = True
    if 'hard_currency' not in user:
        user['hard_currency'] = 0
        changed = True
    if 'garage_slots' not in user:
        user['garage_slots'] = 8
        changed = True
    if changed:
        save_user(user)

    return jsonify({
        'ok': True,
        'username': user['username'],
        'display_name': user.get('display_name', user['username']),
        'country': user.get('country', ''),
        'soft_currency': user['soft_currency'],
        'hard_currency': user['hard_currency'],
        'garage_slots': user['garage_slots'],
    })


@app.route('/api/game/stage-begin', methods=['POST'])
@csrf.exempt  # type: ignore[untyped-decorator]
@game_auth_required
def api_game_stage_begin() -> Response | tuple[Response, int]:
    """Store pre-stage setup data (tuning, tyres, livery) before a stage starts."""
    data = request.get_json(silent=True) or {}
    event_id = data.get('event_id', '').strip()
    username = g.game_user

    if not event_id:
        return _api_error('event_id is required')
    try:
        _validate_id(event_id)
    except Exception:
        return _api_error('invalid event_id')

    event = get_event(event_id)
    if not event:
        return _api_error('event not found', 404)

    event_club_id = event.get('club_id')
    if event_club_id:
        user = get_user(username) or {}
        if event_club_id not in (user.get('clubs') or []):
            return _api_error('not a member of this club', 403)

    stage_index = int(data.get('stage_index', 0))
    event_index = int(data.get('event_index', 0) or 0)
    # Flatten (event_index, stage_index) so multi-event championships don't
    # collide; identity for single-event (event_index 0).
    pos = _global_stage_index(event, event_index, stage_index)

    results = get_results(event_id)
    # Store in_progress keyed by username -> flat stage ordinal
    in_progress = results.setdefault('in_progress', {})
    user_progress = in_progress.setdefault(username, {})
    user_progress[str(pos)] = {
        'vehicle_id': data.get('vehicle_id'),
        'livery_id': data.get('livery_id'),
        'tuning_setup_b64': data.get('tuning_setup_b64', ''),
        'tyre_compound': data.get('tyre_compound', 2),
        'tyres_remaining': data.get('tyres_remaining', 3),
        'nationality_id': data.get('nationality_id', 0),
    }
    save_results(event_id, results)
    return jsonify({'ok': True})


@app.route('/api/game/stage-complete', methods=['POST'])
@csrf.exempt  # type: ignore[untyped-decorator]
@game_auth_required
def api_game_stage_complete() -> Response | tuple[Response, int]:
    """Accept a completed stage submission from the game server."""
    data = request.get_json(silent=True) or {}
    event_id = data.get('event_id', '').strip()
    username = g.game_user  # from token auth
    if not event_id:
        return _api_error('event_id is required')

    try:
        _validate_id(event_id)
    except Exception:
        return _api_error('invalid event_id')

    event = get_event(event_id)
    if not event:
        return _api_error('event not found', 404)

    event_club_id = event.get('club_id')
    if event_club_id:
        user = get_user(username) or {}
        if event_club_id not in (user.get('clubs') or []):
            return _api_error('not a member of this club', 403)

    stage_index = int(data.get('stage_index', 0))
    event_index = int(data.get('event_index', 0) or 0)
    # Flatten (event_index, stage_index); identity for single-event.
    pos = _global_stage_index(event, event_index, stage_index)
    time_ms = int(data.get('time_ms', 0))
    vehicle_id = data.get('vehicle_id')
    penalties_ms = int(data.get('penalties_ms', 0))

    results = get_results(event_id)
    entries = results.get('entries', [])

    # Pull any in_progress data stored by stage-begin for this user/stage
    in_progress_entry: dict[str, Any] = (
        results.get('in_progress', {})
        .get(username, {})
        .get(str(pos), {})
    )

    existing = next((e for e in entries if e['username'] == username), None)

    if existing is None:
        # New entry — pad all previous stages with 0 so indices stay consistent
        pad = [{'time_ms': 0, 'penalties_ms': 0, 'submitted_at': None}
               for _ in range(pos)]
        existing = {
            'username': username,
            'car': str(vehicle_id) if vehicle_id is not None else '',
            'stages': pad,
            'total_time_ms': 0,
            'vehicle_id': vehicle_id,
            'attempts_used': 0,
        }
        entries.append(existing)
    else:
        existing.setdefault('attempts_used', 0)

    # Extend padding to the target index so we can preserve any prior entry.
    while len(existing['stages']) <= pos:
        existing['stages'].append({'time_ms': 0, 'penalties_ms': 0, 'submitted_at': None})
    prev_stage_entry: dict[str, Any] = existing['stages'][pos] or {}

    # Routing/identity fields the dispatcher sends in the JSON body but that
    # don't belong inside a stage entry.
    _routing_keys = {'event_id', 'username', 'stage_index', 'event_index'}

    # Merge layers in oldest→newest order so newer wins:
    #   1. prev_stage_entry  — preserves data from a previous submission
    #   2. in_progress_entry — values captured at stage-begin (tuning, livery,
    #      tyres, etc.) — these don't change during the stage run
    #   3. data              — fields explicitly sent by this submission;
    #      partial submissions (e.g. the leaderboard pre-persist that only
    #      knows time_ms) leave most fields out, which is intentional —
    #      missing → preserve, never overwrite with invented zeros.
    stage_entry: dict[str, Any] = {
        **prev_stage_entry,
        **{k: v for k, v in (in_progress_entry or {}).items() if v is not None},
        **{k: v for k, v in data.items()
           if v is not None and k not in _routing_keys},
    }
    # Always-current bookkeeping
    stage_entry['time_ms'] = time_ms
    stage_entry['submitted_at'] = datetime.now().isoformat()
    if vehicle_id is not None:
        stage_entry['vehicle_id'] = vehicle_id
    # Defaults for fields we still want to reason about even on a partial
    # pre-persist call. setdefault preserves any prior real value.
    stage_entry.setdefault('penalties_ms', 0)
    stage_entry.setdefault('race_status', 0)

    existing['stages'][pos] = stage_entry

    # Count a DNF/retired finish as a consumed attempt. race_status==0 ("UNKNOWN"
    # in the game's enum) is what the client actually sends for a clean finish,
    # per dispatcher.py's race_status==0 gate, so don't burn an attempt on that.
    if stage_entry['race_status'] != 0:
        existing['attempts_used'] = existing.get('attempts_used', 0) + 1

    # Recalculate total from all stages that have a real time
    existing['total_time_ms'] = sum(
        s['time_ms'] + s.get('penalties_ms', 0)
        for s in existing['stages']
        if s.get('time_ms', 0) > 0
    )
    if vehicle_id is not None:
        existing['vehicle_id'] = vehicle_id

    entries.sort(key=lambda e: e['total_time_ms'])
    results['entries'] = entries
    save_results(event_id, results)

    position = next(
        (i + 1 for i, e in enumerate(entries) if e['username'] == username), 0
    )
    return jsonify({'ok': True, 'position': position, 'total_entries': len(entries)})


@app.route('/api/game/my-progress')
@csrf.exempt  # type: ignore[untyped-decorator]
@game_auth_required
def api_game_my_progress() -> Response:
    """Return the authenticated user's full stage progress across all events."""
    username = g.game_user
    events_out = []
    for evt in get_all_events():
        evt_id = evt.get('id', '')
        if not evt_id:
            continue
        res = get_results(evt_id)
        user_entry = next(
            (e for e in res.get('entries', []) if e.get('username') == username),
            None,
        )
        if not user_entry:
            continue

        completed: list[dict[str, Any]] = []
        for i, s in enumerate(user_entry.get('stages', [])):
            if not s or s.get('time_ms', 0) <= 0:
                continue
            completed.append({
                'stage_index': i,
                'time_ms': s.get('time_ms', 0),
                'penalties_ms': s.get('penalties_ms', 0),
                'meters_driven': s.get('meters_driven', 0),
                'distance_driven': s.get('distance_driven', 0),
                'vehicle_id': s.get('vehicle_id') or user_entry.get('vehicle_id'),
                'livery_id': s.get('livery_id', 0),
                'nationality_id': s.get('nationality_id', 0),
                'has_repaired': s.get('has_repaired', False),
                'repair_penalty_ms': s.get('repair_penalty_ms', 0),
                'tuning_setup_b64': s.get('tuning_setup_b64', ''),
                'tyre_compound': s.get('tyre_compound', 2),
                'tyres_remaining': s.get('tyres_remaining', 3),
                'vehicle_damage': s.get('comp_damage') or {},
                'vehicle_mud': s.get('vehicle_mud') or {},
            })

        events_out.append({
            'event_id': evt_id,
            'completed_stages': completed,
            'total_time_ms': user_entry.get('total_time_ms', 0),
            'attempts_used': user_entry.get('attempts_used', 0),
        })

    return jsonify({'ok': True, 'events': events_out})


@app.route('/api/game/leaderboard/<event_id>')
@csrf.exempt  # type: ignore[untyped-decorator]
@game_auth_required
def api_game_leaderboard(event_id: str) -> Response | tuple[Response, int]:
    """Return leaderboard entries for an event."""
    try:
        _validate_id(event_id)
    except Exception:
        return _api_error('invalid event_id')

    results = get_results(event_id)
    entries = results.get('entries', [])
    event = get_event(event_id)
    points = _championship_points(event, entries) if event else {}
    out = []
    for i, e in enumerate(entries):
        out.append({
            'rank': i + 1,
            'username': e['username'],
            'car': e.get('car', ''),
            'vehicle_id': e.get('vehicle_id'),
            'total_time_ms': e['total_time_ms'],
            'points': points.get(e['username'], 0),
            'stages': e.get('stages', []),
        })
    return jsonify({'ok': True, 'entries': out, 'total': len(out)})


@app.route('/api/game/events/<event_id>')
@csrf.exempt  # type: ignore[untyped-decorator]
@game_auth_required
def api_game_event(event_id: str) -> Response | tuple[Response, int]:
    """Return event details with stages."""
    try:
        _validate_id(event_id)
    except Exception:
        return _api_error('invalid event_id')

    event = get_event(event_id)
    if not event:
        return _api_error('event not found', 404)
    return jsonify({'ok': True, 'event': event})


@app.route('/api/game/auth', methods=['POST'])
@csrf.exempt  # type: ignore[untyped-decorator]
def api_game_auth() -> Response | tuple[Response, int]:
    """Validate a game session / link a Steam account to a web account."""
    data = request.get_json(silent=True) or {}
    steam_name = data.get('steam_name', '').strip()
    account_id = data.get('account_id')

    if not steam_name:
        return _api_error('steam_name is required')

    # Look for a user whose display_name or username matches the Steam name
    users = get_all_users()
    user = next(
        (u for u in users
         if u.get('display_name', '').lower() == steam_name.lower()
         or u.get('username', '').lower() == steam_name.lower()),
        None,
    )

    if user:
        # Optionally persist the account_id link
        if account_id is not None and user.get('steam_account_id') != account_id:
            user['steam_account_id'] = account_id
            save_user(user)
        return jsonify({
            'ok': True,
            'linked': True,
            'username': user['username'],
            'display_name': user['display_name'],
        })

    # No match — return ok but unlinked so the game server can still proceed
    return jsonify({
        'ok': True,
        'linked': False,
        'steam_name': steam_name,
    })


# ── Time Trial helpers ───────────────────────────────────

def _stable_int_id(string_id: str, base: int = 100000) -> int:
    """Derive a stable positive integer from a string (md5-based, deterministic)."""
    h = int.from_bytes(hashlib.md5(string_id.encode()).digest()[:4], 'little')
    return base + (h % 90000)


def _tt_key(vclass: str, track: str, conditions: str, category: str) -> str:
    return f'{vclass}_{track}_{conditions}_{category}'


def _tt_path(key: str) -> str:
    return os.path.join(TIME_TRIALS_DIR, f'{key}.json')


def _load_tt(key: str) -> list[Any]:
    p = _tt_path(key)
    if os.path.exists(p):
        return _load(p)  # type: ignore[no-any-return]
    return []


def _save_tt(key: str, entries: list[Any]) -> None:
    _save(_tt_path(key), entries)


def _merge_tt_entries(entry_lists: list[list[Any]]) -> list[Any]:
    """Merge per-category boards into one ranking.

    Time trials are stored per `category` (the game posts to a category-keyed
    leaderboard), but for ranking "who is fastest on this stage in this class
    and conditions" the category is not a meaningful split. Splitting by it
    fragments the ranking and hides the overall fastest lap on a second board.
    Here we collapse the categories: keep each user's best time across all of
    them, sorted ascending. The per-category files stay on disk untouched, so
    the split can be rebuilt later if category ever proves meaningful.
    """
    best: dict[str, Any] = {}
    for entries in entry_lists:
        for e in entries:
            u = e['username']
            if u not in best or e['stage_time_ms'] < best[u]['stage_time_ms']:
                best[u] = e
    return sorted(best.values(), key=lambda e: e['stage_time_ms'])


def _tt_board_files() -> list[tuple[int, int, int, int, str]]:
    """Return (vclass, track, conditions, category, stem) for each board file."""
    out: list[tuple[int, int, int, int, str]] = []
    if not os.path.isdir(TIME_TRIALS_DIR):
        return out
    for fn in sorted(os.listdir(TIME_TRIALS_DIR)):
        if not fn.endswith('.json'):
            continue
        stem = fn[:-5]
        parts = stem.split('_')
        if len(parts) != 4:
            continue
        try:
            vclass, track, conditions, category = (int(p) for p in parts)
        except ValueError:
            continue
        out.append((vclass, track, conditions, category, stem))
    return out


def _load_tt_merged(vclass: str, track: str, conditions: str) -> list[Any]:
    """Load and merge every category board for a (vclass, track, conditions)."""
    lists = [
        _load_tt(stem)
        for v, t, c, _cat, stem in _tt_board_files()
        if str(v) == vclass and str(t) == track and str(c) == conditions
    ]
    return _merge_tt_entries(lists)


def _list_tt_groups() -> list[dict[str, Any]]:
    """One record per (vclass, track, conditions), merging across category.

    `count` is the number of unique users after merging the per-category
    boards, so the UI never surfaces category as a separate leaderboard.
    """
    grouped: dict[tuple[int, int, int], list[list[Any]]] = {}
    for vclass, track, conditions, _category, stem in _tt_board_files():
        grouped.setdefault((vclass, track, conditions), []).append(_load_tt(stem))
    return [
        {
            'vclass': vclass,
            'track': track,
            'conditions': conditions,
            'count': len(_merge_tt_entries(lists)),
        }
        for (vclass, track, conditions), lists in grouped.items()
    ]


# ── Time Trial API endpoints ──────────────────────────────

@app.route('/api/game/time-trial-submit', methods=['POST'])
@csrf.exempt  # type: ignore[untyped-decorator]
@game_auth_required
def api_game_time_trial_submit() -> Response | tuple[Response, int]:
    """Accept a time trial result from the game server and persist it."""
    data = request.get_json(silent=True) or {}

    try:
        vclass_int = int(data['vehicle_class_id'])
        track = str(int(data['track_model_id']))
        conditions = str(int(data['conditions_id']))
        category = str(int(data['category']))
        vehicle_id = int(data['vehicle_id'])
        livery_id = int(data.get('livery_id', 0))
        stage_time_ms = int(data['stage_time_ms'])
        nationality_id = int(data.get('nationality_id', 0))
        using_wheel = bool(data.get('using_wheel', False))
        using_assists = bool(data.get('using_assists', False))
        ghost_data_b64 = str(data.get('ghost_data_b64', ''))
    except (KeyError, TypeError, ValueError) as exc:
        return _api_error(f'invalid payload: {exc}')

    # Defense in depth: an older client sends 0 here when its dispatcher
    # didn't see a prior GetLeaderboardId. Recover from the vehicle's class.
    if vclass_int not in GAME_VEHICLE_CLASSES:
        vehicle_meta = GAME_VEHICLES.get(vehicle_id)
        if vehicle_meta is None:
            return _api_error(f'unknown vehicle_id: {vehicle_id}')
        vclass_int = vehicle_meta['class']
    vclass = str(vclass_int)

    if stage_time_ms <= 0:
        return _api_error('stage_time_ms must be positive')

    username = g.game_user
    key = _tt_key(vclass, track, conditions, category)
    entries = _load_tt(key)

    # Replace user's existing entry only if the new time is better
    existing = next((e for e in entries if e['username'] == username), None)
    if existing is not None:
        if stage_time_ms >= existing['stage_time_ms']:
            # Not a personal best — acknowledge but don't store
            return jsonify({'ok': True, 'stored': False, 'reason': 'not a personal best'})
        entries = [e for e in entries if e['username'] != username]

    entries.append({
        'username': username,
        'stage_time_ms': stage_time_ms,
        'vehicle_id': vehicle_id,
        'livery_id': livery_id,
        'nationality_id': nationality_id,
        'using_wheel': using_wheel,
        'using_assists': using_assists,
        'ghost_data_b64': ghost_data_b64,
        # The board file is keyed by category, but stamp it on the entry too so
        # entries stay self-describing if boards are ever merged on disk. The
        # web view collapses categories on read (see _merge_tt_entries).
        'category': int(category),
        'submitted_at': datetime.now().isoformat(),
    })
    entries.sort(key=lambda e: e['stage_time_ms'])
    _save_tt(key, entries)

    return jsonify({'ok': True, 'stored': True, 'rank': next(
        i + 1 for i, e in enumerate(entries) if e['username'] == username
    )})


@app.route('/api/game/time-trial-leaderboard')
@csrf.exempt  # type: ignore[untyped-decorator]
@game_auth_required
def api_game_time_trial_leaderboard() -> Response | tuple[Response, int]:
    """Return time trial leaderboard entries for a (vclass, track, conditions).

    `category` is accepted for backward compatibility but ignored: entries are
    merged across categories so the in-game board shows one unified ranking,
    matching the web leaderboard (see _merge_tt_entries).
    """
    try:
        vclass = str(int(request.args['vclass']))
        track = str(int(request.args['track']))
        conditions = str(int(request.args['conditions']))
    except (KeyError, TypeError, ValueError) as exc:
        return _api_error(f'invalid query params: {exc}')

    entries = _load_tt_merged(vclass, track, conditions)

    out = []
    for i, e in enumerate(entries):
        out.append({
            'rank': i + 1,
            'username': e['username'],
            'stage_time_ms': e['stage_time_ms'],
            'vehicle_id': e['vehicle_id'],
            'livery_id': e.get('livery_id', 0),
            'nationality_id': e.get('nationality_id', 0),
            'using_wheel': e.get('using_wheel', False),
            'using_assists': e.get('using_assists', False),
        })

    return jsonify({'ok': True, 'entries': out, 'total': len(out)})


@app.route('/api/game/time-trial-leaderboard-id')
@csrf.exempt  # type: ignore[untyped-decorator]
@game_auth_required
def api_game_time_trial_leaderboard_id() -> Response | tuple[Response, int]:
    """Return a stable integer LeaderboardId for a time trial 4-tuple."""
    try:
        vclass = str(int(request.args['vclass']))
        track = str(int(request.args['track']))
        conditions = str(int(request.args['conditions']))
        category = str(int(request.args['category']))
    except (KeyError, TypeError, ValueError) as exc:
        return _api_error(f'invalid query params: {exc}')

    lb_id = _stable_int_id(f'tt-{vclass}-{track}-{conditions}-{category}', base=4_000_000)
    return jsonify({'ok': True, 'leaderboard_id': lb_id})


# ── Cron API ─────────────────────────────────────────────
# Externally triggered (cron, systemd timer, uptime monitor, etc.).
# Authenticated via the X-Cron-Key header matching CRON_API_KEY.
# The handler is idempotent — safe to invoke off-schedule.


def cron_auth_required(f: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not CRON_API_KEY:
            return _api_error('cron disabled (CRON_API_KEY not set)', 503)
        supplied = request.headers.get('X-Cron-Key', '')
        if not hmac.compare_digest(supplied, CRON_API_KEY):
            return _api_error('unauthorized', 401)
        return f(*args, **kwargs)
    return wrapper


@app.route('/api/cron', methods=['POST'])
@csrf.exempt  # type: ignore[untyped-decorator]
@cron_auth_required
def api_cron() -> Response:
    from events_generator import run_cron_tick  # lazy import to avoid cycles
    result = run_cron_tick(datetime.utcnow())
    return jsonify({'ok': True, **result})


# ── Main ─────────────────────────────────────────────────

if __name__ == '__main__':
    seed_data()
    app.run(host='0.0.0.0', port=5001, debug=True)
