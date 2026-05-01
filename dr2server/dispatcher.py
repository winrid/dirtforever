from __future__ import annotations

import hashlib
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
        # Local player's web username, lazily resolved via api_client.test_token().
        # Used to identify the player's own row in leaderboard responses.
        self._my_username: Optional[str] = None
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

            stage = Stage(
                stage_id=0,
                track_model_id=track_id,
                has_service_area=True,
                leaderboard_id=chal_id * 10,
                stage_conditions=conditions,
            )
            event = Event(
                event_id=chal_id,
                location_id=loc_id,
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

        # Convert to EgoNet format — ChampionshipLeaderboard entries use a
        # different structure than time-trial entries: Points instead of time.
        egonet_entries = []
        for i, e in enumerate(entries[start_rank:start_rank + limit]):
            uname = e.get("username", "Unknown")
            acc = stable_account_id(uname)
            egonet_entries.append({
                "Presence": {
                    "Name": uname,
                    "IsCrossPlatform": True,
                    "NetworkId": 0,
                    "EgoNetId": Int64(acc),
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
                "Rank":           e.get("rank", i + 1),
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
              f"refreshing from clubs API")
        try:
            self._clubs_from_api()
        except Exception as exc:
            print(f"[STAGE] {label} clubs refresh raised: {exc}")
            return None
        event_id = self._challenge_event_map.get(challenge_id)
        if event_id:
            print(f"[STAGE] {label} resolved after refresh: event_id={event_id}")
            return event_id
        print(f"[STAGE] {label} challenge_id={challenge_id} not in any known "
              f"event after refresh; refusing to misroute submission")
        return None

    def _total_stages_for_event(self, event_id: str) -> int:
        """Look up the configured stage count for an event. 0 if unknown."""
        if self.api_client is None or not event_id:
            return 0
        try:
            evt = self.api_client.get_event(event_id)
        except Exception as exc:
            print(f"[STAGE] get_event({event_id}) raised: {exc}")
            return 0
        if not evt:
            return 0
        return len(evt.get("stages", []) or [])

    def _stage_begin(self, params: Dict[str, Any]) -> Dict[str, Any]:
        import base64
        req = StageBeginRequest.from_egonet(params)
        print(f"[STAGE] Begin: challenge={req.challenge_id} event={req.event_index} "
              f"stage={req.stage_index} vehicle={req.vehicle_id} livery={req.livery_id} "
              f"tyres={req.tyres_remaining} compound={req.tyre_compound}")

        event_id = self._resolve_event_id(req.challenge_id, "Begin")

        # Persist the pre-stage setup so my-progress reflects it for later calls.
        if event_id and self.api_client is not None:
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

        # Build the Progress block that will be relayed back to the client.
        # The client uses this as the source of truth for the stage-start UI,
        # so values must reflect the persisted state of prior completed stages
        # (damage, ChampTimeMs) and echo the request for this stage's setup
        # (Vehicle/Livery/Tyres/Tuning).
        ep = self._user_progress_for_event(event_id) if event_id else None
        completed_stages = (ep or {}).get("completed_stages", []) if ep else []
        prior_completed = [s for s in completed_stages if s.get("stage_index", 0) < req.stage_index]
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
        total_stages = self._total_stages_for_event(event_id) if event_id else 0

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

        all_done = (
            total_stages > 0
            and len(completed_stages) >= total_stages
        )
        if all_done:
            target_stage_index = total_stages - 1
            state_out = 2  # event finished
        else:
            target_stage_index = req.stage_index + 1
            state_out = 0  # between stages, ready for next StageBegin

        # ChampTimeMs: prefer the web side's recomputed total when available,
        # otherwise sum what we have locally (request value included).
        if ep and "total_time_ms" in ep:
            champ_time_ms = int(ep.get("total_time_ms", 0) or 0)
        else:
            champ_time_ms = sum(int(s.get("time_ms", 0) or 0) for s in completed_stages)
            if req.race_status == 0:
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
