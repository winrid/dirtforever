from __future__ import annotations

import calendar
import hashlib
import secrets
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from .account_store import AccountStore
from .api_client import DirtForeverClient
from .egonet import Int64, Timestamp, UInt16, UInt32, UInt8
from .game_data import (
    Location, Track, VEHICLES, CONFIRMED_VEHICLE_CLASS_IDS,
    default_stage_conditions_for_location,
    STAGE_CONDITIONS_LABELS, surface_degrad_for_level, service_area_for_level,
    RX_DRYING_TIME, RX_GRID_ENTRANTS, RX_NUMBER_RESTARTS, RX_SVC_SETTINGS_ID,
    rallycross_stage_plan,
)
from .models import (
    Challenge, Club, CompDamage, EntryWindow, Event, LeaderboardEntry,
    Reward, Stage, StageBeginRequest, StageCompleteRequest, TierReward, _val,
)


Handler = Callable[[Dict[str, Any]], Union[Dict[str, Any], bytes]]

# Sentinel to indicate the handler returned raw EgoNet binary bytes
# that should be sent directly without re-encoding.
RAW_BINARY_MARKER = "__raw_binary__"

# Fallback AccountId for local-only mode (no api_client, so no web username
# to derive an ID from). Local-only has no cross-player leaderboards, so the
# value just needs to be a stable, valid si64.
_FALLBACK_ACCOUNT_ID: int = 259912747194382660


def stable_account_id(username: str) -> int:
    """Derive a stable si64 AccountId from a web username.

    Used at Login.Login and on every leaderboard Presence row so the game's
    own-row check (local AccountId == row.AccountRef) succeeds naturally
    without per-row special-casing. SHA-256 truncated to 63 bits keeps the
    value positive in si64; collision odds are ~1 in 2**63.

    Returns 0 for the empty string.
    """
    if not username:
        return 0
    digest = hashlib.sha256(username.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") & 0x7FFFFFFFFFFFFFFF


def _apply_rallycross_stage_format(stage: Stage, stage_type: int, laps: int) -> Stage:
    """Give a Stage the lapped-race shape every RaceNet rallycross stage had.

    The rally shape (StageType 0, NumberLaps 0) on an RX circuit crashes the
    game on load.  See game_data.rallycross_stage_plan for the source values.
    """
    stage.stage_type = stage_type
    stage.number_laps = laps
    stage.has_service_area = True
    stage.svc_settings_id = RX_SVC_SETTINGS_ID
    stage.surface_degrad = 0.0
    stage.drying_time = RX_DRYING_TIME
    return stage


def _stable_int_id(string_id: str, base: int = 100000, offset: int = 0) -> int:
    """Derive a stable positive integer ID from a string identifier.

    Uses md5 so the same string ALWAYS produces the same integer across
    process restarts (Python's built-in hash() is randomized per-process).
    The result is kept well within 31-bit signed range to avoid EgoNet
    encoding issues.
    """
    import hashlib
    h = int.from_bytes(hashlib.md5(string_id.encode()).digest()[:4], "little")
    return base + (h % 90000) + offset

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "data" / "upstream_templates"


# Vehicle ID -> default LiveryId, from the upstream inventory template.
# The game requires LiveryId to belong to the VehicleId, otherwise Progress
# entries load the wrong car.
_LIVERY_FOR_VEHICLE: Dict[int, int] = {
    382: 2906, 395: 3511, 396: 2923, 399: 2921, 400: 2918, 401: 2912,
    468: 2929, 469: 3473, 470: 2927, 471: 2919, 478: 2915, 480: 2917,
    482: 3437, 483: 2904, 484: 2905, 485: 2689, 490: 2705, 511: 2951,
    513: 3079, 529: 2892, 532: 2897, 534: 2899, 535: 3050, 536: 2910,
    537: 2914, 538: 2926, 541: 2938, 547: 2949, 548: 2950, 550: 2953,
    555: 3359, 556: 3360, 558: 3362, 559: 3363, 561: 3365, 563: 3367,
    565: 3369, 570: 3374, 572: 3475, 573: 3484, 574: 3485, 575: 3494,
    576: 3513, 577: 3654, 578: 3690, 579: 3719, 580: 3711, 581: 3713,
    582: 3722, 585: 3765, 586: 3767, 587: 3770, 588: 3763, 589: 3772,
    590: 3764, 593: 3774, 597: 3779,
}


# Official-challenge (Events page) values observed in the real upstream
# GetChallenges capture (data/upstream_templates/RaceNetChallenges_GetChallenges.bin,
# decoded 2026-08-03). The game localizes the lng_* keys into "Daily Challenge"
# etc. and groups tiles by Category: 1=daily, 2=weekly, 3=monthly, 4=special.
_OFFICIAL_NAME_KEYS: Dict[str, str] = {
    "daily": "lng_daily_challenge",
    "weekly": "lng_weekly_challenge_header",
    "monthly": "lng_monthly_challenge_header",
}
_OFFICIAL_CATEGORY: Dict[str, int] = {"daily": 1, "weekly": 2, "monthly": 3}
_OFFICIAL_CATEGORY_SPECIAL = 4
# MaxEventCredits per period, taken from representative non-AI challenges in
# the same capture (daily 937167, weekly 937154, monthly 937098).
_OFFICIAL_MAX_CREDITS: Dict[str, int] = {
    "daily": 3500, "weekly": 70600, "monthly": 130900,
}


def _load_template(method: str) -> Optional[bytes]:
    """Load a captured upstream binary response template for the given method."""
    safe_name = method.replace(".", "_") + ".bin"
    path = TEMPLATE_DIR / safe_name
    if path.is_file():
        return path.read_bytes()
    return None


class RpcDispatcher:
    def __init__(
        self,
        account_store: AccountStore,
        api_client: Optional[DirtForeverClient] = None,
    ) -> None:
        self.account_store = account_store
        self.api_client = api_client
        # Toggle for diagnostic prints emitted alongside state transitions.
        # The GUI sets this from config["verbose_logging"]; default off so
        # released builds stay quiet unless a user opts in for support.
        self.verbose_logging: bool = False
        # Maps numeric challenge_id -> web event_id string, populated when
        # clubs are fetched from the API.
        self._challenge_event_map: Dict[int, str] = {}
        # Maps the per-sub-event challenge_id of a multi-event championship to
        # its sub-event index (0-based).  Only populated for multi-event
        # championships; single-event challenges are absent (index 0).
        self._challenge_subevent_map: Dict[int, int] = {}
        # Maps numeric club_id -> web club_id string
        self._club_id_map: Dict[int, str] = {}
        # Maps time-trial LeaderboardId -> (vclass, track, conditions, category) tuple
        self._tt_lb_map: Dict[int, tuple] = {}
        # The most recent GetLeaderboardId request — used by PostTime to
        # recover the 4-tuple (VehicleClassId is absent in PostTime params).
        self._last_tt_request: Optional[tuple] = None
        # Local player's web username, lazily resolved via api_client.test_token().
        # Used to identify the player's own row in leaderboard responses.
        self._my_username: Optional[str] = None
        # Streaming-overlay state: track the most recent event/club/vehicle the
        # player engaged with, plus a cached copy of the last clubs payload.
        # Read by StreamingWriter via get_streaming_state(); see dr2server/streaming.py.
        self._current_event_id: Optional[str] = None
        self._current_club_id: Optional[str] = None
        self._current_vehicle_id: Optional[int] = None
        self._clubs_snapshot: Optional[Dict[str, Any]] = None
        self._clubs_snapshot_ts: float = 0.0
        self._handlers: Dict[str, Handler] = {
            "Login.GetCurrentVersion": self._get_current_version,
            "Login.Login": self._login,
            "Login.Tick": self._tick,
            "DataMining.DataEvent": self._accepted,
            "RaceNet.SignIn": self._login,
            "RaceNet.CreateAccount": self._create_account,
            "RaceNet.GetTermsAndConditions": self._get_terms,
            "RaceNet.AcceptTerms": self._accept_terms,
            "RaceNet.CheckAccountLinked": self._account_linked,
            "Clubs.GetClubs": self._clubs,
            "Clubs.GetChampionshipLeaderboard": self._clubs_leaderboard,
            "Clubs.GetChampionshipFriendsLeaderboard": self._clubs_leaderboard,
            "Announcements.GetAnnouncements": self._announcements,
            "Localisation.GetStrings": self._localisation,
            "RaceNetLeaderboard.GetLeaderboardEntries": self._leaderboard,
            "RaceNetLeaderboard.GetFriendsEntries": self._leaderboard,
            "TimeTrial.GetLeaderboardId": self._time_trial_id,
            "TimeTrial.PostTime": self._post_time,
            "Status.GetNextStatusEvent": self._status,
            "Advertising.EnabledCheck": self._advertising_enabled,
            "VanityFlags.GetVanityFlags": self._vanity_flags,
            "Staff.GetStaff": self._staff,
            "RaceNetInventory.GetInventory": self._inventory,
            "RaceNetInventory.GetStore": self._template_or_stub("RaceNetInventory.GetStore", self._store),
            "RaceNetInventory.GetRewards": self._rewards,
            "RaceNetChallenges.GetChallenges": self._get_challenges,
            "RaceNetChallenges.GetStageSplits": self._stage_splits,
            "RaceNetChallenges.StageBegin": self._stage_begin,
            "RaceNetChallenges.StageComplete": self._stage_complete,
            "RaceNetCareerLadder.GetRallyTierList": self._rally_tier_list,
            "RaceNetCareerLadder.GetRallycrossTierList": self._rallycross_tier_list,
            "RaceNetCareerLadder.GetRallyChampionship": self._template_handler("RaceNetCareerLadder.GetRallyChampionship"),
            "RaceNetCareerLadder.GetRallycrossChampionship": self._template_handler("RaceNetCareerLadder.GetRallycrossChampionship"),
            "RaceNetCareerLadder.ResetRallyChampionship": self._template_handler("RaceNetCareerLadder.ResetRallyChampionship"),
            "RaceNetCareerLadder.ResetRallycrossChampionship": self._template_handler("RaceNetCareerLadder.ResetRallycrossChampionship"),
            "Repairs.GetUpgradeTuningPrices": self._template_handler("Repairs.GetUpgradeTuningPrices"),
            "Repairs.ComputeRepairCost": self._template_handler("Repairs.ComputeRepairCost"),
            # Write actions performed in the Service Area / Vehicle
            # Preparation screens.  The client VALIDATES the response body of
            # these: real upstream answers with a {"Result": 0, ...} envelope,
            # NOT the {"Accepted": true} ack most methods use.  A bare ack (or
            # the old default stub) makes the client show "LIVERY ERROR" /
            # "unknown error applying engine tuning" even with result-code 0,
            # and made the pre-fix stub emit result-code 1 (CONNECTION FAILED).
            # Response shapes captured from real upstream (159.153.126.42) —
            # see _repairs_* handlers below.
            "Repairs.SetLivery": self._repairs_set_livery,
            "Repairs.FitTuning": self._repairs_fit_tuning,
            "Repairs.PurchaseTuning": self._repairs_fit_tuning,
            "Repairs.PurchaseUpgrade": self._repairs_fit_tuning,
            "Repairs.PerformRepairs": self._repairs_perform,
            "Repairs.ApplyDamage": self._repairs_set_livery,
            # No upstream capture yet for these; the result-0 ack clears the
            # connection-failed screen.  Revisit with a capture if the client
            # rejects the ack for a store purchase / sale.
            "RaceNetInventory.Purchase": self._accepted,
            "RaceNetInventory.Sell": self._accepted,
            "Clubs.UpdateVehicleDamage": self._accepted,
            # Challenge lifecycle acknowledgements (community Daily/Weekly/
            # Monthly events).  The stage results themselves still go through
            # RaceNetChallenges.StageBegin/StageComplete above; these bracket
            # the attempt and only need a success ack.
            "RaceNetChallenges.StartChallenge": self._accepted,
            "RaceNetChallenges.ResumeChallenge": self._accepted,
            "RaceNetChallenges.AbortChallenge": self._accepted,
            # "My Team" career-ladder stage results (Career Rally / Career
            # Rallycross).  That mode keeps progress client-side, so the
            # backend call is a telemetry ack; return success so the end of a
            # career stage doesn't hit the connection-failed screen.
            "RaceNetCareerLadder.RallyStageBegin": self._accepted,
            "RaceNetCareerLadder.RallyStageComplete": self._accepted,
            "RaceNetCareerLadder.RallycrossStageBegin": self._accepted,
            "RaceNetCareerLadder.RallycrossStageComplete": self._accepted,
            "RaceNetCareerLadder.RallyChampionshipBegin": self._accepted,
            "RaceNetCareerLadder.RallycrossChampionshipBegin": self._accepted,
            "Season.Get": self._season,
            "Esports.SeasonActivityCheck": self._esports_activity,
            "Esports.EnabledCheck": self._esports_enabled,
            "Esports.ActivityCheck": self._esports_activity,
            "Esports.HasAcceptedTerms": self._esports_terms_status,
        }

    def _template_handler(self, method: str) -> Handler:
        """Return a handler that serves raw upstream binary template for the given method."""
        template = _load_template(method)

        def handler(params: Dict[str, Any]) -> Union[Dict[str, Any], bytes]:
            if template:
                return template
            return {"ok": True, "stub": True, "message": f"No template for {method}"}

        return handler

    def _template_or_stub(self, method: str, fallback: Handler) -> Handler:
        """Return template handler if a template exists, otherwise use the fallback."""
        template = _load_template(method)

        def handler(params: Dict[str, Any]) -> Union[Dict[str, Any], bytes]:
            if template:
                return template
            return fallback(params)

        return handler

    def dispatch(self, method: str, params: Dict[str, Any]) -> Union[Dict[str, Any], bytes]:
        handler = self._handlers.get(method, self._default_handler(method))
        return handler(params)

    def _default_handler(self, method: str) -> Handler:
        def handler(params: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "ok": True,
                "method": method,
                "stub": True,
                "message": "No concrete handler yet; request captured for analysis.",
                "echo": params,
            }

        return handler

    @staticmethod
    def _tick(params: Dict[str, Any]) -> Dict[str, Any]:
        return {"ok": True}

    @staticmethod
    def _accepted(params: Dict[str, Any]) -> Dict[str, Any]:
        return {"ok": True, "Accepted": True}

    def _get_current_version(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "ok": True,
            "Version": 1309032,
        }

    def _create_account(self, params: Dict[str, Any]) -> Dict[str, Any]:
        username = params.get("username") or params.get("user") or params.get("name")
        password = params.get("password") or params.get("pass")
        email = params.get("email", "")
        if not username or not password:
            return {"ok": False, "error": "username and password are required"}

        try:
            account = self.account_store.create_account(username, password, email)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

        return {
            "ok": True,
            "account": {
                "username": account.username,
                "email": account.email,
                "display_name": account.profile.get("display_name", account.username),
            },
        }

    def _login(self, params: Dict[str, Any]) -> Dict[str, Any]:
        username = params.get("username") or params.get("user") or params.get("email")
        password = params.get("password") or params.get("pass")
        if not username or not password:
            return {"ok": False, "error": "username and password are required"}

        account = self.account_store.authenticate(username, password)
        if not account:
            return {"ok": False, "error": "invalid credentials"}

        return {
            "ok": True,
            "session": {
                "token": secrets.token_urlsafe(24),
                "username": account.username,
            },
            "profile": account.profile,
        }

    def _get_terms(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "ok": True,
            "terms_version": "community-bootstrap-1",
            "text": "Community server terms placeholder.",
        }

    def _accept_terms(self, params: Dict[str, Any]) -> Dict[str, Any]:
        username = params.get("username") or params.get("user")
        if not username:
            return {"ok": False, "error": "username is required"}
        try:
            account = self.account_store.mark_terms_accepted(username)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "accepted_terms": account.profile.get("flags", {}).get("accepted_terms", False)}

    @staticmethod
    def _account_linked(params: Dict[str, Any]) -> Dict[str, Any]:
        return {"ok": True, "IsLinked": True}

    def _clubs(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Return club challenges.

        Resolution order:
          1. If DR2_DEBUG_CLUBS_FILE env var is set, serve a synthetic clubs
             response built from that JSON file (one Challenge per probe
             entry).  This is used for the enum-mapping testing round to
             probe specific LocationId/TrackModelId/StageConditions tuples
             and read the game's resolved labels from the event-details UI.
          2. Otherwise, if api_client is configured, fetch from dirtforever.net.
          3. Otherwise, return the hardcoded local-dev fallback.
        """
        import os
        debug_path = os.environ.get("DR2_DEBUG_CLUBS_FILE")
        if debug_path:
            try:
                return self._debug_clubs_from_file(debug_path)
            except Exception as exc:
                print(f"[CLUBS] DR2_DEBUG_CLUBS_FILE={debug_path} failed: {exc}")
                # Fall through to normal path

        if self.api_client is not None:
            result = self._clubs_from_api()
            if result is not None:
                return result
            # API is configured but returned nothing — return empty, not hardcoded data
            print("[CLUBS] API returned no clubs — returning empty")
            return {"ok": True, "Challenges": [], "Progress": [], "Clubs": []}

        return self._clubs_hardcoded_fallback()

    def _debug_clubs_from_file(self, path: str) -> Dict[str, Any]:
        """Build a synthetic clubs response from a JSON probe file.

        The JSON schema:
            {
              "probes": [
                {"name": "P01 L13 T626", "location_id": 13,
                 "track_model_id": 626, "stage_conditions": 1},
                ...
              ]
            }

        Each probe becomes its OWN club (with one challenge with one event
        with one stage) so the probes can be navigated via the clubs list's
        Left/Right arrows without hitting championship event-lock gates.
        The probe's `name` is used as the Club.Name so it can be identified
        from the Clubs list tile label.  Keep names ≤16 chars.
        """
        import json as _json
        with open(path, encoding="utf-8") as f:
            spec = _json.load(f)

        probes: List[Dict[str, Any]] = spec.get("probes", [])

        now = int(time.time())
        window = EntryWindow(
            visible=now - 172800, start=now - 86400,
            last_entry=now + 86400, end=now + 86400,
        )

        clubs_egonet: List[Dict[str, Any]] = []
        challenges_egonet: List[Dict[str, Any]] = []
        progress_egonet: List[Dict[str, Any]] = []

        for idx, probe in enumerate(probes):
            name = str(probe.get("name", f"P{idx:02d}"))[:20]
            loc_id = int(probe["location_id"])
            track_id = int(probe["track_model_id"])
            conditions = int(probe.get("stage_conditions", 1))

            club_int_id = _stable_int_id(f"debug-club-{idx}",
                                         base=100000, offset=idx)
            self._club_id_map[club_int_id] = f"debug-club-{idx}"

            chal_id = _stable_int_id(f"debug-probe-{idx}",
                                     base=700000, offset=idx)
            self._challenge_event_map[chal_id] = f"debug-{idx}"

            # Everything the location implies has to agree with the location,
            # or the game client crashes outright rather than erroring: the
            # discipline, and on a rallycross circuit the lapped-race stage
            # shape (see game_data.rallycross_stage_plan).
            try:
                is_rx = Location(loc_id).discipline == "rallycross"
            except (ValueError, AttributeError):
                is_rx = False
            discipline_id = 2 if is_rx else 1
            stage = Stage(
                stage_id=0,
                track_model_id=track_id,
                leaderboard_id=chal_id * 10,
                stage_conditions=conditions,
            )
            if is_rx:
                _apply_rallycross_stage_format(stage, *rallycross_stage_plan(1)[0])
            event = Event(
                event_id=chal_id,
                location_id=loc_id,
                discipline_id=discipline_id,
                number_restarts=RX_NUMBER_RESTARTS if is_rx else 0,
                stages=[stage],
                leaderboard_id=chal_id + 900000,
            )
            clubs_egonet.append(
                Club(
                    id=club_int_id,
                    name=name,
                    creator_name="discovery",
                    amount_of_events=1,
                ).to_egonet()
            )
            challenges_egonet.append(
                Challenge(
                    name=name,
                    challenge_id=chal_id,
                    club_id=club_int_id,
                    # Default to H2 FWD (vclass 100) if probe doesn't specify;
                    # empty requirements list appears to crash the game client.
                    requirements=[{"Type": 1, "Value": UInt32(int(probe.get("vehicle_class_id", 100)))}],
                    events=[event],
                    entry_window=window,
                    num_entrants=0,
                    leaderboard_id=chal_id + 800000,
                ).to_egonet()
            )

        print(f"[CLUBS] DEBUG MODE: serving {len(probes)} probes from {path}")
        return {
            "ok": True,
            "Challenges": challenges_egonet,
            "Progress": progress_egonet,
            "Clubs": clubs_egonet,
        }

    def _empty_clubs(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Deprecated alias kept for backwards compatibility."""
        return self._clubs(params)

    def _clubs_from_api(self) -> Optional[Dict[str, Any]]:
        """Fetch and convert clubs from the web API.  Returns None on failure."""
        assert self.api_client is not None
        try:
            data = self.api_client.get_clubs()
        except Exception as exc:
            print(f"[CLUBS] api_client.get_clubs() raised: {exc}")
            return None

        self._clubs_snapshot = data
        self._clubs_snapshot_ts = time.time()

        web_clubs = data.get("clubs", [])
        web_events = data.get("events", [])
        if self.verbose_logging:
            print(f"[STREAM] dispatcher: clubs_snapshot updated — "
                  f"{len(web_clubs)} clubs, {len(web_events)} events")

        if not web_clubs and not web_events:
            return None

        # Index events by their club_id for quick lookup
        events_by_club: Dict[str, list] = {}
        for evt in web_events:
            cid = evt.get("club_id") or "__global__"
            events_by_club.setdefault(cid, []).append(evt)

        clubs_egonet: List[Dict] = []
        challenges_egonet: List[Dict] = []
        # Multi-event championships build their own (correctly-keyed) Progress
        # entries; collect them here and exclude those events from the generic
        # per-event Progress builder so it can't emit a wrong-challenge entry.
        multi_progress: List[Dict[str, Any]] = []
        multi_event_ids: set = set()

        # Convert web clubs with their associated events.  Each web "event" is a
        # championship: one Challenge holding one or more game Events.
        for idx, wclub in enumerate(web_clubs):
            club_str_id: str = wclub.get("id", f"club-{idx}")
            club_name: str = wclub.get("name", f"Club {idx}")
            creator: str = wclub.get("created_by", "CommunityServer")

            # Derive a stable numeric ID from the string ID
            club_int_id = _stable_int_id(club_str_id, base=2000, offset=idx)
            self._club_id_map[club_int_id] = club_str_id

            club_events = events_by_club.get(club_str_id, [])
            if not club_events:
                continue  # skip clubs with no active events

            # A club whose single championship has >1 sub-event follows the
            # verified RaceNet multi-event model: serve one active event at a
            # time and advertise AmountOfEvents=N / EventIndex=current on the
            # Club (see notes/protocol_notes.md).  Every other club keeps the
            # original one-Challenge-per-championship behaviour untouched.
            if len(club_events) == 1:
                layout = [len(ev.get("stages", []) or [])
                          for ev in self._events_of(club_events[0])]
                if len(layout) > 1:
                    served = self._serve_multi_event_club(
                        club_events[0], club_str_id, club_int_id,
                        club_name, creator, layout,
                    )
                    if served is not None:
                        club_egonet, challenge_egonet, prog_entry = served
                        clubs_egonet.append(club_egonet)
                        challenges_egonet.append(challenge_egonet)
                        if prog_entry is not None:
                            multi_progress.append(prog_entry)
                        multi_event_ids.add(club_events[0].get("id", ""))
                    continue

            # Emit the Club entry ONCE per club (outside the event loop)
            clubs_egonet.append(
                Club(
                    id=club_int_id,
                    name=club_name,
                    creator_name=creator,
                    amount_of_events=len(club_events),
                ).to_egonet()
            )

            for evt_idx, wevt in enumerate(club_events):
                chal_id = _stable_int_id(wevt.get("id", f"{club_str_id}-{evt_idx}"),
                                         base=200000, offset=evt_idx)
                # Remember the mapping so StageComplete can reverse it
                self._challenge_event_map[chal_id] = wevt.get("id", "")

                car_class_label: str = wevt.get("car_class", "")
                vclass_id = self.api_client.resolve_vclass_id(car_class_label)
                # A club challenge must carry a confirmed vehicle-class
                # Requirement.  An unmappable class would otherwise produce an
                # empty/invalid Requirement, which crashes the game client, so
                # skip the championship rather than guess a fallback class.
                if vclass_id is None or vclass_id not in CONFIRMED_VEHICLE_CLASS_IDS:
                    print(f"[CLUBS] Unmappable car class '{car_class_label}' for "
                          f"event {wevt.get('id')} — skipping")
                    continue

                events_out = self._build_events_for_champ(wevt, chal_id)
                if not events_out:
                    print(f"[CLUBS] No resolvable events for {wevt.get('id')} — skipping")
                    continue

                num_entrants = len(wevt.get("entries", [])) if "entries" in wevt else 0
                challenges_egonet.append(
                    self._challenge_egonet(
                        wevt, chal_id, club_int_id,
                        [{"Type": 1, "Value": UInt32(vclass_id)}],
                        events_out, num_entrants, club_name,
                    )
                )

        # Also include "global" events (no club_id) as standalone entries
        for evt_idx, wevt in enumerate(events_by_club.get("__global__", [])):
            chal_id = _stable_int_id(wevt.get("id", f"global-{evt_idx}"),
                                     base=300000, offset=evt_idx)
            self._challenge_event_map[chal_id] = wevt.get("id", "")

            car_class_label = wevt.get("car_class", "")
            vclass_id = self.api_client.resolve_vclass_id(car_class_label)
            # Must carry a confirmed class Requirement — an unmappable class
            # crashes the game, so skip rather than guess a fallback.
            if vclass_id is None or vclass_id not in CONFIRMED_VEHICLE_CLASS_IDS:
                print(f"[CLUBS] Unmappable car class '{car_class_label}' for "
                      f"global event {wevt.get('id')} — skipping")
                continue

            events_out = self._build_events_for_champ(wevt, chal_id)
            if not events_out:
                continue

            # Use a synthetic club_id = 0 for global events
            global_club_id = 9000 + evt_idx
            clubs_egonet.append(
                Club(
                    id=global_club_id,
                    name=wevt.get("name", "Community Event"),
                    creator_name="CommunityServer",
                    amount_of_events=1,
                ).to_egonet()
            )
            challenges_egonet.append(
                self._challenge_egonet(
                    wevt, chal_id, global_club_id,
                    [{"Type": 1, "Value": UInt32(vclass_id)}],
                    events_out, 0, "Community Event",
                )
            )

        if not challenges_egonet:
            return None

        progress_egonet = multi_progress + self._build_user_progress(
            [e for e in web_events if e.get("id") not in multi_event_ids]
        )

        return {
            "ok": True,
            "Challenges": challenges_egonet,
            "Progress": progress_egonet,
            "Clubs": clubs_egonet,
        }

    # ── Championship → Challenge conversion helpers ────────────────────────

    @staticmethod
    def _epoch_utc(iso: str) -> int:
        """Naive-UTC ISO timestamp -> epoch seconds.

        Uses ``calendar.timegm`` (NOT ``datetime.timestamp()``, which would
        apply the host's local UTC offset) because the web app stores all
        times as naive UTC.
        """
        return calendar.timegm(datetime.fromisoformat(iso).timetuple())

    def _window_for(self, wevt: Dict[str, Any]) -> EntryWindow:
        """Build the Challenge EntryWindow from the championship start/end.

        Falls back to a now-relative window when the timestamps are missing or
        unparseable, matching the pre-scheduling behaviour.
        """
        try:
            start_ep = self._epoch_utc(wevt["start_time"])
            end_ep = self._epoch_utc(wevt["end_time"])
            if end_ep > start_ep:
                return EntryWindow(
                    visible=start_ep, start=start_ep,
                    last_entry=end_ep, end=end_ep,
                )
        except (KeyError, ValueError, TypeError):
            pass
        now = int(time.time())
        return EntryWindow(
            visible=now - 172800, start=now - 86400,
            last_entry=now + 86400, end=now + 86400,
        )

    @staticmethod
    def _stage_lb(chal_id: int, event_index: int, stage_index: int) -> int:
        """Unique stage LeaderboardId encoding (event_index, stage_index).

        For event_index 0 this reduces to the original ``chal_id*10 + stage``
        scheme, so single-event championships (every event today) keep their
        exact ids.  The results plumbing that reverses this for events past
        index 0 lands in a later stage.
        """
        return chal_id * 10 + event_index * 1_000_000 + stage_index

    def _events_of(self, wevt: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Return the championship's sub-events (v2 shape), or synthesize one
        from the legacy top-level fields so pre-v2 / debug-file events work."""
        events = wevt.get("events")
        if events:
            return events
        return [{
            "location": wevt.get("location", ""),
            "car_class": wevt.get("car_class", ""),
            "stages": wevt.get("stages", []),
        }]

    def _build_subevent(self, wevt: Dict[str, Any], chal_id: int, ei: int,
                        ev: Dict[str, Any]) -> Optional[Event]:
        """Build one game Event (a championship sub-event); None if the
        location/tracks can't be resolved.

        Resolves its own location + verified routes and builds stages from the
        stored per-stage route/conditions/surface-deg/service-area values (with
        backward-compatible fallbacks for legacy files).
        """
        assert self.api_client is not None  # only called with an api_client present
        loc_name = ev.get("location", "") or wevt.get("location", "")
        location_id = self.api_client.resolve_location_id(loc_name)
        if location_id is None:
            print(f"[CLUBS] Unknown location '{loc_name}' in event "
                  f"{wevt.get('id')} #{ei} — skipping sub-event")
            return None
        track_ids = self.api_client.tracks_for_location(location_id)
        if not track_ids:
            print(f"[CLUBS] No tracks for location {location_id} "
                  f"('{loc_name}') in event {wevt.get('id')} #{ei} — skipping")
            return None
        try:
            is_rx = Location(location_id).discipline == "rallycross"
        except (ValueError, AttributeError):
            is_rx = False
        stages = self._stages_for_subevent(ev, chal_id, ei, track_ids, is_rx=is_rx)
        # Rallycross is a lapped race: RaceNet's own RX events carry 5 restarts
        # and, on the multi-stage knockout format, a 20-car AI grid.  The
        # single-stage format is the solo daily (no grid).
        return Event(
            event_id=chal_id + ei * 10_000_000,
            location_id=location_id,
            discipline_id=2 if is_rx else 1,
            number_restarts=RX_NUMBER_RESTARTS if is_rx else 0,
            number_entrants=RX_GRID_ENTRANTS if (is_rx and len(stages) > 1) else 0,
            stages=stages,
            leaderboard_id=chal_id + 900000 + ei * 10_000_000,
        )

    def _build_events_for_champ(self, wevt: Dict[str, Any], chal_id: int) -> List[Event]:
        """Build the list of game Events for one championship (all sub-events)."""
        events_out: List[Event] = []
        for ei, ev in enumerate(self._events_of(wevt)):
            event = self._build_subevent(wevt, chal_id, ei, ev)
            if event is not None:
                events_out.append(event)
        return events_out

    @staticmethod
    def _active_event_index(layout: List[int], ep: Optional[Dict[str, Any]]) -> int:
        """Sub-event the player is currently on in a multi-event championship.

        Equals the number of fully-completed leading sub-events, capped at
        ``N-1`` so the last event stays 'active' once the championship is
        finished (matching RaceNet's ``EventIndex == AmountOfEvents-1`` at
        completion).

        The web backend stores completed stages in flat championship-ordinal
        slots (``_global_stage_index``) without a per-stage ``event_index``
        (see tests/test_championship_results.py), so progression is derived
        from the flat completed-stage count against the per-event stage layout.
        Stages complete in order within a championship, so a running count is
        sufficient.
        """
        completed_count = len((ep or {}).get("completed_stages", []))
        k = 0
        cumulative = 0
        for count in layout:
            cumulative += count
            if count > 0 and completed_count >= cumulative:
                k += 1
            else:
                break
        return min(k, max(len(layout) - 1, 0))

    def _serve_multi_event_club(
        self, wevt: Dict[str, Any], club_str_id: str, club_int_id: int,
        club_name: str, creator: str, layout: List[int],
    ) -> Optional[tuple[Dict[str, Any], Dict[str, Any], Optional[Dict[str, Any]]]]:
        """Serve a multi-event championship the RaceNet way: only the active
        sub-event, as its own single-event Challenge, with the Club advertising
        ``AmountOfEvents=N`` / ``EventIndex=current``.

        Returns ``(club_egonet, challenge_egonet, progress_egonet_or_None)`` or
        ``None`` if unresolvable.  The Progress entry (when the player has
        completed stages of the active event) is keyed to the ACTIVE challenge
        id and reflects THAT event's completion, so a finished event/championship
        shows as complete instead of enterable.  A distinct ChallengeID per
        sub-event makes the client re-fetch a fresh challenge when the
        championship advances (real RaceNet 946876->946877).
        """
        assert self.api_client is not None
        num_events = len(layout)
        wevt_id = wevt.get("id", "")

        car_class_label: str = wevt.get("car_class", "")
        vclass_id = self.api_client.resolve_vclass_id(car_class_label)
        if vclass_id is None or vclass_id not in CONFIRMED_VEHICLE_CLASS_IDS:
            print(f"[CLUBS] Unmappable car class '{car_class_label}' for "
                  f"championship {wevt_id} — skipping")
            return None

        ep = self._user_progress_for_event(wevt_id) if wevt_id else None
        active = self._active_event_index(layout, ep)

        base_chal_id = _stable_int_id(wevt_id or f"{club_str_id}-0",
                                      base=200000, offset=0)
        active_chal_id = base_chal_id + active
        self._challenge_event_map[active_chal_id] = wevt_id
        self._challenge_subevent_map[active_chal_id] = active

        event = self._build_subevent(wevt, base_chal_id, active,
                                     self._events_of(wevt)[active])
        if event is None:
            print(f"[CLUBS] Active event {active} of {wevt_id} unresolvable — skipping")
            return None

        num_entrants = len(wevt.get("entries", [])) if "entries" in wevt else 0
        club_egonet = Club(
            id=club_int_id, name=club_name, creator_name=creator,
            amount_of_events=num_events, event_index=active,
        ).to_egonet()
        challenge_egonet = self._challenge_egonet(
            wevt, active_chal_id, club_int_id,
            [{"Type": 1, "Value": UInt32(vclass_id)}],
            [event], num_entrants, club_name,
        )
        progress_egonet = self._multi_event_progress(active_chal_id, layout, active, ep)
        return club_egonet, challenge_egonet, progress_egonet

    def _multi_event_progress(
        self, challenge_id: int, layout: List[int], active: int,
        ep: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Progress entry for the active event of a multi-event championship,
        keyed to the currently-served challenge id.

        Returns None when the player hasn't completed any of THIS event's stages
        (so the game shows it enterable).  When the event's stages are all done
        the entry is ``State=2`` (finished) — which is how a completed event /
        championship is shown as complete rather than re-enterable.
        """
        completed = (ep or {}).get("completed_stages", [])
        completed_count = len(completed)
        offset = sum(layout[:active])
        event_stage_count = layout[active] if 0 <= active < len(layout) else 0
        # Stages complete in order, so within-event progress is the flat count
        # minus this event's starting offset, clamped to the event's stage count.
        done_in_event = max(0, min(completed_count - offset, event_stage_count))
        if done_in_event <= 0:
            return None  # not started -> enterable, no Progress entry

        all_done = done_in_event >= event_stage_count
        state = 2 if all_done else 1
        target_stage_index = (event_stage_count - 1) if all_done else done_in_event

        last = completed[completed_count - 1] if completed else {}
        vehicle_id = last.get("vehicle_id") or 0
        if not isinstance(vehicle_id, int):
            vehicle_id = 0
        livery_id = last.get("livery_id", 0) or _LIVERY_FOR_VEHICLE.get(vehicle_id, 0)
        return self._build_progress_dict(
            challenge_id=challenge_id,
            target_stage_index=target_stage_index,
            state=state,
            vehicle_id=vehicle_id,
            livery_id=livery_id,
            meters_driven=last.get("meters_driven", 0) or 0,
            champ_time_ms=self._time_in_range(completed, offset, event_stage_count),
            has_repaired=bool(last.get("has_repaired", False)),
            repair_penalty_ms=int(last.get("repair_penalty_ms", 0) or 0),
            vehicle_damage=self._damage_from_dict(last.get("vehicle_damage")),
            tyre_compound=int(last.get("tyre_compound", 0) or 7),
            tyres_remaining=int(last.get("tyres_remaining", 0) or 2),
            tuning_bytes=self._decode_tuning_b64(last.get("tuning_setup_b64", "") or ""),
            attempts_left=self._attempts_left_for(ep),
        )

    @staticmethod
    def _default_conditions_for_track(track_id: int) -> Optional[int]:
        """First conditions option of the location this track belongs to.

        Used only when a stage carries no id at all: there is no globally safe
        value to fall back on (Varmland offers snow only, so not even 1).
        """
        try:
            location = Track(track_id).location
        except ValueError:
            return None
        return default_stage_conditions_for_location(location)

    def _stages_for_subevent(self, ev: Dict[str, Any], chal_id: int,
                             ei: int, track_ids: List[int],
                             is_rx: bool = False) -> List[Stage]:
        track_set = set(track_ids)
        web_stages = ev.get("stages") or [None]
        stages: List[Stage] = []
        rx_plan = rallycross_stage_plan(len(web_stages)) if is_rx else []
        for si, ws in enumerate(web_stages):
            ws = ws or {}
            # Route: use the stored verified track_id; fall back to positional.
            tid = ws.get("track_id")
            try:
                tid = int(tid) if tid is not None else None
            except (TypeError, ValueError):
                tid = None
            track_id = tid if (tid is not None and tid in track_set) \
                else track_ids[si % len(track_ids)]
            # Conditions: served as stored.  Validity is a per-location
            # property (see STAGE_CONDITIONS_BY_LOCATION) enforced where events
            # are written — the create forms and the generator — and repaired
            # in stored data by web/migrations, so nothing is converted here.
            #
            # A stage with NO id at all still needs one, and the Stage default
            # is 1, which Varmland cannot load.  Take the default from the
            # location this stage will actually load instead; only data written
            # by something other than this server can reach it.
            cid = ws.get("conditions_id")
            try:
                cid = int(cid) if cid is not None else None
            except (TypeError, ValueError):
                cid = None
            if cid is None:
                cid = self._default_conditions_for_track(track_id)
            stage_conditions = cid if cid is not None else Stage().stage_conditions
            # Surface degradation (best-guess mapping; default = engine value).
            surface_degrad = (
                surface_degrad_for_level(ws["surface_deg"])
                if ws.get("surface_deg") is not None else 0.25
            )
            # Service area (best-guess mapping; legacy fallback = alternate parity).
            if ws.get("service_area") is not None:
                has_service_area, svc_settings_id = service_area_for_level(ws["service_area"])
            else:
                has_service_area, svc_settings_id = (si % 2 == 0), 2
            stage = Stage(
                stage_id=si,
                track_model_id=track_id,
                has_service_area=has_service_area,
                svc_settings_id=svc_settings_id,
                surface_degrad=surface_degrad,
                leaderboard_id=self._stage_lb(chal_id, ei, si),
                stage_conditions=stage_conditions,
            )
            if is_rx:
                # A rallycross stage is a lapped race; the stored service-area
                # and surface-degradation levels are rally concepts, so the
                # values RaceNet always used for RX replace them.
                _apply_rallycross_stage_format(stage, *rx_plan[si])
            stages.append(stage)
        if not stages:
            stage = Stage(
                stage_id=0, track_model_id=track_ids[0],
                has_service_area=True,
                leaderboard_id=self._stage_lb(chal_id, ei, 0),
            )
            if is_rx:
                _apply_rallycross_stage_format(stage, *rallycross_stage_plan(1)[0])
            stages.append(stage)
        return stages

    def _challenge_egonet(self, wevt: Dict[str, Any], chal_id: int, club_int_id: int,
                          requirements: List[Dict[str, Any]], events_out: List[Event],
                          num_entrants: int, default_name: str) -> Dict[str, Any]:
        settings = wevt.get("settings") or {}
        return Challenge(
            name=wevt.get("name", default_name),
            challenge_id=chal_id,
            club_id=club_int_id,
            requirements=requirements,
            events=events_out,
            entry_window=self._window_for(wevt),
            num_entrants=num_entrants,
            leaderboard_id=chal_id + 800000,
            is_hardcore=bool(settings.get("hardcore_damage", True)),
            exterior_cams=not bool(settings.get("force_cockpit_camera", False)),
            allow_assists=bool(settings.get("allow_assists", True)),
            unxpectd_moments=bool(settings.get("unexpected_moments", True)),
        ).to_egonet()

    # VehicleDamage field order MUST match upstream exactly — the game
    # parses this as an ordered struct. Used by Progress builders below.
    @staticmethod
    def _damage_from_dict(d: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        d = d or {}
        return {
            "WheelsWear":   UInt32(int(d.get("wheels_wear", 0))),
            "Turbo":        UInt32(int(d.get("turbo", 0))),
            "Springs":      UInt32(int(d.get("springs", 0))),
            "Radiator":     float(d.get("radiator", 0.0)),
            "Lights":       float(d.get("lights", 0.0)),
            "Gearbox":      UInt32(int(d.get("gearbox", 0))),
            "WheelsImpact": UInt32(int(d.get("wheels_impact", 0))),
            "Exhaust":      float(d.get("exhaust", 0.0)),
            "DiffImpact":   UInt32(int(d.get("diff_impact", 0))),
            "DiffWear":     UInt32(int(d.get("diff_wear", 0))),
            "Dampers":      UInt32(int(d.get("dampers", 0))),
            "Clutch":       float(d.get("clutch", 0.0)),
            "Brakes":       UInt32(int(d.get("brakes", 0))),
            "Bodywork":     UInt32(int(d.get("bodywork", 0))),
            "Engine":       float(d.get("engine", 0.0)),
            "QuickRepairs": UInt16(int(d.get("quick_repairs", 0))),
        }

    # VehicleMud field order MUST match upstream exactly — only included in
    # StageComplete responses (not StageBegin, not Clubs.GetClubs).
    @staticmethod
    def _mud_from_dict(d: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        d = d or {}
        return {
            "Dirt":        float(d.get("dirt", 0.0)),
            "WheelMud0":   float(d.get("wheel_mud_0", d.get("wheel_mud0", 0.0))),
            "WheelMud1":   float(d.get("wheel_mud_1", d.get("wheel_mud1", 0.0))),
            "WheelMud2":   float(d.get("wheel_mud_2", d.get("wheel_mud2", 0.0))),
            "WheelMud3":   float(d.get("wheel_mud_3", d.get("wheel_mud3", 0.0))),
            "Mud":         float(d.get("mud", 0.0)),
            "CleanHeight": float(d.get("clean_height", 0.0)),
            "CleanDirt":   float(d.get("clean_dirt", 0.0)),
            "CleanMud":    float(d.get("clean_mud", 0.0)),
        }

    @staticmethod
    def _build_progress_dict(
        challenge_id: int,
        target_stage_index: int,
        state: int,
        vehicle_id: int,
        livery_id: int,
        meters_driven: int,
        champ_time_ms: int,
        has_repaired: bool,
        repair_penalty_ms: int,
        vehicle_damage: Dict[str, Any],
        tyre_compound: int,
        tyres_remaining: int,
        tuning_bytes: bytes,
        attempts_left: int,
        percentile: int = 0,
        vehicle_mud: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build a single Progress dict matching upstream's wire shape exactly.

        Field order, names, and EgoNet types are all verified against captured
        upstream RaceNetChallenges.StageBegin/StageComplete responses (1606-byte
        and 822-byte bodies decoded on 2026-04-27 from 159.153.126.42).

        ``vehicle_mud`` is only populated for StageComplete-style responses;
        StageBegin and Clubs.GetClubs Progress entries omit it.
        """
        progress: Dict[str, Any] = {
            "ChallengeID":   challenge_id,
            "EventIndex":    0,
            "StageIndex":    target_stage_index,
            "State":         state,
            "StageTimeMs":   UInt32(0),
            "VehicleInstId": Int64(0),
            "VehicleId":     UInt32(vehicle_id),
            "LiveryId":      UInt32(livery_id),
            "MetersDriven":  meters_driven,
            "Percentile":    percentile,
            "ChampTimeMs":   UInt32(champ_time_ms),
            "HasRepaired":   has_repaired,
            "RepairPenalty": UInt32(repair_penalty_ms),
            "VehicleDamage": vehicle_damage,
        }
        if vehicle_mud is not None:
            progress["VehicleMud"] = vehicle_mud
        progress["TyreCompound"]   = UInt32(tyre_compound)
        progress["TyresRemaining"] = UInt32(tyres_remaining)
        progress["TuningSetup"]    = tuning_bytes
        progress["AttemptsLeft"]   = attempts_left
        return progress

    @staticmethod
    def _zero_reward() -> Dict[str, Any]:
        """Build a fully-zeroed EventReward/ChampReward matching upstream's shape.

        Field order and EgoNet types verified against the StageComplete capture.
        ``Reason.Source`` mirrors the observed upstream wire value (4) — see
        :class:`game_data.RewardSource.UNKNOWN_4`.
        """
        from .game_data import RewardSource
        return {
            "Id": Int64(0),
            "Reason": {
                "Source":         int(RewardSource.UNKNOWN_4),
                "Type":           0,
                "FinishPosition": 0,
                "FinishTimeMs":   0,
                "SourceEntityId": Int64(0),
                "SourceName":     "",
            },
            "Message":         "",
            "SoftCurrency":    0,
            "GarageSlots":     0,
            "Items":           [],
            "IsGlobalBoosted": False,
        }

    def _get_my_progress_safe(self) -> Optional[Dict[str, Any]]:
        """Fetch get_my_progress(), suppressing/logging any error."""
        if self.api_client is None:
            return None
        try:
            return self.api_client.get_my_progress()
        except Exception as exc:
            print(f"[PROGRESS] get_my_progress() failed: {exc}")
            return None

    def _user_progress_for_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Return the my_progress entry for a given web event_id, or None."""
        my_progress = self._get_my_progress_safe()
        if not my_progress:
            return None
        for ep in my_progress.get("events", []):
            if ep.get("event_id", "") == event_id:
                return ep
        return None

    def _attempts_left_for(self, ep: Optional[Dict[str, Any]]) -> int:
        """Compute AttemptsLeft from stored attempts_used.

        Sources attempts_allowed from the Challenge dataclass default so that
        the value is wired through model config rather than a literal in the
        response builder.
        """
        attempts_allowed = Challenge().attempts_allowed
        attempts_used = int((ep or {}).get("attempts_used", 0))
        return max(attempts_allowed - attempts_used, 0)

    def _decode_tuning_b64(self, tuning_b64: str) -> bytes:
        """Decode a stored tuning blob; fall back to the default blob if empty."""
        import base64
        try:
            tuning_bytes = base64.b64decode(tuning_b64) if tuning_b64 else b""
        except Exception:
            tuning_bytes = b""
        if not tuning_bytes:
            # Game crashes on empty/malformed TuningSetup blobs; the fallback
            # is a known-valid neutral blob, NOT an invented gameplay default.
            from .tuning import TuningBlob
            tuning_bytes = TuningBlob.default_bytes()
        return tuning_bytes

    def _build_user_progress(self, web_events: list) -> list:
        """Build Progress entries for the current user across all club events.

        One entry per event where the user has at least one completed stage.
        Used by the Clubs.GetClubs response.
        """
        if self.api_client is None:
            return []

        my_progress = self._get_my_progress_safe()
        progress_by_event: Dict[str, Any] = {}
        if my_progress:
            for ep in my_progress.get("events", []):
                eid = ep.get("event_id", "")
                if eid:
                    progress_by_event[eid] = ep

        progress: list = []
        for evt in web_events:
            evt_id = evt.get("id", "")
            if not evt_id:
                continue

            chal_id = None
            for k, v in self._challenge_event_map.items():
                if v == evt_id:
                    chal_id = k
                    break
            if chal_id is None:
                continue

            ep = progress_by_event.get(evt_id)
            if not ep:
                continue
            completed_stages = ep.get("completed_stages", [])
            if not completed_stages:
                continue

            total_stages_in_event = len(evt.get("stages", []))
            all_done = (
                total_stages_in_event > 0
                and len(completed_stages) >= total_stages_in_event
            )

            last_stage = completed_stages[-1]
            next_stage_idx = last_stage.get("stage_index", 0) + 1
            if all_done:
                stage_index_out = total_stages_in_event - 1
                state_out = 2
            else:
                stage_index_out = next_stage_idx
                state_out = 1

            vehicle_id = last_stage.get("vehicle_id") or 0
            if not isinstance(vehicle_id, int):
                vehicle_id = 0
            livery_id = last_stage.get("livery_id", 0)
            if not livery_id:
                livery_id = _LIVERY_FOR_VEHICLE.get(vehicle_id, 0)

            progress.append(self._build_progress_dict(
                challenge_id=chal_id,
                target_stage_index=stage_index_out,
                state=state_out,
                vehicle_id=vehicle_id,
                livery_id=livery_id,
                meters_driven=last_stage.get("meters_driven", 0) or 0,
                champ_time_ms=ep.get("total_time_ms", 0),
                has_repaired=bool(last_stage.get("has_repaired", False)),
                repair_penalty_ms=int(last_stage.get("repair_penalty_ms", 0) or 0),
                vehicle_damage=self._damage_from_dict(last_stage.get("vehicle_damage")),
                tyre_compound=int(last_stage.get("tyre_compound", 0) or 7),
                tyres_remaining=int(last_stage.get("tyres_remaining", 0) or 2),
                tuning_bytes=self._decode_tuning_b64(last_stage.get("tuning_setup_b64", "") or ""),
                attempts_left=self._attempts_left_for(ep),
            ))

        return progress

    @staticmethod
    def _clubs_hardcoded_fallback() -> Dict[str, Any]:
        """Return hardcoded test club challenges (original implementation)."""
        now = int(time.time())
        window = EntryWindow(
            visible=now - 172800, start=now - 86400,
            last_entry=now + 86400, end=now + 86400,
        )

        clubs_data = [
            (1001, "Community Rally NZ", "CommunityServer", "Community Rally - New Zealand",
             100001, Location.NEW_ZEALAND, [
                 Stage(stage_id=0, track_model_id=Track.OCEAN_BEACH,                 has_service_area=True,  leaderboard_id=3000001),
                 Stage(stage_id=1, track_model_id=Track.OCEAN_BEACH_SPRINT_REVERSE,  has_service_area=False, leaderboard_id=3000002),
                 Stage(stage_id=2, track_model_id=Track.WAIMARAMA_POINT_REVERSE,     has_service_area=True,  leaderboard_id=3000003),
                 Stage(stage_id=3, track_model_id=Track.TE_AWANGA_FORWARD,           has_service_area=False, leaderboard_id=3000004),
             ], 12),
            (1002, "Community Rally ARG", "CommunityServer", "Community Rally - Argentina",
             100002, Location.ARGENTINA, [
                 Stage(stage_id=0, track_model_id=Track.VALLE_DE_LOS_PUENTES,              has_service_area=True,  leaderboard_id=3000005),
                 Stage(stage_id=1, track_model_id=Track.VALLE_DE_LOS_PUENTES_A_LA_INVERSA, has_service_area=False, leaderboard_id=3000006),
             ], 8),
            (1003, "Community Rally ESP", "CommunityServer", "Community Rally - Spain",
             100003, Location.SPAIN, [
                 Stage(stage_id=0, track_model_id=Track.DESCENSO_POR_CARRETERA,  has_service_area=True,  leaderboard_id=3000007),
                 Stage(stage_id=1, track_model_id=Track.SUBIDA_POR_CARRETERA,    has_service_area=False, leaderboard_id=3000008),
                 Stage(stage_id=2, track_model_id=Track.COMIENZO_DE_BELLRIU,     has_service_area=True,  leaderboard_id=3000009),
             ], 15),
        ]

        challenges = []
        clubs = []
        for club_id, club_name, creator, chal_name, cid, loc, stages, entrants in clubs_data:
            clubs.append(Club(id=club_id, name=club_name, creator_name=creator,
                              amount_of_events=1).to_egonet())
            challenges.append(Challenge(
                name=chal_name, challenge_id=cid, club_id=club_id,
                events=[Event(event_id=cid, location_id=loc, stages=stages,
                              leaderboard_id=cid + 900000)],
                entry_window=window, num_entrants=entrants,
                leaderboard_id=cid + 800000,
            ).to_egonet())

        return {"ok": True, "Challenges": challenges, "Progress": [], "Clubs": clubs}

    def _resolve_my_username(self) -> Optional[str]:
        """Return the local player's web username, cached after first lookup.

        Resolved via the API token configured at server start (each player
        runs their own server bound to their dirtforever.net account, so
        there's effectively one user per server). Returns None when no
        api_client is configured or the token check fails.
        """
        if self._my_username is not None:
            return self._my_username
        if self.api_client is None:
            return None
        try:
            username = self.api_client.test_token()
        except Exception as exc:
            print(f"[LB] test_token() raised: {exc}")
            return None
        if username:
            self._my_username = username
            print(f"[LB] Resolved local username: {username}")
        return self._my_username

    def my_account_id(self) -> int:
        """Stable AccountId for the local player.

        Hashed from the web username via :func:`stable_account_id` so the
        value matches the EgoNetId/AccountRef on the player's leaderboard
        row without any tagging step. Falls back to a labeled constant when
        no api_client is configured (local-only mode has no cross-player
        leaderboards).
        """
        username = self._resolve_my_username()
        if username:
            return stable_account_id(username)
        return _FALLBACK_ACCOUNT_ID

    def _player_rank_in(self, egonet_entries: list) -> int:
        """Return the 1-based rank of the local player's row, or 0 if absent.

        Used to populate ``PlayerRank`` in leaderboard responses. Read-only:
        per-row IDs are assigned at construction time via
        :func:`stable_account_id`, so no mutation is needed here.
        """
        me = self._resolve_my_username()
        if not me:
            return 0
        for e in egonet_entries:
            presence = e.get("Presence")
            if not isinstance(presence, dict):
                continue
            if presence.get("Name", "") != me:
                continue
            rank = e.get("Rank", 0)
            return int(getattr(rank, "value", rank) or 0)
        return 0

    def _clubs_leaderboard(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Return leaderboard entries for a club championship."""
        if self.api_client is None:
            return {"ok": True, "Entries": [], "Total": 0}

        club_id = params.get("ClubId")
        club_id = getattr(club_id, "value", club_id)
        start_rank = params.get("StartRank", 0)
        start_rank = getattr(start_rank, "value", start_rank)
        limit = params.get("Limit", 50)
        limit = getattr(limit, "value", limit)

        # Map numeric club_id back to web club_id string
        web_club_id = self._club_id_map.get(club_id)

        # Find an event for this club (fall back to first active event)
        event_id = None
        try:
            data = self.api_client.get_clubs()
            events = data.get("events", [])
            if web_club_id:
                for e in events:
                    if e.get("club_id") == web_club_id and e.get("active"):
                        event_id = e.get("id")
                        break
            if not event_id:
                active = [e for e in events if e.get("active")]
                if active:
                    event_id = active[0].get("id")
        except Exception as exc:
            print(f"[CLUB_LB] fetch clubs failed: {exc}")

        entries = []
        if event_id:
            try:
                entries = self.api_client.get_leaderboard(event_id) or []
            except Exception as exc:
                print(f"[CLUB_LB] get_leaderboard({event_id}) failed: {exc}")

        # The web leaderboard is ordered by total time; championship
        # standings are ordered by points. The sort is stable, so drivers on
        # equal points keep their fastest-first order as the tiebreak.
        entries = sorted(entries, key=lambda e: -int(e.get("points", 0) or 0))

        # Convert to EgoNet format — ChampionshipLeaderboard entries use a
        # different structure than time-trial entries: Points instead of time.
        #
        # Presence rows mirror the proxied upstream captures for this endpoint
        # (captures/20260410-2034*.json, club 377197): every row is the
        # cross-platform form — IsCrossPlatform=true, NetworkId=0,
        # EgoNetId=-2, AccountRef=<account id or 0>. -2 is the sentinel the
        # game reads as "use the inline Name"; a cross-platform row with a
        # real-looking EgoNetId makes the game try to resolve the presence
        # instead, and it falls back to the "Dirt Player" placeholder when
        # that fails. Upstream's own row had AccountRef=0 too, so the own-row
        # match on this endpoint comes from PlayerRank, not AccountRef.
        egonet_entries = []
        for i, e in enumerate(entries[start_rank:start_rank + limit]):
            uname = e.get("username", "Unknown")
            acc = stable_account_id(uname)
            egonet_entries.append({
                "Presence": {
                    "Name": uname,
                    "IsCrossPlatform": True,
                    "NetworkId": 0,
                    "EgoNetId": Int64(-2),
                    "AccountRef": Int64(acc),
                },
                "Points": e.get("points", 0),
                "Rank": start_rank + i + 1,
                "IsVIP": False,
                "Nationality": UInt32(e.get("nationality_id", 0)),
            })

        player_rank = self._player_rank_in(egonet_entries)
        print(f"[CLUB_LB] club_id={club_id} event={event_id} returning "
              f"{len(egonet_entries)} entries player_rank={player_rank}")
        return {
            "ok": True,
            "TotalEntries": len(entries),
            "Entries": egonet_entries,
            "PlayerRank": player_rank,
        }

    @staticmethod
    def _announcements(params: Dict[str, Any]) -> Dict[str, Any]:
        # Real upstream returns just {"Announcements": []}
        return {
            "ok": True,
            "Announcements": [],
        }

    @staticmethod
    def _localisation(params: Dict[str, Any]) -> Dict[str, Any]:
        keys = params.get("keys", [])
        return {"ok": True, "strings": {key: key for key in keys}}

    @staticmethod
    def _cap_entries_at_stage(
        entries: List[Dict[str, Any]],
        cutoff_stage_index: int,
        start_stage_index: int = 0,
    ) -> List[Dict[str, Any]]:
        """Return entries that completed every stage in
        [start_stage_index, cutoff_stage_index].

        Each kept entry is a shallow copy annotated with ``partial_total_ms``
        (sum of ``time_ms + penalties_ms`` across stages start..cutoff
        inclusive). ``start_stage_index`` is the flat ordinal of the first
        stage of the rally being viewed, so a multi-rally championship shows
        each rally's own times instead of a running championship total.
        Entries are excluded when any stage in that range is missing, ``None``,
        or has ``time_ms <= 0``. The result is stably sorted ascending by
        ``partial_total_ms``.
        """
        kept: List[Dict[str, Any]] = []
        start_stage_index = max(0, start_stage_index)
        for e in entries:
            stages = e.get("stages") or []
            if len(stages) <= cutoff_stage_index:
                continue
            partial = 0
            ok = True
            for i in range(start_stage_index, cutoff_stage_index + 1):
                s = stages[i]
                if not s:
                    ok = False
                    break
                t = int(s.get("time_ms", 0) or 0)
                if t <= 0:
                    ok = False
                    break
                partial += t + int(s.get("penalties_ms", 0) or 0)
            if not ok:
                continue
            capped = dict(e)
            capped["partial_total_ms"] = partial
            kept.append(capped)
        kept.sort(key=lambda x: x["partial_total_ms"])
        return kept

    def _leaderboard(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if self.api_client is None:
            return {"ok": True, "TotalEntries": 0, "Entries": [], "PlayerRank": 0}

        # LeaderboardId from params — unwrap the EgoNet type wrapper
        lb_id = params.get("LeaderboardId") or params.get("leaderboard_id")
        lb_id = getattr(lb_id, "value", lb_id)
        if lb_id is None:
            return {"ok": True, "TotalEntries": 0, "Entries": [], "PlayerRank": 0}

        # ── Time Trial leaderboard ──────────────────────────────────────────
        if lb_id in self._tt_lb_map:
            vclass, track, conditions, category = self._tt_lb_map[lb_id]
            print(f"[LB] Time-trial lb_id={lb_id} -> "
                  f"vclass={vclass} track={track} conditions={conditions} cat={category}")
            try:
                entries = self.api_client.get_time_trial_leaderboard(
                    vclass, track, conditions, category
                )
            except Exception as exc:
                print(f"[LB] get_time_trial_leaderboard raised: {exc}")
                entries = []

            egonet_entries = []
            leader_ms = entries[0].get("stage_time_ms", 0) if entries else 0
            for e in entries:
                time_ms = e.get("stage_time_ms", 0)
                vid     = int(e.get("vehicle_id", 0) or 0)
                lid     = int(e.get("livery_id", 0) or 0)
                nat     = int(e.get("nationality_id", 0) or 0)
                rank    = int(e.get("rank", 0))
                uname   = e.get("username", "Unknown")
                acc     = stable_account_id(uname)
                egonet_entries.append({
                    "Presence": {
                        "Name": uname,
                        "IsCrossPlatform": False,
                        "NetworkId": 0,
                        "EgoNetId": Int64(acc),
                        "AccountRef": Int64(acc),
                    },
                    "PersonalBest":   Int64(time_ms),
                    "CumulativeBest": Int64(time_ms),
                    "TimeDiff":       Int64(time_ms - leader_ms),
                    "Rank":           rank,
                    "VehicleId":      UInt32(vid),
                    "IsFounder":      False,
                    "IsVIP":          False,
                    "Nationality":    UInt32(nat),
                    "GhostAvailable": False,
                    "LiveryId":       UInt32(lid),
                })
            player_rank = self._player_rank_in(egonet_entries)
            return {
                "ok": True,
                "TotalEntries": len(egonet_entries),
                "Entries": egonet_entries,
                "PlayerRank": player_rank,
            }

        # ── Club / championship leaderboard ────────────────────────────────
        # LeaderboardId is derived from challenge_id as chal_id+800000 (event-level)
        # or chal_id*10+N (stage-level). Try both schemes.
        event_id = None
        stage_index_for_lb: Optional[int] = None  # stage-level: FLAT ordinal
        # Flat-ordinal range of the rally (sub-event) this board belongs to.
        # Each rally of a championship is served as its own challenge, so its
        # boards must only ever total that rally's stages. range_count None
        # means "single-event / unknown": the whole flat list is one rally.
        range_start = 0
        range_count: Optional[int] = None
        # Layouts fetched during THIS request only (one web call per event);
        # nothing is kept across requests so a championship edit is always
        # picked up on the next call.
        layouts: Dict[str, List[int]] = {}

        def layout_of(eid: str) -> List[int]:
            if eid not in layouts:
                layouts[eid] = self._champ_layout(eid)
            return layouts[eid]

        chal_id = lb_id - 800000 if lb_id >= 800000 else None
        if chal_id and chal_id in self._challenge_event_map:
            event_id = self._challenge_event_map[chal_id]
            sub = self._challenge_subevent_map.get(chal_id)
            if sub is not None:
                range_start, range_count = self._subevent_range(
                    event_id, sub, layout_of(event_id))
        elif (
            (lb_id // 10) in self._challenge_event_map
            and self._challenge_subevent_map.get(lb_id // 10, 0) == 0
        ):
            # Stage ids are derived from the championship's BASE challenge id
            # (sub-event 0). A served challenge id for sub-event k is base+k,
            # so only a base id can be decoded this way; anything else goes
            # through the general decode below.
            event_id = self._challenge_event_map[lb_id // 10]
            stage_index_for_lb = lb_id % 10  # event 0: flat ordinal == stage index
            if (lb_id // 10) in self._challenge_subevent_map:
                range_start, range_count = self._subevent_range(
                    event_id, 0, layout_of(event_id))

        # Championship stage id: base_chal_id*10 + event_index*1_000_000
        # + stage_index. The map holds the SERVED id (base + event_index), so
        # recover the base first. Resolve to a FLAT ordinal so the
        # cutoff/pre-persist land on the right stage.
        if event_id is None:
            for cid, eid in self._challenge_event_map.items():
                base = cid - self._challenge_subevent_map.get(cid, 0)
                diff = lb_id - base * 10
                if diff < 0:
                    continue
                ei, si = divmod(diff, 1_000_000)
                if ei >= 100 or si >= 100:
                    continue
                layout = layout_of(eid)
                if ei >= len(layout) or si >= layout[ei]:
                    continue
                event_id = eid
                range_start = sum(layout[:ei])
                range_count = layout[ei]
                stage_index_for_lb = range_start + si
                break

        # Fallback: game may have cached an old leaderboard_id. Use the
        # first active event.
        if not event_id:
            try:
                data = self.api_client.get_clubs()
                active_events = [e for e in data.get("events", []) if e.get("active")]
                if active_events:
                    event_id = active_events[0].get("id", "")
                    print(f"[LB] Fallback: lb_id={lb_id} -> event_id={event_id}")
            except Exception as exc:
                print(f"[LB] Fallback fetch failed: {exc}")

        if not event_id:
            event_id = str(lb_id)  # last resort

        # Pre-persist the player's just-completed stage time, if any.
        # The game queries this leaderboard AFTER the stage finishes but
        # BEFORE RaceNetChallenges.StageComplete fires (the player views
        # the standings before dismissing them, which is when StageComplete
        # actually goes out). The request body carries PlayerBest (this
        # stage's time, ms) and PlayerCumulBest (cumulative), so we can
        # persist the time now and let the eventual StageComplete update
        # the same entry with damage/mud. Pass only what we actually know
        # — the rest of the stage entry is preserved by the web side from
        # the stage-begin in_progress data.
        player_best_ms = int(getattr(params.get("PlayerBest", 0), "value",
                                     params.get("PlayerBest", 0)) or 0)
        if (
            player_best_ms > 0
            and stage_index_for_lb is not None
            and event_id
        ):
            try:
                self.api_client.submit_stage(
                    event_id=event_id,
                    username="",  # web side resolves from token
                    stage_index=stage_index_for_lb,
                    time_ms=player_best_ms,
                )
                print(f"[LB] Pre-persisted player time from leaderboard query: "
                      f"event={event_id} stage={stage_index_for_lb} "
                      f"time_ms={player_best_ms}")
            except Exception as exc:
                print(f"[LB] Pre-persist raised: {exc}")

        try:
            entries = self.api_client.get_leaderboard(event_id)
        except Exception as exc:
            print(f"[LB] api_client.get_leaderboard({event_id}) raised: {exc}")
            entries = []

        # Determine the cutoff stage for capping opponents' totals. For
        # stage-level leaderboard requests the cutoff is encoded in lb_id.
        # For event-level requests we use the requesting user's max
        # completed stage so opponents who finished more stages don't look
        # artificially slower. cutoff=None means "no cap" (full totals).
        cutoff: Optional[int] = None
        range_end = (range_start + range_count) if range_count else None
        if stage_index_for_lb is not None:
            cutoff = stage_index_for_lb
        else:
            me = self._resolve_my_username()
            if me:
                my_entry = next(
                    (e for e in entries if e.get("username") == me), None
                )
                if my_entry:
                    max_idx = -1
                    for i, s in enumerate(my_entry.get("stages") or []):
                        if i < range_start or (range_end is not None and i >= range_end):
                            continue
                        if s and int(s.get("time_ms", 0) or 0) > 0:
                            max_idx = i
                    if max_idx >= 0:
                        cutoff = max_idx
            # A rally the player hasn't started yet: show the finished-rally
            # standings rather than the whole championship's running totals.
            if cutoff is None and range_end is not None:
                cutoff = range_end - 1

        if cutoff is not None:
            source = self._cap_entries_at_stage(entries, cutoff, range_start)
            use_partial = True
        else:
            source = entries
            use_partial = False

        leader_ms = 0
        if source:
            if use_partial:
                leader_ms = int(source[0]["partial_total_ms"])
            else:
                leader_ms = int(source[0].get("total_time_ms", 0) or 0)

        egonet_entries = []
        for i, e in enumerate(source):
            if use_partial:
                total_ms = int(e["partial_total_ms"])
            else:
                total_ms = int(e.get("total_time_ms", 0) or 0)
            vehicle_id = e.get("vehicle_id", 0)
            if not isinstance(vehicle_id, int):
                vehicle_id = 0
            uname = e.get("username", "Unknown")
            acc = stable_account_id(uname)
            egonet_entries.append({
                "Presence": {
                    "Name": uname,
                    "IsCrossPlatform": False,
                    "NetworkId": Int64(0),
                    "EgoNetId": Int64(acc),
                    "AccountRef": Int64(acc),
                },
                "PersonalBest":   Int64(total_ms),
                "CumulativeBest": Int64(total_ms),
                "TimeDiff":       Int64(total_ms - leader_ms),
                "Rank":           (i + 1) if use_partial else e.get("rank", i + 1),
                "VehicleId":      UInt32(vehicle_id),
                "IsFounder":      False,
                "IsVIP":          False,
                "Nationality":    UInt32(0),
                "GhostAvailable": False,
                "LiveryId":       UInt32(0),
            })
        player_rank = self._player_rank_in(egonet_entries)
        return {
            "ok": True,
            "TotalEntries": len(egonet_entries),
            "Entries": egonet_entries,
            "PlayerRank": player_rank,
        }

    def _time_trial_id(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle TimeTrial.GetLeaderboardId.

        Returns a stable numeric LeaderboardId for the (vclass, track,
        conditions, category) 4-tuple.  When api_client is available, the ID
        is fetched from the web server so it stays consistent across restarts.
        Falls back to a local md5-based hash when no api_client is set.
        """
        def _extract(key: str) -> int:
            v = params.get(key, 0)
            return int(getattr(v, "value", v) or 0)

        vclass     = _extract("VehicleClassId")
        track      = _extract("TrackModelId")
        conditions = _extract("ConditionsId")
        category   = _extract("Category")

        tt_tuple = (vclass, track, conditions, category)
        self._last_tt_request = tt_tuple

        if self.api_client is not None:
            try:
                lb_id = self.api_client.get_time_trial_leaderboard_id(
                    vclass, track, conditions, category
                )
                if lb_id is not None:
                    self._tt_lb_map[lb_id] = tt_tuple
                    print(f"[TT] GetLeaderboardId vclass={vclass} track={track} "
                          f"conditions={conditions} cat={category} -> lb_id={lb_id}")
                    return {"ok": True, "ShouldPost": True, "LeaderboardId": Int64(lb_id)}
            except Exception as exc:
                print(f"[TT] get_time_trial_leaderboard_id raised: {exc}")

        # Local fallback: deterministic hash in the 4_000_000 base range
        lb_id = _stable_int_id(
            f"tt-{vclass}-{track}-{conditions}-{category}", base=4_000_000
        )
        self._tt_lb_map[lb_id] = tt_tuple
        print(f"[TT] GetLeaderboardId (local) vclass={vclass} track={track} "
              f"conditions={conditions} cat={category} -> lb_id={lb_id}")
        return {"ok": True, "ShouldPost": True, "LeaderboardId": Int64(lb_id)}

    def _post_time(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle TimeTrial.PostTime.

        Extracts stage time and related fields from the EgoNet params, then
        submits them to the web API via api_client.  Always returns Accepted.
        """
        def _extract(key: str, default: Any = 0) -> Any:
            v = params.get(key, default)
            return getattr(v, "value", v)

        vehicle_id    = int(_extract("VehicleId", 0) or 0)
        livery_id     = int(_extract("LiveryId", 0) or 0)
        track         = int(_extract("TrackModelId", 0) or 0)
        nationality   = int(_extract("NationalityId", 0) or 0)
        conditions    = int(_extract("ConditionsId", 0) or 0)
        category      = int(_extract("Category", 0) or 0)
        using_wheel   = bool(_extract("UsingWheel", False))
        using_assists = bool(_extract("UsingAssists", False))
        stage_time_f  = float(_extract("StageTime", 0.0) or 0.0)
        stage_time_ms = int(stage_time_f * 1000)

        # Ghost data is a raw bytes blob in the EgoNet params
        import base64
        ghost_raw = params.get("GhostData", b"")
        if isinstance(ghost_raw, (bytes, bytearray)):
            ghost_b64 = base64.b64encode(ghost_raw).decode("ascii")
        else:
            ghost_b64 = str(ghost_raw)

        # VehicleClassId is not sent in PostTime — recover from the cached
        # GetLeaderboardId call for this session, or fall back to the class
        # baked into VehicleId. The cache is empty on a fresh dispatcher
        # session (host restart, alternate code path that skips
        # GetLeaderboardId), so without the vehicle fallback the time gets
        # filed under vclass=0 and shows up as "Class 0" on the web board.
        vclass = 0
        if self._last_tt_request is not None:
            vclass = self._last_tt_request[0]
        if vclass == 0 and vehicle_id in VEHICLES:
            vclass = VEHICLES[vehicle_id]["class"]

        entry_id = secrets.token_hex(8)

        if self.api_client is not None and stage_time_ms > 0:
            try:
                ok = self.api_client.submit_time_trial(
                    vehicle_class_id=vclass,
                    track_model_id=track,
                    conditions_id=conditions,
                    category=category,
                    vehicle_id=vehicle_id,
                    livery_id=livery_id,
                    stage_time_ms=stage_time_ms,
                    nationality_id=nationality,
                    using_wheel=using_wheel,
                    using_assists=using_assists,
                    ghost_data_b64=ghost_b64,
                )
                if ok:
                    print(f"[TT] PostTime accepted: vclass={vclass} track={track} "
                          f"time_ms={stage_time_ms} entry_id={entry_id}")
                else:
                    print(f"[TT] PostTime: submit_time_trial returned False "
                          f"(vclass={vclass} track={track} time_ms={stage_time_ms})")
            except Exception as exc:
                print(f"[TT] submit_time_trial raised: {exc}")

        return {"ok": True, "Accepted": True, "EntryId": entry_id}

    @staticmethod
    def _status(params: Dict[str, Any]) -> Dict[str, Any]:
        # Real upstream returns empty body with X-EgoNet-Result=1
        return {"ok": True, "result_code": "1"}

    @staticmethod
    def _advertising_enabled(params: Dict[str, Any]) -> Dict[str, Any]:
        # Real field name: IsEnabled (not Enabled)
        return {"ok": True, "IsEnabled": False}

    @staticmethod
    def _vanity_flags(params: Dict[str, Any]) -> Dict[str, Any]:
        # Real field name: VanityFlags (not Flags)
        return {"ok": True, "VanityFlags": 0}

    @staticmethod
    def _staff(params: Dict[str, Any]) -> Dict[str, Any]:
        # Real upstream has detailed staff structure
        # Use template if available, otherwise return minimal valid structure
        template = _load_template("Staff.GetStaff")
        if template:
            return template  # type: ignore[return-value]
        return {
            "ok": True,
            "ChiefEngineer": {
                "ChiefEngineerId": 1,
                "ResearchLevel": 1,
                "DiagnosticLevel": 1,
                "ResearchUpCost": 100000,
                "DiagUpCost": 100000,
            },
            "Engineers": [
                {
                    "EngineerId": 1,
                    "EngineLevel": 1,
                    "ChassisLevel": 1,
                    "DrivetrainLevel": 1,
                    "RepairLevelFwd": 1,
                    "RepairLevelRwd": 1,
                    "RepairLevel4wd": 1,
                    "EngineUpCost": 100000,
                    "ChassisUpCost": 100000,
                    "DriveUpCost": 100000,
                    "RepairFwdUpCost": 100000,
                    "RepairRwdUpCost": 100000,
                    "Repair4wdUpCost": 100000,
                },
            ],
            "NextEngCost": 100000,
            "CoDriver": {
                "CoDriverId": 1,
                "WheelLevel": 1,
                "LogisticsLevel": 1,
                "RepairLevel": 1,
                "WheelUpCost": 100000,
                "LogisticsUpCost": 100000,
                "RepairUpCost": 100000,
            },
            "RxSpotter": 1,
        }

    def _inventory(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Return the player's inventory.

        When api_client is set, fetch the player's game profile from
        dirtforever.net and use real per-user currency/slot values.
        Falls back to a zero-balance stub when no api_client is configured
        or the profile fetch fails.
        """
        soft_currency = 0
        hard_currency = 0
        garage_slots = 8
        garage: Dict[str, Any] = {}

        if self.api_client is not None:
            try:
                profile = self.api_client.get_profile()
            except Exception as exc:
                print(f"[INVENTORY] api_client.get_profile() raised: {exc}")
                profile = None

            if profile:
                soft_currency = int(profile.get("soft_currency", 500000))
                hard_currency = int(profile.get("hard_currency", 0))
                garage_slots = int(profile.get("garage_slots", 8))
                garage = profile.get("garage") or {}
            else:
                # Profile fetch failed — give starter credits so the game is playable
                soft_currency = 500000

        return {
            "ok": True,
            "Inventory": {
                "SoftCurrency": soft_currency,
                "HardCurrency": hard_currency,
                "GarageSlots": 100,
                "Vehicles": self._all_vehicles(garage),
                "Upgrades": [],
                "Entitlements": [],
                "Liveries": [],
                "SeasonFlags": UInt32(15),
            },
        }

    @staticmethod
    def _all_vehicles(garage: Optional[Dict[str, Any]] = None) -> list:
        """Generate a full garage with every known vehicle, undamaged and ready.

        ``garage`` maps VehicleInstId (str) -> {tuning_id, livery_id} for the
        engine tuning / livery the player fitted, so a fitted setup persists
        across restarts instead of every vehicle reverting to TuningId/LiveryId
        0.  The instance id is the vehicle's ``Id`` field (idx + 1)."""
        garage = garage or {}
        # All vehicle IDs from the upstream inventory capture
        vehicle_ids = [
            382, 395, 396, 399, 400, 401, 468, 469, 470, 471,
            478, 480, 482, 483, 484, 485, 490, 502, 504, 511,
            513, 527, 529, 530, 531, 532, 533, 534, 535, 536,
            537, 538, 541, 543, 547, 548, 550, 554, 555, 556,
            557, 558, 559, 560, 561, 562, 563, 564, 565, 566,
            567, 569, 570, 571, 572, 573, 574, 575, 576, 577,
            578, 579, 580, 581, 582, 585, 586, 587, 588, 589,
            590, 593, 597, 600,
        ]
        vehicles = []
        for idx, vid in enumerate(vehicle_ids):
            inst_id = idx + 1
            fitted = garage.get(str(inst_id), {}) if garage else {}
            livery_id = int(fitted.get("livery_id", 0) or 0)
            tuning_id = int(fitted.get("tuning_id", 0) or 0)
            vehicles.append({
                "VehicleId": UInt32(vid),
                "LiveryId": UInt32(livery_id),
                "TuningId": UInt32(tuning_id),
                "UpgAvailable": 127,
                "UpgEnabled": 127,
                "TuningReady": 15,
                "TuningPurchased": 63,
                "IsNew": False,
                "IsRepairFree": True,
                "IsSellable": False,
                "Damage": {
                    "QuickRepairs": 0, "Bodywork": 0.0, "Brakes": 0.0,
                    "Gearbox": 0.0, "Differential": 0.0, "Wheels": 0.0,
                    "Engine": 0.0, "Radiator": 0.0, "Turbo": 0.0,
                    "Exhaust": 0.0, "Dampers": 0.0, "Clutch": 0.0,
                    "Springs": 0.0, "Lights": 0.0,
                },
                "CompDamage": {
                    "WheelsWear": UInt32(0), "Turbo": UInt32(0),
                    "Springs": UInt32(0), "Radiator": 0.0,
                    "Lights": 0.0, "Gearbox": UInt32(0),
                    "WheelsImpact": UInt32(0), "Exhaust": 0.0,
                    "DiffImpact": UInt32(0), "DiffWear": UInt32(0),
                    "Dampers": UInt32(0), "Clutch": 0.0,
                    "Brakes": UInt32(0), "Bodywork": UInt32(0),
                    "Engine": 0.0, "QuickRepairs": 0,
                },
                "SellPrice": 0,
                "ResearchTarget": UInt32(0),
                "ResearchPercent": 1.0,
                "IsLocked": False,
                "LockChallengeId": 0,
                "LockEntity": Int64(0),
                "LockReason": 0,
                "LockExpiry": Timestamp(0),
                "LockLocation": UInt32(0),
                "DistanceDriven": 0,
                "Podiums": 0,
                "EventsEntered": 0,
                "EventsFinished": 0,
                "Terminals": 0,
                "Id": Int64(inst_id),
            })
        return vehicles

    @staticmethod
    def _store(params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "ok": True,
            "Products": [],
            "RefreshSeconds": 3600,
            "CurrencyFilter": int(params.get("CurrencyFilter", 0) or 0),
        }

    @staticmethod
    def _rewards(params: Dict[str, Any]) -> Dict[str, Any]:
        # Real upstream returns just {"Rewards": []}
        return {"ok": True, "Rewards": []}

    # -- Repairs.* write actions ------------------------------------------
    # These are performed synchronously from the vehicle-prep UI and the
    # client validates the response body.  Shapes captured from real upstream
    # (159.153.126.42) on 2026-08-23:
    #   Repairs.SetLivery {VehicleInstId, LiveryId}      -> {"Result": 0}
    #   Repairs.FitTuning {VehicleInstId, EngineTuningId}-> {"Cost": N, "Result": 0}
    #   Repairs.PerformRepairs {per-part levels}         -> {"Result": 0,
    #        "Cost": N, "Damage": {..14 floats..},
    #        "CompDamage": {..16 fields..}, "NewSellPrice": N}
    # ``Cost`` is what the server charged; we return 0 so the community server
    # applies liveries/tuning/repairs for free (Result 0 is the success flag).

    def _repairs_set_livery(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # Persist the garage livery so GetInventory reflects it after a
        # restart.  VehicleInstId is the inventory instance id; the web side
        # ignores transient (<= 0) ids.
        inst = int(_val(params.get("VehicleInstId", 0)) or 0)
        livery = int(_val(params.get("LiveryId", 0)) or 0)
        if self.api_client is not None and inst > 0:
            try:
                self.api_client.set_garage(inst, livery_id=livery)
            except Exception as exc:
                print(f"[REPAIRS] SetLivery persist raised: {exc}")
        return {"ok": True, "Result": 0}

    def _repairs_fit_tuning(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # Persist the fitted engine tuning so GetInventory reflects it after a
        # restart.  EngineTuningId maps to the vehicle's inventory TuningId.
        inst = int(_val(params.get("VehicleInstId", 0)) or 0)
        tuning = int(_val(params.get("EngineTuningId", 0)) or 0)
        if self.api_client is not None and inst > 0:
            try:
                self.api_client.set_garage(inst, tuning_id=tuning)
            except Exception as exc:
                print(f"[REPAIRS] FitTuning persist raised: {exc}")
        return {"ok": True, "Result": 0, "Cost": 0}

    def _repairs_perform(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # Return the vehicle fully repaired (all damage zeroed): the client
        # applies the returned Damage/CompDamage to the car.  Field layout
        # mirrors the per-vehicle blocks in _all_vehicles().
        damage = {
            "QuickRepairs": 0, "Bodywork": 0.0, "Brakes": 0.0,
            "Gearbox": 0.0, "Differential": 0.0, "Wheels": 0.0,
            "Engine": 0.0, "Radiator": 0.0, "Turbo": 0.0,
            "Exhaust": 0.0, "Dampers": 0.0, "Clutch": 0.0,
            "Springs": 0.0, "Lights": 0.0,
        }
        comp_damage = {
            "WheelsWear": UInt32(0), "Turbo": UInt32(0),
            "Springs": UInt32(0), "Radiator": 0.0,
            "Lights": 0.0, "Gearbox": UInt32(0),
            "WheelsImpact": UInt32(0), "Exhaust": 0.0,
            "DiffImpact": UInt32(0), "DiffWear": UInt32(0),
            "Dampers": UInt32(0), "Clutch": 0.0,
            "Brakes": UInt32(0), "Bodywork": UInt32(0),
            "Engine": 0.0, "QuickRepairs": 0,
        }
        return {
            "ok": True,
            "Result": 0,
            "Cost": 0,
            "Damage": damage,
            "CompDamage": comp_damage,
            "NewSellPrice": 0,
        }

    def _get_challenges(self, params: Dict[str, Any]) -> Union[Dict[str, Any], bytes]:
        """Serve the Events page (RaceNetChallenges.GetChallenges).

        Real RaceNet returned the official daily/weekly/monthly challenges
        here — separate from club championships, which live in Clubs.GetClubs.
        We build the same shape from the web API's active non-club events.

        Without an api_client (local-only mode) fall back to the captured
        upstream template: its entry windows have long expired so the game
        shows an empty Events page, but the payload is structurally valid —
        the exact behaviour this handler had before officials were wired up.
        """
        if self.api_client is None:
            template = _load_template("RaceNetChallenges.GetChallenges")
            if template:
                return template
            return {"ok": True, "Challenges": [], "Progress": []}

        challenges, web_events = self._official_challenges_from_api()
        return {
            "ok": True,
            "Challenges": challenges,
            "Progress": self._build_user_progress(web_events),
        }

    def _official_challenges_from_api(
        self,
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Convert active official (non-club) web events to EgoNet Challenges.

        Returns ``(challenges_egonet, web_events_served)``. Populates
        ``_challenge_event_map`` for each served challenge so StageBegin /
        StageComplete / leaderboard lookups can route back to the web event.

        Fixed field values (ClubId=0, ChallengeType=1, ScoringType=0, Mode=0,
        UseInvVehicle=True, the lng_* display names, the Category tab ids and
        the 10-minute EntryWindow submit grace) all mirror the real upstream
        GetChallenges capture in data/upstream_templates/.
        """
        assert self.api_client is not None
        try:
            web_events = self.api_client.get_challenges()
        except Exception as exc:
            print(f"[CHALLENGES] api_client.get_challenges() raised: {exc}")
            return [], []

        challenges_egonet: List[Dict[str, Any]] = []
        served: List[Dict[str, Any]] = []
        for idx, wevt in enumerate(web_events):
            wevt_id = wevt.get("id", f"official-{idx}")
            chal_id = _stable_int_id(wevt_id, base=400000, offset=idx)

            car_class_label: str = wevt.get("car_class", "")
            vclass_id = self.api_client.resolve_vclass_id(car_class_label)
            # Same rule as clubs: an unmappable class would produce an invalid
            # Requirement, which crashes the game — skip rather than guess.
            if vclass_id is None or vclass_id not in CONFIRMED_VEHICLE_CLASS_IDS:
                print(f"[CHALLENGES] Unmappable car class '{car_class_label}' "
                      f"for official event {wevt_id} — skipping")
                continue

            events_out = self._build_events_for_champ(wevt, chal_id)
            if not events_out:
                print(f"[CHALLENGES] No resolvable events for {wevt_id} — skipping")
                continue

            self._challenge_event_map[chal_id] = wevt_id

            window = self._window_for(wevt)
            # Upstream officials keep submissions open 600s past LastEntry
            # (End = LastEntry + 600 on every challenge in the capture).
            window.end = window.last_entry + 600

            etype = str(wevt.get("type", "") or "")
            settings = wevt.get("settings") or {}
            challenges_egonet.append(Challenge(
                name=_OFFICIAL_NAME_KEYS.get(etype, wevt.get("name", "Community Challenge")),
                challenge_type=1,
                scoring_type=0,
                challenge_id=chal_id,
                club_id=0,
                requirements=[{"Type": 1, "Value": UInt32(vclass_id)}],
                events=events_out,
                entry_window=window,
                num_entrants=len(wevt.get("entries", [])) if "entries" in wevt else 0,
                leaderboard_id=chal_id + 800000,
                is_hardcore=bool(settings.get("hardcore_damage", True)),
                exterior_cams=not bool(settings.get("force_cockpit_camera", False)),
                allow_assists=bool(settings.get("allow_assists", True)),
                unxpectd_moments=bool(settings.get("unexpected_moments", True)),
                category=_OFFICIAL_CATEGORY.get(etype, _OFFICIAL_CATEGORY_SPECIAL),
                mode=0,
                use_inv_vehicle=True,
                max_event_credits=_OFFICIAL_MAX_CREDITS.get(
                    etype, Challenge().max_event_credits),
            ).to_egonet())
            served.append(wevt)

        return challenges_egonet, served

    def _resolve_event_id(self, challenge_id: int, label: str) -> Optional[str]:
        """Map a numeric challenge_id back to a web event_id.

        ``_challenge_event_map`` is in-memory only and gets reset when the
        server restarts. If the game has a cached challenge_id from before
        the restart, we won't find it on the first request — repopulate the
        map by re-fetching the clubs list, then try again.

        If the challenge_id still isn't found, return None instead of
        falling back to a random event. Writing a stage submission to the
        wrong event id silently corrupts that event's leaderboard and the
        Progress/Tuning state for the actual event the player was in.
        """
        if self.api_client is None:
            return None
        event_id = self._challenge_event_map.get(challenge_id)
        if event_id:
            return event_id
        print(f"[STAGE] {label} unknown challenge_id={challenge_id} "
              f"(map has {len(self._challenge_event_map)} entries); "
              f"refreshing from clubs + challenges APIs")
        try:
            self._clubs_from_api()
        except Exception as exc:
            print(f"[STAGE] {label} clubs refresh raised: {exc}")
        # Official (Events page) challenges live in a different feed — refresh
        # it too so a game-cached official challenge_id survives a restart.
        self._official_challenges_from_api()
        event_id = self._challenge_event_map.get(challenge_id)
        if event_id:
            print(f"[STAGE] {label} resolved after refresh: event_id={event_id}")
            return event_id
        print(f"[STAGE] {label} challenge_id={challenge_id} not in any known "
              f"event after refresh; refusing to misroute submission")
        return None

    def get_streaming_state(self) -> Dict[str, Any]:
        """Read-only snapshot consumed by the OBS/SimHub overlay writer."""
        return {
            "event_id": self._current_event_id,
            "club_id": self._current_club_id,
            "vehicle_id": self._current_vehicle_id,
            "clubs_snapshot": self._clubs_snapshot,
        }

    def _champ_layout(self, event_id: str) -> List[int]:
        """Stage counts per sub-event for a championship; [] if unknown.

        For legacy / single-event events this is ``[len(stages)]``, so callers
        that sum it get the same number the old single-event path produced.
        """
        if self.api_client is None or not event_id:
            return []
        try:
            evt = self.api_client.get_event(event_id)
        except Exception as exc:
            print(f"[STAGE] get_event({event_id}) raised: {exc}")
            return []
        if not evt:
            return []
        evs = evt.get("events")
        if evs:
            return [len(ev.get("stages", []) or []) for ev in evs]
        return [len(evt.get("stages", []) or [])]

    def _stage_offset(self, event_id: str, event_index: int) -> int:
        """Flat-ordinal offset for the first stage of sub-event ``event_index``.

        Zero for event_index 0 (no fetch), so the single-event path is
        unchanged; otherwise the sum of earlier sub-events' stage counts.
        """
        if event_index <= 0:
            return 0
        return sum(self._champ_layout(event_id)[:event_index])

    def _subevent_range(self, event_id: str, event_index: int,
                        layout: Optional[List[int]] = None) -> tuple[int, Optional[int]]:
        """``(offset, count)`` flat-ordinal range of sub-event ``event_index``;
        count is None when the layout is unknown. Pass ``layout`` when the
        caller already fetched it so a request doesn't hit the web twice."""
        if layout is None:
            layout = self._champ_layout(event_id)
        if not layout or event_index < 0 or event_index >= len(layout):
            return 0, None
        return sum(layout[:event_index]), layout[event_index]

    @staticmethod
    def _time_in_range(completed_stages: List[Dict[str, Any]],
                       offset: int, count: Optional[int]) -> int:
        """Sum of completed-stage times whose flat ``stage_index`` falls in
        this rally's range. Each rally is its own challenge, so its
        ChampTimeMs must not carry earlier rallies' times."""
        total = 0
        for s in completed_stages:
            idx = int(s.get("stage_index", 0) or 0)
            if idx < offset or (count is not None and idx >= offset + count):
                continue
            total += int(s.get("time_ms", 0) or 0)
        return total

    def _total_stages_for_event(self, event_id: str) -> int:
        """Total configured stage count across ALL sub-events (championship
        total). 0 if unknown; equals the stage count for single-event events."""
        return sum(self._champ_layout(event_id))

    def _stage_begin(self, params: Dict[str, Any]) -> Dict[str, Any]:
        import base64
        req = StageBeginRequest.from_egonet(params)
        print(f"[STAGE] Begin: challenge={req.challenge_id} event={req.event_index} "
              f"stage={req.stage_index} vehicle={req.vehicle_id} livery={req.livery_id} "
              f"tyres={req.tyres_remaining} compound={req.tyre_compound}")

        event_id = self._resolve_event_id(req.challenge_id, "Begin")
        # The game always reports event_index=0 (each championship event is a
        # separate challenge); recover the real sub-event from the challenge_id.
        sub_index = self._challenge_subevent_map.get(req.challenge_id, req.event_index)
        # Flat championship-wide stage ordinal; == stage_index for event 0.
        gidx = req.stage_index + (self._stage_offset(event_id, sub_index) if event_id else 0)

        if event_id:
            self._current_event_id = event_id
        if req.vehicle_id:
            self._current_vehicle_id = req.vehicle_id
        if event_id and self._clubs_snapshot:
            for evt in self._clubs_snapshot.get("events", []) or []:
                if evt.get("id") == event_id:
                    self._current_club_id = evt.get("club_id") or self._current_club_id
                    break
        if self.verbose_logging:
            print(f"[STREAM] dispatcher: stage_begin set "
                  f"event_id={self._current_event_id!r} "
                  f"club_id={self._current_club_id!r} "
                  f"vehicle_id={self._current_vehicle_id!r}")

        # Persist the pre-stage setup so my-progress reflects it for later calls.
        if event_id and self.api_client is not None:
            tuning_b64 = base64.b64encode(req.tuning_setup).decode("ascii") if req.tuning_setup else ""
            try:
                self.api_client.submit_stage_begin(
                    event_id=event_id,
                    stage_index=req.stage_index,
                    event_index=sub_index,
                    vehicle_id=req.vehicle_id if req.vehicle_id else None,
                    livery_id=req.livery_id,
                    tuning_setup_b64=tuning_b64,
                    tyre_compound=req.tyre_compound,
                    tyres_remaining=req.tyres_remaining,
                    nationality_id=req.nationality_id,
                )
            except Exception as exc:
                print(f"[STAGE] Begin api_client.submit_stage_begin() raised: {exc}")

        # Build the Progress block that will be relayed back to the client.
        # The client uses this as the source of truth for the stage-start UI,
        # so values must reflect the persisted state of prior completed stages
        # (damage, ChampTimeMs) and echo the request for this stage's setup
        # (Vehicle/Livery/Tyres/Tuning).
        ep = self._user_progress_for_event(event_id) if event_id else None
        completed_stages = (ep or {}).get("completed_stages", []) if ep else []
        # Only THIS rally's earlier stages count: each rally of a championship
        # is its own challenge, so its time (and damage) starts from zero.
        rally_offset = gidx - req.stage_index
        prior_completed = [
            s for s in completed_stages
            if rally_offset <= int(s.get("stage_index", 0) or 0) < gidx
        ]
        last_prior = prior_completed[-1] if prior_completed else None

        if last_prior is not None:
            vehicle_damage = self._damage_from_dict(last_prior.get("vehicle_damage"))
            champ_time_ms = sum(int(s.get("time_ms", 0) or 0) for s in prior_completed)
        else:
            vehicle_damage = self._damage_from_dict(None)  # all zeros
            champ_time_ms = 0

        progress = self._build_progress_dict(
            challenge_id=req.challenge_id,
            target_stage_index=req.stage_index,
            state=1,  # 1 = stage active/in-progress
            vehicle_id=req.vehicle_id or 0,
            livery_id=req.livery_id or 0,
            meters_driven=0,  # fresh stage start
            champ_time_ms=champ_time_ms,
            has_repaired=False,
            repair_penalty_ms=0,
            vehicle_damage=vehicle_damage,
            tyre_compound=req.tyre_compound,
            tyres_remaining=req.tyres_remaining,
            tuning_bytes=req.tuning_setup or self._decode_tuning_b64(""),
            attempts_left=self._attempts_left_for(ep),
        )

        return {"ok": True, "Progress": progress, "ResultCode": 0}

    def _stage_complete(self, params: Dict[str, Any]) -> Dict[str, Any]:
        import dataclasses
        req = StageCompleteRequest.from_egonet(params)
        print(f"[STAGE] Complete: challenge={req.challenge_id} event={req.event_index} "
              f"stage={req.stage_index} time={req.stage_time:.3f}s "
              f"distance={req.meters_driven}m status={req.race_status} "
              f"wheel={req.using_wheel} assists={req.using_assists}")

        event_id = self._resolve_event_id(req.challenge_id, "Complete")
        # Recover the real sub-event index (the game always sends event_index=0).
        sub_index = self._challenge_subevent_map.get(req.challenge_id, req.event_index)

        # Convert the request payloads back to plain dicts for the API call.
        mud_dict = dataclasses.asdict(req.vehicle_mud)
        dmg_dict = dataclasses.asdict(req.comp_damage)
        _qr = getattr(req.comp_damage.quick_repairs, "value", req.comp_damage.quick_repairs)
        has_repaired = req.recov_to_service or _qr > 0
        time_ms = int(req.stage_time * 1000)

        # Persist if we have a target event AND the stage was finished cleanly.
        # DNF/restart submissions (race_status != 0) are skipped for the
        # leaderboard, but we still build a Progress response below.
        if event_id and self.api_client is not None and req.race_status == 0:
            try:
                self.api_client.submit_stage(
                    event_id=event_id,
                    username="",  # server uses g.game_user from token
                    stage_index=req.stage_index,
                    event_index=sub_index,
                    time_ms=time_ms,
                    vehicle_id=req.vehicle_id if req.vehicle_id else None,
                    meters_driven=req.meters_driven,
                    distance_driven=req.distance_driven,
                    vehicle_mud=mud_dict,
                    comp_damage=dmg_dict,
                    using_wheel=req.using_wheel,
                    using_assists=req.using_assists,
                    race_status=req.race_status,
                    nationality_id=req.nationality_id,
                    livery_id=req.livery_id,
                    has_repaired=has_repaired,
                    repair_penalty_ms=0,  # client doesn't send this directly
                )
                print(f"[STAGE] Submitted to API: event={event_id} "
                      f"stage={req.stage_index} time_ms={time_ms}")
            except Exception as exc:
                print(f"[STAGE] api_client.submit_stage() raised: {exc}")
        elif req.race_status != 0:
            print(f"[STAGE] Not submitting (race_status={req.race_status}, not finished)")
        elif not event_id:
            print(f"[STAGE] Cannot submit — no event_id available")

        # Build the Progress block to relay back. Source-of-truth values:
        #   - VehicleDamage / VehicleMud / Meters: this StageComplete request
        #     (the just-submitted state IS the new persisted state)
        #   - TuningSetup: the most recent stored setup for this event/user;
        #     unchanged at stage end
        #   - ChampTimeMs: sum of all completed-stage times (including this one
        #     if persisted)
        ep = self._user_progress_for_event(event_id) if event_id else None
        completed_stages = (ep or {}).get("completed_stages", []) if ep else []
        # Judge completion against THIS event's own stage count: a multi-event
        # championship serves one event per challenge (each with its own stages),
        # so the championship-wide total would tell the client to advance to a
        # stage the served challenge doesn't have — which crashes the game.
        # One layout fetch for this request; reused for the ChampTimeMs range.
        _layout = self._champ_layout(event_id) if event_id else []
        if req.challenge_id in self._challenge_subevent_map:
            event_stage_count = _layout[sub_index] if 0 <= sub_index < len(_layout) else 0
        else:
            event_stage_count = sum(_layout)

        # The StageComplete request doesn't carry TuningSetup / TyreCompound /
        # TyresRemaining — those were set at StageBegin and persisted by the
        # web side under the in_progress key, then merged into the stage entry.
        # Pull them from the latest completed stage entry (just-submitted on
        # the happy path, prior stage on DNF). Fall back to defaults when the
        # web fetch hasn't seen our submission yet.
        latest = completed_stages[-1] if completed_stages else {}
        tuning_bytes = self._decode_tuning_b64(latest.get("tuning_setup_b64", "") or "")
        tyre_compound = int(latest.get("tyre_compound", 0) or 7)
        tyres_remaining = int(latest.get("tyres_remaining", 0) or 2)

        if req.challenge_id in self._challenge_subevent_map:
            # Per-event challenge: this event's stages complete in order, so the
            # local (0-based) index reaching the event's count means it's done.
            completed_in_event = (req.stage_index + 1) if req.race_status == 0 else req.stage_index
            all_done = event_stage_count > 0 and completed_in_event >= event_stage_count
        else:
            all_done = event_stage_count > 0 and len(completed_stages) >= event_stage_count
        if all_done:
            target_stage_index = event_stage_count - 1
            state_out = 2  # event finished
        else:
            target_stage_index = req.stage_index + 1
            state_out = 0  # between stages, ready for next StageBegin

        # ChampTimeMs: this rally's stages only (each rally is its own
        # challenge). Add this stage's time if the web fetch hasn't seen the
        # submission yet.
        if req.challenge_id in self._challenge_subevent_map and event_id:
            rally_offset, rally_count = self._subevent_range(event_id, sub_index, _layout)
        else:
            rally_offset, rally_count = 0, None
        gidx = rally_offset + req.stage_index
        champ_time_ms = self._time_in_range(completed_stages, rally_offset, rally_count)
        if req.race_status == 0 and not any(
            int(s.get("stage_index", 0) or 0) == gidx for s in completed_stages
        ):
            champ_time_ms += time_ms

        progress = self._build_progress_dict(
            challenge_id=req.challenge_id,
            target_stage_index=target_stage_index,
            state=state_out,
            vehicle_id=req.vehicle_id or 0,
            livery_id=req.livery_id or 0,
            meters_driven=req.meters_driven or 0,
            champ_time_ms=champ_time_ms,
            has_repaired=has_repaired,
            repair_penalty_ms=0,
            vehicle_damage=self._damage_from_dict(dmg_dict),
            tyre_compound=tyre_compound,
            tyres_remaining=tyres_remaining,
            tuning_bytes=tuning_bytes,
            attempts_left=self._attempts_left_for(ep),
            vehicle_mud=self._mud_from_dict(mud_dict),
        )

        # Reward / research fields all zero — matches mid-event upstream shape.
        # When the user completes the final stage of an event, real upstream
        # presumably returns populated rewards; we have no capture of that yet,
        # so we keep zeros for now (rewards UI will show empty post-event).
        return {
            "ok": True,
            "Progress":        progress,
            "EventReward":     self._zero_reward(),
            "ChampReward":     self._zero_reward(),
            "ResearchTarget":  UInt32(0),
            "ResearchPercent": 0.0,
            "OldResearchTgt":  UInt32(0),
            "OldResearchPct":  0.0,
            "ResultCode":      0,
        }

    @staticmethod
    def _stage_splits(params: Dict[str, Any]) -> Dict[str, Any]:
        return {"ok": True, "Splits": [], "Entries": []}

    @staticmethod
    def _rally_tier_list(params: Dict[str, Any]) -> Dict[str, Any]:
        # Real upstream structure: double-nested TierList with only DriverID per entry
        tier_entries = [{"DriverID": i} for i in range(150)]
        return {
            "ok": True,
            "TierList": {
                "TierList": tier_entries,
                "PrevPlayerTier": 0,
                "PlayerTier": 0,
            },
        }

    @staticmethod
    def _rallycross_tier_list(params: Dict[str, Any]) -> Dict[str, Any]:
        tier_entries = [{"DriverID": i} for i in range(100)]
        return {
            "ok": True,
            "TierList": {
                "TierList": tier_entries,
                "PrevPlayerTier": 0,
                "PlayerTier": 0,
            },
        }

    @staticmethod
    def _season(params: Dict[str, Any]) -> Dict[str, Any]:
        # Real upstream returns {"SeasonId": 5}
        return {
            "ok": True,
            "SeasonId": 5,
        }

    @staticmethod
    def _esports_enabled(params: Dict[str, Any]) -> Dict[str, Any]:
        return {"ok": True, "IsEnabled": False}

    @staticmethod
    def _esports_activity(params: Dict[str, Any]) -> Dict[str, Any]:
        # Real upstream: {"IsActive": false, "Type": 0}
        return {"ok": True, "IsActive": False, "Type": 0}

    @staticmethod
    def _esports_terms_status(params: Dict[str, Any]) -> Dict[str, Any]:
        return {"ok": True, "Accepted": True}
