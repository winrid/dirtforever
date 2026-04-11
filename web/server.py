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

for d in (USERS_DIR, CLUBS_DIR, EVENTS_DIR, RESULTS_DIR, TIME_TRIALS_DIR):
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
    return dict(current_user=current_user())


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

STAGES = {
    'Argentina': [
        ('Las Juntas', 8.25), ('Valle de los puentes', 7.55),
        ('Camino de acantilados', 5.30), ('San Isidro', 6.85),
        ('Miraflores', 3.35), ('El Rodeo', 7.00),
    ],
    'Australia': [
        ('Mount Kaye Pass', 12.50), ('Chandlers Creek', 12.34),
        ('Bondi Forest', 7.00), ('Rockton Plains', 6.87),
        ('Yambulla Mountain Ascent', 6.64), ('Noorinbee Ridge Descent', 6.30),
    ],
    'Finland': [
        ('Kakaristo', 16.20), ('Kontinjarvi', 15.04),
        ('Naarajarvi', 12.14), ('Jyrkysjarvi', 7.51),
        ('Kailajarvi', 7.43), ('Paskuri', 5.72),
    ],
    'Greece': [
        ('Fourketa Kourva', 10.36), ('Anodou Farmakas', 9.10),
        ('Pomona Erixi', 5.09), ('Koryfi Dafni', 4.95),
        ('Abies Koilada', 7.09), ('Tsiristra Thea', 5.79),
    ],
    'Monaco': [
        ('Vallee descendante', 10.87), ("Pra d'Alart", 9.83),
        ('Col de Turini Depart', 9.05), ('Route de Turini', 10.87),
        ('Col de Turini Sprint', 5.17), ('Gordolon', 5.17),
    ],
    'New Zealand': [
        ('Waimarama Point Forward', 15.06), ('Te Awanga Forward', 11.44),
        ('Waimarama Sprint Forward', 5.23), ('Elsthorpe Sprint Forward', 4.79),
        ('Ocean Beach Sprint Forward', 7.15), ('Te Awanga Sprint Forward', 4.83),
    ],
    'Poland': [
        ('Leczna', 16.46), ('Zienki', 13.42),
        ('Zagorze', 8.75), ('Jezioro Rotcze', 6.59),
        ('Borysik', 6.82), ('Jozefow', 9.17),
    ],
    'Scotland': [
        ('Rosebank Farm', 7.17), ('South Morningside', 12.58),
        ('Annbank Station', 7.77), ('Newhouse Bridge', 12.85),
    ],
    'Spain': [
        ('Comiols', 14.35), ('Descenso por carretera', 10.57),
        ('Centenera', 10.57), ('Ascenso bosque', 5.30),
        ('Vinedos dentro del monasterio', 6.81), ('El Montaje', 3.20),
    ],
    'Sweden': [
        ('Hamra', 12.34), ('Ransbysater', 11.98),
        ('Elgsjon', 7.28), ('Stor-jangen Sprint', 6.69),
        ('Algsjon Sprint', 5.25), ('Ostra Hinnsjon', 4.93),
    ],
    'USA': [
        ('Beaver Creek Trail Forward', 12.86),
        ('North Fork Pass', 12.50),
        ('Hancock Creek Burst', 6.89),
        ('Fuller Mountain Ascent', 6.64),
        ('Fury Lake Depart', 5.97),
        ('Hancock Hill Sprint', 6.01),
    ],
    'Wales': [
        ('River Severn Valley', 11.40), ('Sweet Lamb', 9.93),
        ('Geufron Forest', 10.03), ('Pant Mawr', 5.72),
        ('Bidno Moorland', 4.87), ('Bronfelen', 5.10),
    ],
}

CAR_CLASSES = {
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

CONDITIONS = ['Clear', 'Overcast', 'Light Rain', 'Heavy Rain', 'Dusk', 'Night']

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
    'United Kingdom': '\U0001F1EC\U0001F1E7',
    'United States':  '\U0001F1FA\U0001F1F8',
    'Uruguay':        '\U0001F1FA\U0001F1FE',
    'Vietnam':        '\U0001F1FB\U0001F1F3',
    'Wales':          '\U0001F3F4\U000E0067\U000E0062\U000E0077\U000E006C\U000E0073\U000E007F',
}

LOCATION_SURFACE = {
    'Monaco': 'Tarmac',
    'Spain': 'Tarmac',
}

DURATION_OPTIONS = {
    '24h': ('daily', timedelta(hours=24)),
    '1week': ('weekly', timedelta(weeks=1)),
    '1month': ('monthly', timedelta(days=30)),
}


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
            'location': 'Monaco',
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
        stages = []
        for si in spec['stage_indices']:
            name, km = all_stages[si]
            stages.append({'name': name, 'distance_km': km, 'conditions': spec['conditions']})

        event = {
            'id': spec['id'],
            'name': spec['name'],
            'type': spec['type'],
            'location': spec['location'],
            'car_class': spec['car_class'],
            'surface': spec['surface'],
            'conditions': spec['conditions'],
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
    events = get_all_events()
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
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    user = get_user(username)
    if not user or not check_password(password, user):
        flash('Invalid username or password.', 'error')
        return redirect(url_for('login'))
    session['username'] = username
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
    active = [e for e in events if e.get('active')]

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


@app.route('/leaderboards')
def leaderboards() -> str | Response:
    events = get_all_events()
    event_id = request.args.get('event')
    stage_idx = request.args.get('stage', type=int)

    selected_event = None
    entries = []
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
        return redirect(url_for('leaderboards', event=events[0]['id']))

    return render_template(
        'leaderboards.html', events=events, selected_event=selected_event,
        entries=entries, leader_time=leader_time, stage_idx=stage_idx,
    )


@app.route('/clubs')
def clubs() -> str:
    all_clubs = get_all_clubs()
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
    }
    save_club(club)
    user.setdefault('clubs', []).append(cid)
    save_user(user)
    flash(f'Club "{name}" created!', 'success')
    return redirect(url_for('club_detail', club_id=cid))


@app.route('/clubs/<club_id>')
def club_detail(club_id: str) -> str:
    club = get_club(club_id)
    if not club:
        abort(404)
    members = [get_user(m) for m in club.get('members', []) if get_user(m)]
    events = [e for e in get_all_events() if e.get('club_id') == club_id]
    return render_template(
        'club_detail.html', club=club, members=members, events=events,
        stages=STAGES, car_classes=CAR_CLASSES, conditions=CONDITIONS,
    )


@app.route('/clubs/<club_id>/join', methods=['POST'])
@verified_required
def join_club(club_id: str) -> Response:
    club = get_club(club_id)
    if not club:
        abort(404)
    user = current_user()
    assert user is not None
    if user['username'] not in club['members']:
        club['members'].append(user['username'])
        save_club(club)
        user.setdefault('clubs', []).append(club_id)
        save_user(user)
        flash(f'Joined {club["name"]}!', 'success')
    return redirect(url_for('club_detail', club_id=club_id))


@app.route('/clubs/<club_id>/leave', methods=['POST'])
@verified_required
def leave_club(club_id: str) -> Response:
    club = get_club(club_id)
    if not club:
        abort(404)
    user = current_user()
    assert user is not None
    if user['username'] in club['members']:
        club['members'].remove(user['username'])
        save_club(club)
        if club_id in user.get('clubs', []):
            user['clubs'].remove(club_id)
            save_user(user)
        flash(f'Left {club["name"]}.', 'info')
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
    cond = request.form.get('conditions', '').strip()
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
    if car_class not in CAR_CLASSES:
        errors.append('Invalid vehicle class.')
    if cond not in CONDITIONS:
        errors.append('Invalid conditions.')
    if duration not in DURATION_OPTIONS:
        errors.append('Invalid duration.')
    available = len(STAGES.get(location, []))
    if num_stages < 1 or (available and num_stages > available):
        errors.append(f'Stage count must be between 1 and {available}.')

    if errors:
        for e in errors:
            flash(e, 'error')
        return redirect(url_for('club_detail', club_id=club_id))

    event_type, delta = DURATION_OPTIONS[duration]
    now = datetime.now()
    surface = LOCATION_SURFACE.get(location, 'Gravel')

    stage_list = [
        {'name': sname, 'distance_km': dist, 'conditions': cond}
        for sname, dist in STAGES[location][:num_stages]
    ]

    event = {
        'id': f'evt-{uuid.uuid4().hex[:8]}',
        'name': name,
        'type': event_type,
        'location': location,
        'car_class': car_class,
        'surface': surface,
        'conditions': cond,
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


@app.route('/events')
def events() -> str:
    t = request.args.get('type', 'daily')
    all_events = get_all_events()
    filtered = [e for e in all_events if e.get('type') == t]
    counts: dict[str, int] = {}
    for e in all_events:
        counts[e['type']] = counts.get(e['type'], 0) + 1
    return render_template('events.html', events=filtered, event_type=t, counts=counts)


@app.route('/events/<event_id>')
def event_detail(event_id: str) -> str:
    event = get_event(event_id)
    if not event:
        abort(404)
    results = get_results(event_id)
    entries = results.get('entries', [])
    club = get_club(event['club_id']) if event.get('club_id') else None
    cars = CAR_CLASSES.get(event.get('car_class', ''), [])
    return render_template('event_detail.html', event=event, entries=entries, club=club, cars=cars)


@app.route('/events/<event_id>/submit', methods=['POST'])
@verified_required
def submit_time(event_id: str) -> Response:
    event = get_event(event_id)
    if not event:
        abort(404)

    user = current_user()
    assert user is not None
    results = get_results(event_id)
    entries = results.get('entries', [])

    existing = next((e for e in entries if e['username'] == user['username']), None)
    if existing:
        flash('You have already submitted times for this event.', 'warning')
        return redirect(url_for('event_detail', event_id=event_id))

    car = request.form.get('car', '')
    stage_times = []
    total = 0
    for i, stage in enumerate(event.get('stages', [])):
        raw = request.form.get(f'stage_{i}', '0')
        try:
            parts = raw.replace(',', '.').split(':')
            if len(parts) == 2:
                mins, rest = parts
                secs_parts = rest.split('.')
                secs = int(secs_parts[0])
                millis = int(secs_parts[1].ljust(3, '0')[:3]) if len(secs_parts) > 1 else 0
                ms = int(mins) * 60000 + secs * 1000 + millis
            else:
                ms = int(float(raw) * 1000)
        except (ValueError, IndexError):
            ms = 0

        if ms <= 0:
            flash(f'Invalid time for stage {i + 1}.', 'error')
            return redirect(url_for('event_detail', event_id=event_id))

        stage_times.append({
            'time_ms': ms,
            'penalties_ms': 0,
            'submitted_at': datetime.now().isoformat(),
        })
        total += ms

    entry = {
        'username': user['username'],
        'car': car,
        'stages': stage_times,
        'total_time_ms': total,
    }
    entries.append(entry)
    entries.sort(key=lambda e: e['total_time_ms'])
    results['entries'] = entries
    save_results(event_id, results)

    pos = next(i for i, e in enumerate(entries) if e['username'] == user['username']) + 1
    flash(f'Times submitted! You placed P{pos} of {len(entries)}.', 'success')
    return redirect(url_for('event_detail', event_id=event_id))


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
                results_list.append({
                    'event': evt,
                    'entry': entry,
                    'position': pos,
                    'total_entries': len(res['entries']),
                })

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
    """Return all clubs and their active events for the game server."""
    clubs = get_all_clubs()
    events = [e for e in get_all_events() if e.get('active')]
    return jsonify({'ok': True, 'clubs': clubs, 'events': events})


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

    stage_index = int(data.get('stage_index', 0))

    results = get_results(event_id)
    # Store in_progress keyed by username -> stage_index
    in_progress = results.setdefault('in_progress', {})
    user_progress = in_progress.setdefault(username, {})
    user_progress[str(stage_index)] = {
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

    stage_index = int(data.get('stage_index', 0))
    time_ms = int(data.get('time_ms', 0))
    vehicle_id = data.get('vehicle_id')
    penalties_ms = int(data.get('penalties_ms', 0))

    results = get_results(event_id)
    entries = results.get('entries', [])

    # Pull any in_progress data stored by stage-begin for this user/stage
    in_progress_entry: dict[str, Any] = (
        results.get('in_progress', {})
        .get(username, {})
        .get(str(stage_index), {})
    )

    existing = next((e for e in entries if e['username'] == username), None)

    if existing is None:
        # New entry — pad all previous stages with 0 so indices stay consistent
        pad = [{'time_ms': 0, 'penalties_ms': 0, 'submitted_at': None}
               for _ in range(stage_index)]
        existing = {
            'username': username,
            'car': str(vehicle_id) if vehicle_id is not None else '',
            'stages': pad,
            'total_time_ms': 0,
            'vehicle_id': vehicle_id,
        }
        entries.append(existing)

    # Merge in_progress fields as defaults — explicit data takes priority
    def _pick(key: str, default: Any = None) -> Any:
        v = data.get(key)
        if v is None:
            v = in_progress_entry.get(key, default)
        return v

    stage_entry: dict[str, Any] = {
        'time_ms': time_ms,
        'penalties_ms': penalties_ms,
        'submitted_at': datetime.now().isoformat(),
        'meters_driven': int(data.get('meters_driven', 0)),
        'distance_driven': int(data.get('distance_driven', 0)),
        'using_wheel': bool(data.get('using_wheel', False)),
        'using_assists': bool(data.get('using_assists', False)),
        'race_status': int(data.get('race_status', 0)),
        'has_repaired': bool(data.get('has_repaired', False)),
        'repair_penalty_ms': int(data.get('repair_penalty_ms', 0)),
        'vehicle_id': vehicle_id if vehicle_id is not None else in_progress_entry.get('vehicle_id'),
        'livery_id': _pick('livery_id', 0),
        'nationality_id': _pick('nationality_id', 0),
        'tuning_setup_b64': _pick('tuning_setup_b64', ''),
        'tyre_compound': _pick('tyre_compound', 2),
        'tyres_remaining': _pick('tyres_remaining', 3),
        'vehicle_mud': data.get('vehicle_mud') or {},
        'comp_damage': data.get('comp_damage') or {},
    }

    # Extend or replace at the right index
    while len(existing['stages']) <= stage_index:
        existing['stages'].append({'time_ms': 0, 'penalties_ms': 0, 'submitted_at': None})
    existing['stages'][stage_index] = stage_entry

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
    out = []
    for i, e in enumerate(entries):
        out.append({
            'rank': i + 1,
            'username': e['username'],
            'car': e.get('car', ''),
            'vehicle_id': e.get('vehicle_id'),
            'total_time_ms': e['total_time_ms'],
            'stages': e.get('stages', []),
        })
    return jsonify({'ok': True, 'entries': out})


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


# ── Time Trial API endpoints ──────────────────────────────

@app.route('/api/game/time-trial-submit', methods=['POST'])
@csrf.exempt  # type: ignore[untyped-decorator]
@game_auth_required
def api_game_time_trial_submit() -> Response | tuple[Response, int]:
    """Accept a time trial result from the game server and persist it."""
    data = request.get_json(silent=True) or {}

    try:
        vclass = str(int(data['vehicle_class_id']))
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
    """Return time trial leaderboard entries for a given 4-tuple."""
    try:
        vclass = str(int(request.args['vclass']))
        track = str(int(request.args['track']))
        conditions = str(int(request.args['conditions']))
        category = str(int(request.args['category']))
    except (KeyError, TypeError, ValueError) as exc:
        return _api_error(f'invalid query params: {exc}')

    key = _tt_key(vclass, track, conditions, category)
    entries = _load_tt(key)

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
