"""
Auto-generation of daily/weekly/monthly official events.

Inspired by DR2 RaceNet: three concurrent variants per period (Standard /
Bonus / D+ in the original). Each variant rolls a distinct random location
and car class so the 3 events in a period always differ.

Idempotency: every generated event carries a stable ``slot_id`` (e.g.
``daily-2026-04-10-v1``). The cron tick is safe to re-invoke — late, twice,
or after a crash — because matching ``slot_id``s are skipped. The RNG is
seeded off the ``slot_id`` itself, so an event recreated on a later tick
has the same content as the original roll.

All times are naive UTC, matching the rest of the codebase's datetime usage.
"""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta
from typing import Any

from server import (
    save_event,
    get_all_events,
    STAGES,
    CAR_CLASSES,
    CONDITIONS,
    LOCATION_SURFACE,
)

VARIANTS = 3                 # mirrors DR2 Standard / Bonus / D+
DAILY_RESET_HOUR_UTC = 10    # matches DR2 RaceNet's global reset at 10:00 UTC

# Daily = one quick stage, weekly = mini-rally, monthly = full rally (all stages).
STAGES_PER_TYPE = {'daily': 1, 'weekly': 3}


def _day_anchor(now: datetime) -> datetime:
    today_reset = now.replace(hour=DAILY_RESET_HOUR_UTC, minute=0, second=0, microsecond=0)
    if now < today_reset:
        return today_reset - timedelta(days=1)
    return today_reset


def _week_anchor(now: datetime) -> datetime:
    day_anchor = _day_anchor(now)
    return day_anchor - timedelta(days=day_anchor.weekday())


def _month_anchor(now: datetime) -> datetime:
    first = now.replace(day=1, hour=DAILY_RESET_HOUR_UTC,
                        minute=0, second=0, microsecond=0)
    if now < first:
        # now is between 00:00 and 10:00 on the 1st — roll back to previous month.
        prev_last_day = first - timedelta(days=1)
        first = prev_last_day.replace(day=1, hour=DAILY_RESET_HOUR_UTC,
                                      minute=0, second=0, microsecond=0)
    return first


def _next_month(start: datetime) -> datetime:
    if start.month == 12:
        return start.replace(year=start.year + 1, month=1)
    return start.replace(month=start.month + 1)


def current_slots(now: datetime) -> list[tuple[str, str, datetime, datetime]]:
    """Return ``(event_type, slot_base, start, end)`` for the 3 active periods.

    ``slot_base`` is the prefix; the variant index is appended later.
    """
    daily_start = _day_anchor(now)
    daily_end = daily_start + timedelta(days=1)
    daily_base = f"daily-{daily_start.strftime('%Y-%m-%d')}"

    weekly_start = _week_anchor(now)
    weekly_end = weekly_start + timedelta(days=7)
    iso_year, iso_week, _ = weekly_start.isocalendar()
    weekly_base = f"weekly-{iso_year}-W{iso_week:02d}"

    monthly_start = _month_anchor(now)
    monthly_end = _next_month(monthly_start)
    monthly_base = f"monthly-{monthly_start.strftime('%Y-%m')}"

    return [
        ('daily',   daily_base,   daily_start,   daily_end),
        ('weekly',  weekly_base,  weekly_start,  weekly_end),
        ('monthly', monthly_base, monthly_start, monthly_end),
    ]


def _rng_for(slot_id: str) -> random.Random:
    seed = int(hashlib.md5(slot_id.encode()).hexdigest(), 16)
    return random.Random(seed)


def _event_id_for(slot_id: str) -> str:
    return f"evt-{hashlib.md5(slot_id.encode()).hexdigest()[:8]}"


def _name_for(event_type: str, location: str, variant_index: int,
              start: datetime) -> str:
    if event_type == 'daily':
        return f"Daily #{variant_index} {location} {start:%b %d}"
    if event_type == 'weekly':
        _, iso_week, _ = start.isocalendar()
        return f"Weekly #{variant_index} {location} W{iso_week:02d}"
    return f"Monthly #{variant_index} {location} {start:%b %Y}"


def generate_event(
    event_type: str,
    slot_id: str,
    start: datetime,
    end: datetime,
    variant_index: int,
    used_locations: set[str],
    used_classes: set[str],
) -> dict[str, Any]:
    """Deterministically roll an event dict for ``slot_id``.

    Filters locations/classes already taken by earlier variants of the same
    period so the 3 concurrent events always differ.
    """
    rng = _rng_for(slot_id)

    loc_pool = sorted(l for l in STAGES if l not in used_locations)
    cls_pool = sorted(c for c in CAR_CLASSES if c not in used_classes)
    location = rng.choice(loc_pool)
    car_class = rng.choice(cls_pool)
    conditions = rng.choice(CONDITIONS)
    surface = LOCATION_SURFACE.get(location, 'Gravel')

    location_stages = STAGES[location]
    if event_type == 'monthly':
        picked = list(location_stages)
    else:
        k = min(STAGES_PER_TYPE[event_type], len(location_stages))
        picked = rng.sample(location_stages, k)

    stage_list = [
        {'name': name, 'distance_km': dist, 'conditions': conditions}
        for name, dist in picked
    ]

    return {
        'id': _event_id_for(slot_id),
        'name': _name_for(event_type, location, variant_index, start),
        'type': event_type,
        'location': location,
        'car_class': car_class,
        'surface': surface,
        'conditions': conditions,
        'stages': stage_list,
        'start_time': start.isoformat(),
        'end_time': end.isoformat(),
        'active': True,
        'featured': False,
        'club_id': None,
        'system': True,
        'slot_id': slot_id,
    }


def deactivate_expired(now: datetime) -> list[str]:
    expired: list[str] = []
    for e in get_all_events():
        if not e.get('system') or not e.get('active'):
            continue
        try:
            end = datetime.fromisoformat(e['end_time'])
        except (KeyError, ValueError):
            continue
        if end <= now:
            e['active'] = False
            save_event(e)
            expired.append(e['id'])
    return expired


def run_cron_tick(now: datetime) -> dict[str, Any]:
    """Top-level entrypoint: expire old events, create missing slots.

    Safe to run off-schedule — matching ``slot_id`` collisions are skipped.
    """
    expired = deactivate_expired(now)

    existing_by_slot: dict[str, dict[str, Any]] = {
        e['slot_id']: e for e in get_all_events()
        if e.get('system') and e.get('slot_id')
    }

    created: list[str] = []
    for event_type, slot_base, start, end in current_slots(now):
        used_locs: set[str] = set()
        used_classes: set[str] = set()
        for v in range(1, VARIANTS + 1):
            slot_id = f'{slot_base}-v{v}'
            existing = existing_by_slot.get(slot_id)
            if existing is not None:
                used_locs.add(existing['location'])
                used_classes.add(existing['car_class'])
                continue
            ev = generate_event(
                event_type, slot_id, start, end, v,
                used_locs, used_classes,
            )
            save_event(ev)
            used_locs.add(ev['location'])
            used_classes.add(ev['car_class'])
            created.append(ev['id'])

    return {'created': created, 'expired': expired}
