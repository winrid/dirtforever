from __future__ import annotations

import secrets
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from .account_store import AccountStore
from .api_client import DirtForeverClient
from .egonet import Int64, Timestamp, UInt16, UInt32, UInt8
from .game_data import Location, Track
from .models import (
    Challenge, Club, CompDamage, EntryWindow, Event, LeaderboardEntry,
    Reward, Stage, StageBeginRequest, StageCompleteRequest, TierReward,
)


Handler = Callable[[Dict[str, Any]], Union[Dict[str, Any], bytes]]

# Sentinel to indicate the handler returned raw EgoNet binary bytes
# that should be sent directly without re-encoding.
RAW_BINARY_MARKER = "__raw_binary__"


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
        # Maps numeric challenge_id -> web event_id string, populated when
        # clubs are fetched from the API.
        self._challenge_event_map: Dict[int, str] = {}
        # Maps numeric club_id -> web club_id string
        self._club_id_map: Dict[int, str] = {}
        # Maps time-trial LeaderboardId -> (vclass, track, conditions, category) tuple
        self._tt_lb_map: Dict[int, tuple] = {}
        # The most recent GetLeaderboardId request — used by PostTime to
        # recover the 4-tuple (VehicleClassId is absent in PostTime params).
        self._last_tt_request: Optional[tuple] = None
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
            "Clubs.GetClubs": self._template_or_stub("Clubs.GetClubs", self._clubs),
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
            "RaceNetChallenges.GetChallenges": self._template_or_stub("RaceNetChallenges.GetChallenges", self._challenges),
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

        When api_client is configured, always fetch from the dirtforever.net
        API.  If the API returns no data, return empty clubs (do NOT fall back
        to hardcoded test data in production mode).  Only use the hardcoded
        fallback when api_client is None (local development mode with no token).
        """
        if self.api_client is not None:
            result = self._clubs_from_api()
            if result is not None:
                return result
            # API is configured but returned nothing — return empty, not hardcoded data
            print("[CLUBS] API returned no clubs — returning empty")
            return {"ok": True, "Challenges": [], "Progress": [], "Clubs": []}

        return self._clubs_hardcoded_fallback()

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

        web_clubs = data.get("clubs", [])
        web_events = data.get("events", [])

        if not web_clubs and not web_events:
            return None

        # Index events by their club_id for quick lookup
        events_by_club: Dict[str, list] = {}
        for evt in web_events:
            cid = evt.get("club_id") or "__global__"
            events_by_club.setdefault(cid, []).append(evt)

        now = int(time.time())
        window = EntryWindow(
            visible=now - 172800, start=now - 86400,
            last_entry=now + 86400, end=now + 86400,
        )

        clubs_egonet: List[Dict] = []
        challenges_egonet: List[Dict] = []

        # Convert web clubs with their associated events
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
                loc_name: str = wevt.get("location", "")
                location_id = self.api_client.resolve_location_id(loc_name)
                if location_id is None:
                    print(f"[CLUBS] Unknown location '{loc_name}' for event "
                          f"{wevt.get('id')} — skipping")
                    continue

                car_class_label: str = wevt.get("car_class", "")
                vclass_id = self.api_client.resolve_vclass_id(car_class_label)

                track_ids = self.api_client.tracks_for_location(location_id)
                if not track_ids:
                    print(f"[CLUBS] No tracks for location {location_id} "
                          f"('{loc_name}') — skipping")
                    continue

                # Build Stage objects — one per web stage entry where possible
                web_stages = wevt.get("stages", [])
                stages: List[Stage] = []
                lb_base = chal_id * 10
                for si, _ws in enumerate(web_stages or [None]):  # at least 1 stage
                    track_id = track_ids[si % len(track_ids)]
                    stages.append(Stage(
                        stage_id=si,
                        track_model_id=track_id,
                        has_service_area=(si % 2 == 0),
                        leaderboard_id=lb_base + si,
                    ))
                if not stages:
                    stages.append(Stage(
                        stage_id=0,
                        track_model_id=track_ids[0],
                        has_service_area=True,
                        leaderboard_id=lb_base,
                    ))

                # Requirements: vehicle class if confirmed, else open class.
                # All IDs verified by in-game testing. Invalid IDs crash the game.
                _CONFIRMED_CLASSES = {72, 73, 74, 78, 86, 89, 92, 93, 94, 95,
                                      96, 97, 98, 99, 100, 101, 102}
                if vclass_id is not None and vclass_id in _CONFIRMED_CLASSES:
                    requirements = [{"Type": 1, "Value": UInt32(vclass_id)}]
                else:
                    requirements = []

                num_entrants = len(wevt.get("entries", [])) if "entries" in wevt else 0

                challenges_egonet.append(
                    Challenge(
                        name=wevt.get("name", club_name),
                        challenge_id=chal_id,
                        club_id=club_int_id,
                        requirements=requirements,
                        events=[
                            Event(
                                event_id=chal_id,
                                location_id=location_id,
                                stages=stages,
                                leaderboard_id=chal_id + 900000,
                            )
                        ],
                        entry_window=window,
                        num_entrants=num_entrants,
                        leaderboard_id=chal_id + 800000,
                    ).to_egonet()
                )

        # Also include "global" events (no club_id) as standalone entries
        for evt_idx, wevt in enumerate(events_by_club.get("__global__", [])):
            chal_id = _stable_int_id(wevt.get("id", f"global-{evt_idx}"),
                                     base=300000, offset=evt_idx)
            self._challenge_event_map[chal_id] = wevt.get("id", "")
            loc_name = wevt.get("location", "")
            location_id = self.api_client.resolve_location_id(loc_name)
            if location_id is None:
                print(f"[CLUBS] Unknown location '{loc_name}' for global event "
                      f"{wevt.get('id')} — skipping")
                continue

            track_ids = self.api_client.tracks_for_location(location_id)
            if not track_ids:
                continue

            web_stages = wevt.get("stages", [])
            stages = []
            lb_base = chal_id * 10
            for si, _ws in enumerate(web_stages or [None]):
                track_id = track_ids[si % len(track_ids)]
                stages.append(Stage(
                    stage_id=si,
                    track_model_id=track_id,
                    has_service_area=(si % 2 == 0),
                    leaderboard_id=lb_base + si,
                ))
            if not stages:
                stages.append(Stage(
                    stage_id=0, track_model_id=track_ids[0],
                    has_service_area=True, leaderboard_id=lb_base,
                ))

            car_class_label = wevt.get("car_class", "")
            vclass_id = self.api_client.resolve_vclass_id(car_class_label)
            requirements = (
                [{"Type": 1, "Value": UInt32(vclass_id)}]
                if vclass_id is not None
                else [{"Type": 1, "Value": UInt32(100)}]
            )

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
                Challenge(
                    name=wevt.get("name", "Community Event"),
                    challenge_id=chal_id,
                    club_id=global_club_id,
                    requirements=requirements,
                    events=[
                        Event(
                            event_id=chal_id,
                            location_id=location_id,
                            stages=stages,
                            leaderboard_id=chal_id + 900000,
                        )
                    ],
                    entry_window=window,
                    num_entrants=0,
                    leaderboard_id=chal_id + 800000,
                ).to_egonet()
            )

        if not challenges_egonet:
            return None

        progress_egonet = self._build_user_progress(web_events)

        return {
            "ok": True,
            "Challenges": challenges_egonet,
            "Progress": progress_egonet,
            "Clubs": clubs_egonet,
        }

    def _build_user_progress(self, web_events: list) -> list:
        """Build Progress entries for the current user from stored stage data.

        Calls get_my_progress() so we use all the real captured values
        (tuning setup, tyre compound, vehicle damage, etc.) instead of
        hard-coded defaults.
        """
        if self.api_client is None:
            return []

        import base64

        # Fetch real per-user progress from the web API
        try:
            my_progress = self.api_client.get_my_progress()
        except Exception as exc:
            print(f"[PROGRESS] get_my_progress() failed: {exc}")
            my_progress = None

        # Build a quick lookup: event_id -> event data from my_progress
        progress_by_event: Dict[str, Any] = {}
        if my_progress:
            for ep in my_progress.get("events", []):
                eid = ep.get("event_id", "")
                if eid:
                    progress_by_event[eid] = ep

        # Fetch leaderboard totals for percentile calculation
        # key: event_id -> total entry count
        lb_totals: Dict[str, int] = {}

        # VehicleDamage field order MUST match upstream exactly — the game
        # parses this as an ordered struct.
        def _damage_from_dict(d: Dict[str, Any]) -> Dict[str, Any]:
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

        progress: list = []
        for evt in web_events:
            evt_id = evt.get("id", "")
            if not evt_id:
                continue

            # Reverse-lookup the challenge_id for this event
            chal_id = None
            for k, v in self._challenge_event_map.items():
                if v == evt_id:
                    chal_id = k
                    break
            if chal_id is None:
                continue

            ep = progress_by_event.get(evt_id)
            if not ep:
                continue  # user has no stages completed in this event

            completed_stages = ep.get("completed_stages", [])
            if not completed_stages:
                continue

            total_stages_in_event = len(evt.get("stages", []))
            all_done = (
                total_stages_in_event > 0
                and len(completed_stages) >= total_stages_in_event
            )

            total_ms = ep.get("total_time_ms", 0)

            # Compute percentile from stored rank (percentile computation
            # is best-effort; leave at 0 until we track per-user rank)
            percentile = 0

            # Use the last completed stage's data for the Progress entry
            last_stage = completed_stages[-1]
            next_stage_idx = last_stage.get("stage_index", 0) + 1
            # When all stages are done, cap StageIndex at the last completed
            # stage and use State=2 (completed). Otherwise State=1 (in-progress).
            if all_done:
                stage_index_out = total_stages_in_event - 1
                state_out = 2
            else:
                stage_index_out = next_stage_idx
                state_out = 1

            vehicle_id = last_stage.get("vehicle_id") or 0
            if not isinstance(vehicle_id, int):
                vehicle_id = 0

            # Use upstream-observed defaults where we don't have real data.
            # LiveryId must belong to the vehicle — use the inventory mapping
            # so we don't end up with a livery from a different car.
            livery_id = last_stage.get("livery_id", 0)
            if not livery_id:
                livery_id = _LIVERY_FOR_VEHICLE.get(vehicle_id, 0)
            nationality_id = last_stage.get("nationality_id", 0) or 0
            meters_driven = last_stage.get("meters_driven", 0) or 0
            has_repaired = bool(last_stage.get("has_repaired", False))
            repair_penalty_ms = int(last_stage.get("repair_penalty_ms", 0) or 0)
            tyre_compound = int(last_stage.get("tyre_compound", 0) or 7)
            tyres_remaining = int(last_stage.get("tyres_remaining", 0) or 2)
            damage = _damage_from_dict(last_stage.get("vehicle_damage") or {})

            # Decode tuning setup from base64 back to bytes; use default
            # valid blob when empty (game crashes on empty/malformed blobs)
            tuning_b64 = last_stage.get("tuning_setup_b64", "") or ""
            try:
                tuning_bytes = base64.b64decode(tuning_b64) if tuning_b64 else b""
            except Exception:
                tuning_bytes = b""
            if not tuning_bytes:
                from .tuning import TuningBlob
                tuning_bytes = TuningBlob.default_bytes()

            progress.append({
                "ChallengeID": chal_id,
                "EventIndex": 0,
                "StageIndex": stage_index_out,
                "State": state_out,
                "StageTimeMs": UInt32(0),
                "VehicleInstId": Int64(0),
                "VehicleId": UInt32(vehicle_id),
                "LiveryId": UInt32(livery_id),
                "MetersDriven": meters_driven,
                "Percentile": percentile,
                "ChampTimeMs": UInt32(total_ms),
                "HasRepaired": has_repaired,
                "RepairPenalty": UInt32(repair_penalty_ms),
                "VehicleDamage": damage,
                "TyreCompound": UInt32(tyre_compound),
                "TyresRemaining": UInt32(tyres_remaining),
                "TuningSetup": tuning_bytes,
                "AttemptsLeft": 1,  # must match Challenge.AttemptsAllowed
            })

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
                 Stage(stage_id=0, track_model_id=Track.OCEAN_BEACH,         has_service_area=True,  leaderboard_id=3000001),
                 Stage(stage_id=1, track_model_id=Track.OCEAN_BEACH_REV,     has_service_area=False, leaderboard_id=3000002),
                 Stage(stage_id=2, track_model_id=Track.WAIMARAMA_POINT_REV, has_service_area=True,  leaderboard_id=3000003),
                 Stage(stage_id=3, track_model_id=Track.TE_AWANGA,           has_service_area=False, leaderboard_id=3000004),
             ], 12),
            (1002, "Community Rally ARG", "CommunityServer", "Community Rally - Argentina",
             100002, Location.ARGENTINA, [
                 Stage(stage_id=0, track_model_id=Track.VALLE_DE_LOS_PUENTES,     has_service_area=True,  leaderboard_id=3000005),
                 Stage(stage_id=1, track_model_id=Track.VALLE_DE_LOS_PUENTES_REV, has_service_area=False, leaderboard_id=3000006),
             ], 8),
            (1003, "Community Rally ESP", "CommunityServer", "Community Rally - Spain",
             100003, Location.SPAIN, [
                 Stage(stage_id=0, track_model_id=Track.RIBADELLES,     has_service_area=True,  leaderboard_id=3000007),
                 Stage(stage_id=1, track_model_id=Track.RIBADELLES_REV, has_service_area=False, leaderboard_id=3000008),
                 Stage(stage_id=2, track_model_id=Track.CENTENERA,      has_service_area=True,  leaderboard_id=3000009),
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

        # Convert to EgoNet format — ChampionshipLeaderboard entries use a
        # different structure than time-trial entries: Points instead of time.
        egonet_entries = []
        for i, e in enumerate(entries[start_rank:start_rank + limit]):
            egonet_entries.append({
                "Presence": {
                    "Name": e.get("username", "Unknown"),
                    "IsCrossPlatform": True,
                    "NetworkId": 0,
                    "EgoNetId": Int64(0),
                    "AccountRef": Int64(0),
                },
                "Points": e.get("points", 0),
                "Rank": start_rank + i + 1,
                "IsVIP": False,
                "Nationality": UInt32(e.get("nationality_id", 0)),
            })

        print(f"[CLUB_LB] club_id={club_id} event={event_id} returning {len(egonet_entries)} entries")
        return {
            "ok": True,
            "TotalEntries": len(entries),
            "Entries": egonet_entries,
            "PlayerRank": 0,
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
                egonet_entries.append({
                    "Presence": {
                        "Name": e.get("username", "Unknown"),
                        "IsCrossPlatform": False,
                        "NetworkId": 0,
                        "EgoNetId": Int64(0),
                        "AccountRef": Int64(0),
                    },
                    "PersonalBest":   Int64(time_ms),
                    "CumulativeBest": Int64(time_ms),
                    "TimeDiff":       Int64(time_ms - leader_ms),
                    "Rank":           rank,
                    "VehicleId":      UInt32(vid),
                    "IsFounder":      False,
                    "IsVIP":          False,
                    "Nationality":    UInt32(nat),
                    "GhostAvailable": True,
                    "LiveryId":       UInt32(lid),
                })
            return {
                "ok": True,
                "TotalEntries": len(egonet_entries),
                "Entries": egonet_entries,
                "PlayerRank": 0,
            }

        # ── Club / championship leaderboard ────────────────────────────────
        # LeaderboardId is derived from challenge_id as chal_id+800000 (event-level)
        # or chal_id*10+N (stage-level). Try both schemes.
        event_id = None
        chal_id = lb_id - 800000 if lb_id >= 800000 else None
        if chal_id and chal_id in self._challenge_event_map:
            event_id = self._challenge_event_map[chal_id]
        elif (lb_id // 10) in self._challenge_event_map:
            event_id = self._challenge_event_map[lb_id // 10]

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
        try:
            entries = self.api_client.get_leaderboard(event_id)
        except Exception as exc:
            print(f"[LB] api_client.get_leaderboard({event_id}) raised: {exc}")
            entries = []

        egonet_entries = []
        leader_ms = entries[0].get("total_time_ms", 0) if entries else 0
        for i, e in enumerate(entries):
            total_ms = e.get("total_time_ms", 0)
            vehicle_id = e.get("vehicle_id", 0)
            if not isinstance(vehicle_id, int):
                vehicle_id = 0
            egonet_entries.append({
                "Presence": {
                    "Name": e.get("username", "Unknown"),
                    "IsCrossPlatform": False,
                    "NetworkId": Int64(0),
                    "EgoNetId": Int64(0),
                    "AccountRef": Int64(0),
                },
                "PersonalBest":   Int64(total_ms),
                "CumulativeBest": Int64(total_ms),
                "TimeDiff":       Int64(total_ms - leader_ms),
                "Rank":           e.get("rank", i + 1),
                "VehicleId":      UInt32(vehicle_id),
                "IsFounder":      False,
                "IsVIP":          False,
                "Nationality":    UInt32(0),
                "GhostAvailable": False,
                "LiveryId":       UInt32(0),
            })
        return {
            "ok": True,
            "TotalEntries": len(egonet_entries),
            "Entries": egonet_entries,
            "PlayerRank": 0,
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
        # GetLeaderboardId call for this session.
        if self._last_tt_request is not None:
            vclass, _track, _conditions, _category = self._last_tt_request
        else:
            vclass = 0

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
            else:
                # Profile fetch failed — give starter credits so the game is playable
                soft_currency = 500000

        return {
            "ok": True,
            "Inventory": {
                "SoftCurrency": soft_currency,
                "HardCurrency": hard_currency,
                "GarageSlots": 100,
                "Vehicles": self._all_vehicles(),
                "Upgrades": [],
                "Entitlements": [],
                "Liveries": [],
                "SeasonFlags": UInt32(15),
            },
        }

    @staticmethod
    def _all_vehicles() -> list:
        """Generate a full garage with every known vehicle, undamaged and ready."""
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
            vehicles.append({
                "VehicleId": UInt32(vid),
                "LiveryId": UInt32(0),
                "TuningId": UInt32(0),
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
                "Id": Int64(idx + 1),
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

    @staticmethod
    def _challenges(params: Dict[str, Any]) -> Dict[str, Any]:
        return {"ok": True, "Challenges": []}

    def _stage_begin(self, params: Dict[str, Any]) -> Dict[str, Any]:
        import base64
        req = StageBeginRequest.from_egonet(params)
        print(f"[STAGE] Begin: challenge={req.challenge_id} event={req.event_index} "
              f"stage={req.stage_index} vehicle={req.vehicle_id} livery={req.livery_id} "
              f"tyres={req.tyres_remaining} compound={req.tyre_compound}")

        if self.api_client is not None:
            # Resolve event_id from challenge_id map, fall back to first active event
            event_id = self._challenge_event_map.get(req.challenge_id)
            if not event_id:
                try:
                    data = self.api_client.get_clubs()
                    active_events = [e for e in data.get("events", []) if e.get("active")]
                    if active_events:
                        event_id = active_events[0].get("id", "")
                        print(f"[STAGE] Begin fallback: using event_id={event_id}")
                except Exception as exc:
                    print(f"[STAGE] Begin fallback fetch failed: {exc}")

            if event_id:
                tuning_b64 = base64.b64encode(req.tuning_setup).decode("ascii") if req.tuning_setup else ""
                try:
                    self.api_client.submit_stage_begin(
                        event_id=event_id,
                        stage_index=req.stage_index,
                        vehicle_id=req.vehicle_id if req.vehicle_id else None,
                        livery_id=req.livery_id,
                        tuning_setup_b64=tuning_b64,
                        tyre_compound=req.tyre_compound,
                        tyres_remaining=req.tyres_remaining,
                        nationality_id=req.nationality_id,
                    )
                except Exception as exc:
                    print(f"[STAGE] Begin api_client.submit_stage_begin() raised: {exc}")

        return {"ok": True, "Accepted": True}

    def _stage_complete(self, params: Dict[str, Any]) -> Dict[str, Any]:
        import dataclasses
        req = StageCompleteRequest.from_egonet(params)
        print(f"[STAGE] Complete: challenge={req.challenge_id} event={req.event_index} "
              f"stage={req.stage_index} time={req.stage_time:.3f}s "
              f"distance={req.meters_driven}m status={req.race_status} "
              f"wheel={req.using_wheel} assists={req.using_assists}")

        if self.api_client is not None:
            # Look up the original web event_id from the numeric challenge_id
            event_id = self._challenge_event_map.get(req.challenge_id)
            if not event_id:
                # Fallback: game may have cached an old challenge_id from a
                # previous server session. Fetch current events and use the
                # first active one as a best-effort match.
                print(f"[STAGE] Unknown challenge_id={req.challenge_id} "
                      f"(map has {len(self._challenge_event_map)} entries), "
                      f"trying fallback to first active event...")
                try:
                    data = self.api_client.get_clubs()
                    active_events = [e for e in data.get("events", []) if e.get("active")]
                    if active_events:
                        event_id = active_events[0].get("id", "")
                        print(f"[STAGE] Fallback: using event_id={event_id}")
                except Exception as exc:
                    print(f"[STAGE] Fallback fetch failed: {exc}")

            if not event_id:
                print(f"[STAGE] Cannot submit — no event_id available")
            elif req.race_status != 0:
                print(f"[STAGE] Not submitting (race_status={req.race_status}, not finished)")
            else:
                time_ms = int(req.stage_time * 1000)
                # Convert VehicleMud and CompDamage dataclasses to plain dicts
                mud_dict = dataclasses.asdict(req.vehicle_mud)
                dmg_dict = dataclasses.asdict(req.comp_damage)
                # has_repaired: true if any quick_repairs used or comp_damage
                # indicates repair was applied (RecovToService flag)
                _qr = getattr(req.comp_damage.quick_repairs, "value", req.comp_damage.quick_repairs)
                has_repaired = req.recov_to_service or _qr > 0
                # Username comes from the authenticated token on the web side
                try:
                    ok = self.api_client.submit_stage(
                        event_id=event_id,
                        username="",  # server uses g.game_user from token
                        stage_index=req.stage_index,
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
                        repair_penalty_ms=0,  # game doesn't send this directly
                    )
                    if ok:
                        print(f"[STAGE] Submitted to API: event={event_id} "
                              f"stage={req.stage_index} time_ms={time_ms}")
                except Exception as exc:
                    print(f"[STAGE] api_client.submit_stage() raised: {exc}")

        return {"ok": True, "Accepted": True}

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
