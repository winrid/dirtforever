"""My Team career ladder (Career Rally / Career Rallycross).

The game keeps a mirror of its career championship in the local save and,
every time the My Team screen opens, fetches the server copy with
``RaceNetCareerLadder.Get{Rally,Rallycross}Championship`` and compares
``Championship`` and ``Progress`` (EventIndex / StageIndex / State).  Any
disagreement shows "CHAMPIONSHIP RESET ... discrepancy between local and
server save data" and the client calls ``Reset*Championship``.  So the
server is the source of truth and has to follow the client's own
ChampionshipBegin / StageBegin / StageComplete calls exactly.

This module holds all of that logic with no I/O: a compact JSON "spec"
describing a championship (locations, tracks, conditions, service areas),
a builder turning a spec into a :class:`models.Challenge`, the Progress
wire shape, the tier list, and the :class:`CareerLadder` state machine.
Persistence is injected as ``load`` / ``save`` callables (the dispatcher
wires them to the dirtforever.net ``/api/game/career`` endpoint).

Wire shapes are taken from the captured upstream templates in
``data/upstream_templates/RaceNetCareerLadder_*.bin``; see
``tests/test_career_ladder.py`` which pins the generated output against
those bytes.  The semantics that are still inferred (Progress.State 5,
between-event progress, tier promotion ranks) are marked ASSUMPTION and
tracked in GitHub issue #69.
"""
from __future__ import annotations

import dataclasses
import random
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .egonet import Int64, UInt32, decode_stream
from .game_data import (
    RX_DRYING_TIME, RX_NUMBER_RESTARTS, RX_SVC_SETTINGS_ID,
    get_rally_locations, get_rallycross_locations, get_tracks_for_location,
    rallycross_stage_plan, stage_conditions_for_location,
)
from .models import (
    Challenge, EntryWindow, Event, Item, Reward, Stage, StageBeginRequest,
    StageCompleteRequest, TierReward, _val, damage_to_egonet, zero_reward,
)

DISCIPLINES = ("rally", "rallycross")
SCHEMA_VERSION = 1

# Progress.State values.  0/1/2 are the ones the club-event flow uses; 5 is
# what every fresh career template carries.
STATE_BETWEEN_STAGES = 0
STATE_STAGE_ACTIVE = 1
STATE_EVENT_FINISHED = 2
STATE_NOT_STARTED = 5  # ASSUMPTION (A5): "championship not begun"

# ASSUMPTION (A6): after the last stage of a non-final event the server keeps
# the finished event's index with State 2 (the club flow's shape).  Flip to
# True to report the next event's first stage with State 0 instead.
ADVANCE_EVENT_ON_COMPLETE = False

# ASSUMPTION (A7): five tiers (150 rally drivers / 30 entrants, 100 RX drivers
# / 20 entrants), promotion for a podium, relegation for the bottom three.
TIER_COUNT = 5
MAX_TIER = TIER_COUNT - 1
PROMOTE_MAX_RANK = 3
RELEGATE_BOTTOM_N = 3
# Credits grow per tier so a promotion is visible in the Reward block.
CREDIT_TIER_STEP = 0.15

ENTRY_WINDOW_SECONDS = 2 * 365 * 24 * 3600
HISTORY_CAP = 20

RALLY_SVC_SETTINGS_ID = 3
# DryingTime per rally location as seen in the upstream templates.  The
# field is cosmetic (how fast a wet stage dries); unseen locations use the
# default.
RALLY_DRYING_TIME: Dict[int, int] = {
    36: 120, 34: 120, 14: 720, 3: 360, 37: 90, 17: 300, 5: 180, 13: 210,
    46: 360, 2: 120,
}
RALLY_DRYING_DEFAULT = 180

_DISC_CFG: Dict[str, Dict[str, Any]] = {
    "rally": {
        "discipline_id": 1,
        "events": 6,
        "stages": 4,
        "entrants": 30,
        "difficulty": 50,
        "max_event_credits": 62700,
        "tier_rewards": ((259500, 280600, 10), (231500, 252500, 35),
                         (203400, 224500, 75), (175400, 196400, 100)),
        "fresh_tyres": 1,
    },
    "rallycross": {
        "discipline_id": 2,
        "events": 3,
        "stages": 6,
        "entrants": 20,
        "difficulty": 0,
        "max_event_credits": 47600,
        "tier_rewards": ((123200, 133200, 10), (109900, 119900, 35),
                         (96600, 106600, 75), (83300, 93300, 100)),
        "fresh_tyres": 5,
    },
}
FRESH_ATTEMPTS = 1

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "data" / "upstream_templates"
_TIER_TEMPLATES = {
    "rally": "RaceNetCareerLadder_GetRallyTierList.bin",
    "rallycross": "RaceNetCareerLadder_GetRallycrossTierList.bin",
}
_tier_cache: Dict[str, List[int]] = {}


def _check_discipline(discipline: str) -> str:
    if discipline not in _DISC_CFG:
        raise ValueError(f"unknown career discipline: {discipline!r}")
    return discipline


# ---------------------------------------------------------------------------
# Championship spec: generate / build / inverse
# ---------------------------------------------------------------------------

def _scale_credits(value: int, tier: int) -> int:
    return int(round(value * (1.0 + CREDIT_TIER_STEP * tier) / 100.0)) * 100


def _rally_location_pool() -> List[int]:
    """Rally locations with enough verified routes and a conditions sweep.

    Drops Twin Peaks (no verified routes, no conditions) and anything else
    that could not fill an event with distinct verified stages.
    """
    need = _DISC_CFG["rally"]["stages"]
    return [
        loc for loc in get_rally_locations()
        if len(get_tracks_for_location(loc)) >= need and stage_conditions_for_location(loc)
    ]


def _rx_location_pool() -> List[int]:
    return [
        loc for loc in get_rallycross_locations()
        if get_tracks_for_location(loc) and stage_conditions_for_location(loc)
    ]


def generate_spec(
    discipline: str,
    tier: int = 0,
    rng: Optional[random.Random] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Random fresh championship for ``discipline`` at ``tier``.

    Rally: 6 events on distinct locations, 4 distinct verified routes each,
    a verified condition per stage, service area on the odd stages.
    Rallycross: 3 events on distinct circuits, 6 lapped stages each (four
    heats, semi, final), one condition per event.
    """
    _check_discipline(discipline)
    cfg = _DISC_CFG[discipline]
    rng = rng or random.Random()
    now = time.time() if now is None else now
    tier = max(0, min(MAX_TIER, int(tier)))
    seed = rng.getrandbits(32)
    pick = random.Random(seed)

    events: List[Dict[str, Any]] = []
    if discipline == "rally":
        for loc in pick.sample(_rally_location_pool(), cfg["events"]):
            tracks = pick.sample(get_tracks_for_location(loc), cfg["stages"])
            conds = stage_conditions_for_location(loc)
            stages = []
            for j, track in enumerate(tracks):
                service = (j % 2 == 0)
                stages.append({
                    "track_id": int(track),
                    "conditions_id": int(pick.choice(conds)),
                    "service_area": service,
                    "svc_settings_id": RALLY_SVC_SETTINGS_ID if service else 0,
                    "drying_time": RALLY_DRYING_TIME.get(int(loc), RALLY_DRYING_DEFAULT),
                    "stage_type": 0,
                    "laps": 0,
                })
            events.append({"location_id": int(loc), "stages": stages})
    else:
        plan = rallycross_stage_plan(cfg["stages"])
        for loc in pick.sample(_rx_location_pool(), cfg["events"]):
            track = get_tracks_for_location(loc)[0]
            cond = pick.choice(stage_conditions_for_location(loc))
            stages = [{
                "track_id": int(track),
                "conditions_id": int(cond),
                "service_area": True,
                "svc_settings_id": RX_SVC_SETTINGS_ID,
                "drying_time": RX_DRYING_TIME,
                "stage_type": stage_type,
                "laps": laps,
            } for stage_type, laps in plan]
            events.append({"location_id": int(loc), "stages": stages})

    return {
        "version": SCHEMA_VERSION,
        "discipline": discipline,
        "seed": seed,
        "generated_at": int(now),
        "entry_window_end": int(now) + ENTRY_WINDOW_SECONDS,
        "max_event_credits": _scale_credits(cfg["max_event_credits"], tier),
        "tier_rewards": [
            [_scale_credits(lo, tier), _scale_credits(hi, tier), pct]
            for lo, hi, pct in cfg["tier_rewards"]
        ],
        "events": events,
    }


def spec_from_championship(championship: Dict[str, Any], discipline: str) -> Dict[str, Any]:
    """Inverse of :func:`build_championship` over a decoded wire dict.

    Used to prove the builder reproduces the upstream templates byte for
    byte, and to ingest captured championships later.
    """
    _check_discipline(discipline)
    events = []
    for ev in championship["Events"]:
        stages = []
        for st in ev["Stages"]:
            stages.append({
                "track_id": int(_val(st["TrackModelId"])),
                "conditions_id": int(_val(st["StageConditions"])),
                "service_area": bool(st["HasServiceArea"]),
                "svc_settings_id": int(_val(st["SvcSettingsId"])),
                "drying_time": int(st["DryingTime"]),
                "stage_type": int(st["StageType"]),
                "laps": int(st["NumberLaps"]),
            })
        events.append({"location_id": int(_val(ev["LocationId"])), "stages": stages})
    return {
        "version": SCHEMA_VERSION,
        "discipline": discipline,
        "seed": 0,
        "generated_at": 0,
        "entry_window_end": int(_val(championship["EntryWindow"]["End"])),
        "max_event_credits": int(championship["MaxEventCredits"]),
        "tier_rewards": [
            [int(t["MinSoftCurrency"]), int(t["MaxSoftCurrency"]), int(t["PercentLimit"])]
            for t in championship["Reward"]["TierRewards"]
        ],
        "events": events,
    }


def build_championship(spec: Dict[str, Any]) -> Challenge:
    """Turn a spec into the Challenge the game expects for a career ladder."""
    discipline = _check_discipline(spec["discipline"])
    cfg = _DISC_CFG[discipline]
    is_rx = discipline == "rallycross"
    events: List[Event] = []
    for i, ev in enumerate(spec["events"]):
        stages: List[Stage] = []
        for j, st in enumerate(ev["stages"]):
            stages.append(Stage(
                # RX career stages are numbered 1..6 on the wire; rally 0..3.
                stage_id=j + 1 if is_rx else j,
                track_model_id=int(st["track_id"]),
                has_service_area=bool(st["service_area"]),
                number_practises=0,
                stage_conditions=int(st["conditions_id"]),
                weather_preset_id=1,
                time_of_day_id=4,
                surface_cond_id=1,
                surface_degrad=0.0,
                ambient_temp=0.0,
                track_temp=0.0,
                drying_time=int(st["drying_time"]),
                stage_type=int(st["stage_type"]),
                number_laps=int(st["laps"]),
                leaderboard_id=0,
                delta_time=0.0,
                svc_settings_id=int(st["svc_settings_id"]),
            ))
        events.append(Event(
            event_id=i,
            location_id=int(ev["location_id"]),
            discipline_id=cfg["discipline_id"],
            number_restarts=RX_NUMBER_RESTARTS,
            number_entrants=cfg["entrants"],
            number_classes=1,
            leaderboard_id=0,
            stages=stages,
        ))
    end = int(spec["entry_window_end"])
    return Challenge(
        name="",
        challenge_type=1,
        scoring_type=0,
        challenge_id=0,
        club_id=0,
        requirements=[],
        events=events,
        num_entrants=cfg["entrants"],
        difficulty_level=cfg["difficulty"],
        entry_window=EntryWindow(visible=0, start=0, last_entry=end, end=end),
        state=0,
        reward=Reward(
            soft_currency=0,
            tier_rewards=[
                TierReward(min_soft_currency=int(lo), max_soft_currency=int(hi),
                           percent_limit=int(pct), barrier_time=0.0, item=Item())
                for lo, hi, pct in spec["tier_rewards"]
            ],
        ),
        min_event_credits=0,
        max_event_credits=int(spec["max_event_credits"]),
        leaderboard_id=0,
        is_hardcore=False,
        exterior_cams=False,
        allow_assists=False,
        unxpectd_moments=False,
        dirt_plus_season=0,
        is_promo=False,
        category=0,
        mode=0,
        use_inv_vehicle=False,
        esports_month_id=0,
        attempts_allowed=0,
    )


def spec_bounds(spec: Dict[str, Any]) -> tuple[int, int]:
    """(event count, stages per event) of a spec."""
    events = spec.get("events") or []
    stages = len(events[0]["stages"]) if events else 0
    return len(events), stages


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------

def fresh_progress(discipline: str) -> Dict[str, Any]:
    """Stored-shape Progress of a championship nobody has started."""
    _check_discipline(discipline)
    return {
        "event_index": 0,
        "stage_index": 0,
        "state": STATE_NOT_STARTED,
        "stage_time_ms": 0,
        "vehicle_inst_id": 0,
        "vehicle_id": 0,
        "livery_id": 0,
        "meters_driven": 0,
        "percentile": 0,
        "champ_time_ms": 0,
        "has_repaired": False,
        "repair_penalty_ms": 0,
        "vehicle_damage": {},
        "tyre_compound": 0,
        "tyres_remaining": _DISC_CFG[discipline]["fresh_tyres"],
        "attempts_left": FRESH_ATTEMPTS,
        "last_completed": None,
    }


def progress_to_egonet(p: Dict[str, Any]) -> Dict[str, Any]:
    """Career Progress in the exact upstream wire order and types.

    Unlike the club-event Progress this carries no TuningSetup and no
    VehicleMud (the templates have neither).
    """
    return {
        "ChallengeID":   0,
        "EventIndex":    int(p.get("event_index", 0)),
        "StageIndex":    int(p.get("stage_index", 0)),
        "State":         int(p.get("state", STATE_NOT_STARTED)),
        "StageTimeMs":   UInt32(int(p.get("stage_time_ms", 0))),
        "VehicleInstId": Int64(int(p.get("vehicle_inst_id", 0))),
        "VehicleId":     UInt32(int(p.get("vehicle_id", 0))),
        "LiveryId":      UInt32(int(p.get("livery_id", 0))),
        "MetersDriven":  int(p.get("meters_driven", 0)),
        "Percentile":    int(p.get("percentile", 0)),
        "ChampTimeMs":   UInt32(int(p.get("champ_time_ms", 0))),
        "HasRepaired":   bool(p.get("has_repaired", False)),
        "RepairPenalty": UInt32(int(p.get("repair_penalty_ms", 0))),
        "VehicleDamage": damage_to_egonet(p.get("vehicle_damage")),
        "TyreCompound":  UInt32(int(p.get("tyre_compound", 0))),
        "TyresRemaining": UInt32(int(p.get("tyres_remaining", 0))),
        "AttemptsLeft":  int(p.get("attempts_left", 0)),
    }


# ---------------------------------------------------------------------------
# Tier list
# ---------------------------------------------------------------------------

def tier_driver_ids(discipline: str) -> List[int]:
    """The AI DriverIDs of the ladder, in the order the real server sent them."""
    _check_discipline(discipline)
    ids = _tier_cache.get(discipline)
    if ids is None:
        raw = (_TEMPLATE_DIR / _TIER_TEMPLATES[discipline]).read_bytes()
        decoded = decode_stream(raw)
        ids = [int(_val(row["DriverID"])) for row in decoded["TierList"]["TierList"]]
        _tier_cache[discipline] = ids
    return list(ids)


def tier_list_to_egonet(discipline: str, tier: int, prev_tier: int) -> Dict[str, Any]:
    return {
        "TierList": [{"DriverID": UInt32(i)} for i in tier_driver_ids(discipline)],
        "PrevPlayerTier": int(prev_tier),
        "PlayerTier": int(tier),
    }


# ---------------------------------------------------------------------------
# Stored state
# ---------------------------------------------------------------------------

def new_state(
    discipline: str,
    tier: int = 0,
    prev_tier: int = 0,
    rng: Optional[random.Random] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    _check_discipline(discipline)
    return {
        "version": SCHEMA_VERSION,
        "discipline": discipline,
        "tier": int(tier),
        "prev_tier": int(prev_tier),
        "is_new_champ": False,
        "spec": generate_spec(discipline, tier, rng, now),
        "progress": fresh_progress(discipline),
        "history": [],
    }


_STAGE_KEYS = ("track_id", "conditions_id", "service_area", "svc_settings_id",
               "drying_time", "stage_type", "laps")


def validate_state(obj: Any, discipline: str) -> bool:
    """True when ``obj`` is a usable stored state for ``discipline``."""
    if not isinstance(obj, dict) or obj.get("version") != SCHEMA_VERSION:
        return False
    if obj.get("discipline") != discipline:
        return False
    spec = obj.get("spec")
    progress = obj.get("progress")
    if not isinstance(spec, dict) or not isinstance(progress, dict):
        return False
    cfg = _DISC_CFG.get(discipline)
    if cfg is None or spec.get("discipline") != discipline:
        return False
    events = spec.get("events")
    if not isinstance(events, list) or len(events) != cfg["events"]:
        return False
    for ev in events:
        stages = ev.get("stages") if isinstance(ev, dict) else None
        if not isinstance(stages, list) or len(stages) != cfg["stages"]:
            return False
        if not all(isinstance(st, dict) and all(k in st for k in _STAGE_KEYS) for st in stages):
            return False
    if not isinstance(spec.get("tier_rewards"), list) or "entry_window_end" not in spec:
        return False
    try:
        int(progress.get("event_index", 0))
        int(progress.get("stage_index", 0))
        int(progress.get("state", 0))
        int(obj.get("tier", 0))
    except (TypeError, ValueError):
        return False
    return True


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

LoadFn = Callable[[], Optional[Dict[str, Any]]]
SaveFn = Callable[[str, Dict[str, Any]], bool]


class CareerLadder:
    """Per-player career state for both disciplines.

    ``load()`` returns ``{"rally": state, "rallycross": state}`` (either key
    may be missing) or None on a transport failure; ``save(discipline,
    state)`` returns True on success.  With no callables the ladder lives in
    memory only (local / test mode).
    """

    def __init__(
        self,
        load: Optional[LoadFn] = None,
        save: Optional[SaveFn] = None,
        rng: Optional[random.Random] = None,
        log: Callable[[str], None] = print,
        now: Optional[Callable[[], float]] = None,
    ) -> None:
        self._load = load
        self._save = save
        self._rng = rng or random.Random()
        self._log = log
        self._now = now or time.time
        self._states: Dict[str, Dict[str, Any]] = {}
        # True once the backend copy has been read (or there is no backend).
        # Nothing is written back before that, so a transient failure at
        # startup can never overwrite real server-side progress.
        self._loaded = load is None
        self._lock = threading.RLock()

    # -- persistence -------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if self._loaded or self._load is None:
            return
        try:
            data = self._load()
        except Exception as exc:
            self._log(f"[CAREER] load failed: {exc!r}")
            data = None
        if data is None:
            self._log("[CAREER] backend unavailable, running from memory until it answers")
            return
        self._loaded = True
        for discipline in DISCIPLINES:
            stored = data.get(discipline) if isinstance(data, dict) else None
            if validate_state(stored, discipline):
                # The backend copy wins over anything accumulated in memory
                # while it was unreachable.
                self._states[discipline] = stored
            elif discipline in self._states:
                self._persist(discipline)

    def _persist(self, discipline: str) -> None:
        if self._save is None or not self._loaded:
            return
        try:
            ok = self._save(discipline, self._states[discipline])
        except Exception as exc:
            self._log(f"[CAREER] save {discipline} raised: {exc!r}")
            ok = False
        if not ok:
            self._log(f"[CAREER] save {discipline} failed; progress kept in memory")

    def _state(self, discipline: str) -> Dict[str, Any]:
        _check_discipline(discipline)
        self._ensure_loaded()
        state = self._states.get(discipline)
        if state is None:
            state = new_state(discipline, rng=self._rng, now=self._now())
            self._states[discipline] = state
            self._persist(discipline)
        return state

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _clamp_indices(state: Dict[str, Any], event_index: Any, stage_index: Any) -> tuple[int, int]:
        n_events, n_stages = spec_bounds(state["spec"])
        try:
            e = int(event_index)
        except (TypeError, ValueError):
            e = 0
        try:
            s = int(stage_index)
        except (TypeError, ValueError):
            s = 0
        e = max(0, min(max(n_events - 1, 0), e))
        s = max(0, min(max(n_stages - 1, 0), s))
        return e, s

    @staticmethod
    def _apply_vehicle(p: Dict[str, Any], req: StageBeginRequest) -> None:
        p["vehicle_id"] = int(req.vehicle_id)
        p["vehicle_inst_id"] = int(req.vehicle_inst_id)
        p["livery_id"] = int(req.livery_id)
        p["tyre_compound"] = int(req.tyre_compound)
        p["tyres_remaining"] = int(req.tyres_remaining)

    def _finish_championship(self, state: Dict[str, Any], champ_rank: int) -> None:
        discipline = state["discipline"]
        entrants = _DISC_CFG[discipline]["entrants"]
        tier_before = int(state["tier"])
        tier_after = tier_before
        rank = int(champ_rank)
        if 1 <= rank <= PROMOTE_MAX_RANK and tier_before < MAX_TIER:
            tier_after = tier_before + 1
        elif rank > entrants - RELEGATE_BOTTOM_N and tier_before > 0:
            tier_after = tier_before - 1
        history = state.setdefault("history", [])
        history.append({
            "finished_at": int(self._now()),
            "champ_rank": rank,
            "tier_before": tier_before,
            "tier_after": tier_after,
            "champ_time_ms": int(state["progress"].get("champ_time_ms", 0)),
            "seed": state["spec"].get("seed", 0),
        })
        del history[:-HISTORY_CAP]
        state["prev_tier"] = tier_before
        state["tier"] = tier_after
        state["spec"] = generate_spec(discipline, tier_after, self._rng, self._now())
        state["progress"] = fresh_progress(discipline)
        state["is_new_champ"] = True
        self._log(f"[CAREER] {discipline} championship finished rank={rank} "
                  f"tier {tier_before} -> {tier_after}")

    def _stage_complete_response(self, p: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "Progress":        progress_to_egonet(p),
            "EventReward":     zero_reward(),
            "ChampReward":     zero_reward(),
            "ResearchTarget":  UInt32(0),
            "ResearchPercent": 0.0,
            "OldResearchTgt":  UInt32(0),
            "OldResearchPct":  0.0,
            "ResultCode":      0,
        }

    # -- public API (one method per EgoNet call) ---------------------------

    def current_progress(self, discipline: str) -> Dict[str, Any]:
        with self._lock:
            return progress_to_egonet(self._state(discipline)["progress"])

    def get_championship(self, discipline: str) -> Dict[str, Any]:
        with self._lock:
            state = self._state(discipline)
            return {
                "Championship": build_championship(state["spec"]).to_egonet(),
                "Progress": progress_to_egonet(state["progress"]),
                "IsNewChamp": bool(state.get("is_new_champ", False)),
            }

    def reset_championship(self, discipline: str) -> Dict[str, Any]:
        with self._lock:
            state = self._state(discipline)
            state["spec"] = generate_spec(discipline, state["tier"], self._rng, self._now())
            state["progress"] = fresh_progress(discipline)
            state["is_new_champ"] = False
            self._persist(discipline)
            self._log(f"[CAREER] {discipline} championship reset at tier {state['tier']}")
            return {
                "Championship": build_championship(state["spec"]).to_egonet(),
                "TierList": tier_list_to_egonet(discipline, state["tier"], state["prev_tier"]),
                "Progress": progress_to_egonet(state["progress"]),
            }

    def tier_list(self, discipline: str) -> Dict[str, Any]:
        with self._lock:
            state = self._state(discipline)
            return {"TierList": tier_list_to_egonet(discipline, state["tier"], state["prev_tier"])}

    def championship_begin(self, discipline: str, req: StageBeginRequest) -> Dict[str, Any]:
        with self._lock:
            state = self._state(discipline)
            p = fresh_progress(discipline)
            p["state"] = STATE_BETWEEN_STAGES
            if req.vehicle_id or req.vehicle_inst_id:
                self._apply_vehicle(p, req)
            state["progress"] = p
            state["is_new_champ"] = False
            self._persist(discipline)
            return {"Progress": progress_to_egonet(p), "ResultCode": 0}

    def stage_begin(self, discipline: str, req: StageBeginRequest) -> Dict[str, Any]:
        with self._lock:
            state = self._state(discipline)
            p = state["progress"]
            e, s = self._clamp_indices(state, req.event_index, req.stage_index)
            expected = (int(p.get("event_index", 0)), int(p.get("stage_index", 0)))
            if (e, s) != expected or int(p.get("state", 0)) == STATE_STAGE_ACTIVE:
                self._log(f"[CAREER] {discipline} StageBegin at ({e},{s}) but server had "
                          f"{expected} state={p.get('state')}; adopting the client's position")
            p["event_index"] = e
            p["stage_index"] = s
            p["state"] = STATE_STAGE_ACTIVE
            p["stage_time_ms"] = 0
            p["meters_driven"] = 0
            p["has_repaired"] = False
            self._apply_vehicle(p, req)
            state["is_new_champ"] = False
            self._persist(discipline)
            return {"Progress": progress_to_egonet(p), "ResultCode": 0}

    def stage_complete(self, discipline: str, req: StageCompleteRequest) -> Dict[str, Any]:
        with self._lock:
            state = self._state(discipline)
            p = state["progress"]
            e, s = self._clamp_indices(state, req.event_index, req.stage_index)
            n_events, n_stages = spec_bounds(state["spec"])

            if p.get("last_completed") == [e, s] and int(p.get("state", 0)) != STATE_STAGE_ACTIVE:
                # The client re-sent a result we already applied.
                return self._stage_complete_response(p)

            quick = _val(req.comp_damage.quick_repairs)
            p["vehicle_id"] = int(req.vehicle_id)
            p["vehicle_inst_id"] = int(req.vehicle_inst_id)
            p["livery_id"] = int(req.livery_id)
            p["vehicle_damage"] = dataclasses.asdict(req.comp_damage)
            p["meters_driven"] = int(req.meters_driven)
            p["has_repaired"] = bool(req.recov_to_service or (quick or 0) > 0)
            p["event_index"] = e
            p["stage_index"] = s

            finished = False
            if int(req.race_status) == 0:
                time_ms = int(round(float(req.stage_time) * 1000))
                p["stage_time_ms"] = time_ms
                p["champ_time_ms"] = int(p.get("champ_time_ms", 0)) + time_ms
                p["last_completed"] = [e, s]
                if s < n_stages - 1:
                    p["stage_index"] = s + 1
                    p["state"] = STATE_BETWEEN_STAGES
                elif e < n_events - 1:
                    if ADVANCE_EVENT_ON_COMPLETE:
                        p["event_index"] = e + 1
                        p["stage_index"] = 0
                        p["state"] = STATE_BETWEEN_STAGES
                    else:
                        p["state"] = STATE_EVENT_FINISHED
                else:
                    p["state"] = STATE_EVENT_FINISHED
                    finished = True
            else:
                # Restart / retire: nothing scored, the stage stays current.
                p["stage_time_ms"] = 0
                p["state"] = STATE_BETWEEN_STAGES

            resp = self._stage_complete_response(p)
            if finished:
                self._finish_championship(state, req.champ_rank)
            self._persist(discipline)
            return resp
