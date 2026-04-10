import os
import re
import json
import fcntl
import hashlib
import hmac
import logging
import secrets
import smtplib
import uuid
import random
from datetime import datetime, timedelta
from email.message import EmailMessage
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, abort, jsonify,
)
from flask_wtf.csrf import CSRFProtect

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
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

app.logger.setLevel(logging.DEBUG)

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.path.join(BASE, 'data')
USERS_DIR  = os.path.join(DATA_DIR, 'users')
CLUBS_DIR  = os.path.join(DATA_DIR, 'clubs')
EVENTS_DIR = os.path.join(DATA_DIR, 'events')
RESULTS_DIR = os.path.join(DATA_DIR, 'results')

for d in (USERS_DIR, CLUBS_DIR, EVENTS_DIR, RESULTS_DIR):
    os.makedirs(d, exist_ok=True)


# ── ID validation ───────────────────────────────────────

_SAFE_ID_RE = re.compile(r'^[a-zA-Z0-9_-]+$')


def _validate_id(value):
    if not value or not _SAFE_ID_RE.match(value):
        abort(400)
    return value


# ── File helpers ─────────────────────────────────────────

def _load(path):
    with open(path) as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        try:
            return json.load(f)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _save(path, data):
    with open(path, 'w') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            json.dump(data, f, indent=2)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _list_json(directory):
    out = []
    if os.path.isdir(directory):
        for fn in sorted(os.listdir(directory)):
            if fn.endswith('.json'):
                out.append(_load(os.path.join(directory, fn)))
    return out


# ── User ops ─────────────────────────────────────────────

def get_user(username):
    _validate_id(username)
    p = os.path.join(USERS_DIR, f'{username}.json')
    return _load(p) if os.path.exists(p) else None


def save_user(u):
    _validate_id(u['username'])
    _save(os.path.join(USERS_DIR, f"{u['username']}.json"), u)


def get_all_users():
    return _list_json(USERS_DIR)


def create_user(username, email, password, display_name=None, country='', bio='',
                email_verified=False):
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


def check_password(password, user):
    salt = bytes.fromhex(user['salt'])
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 120_000)
    return hmac.compare_digest(dk.hex(), user['password_hash'])


# ── Email ───────────────────────────────────────────────

def _send_email(to, subject, body):
    app.logger.info('Sending email to=%s subject=%r host=%s port=%s',
                    to, subject, SMTP_HOST or '(not set)', SMTP_PORT)
    if not SMTP_HOST:
        app.logger.warning('EMAIL_HOST not configured — email not sent')
        return False
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = MAIL_FROM
    msg['To'] = to
    msg.set_content(body)
    try:
        app.logger.debug('Connecting to %s:%s (TLS=%s)', SMTP_HOST, SMTP_PORT, SMTP_USE_TLS)
        if SMTP_USE_TLS:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
            server.starttls()
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
        if SMTP_USER:
            app.logger.debug('Authenticating as %s', SMTP_USER)
            server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        app.logger.info('Email sent to %s', to)
        return True
    except Exception:
        app.logger.exception('Failed to send email to %s', to)
        return False


def send_verification_email(user):
    app.logger.info('Sending verification email to user=%s email=%s',
                    user['username'], user['email'])
    link = f'{SITE_URL}/verify/{user["verify_token"]}'
    body = (
        f'Hi {user["display_name"]},\n\n'
        f'Welcome to DirtForever! Please verify your email address by visiting:\n\n'
        f'{link}\n\n'
        f'If you did not create this account, ignore this email.\n\n'
        f'— DirtForever'
    )
    return _send_email(user['email'], 'Verify your DirtForever account', body)


def send_reset_email(user):
    app.logger.info('Sending password reset email to user=%s email=%s',
                    user['username'], user['email'])
    link = f'{SITE_URL}/reset/{user["reset_token"]}'
    body = (
        f'Hi {user["display_name"]},\n\n'
        f'We received a request to reset your DirtForever password. '
        f'Visit the link below to choose a new password:\n\n'
        f'{link}\n\n'
        f'This link expires in 1 hour. If you did not request this, ignore this email.\n\n'
        f'— DirtForever'
    )
    return _send_email(user['email'], 'Reset your DirtForever password', body)


# ── Club ops ─────────────────────────────────────────────

def get_club(cid):
    _validate_id(cid)
    p = os.path.join(CLUBS_DIR, f'{cid}.json')
    return _load(p) if os.path.exists(p) else None


def save_club(c):
    _validate_id(c['id'])
    _save(os.path.join(CLUBS_DIR, f"{c['id']}.json"), c)


def get_all_clubs():
    return _list_json(CLUBS_DIR)


# ── Event ops ────────────────────────────────────────────

def get_event(eid):
    _validate_id(eid)
    p = os.path.join(EVENTS_DIR, f'{eid}.json')
    return _load(p) if os.path.exists(p) else None


def save_event(e):
    _validate_id(e['id'])
    _save(os.path.join(EVENTS_DIR, f"{e['id']}.json"), e)


def get_all_events():
    return _list_json(EVENTS_DIR)


def get_events_by_type(t):
    return [e for e in get_all_events() if e.get('type') == t]


# ── Result ops ───────────────────────────────────────────

def get_results(eid):
    _validate_id(eid)
    p = os.path.join(RESULTS_DIR, f'{eid}.json')
    if os.path.exists(p):
        return _load(p)
    return {'event_id': eid, 'entries': []}


def save_results(eid, data):
    _validate_id(eid)
    _save(os.path.join(RESULTS_DIR, f'{eid}.json'), data)


# ── Auth decorator ───────────────────────────────────────

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'username' not in session:
            flash('Please sign in to continue.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper


def verified_required(f):
    @wraps(f)
    @login_required
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or not user.get('email_verified'):
            flash('Please verify your email address first.', 'warning')
            return redirect(url_for('verify_prompt'))
        return f(*args, **kwargs)
    return wrapper


def current_user():
    if 'username' in session:
        return get_user(session['username'])
    return None


# ── Context & filters ────────────────────────────────────

@app.context_processor
def inject_globals():
    return dict(current_user=current_user())


@app.template_filter('rally_time')
def rally_time_filter(ms):
    if ms is None:
        return '--:--.---'
    ms = int(ms)
    minutes = ms // 60000
    seconds = (ms % 60000) // 1000
    millis = ms % 1000
    return f'{minutes:02d}:{seconds:02d}.{millis:03d}'


@app.template_filter('time_diff')
def time_diff_filter(ms):
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
def timeago_filter(dt_str):
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
def countdown_filter(dt_str):
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


def _seed_users():
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


def _seed_clubs(users):
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


def _gen_time(base_km, rng):
    """Generate a plausible stage time in ms given stage length in km."""
    pace = rng.uniform(5.8, 7.5)  # minutes per km
    base_ms = int(base_km * pace * 60 * 1000)
    variance = rng.uniform(-0.04, 0.08)
    return int(base_ms * (1 + variance))


def _seed_events_and_results(users):
    rng = random.Random(42)
    now = datetime.now()
    usernames = [u['username'] for u in users]

    events_spec = [
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


def seed_data():
    if os.listdir(USERS_DIR):
        return
    users = _seed_users()
    _seed_clubs(users)
    _seed_events_and_results(users)


# ── Routes: pages ────────────────────────────────────────

@app.route('/')
def home():
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
def login():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def login_post():
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
def register():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('register.html')


@app.route('/register', methods=['POST'])
def register_post():
    if request.form.get('website', ''):
        return redirect(url_for('home'))

    username = request.form.get('username', '').strip()
    email    = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    confirm  = request.form.get('confirm', '')

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

    user = create_user(username, email, password)
    send_verification_email(user)
    session['username'] = username
    flash('Account created! Check your email to verify your address.', 'success')
    return redirect(url_for('verify_prompt'))


@app.route('/verify/resend', methods=['POST'])
@login_required
def resend_verification():
    user = current_user()
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
def verify_prompt():
    user = current_user()
    if user.get('email_verified'):
        return redirect(url_for('dashboard'))
    return render_template('verify_email.html', user=user)


@app.route('/verify/<token>')
def verify_email(token):
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
def forgot_password():
    return render_template('forgot_password.html')


@app.route('/forgot', methods=['POST'])
def forgot_password_post():
    email = request.form.get('email', '').strip()
    if not email:
        flash('Please enter your email address.', 'error')
        return redirect(url_for('forgot_password'))

    user = next((u for u in get_all_users() if u.get('email') == email), None)
    # Always show the same message to prevent email enumeration
    flash('If an account with that email exists, we sent a password reset link.', 'info')
    if not user:
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
def reset_password(token):
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
def reset_password_post(token):
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
def logout():
    session.pop('username', None)
    flash('Signed out.', 'info')
    return redirect(url_for('home'))


@app.route('/dashboard')
@login_required
def dashboard():
    user = current_user()
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

    return render_template(
        'dashboard.html', user=user, my_clubs=my_clubs,
        active_events=active, my_results=my_results[:10],
    )


@app.route('/leaderboards')
def leaderboards():
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
def clubs():
    all_clubs = get_all_clubs()
    query = request.args.get('q', '').strip()
    if query:
        q = query.lower()
        all_clubs = [c for c in all_clubs if q in c['name'].lower() or q in c.get('description', '').lower()]
    return render_template('clubs.html', clubs=all_clubs, query=query)


@app.route('/clubs', methods=['POST'])
@verified_required
def create_club():
    name = request.form.get('name', '').strip()
    desc = request.form.get('description', '').strip()
    if not name:
        flash('Club name is required.', 'error')
        return redirect(url_for('clubs'))
    if len(name) > 40:
        flash('Club name must be under 40 characters.', 'error')
        return redirect(url_for('clubs'))

    user = current_user()
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
def club_detail(club_id):
    club = get_club(club_id)
    if not club:
        abort(404)
    members = [get_user(m) for m in club.get('members', []) if get_user(m)]
    events = [e for e in get_all_events() if e.get('club_id') == club_id]
    return render_template('club_detail.html', club=club, members=members, events=events)


@app.route('/clubs/<club_id>/join', methods=['POST'])
@verified_required
def join_club(club_id):
    club = get_club(club_id)
    if not club:
        abort(404)
    user = current_user()
    if user['username'] not in club['members']:
        club['members'].append(user['username'])
        save_club(club)
        user.setdefault('clubs', []).append(club_id)
        save_user(user)
        flash(f'Joined {club["name"]}!', 'success')
    return redirect(url_for('club_detail', club_id=club_id))


@app.route('/clubs/<club_id>/leave', methods=['POST'])
@verified_required
def leave_club(club_id):
    club = get_club(club_id)
    if not club:
        abort(404)
    user = current_user()
    if user['username'] in club['members']:
        club['members'].remove(user['username'])
        save_club(club)
        if club_id in user.get('clubs', []):
            user['clubs'].remove(club_id)
            save_user(user)
        flash(f'Left {club["name"]}.', 'info')
    return redirect(url_for('club_detail', club_id=club_id))


@app.route('/events')
def events():
    t = request.args.get('type', 'daily')
    all_events = get_all_events()
    filtered = [e for e in all_events if e.get('type') == t]
    counts = {}
    for e in all_events:
        counts[e['type']] = counts.get(e['type'], 0) + 1
    return render_template('events.html', events=filtered, event_type=t, counts=counts)


@app.route('/events/<event_id>')
def event_detail(event_id):
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
def submit_time(event_id):
    event = get_event(event_id)
    if not event:
        abort(404)

    user = current_user()
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
def profile(username):
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


# ── Error pages ──────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template('base.html', error='Page not found'), 404


# ── Game API ─────────────────────────────────────────────
# Called by the local game server (dr2server) to sync data.
# No CSRF tokens — the game server is a trusted backend process.


def _api_error(msg, status=400):
    return jsonify({'ok': False, 'error': msg}), status


@app.route('/api/game/clubs')
@csrf.exempt
def api_game_clubs():
    """Return all clubs and their active events for the game server."""
    clubs = get_all_clubs()
    events = [e for e in get_all_events() if e.get('active')]
    return jsonify({'ok': True, 'clubs': clubs, 'events': events})


@app.route('/api/game/stage-complete', methods=['POST'])
@csrf.exempt
def api_game_stage_complete():
    """Accept a completed stage submission from the game server."""
    data = request.get_json(silent=True) or {}
    event_id = data.get('event_id', '').strip()
    username = data.get('username', '').strip()
    if not event_id or not username:
        return _api_error('event_id and username are required')

    try:
        _validate_id(event_id)
        _validate_id(username)
    except Exception:
        return _api_error('invalid event_id or username')

    event = get_event(event_id)
    if not event:
        return _api_error('event not found', 404)

    stage_index = int(data.get('stage_index', 0))
    time_ms = int(data.get('time_ms', 0))
    vehicle_id = data.get('vehicle_id')
    penalties_ms = int(data.get('penalties_ms', 0))

    results = get_results(event_id)
    entries = results.get('entries', [])

    existing = next((e for e in entries if e['username'] == username), None)
    stages = event.get('stages', [])

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

    stage_entry = {
        'time_ms': time_ms,
        'penalties_ms': penalties_ms,
        'submitted_at': datetime.now().isoformat(),
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


@app.route('/api/game/leaderboard/<event_id>')
@csrf.exempt
def api_game_leaderboard(event_id):
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
@csrf.exempt
def api_game_event(event_id):
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
@csrf.exempt
def api_game_auth():
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


# ── Main ─────────────────────────────────────────────────

if __name__ == '__main__':
    seed_data()
    app.run(host='0.0.0.0', port=5001, debug=True)
