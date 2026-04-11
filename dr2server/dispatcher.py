from __future__ import annotations

import secrets
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from .account_store import AccountStore
from .api_client import DirtForeverClient
from .egonet import Int64, Timestamp, UInt32, UInt8
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

    Uses a simple hash so the same string always produces the same integer.
    The result is kept well within 31-bit signed range to avoid EgoNet
    encoding issues.
    """
    h = hash(string_id) & 0x7FFFFFFF  # positive 31-bit value
    return base + (h % 90000) + offset

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "data" / "upstream_templates"


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

            club_events = events_by_club.get(club_str_id, [])
            if not club_events:
                continue  # skip clubs with no active events

            for evt_idx, wevt in enumerate(club_events):
                chal_id = _stable_int_id(wevt.get("id", f"{club_str_id}-{evt_idx}"),
                                         base=200000, offset=evt_idx)
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
                # Only IDs verified by in-game testing. Invalid IDs crash the game.
                _CONFIRMED_CLASSES = {72, 78, 86, 92, 93, 96, 97, 98, 100}
                if vclass_id is not None and vclass_id in _CONFIRMED_CLASSES:
                    requirements = [{"Type": 1, "Value": UInt32(vclass_id)}]
                else:
                    requirements = []

                num_entrants = len(wevt.get("entries", [])) if "entries" in wevt else 0

                clubs_egonet.append(
                    Club(
                        id=club_int_id,
                        name=club_name,
                        creator_name=creator,
                        amount_of_events=len(club_events),
                    ).to_egonet()
                )

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

        return {"ok": True, "Challenges": challenges_egonet, "Progress": [], "Clubs": clubs_egonet}

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

    @staticmethod
    def _clubs_leaderboard(params: Dict[str, Any]) -> Dict[str, Any]:
        return {"ok": True, "Entries": [], "Total": 0}

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
        if self.api_client is not None:
            # LeaderboardId from params — map back to a string event_id if possible
            lb_id = params.get("LeaderboardId") or params.get("leaderboard_id")
            if lb_id is not None:
                event_id = str(lb_id)
                try:
                    entries = self.api_client.get_leaderboard(event_id)
                except Exception as exc:
                    print(f"[LB] api_client.get_leaderboard({event_id}) raised: {exc}")
                    entries = []

                egonet_entries = []
                for i, e in enumerate(entries):
                    total_ms = e.get("total_time_ms", 0)
                    leader_ms = entries[0]["total_time_ms"] if entries else 0
                    egonet_entries.append(
                        LeaderboardEntry(
                            rank=e.get("rank", i + 1),
                            name=e.get("username", ""),
                            vehicle_id=int(e["vehicle_id"]) if e.get("vehicle_id") else 0,
                            stage_time=total_ms / 1000.0,
                            diff_first=(total_ms - leader_ms) / 1000.0,
                        ).to_egonet()
                    )
                return {"ok": True, "Entries": egonet_entries, "Total": len(egonet_entries)}

        return {
            "ok": True,
            "Entries": [],
            "Total": 0,
        }

    @staticmethod
    def _time_trial_id(params: Dict[str, Any]) -> Dict[str, Any]:
        return {"ok": True, "leaderboard_id": "community-time-trial"}

    @staticmethod
    def _post_time(params: Dict[str, Any]) -> Dict[str, Any]:
        return {"ok": True, "Accepted": True, "EntryId": secrets.token_hex(8)}

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

    @staticmethod
    def _stage_begin(params: Dict[str, Any]) -> Dict[str, Any]:
        req = StageBeginRequest.from_egonet(params)
        print(f"[STAGE] Begin: challenge={req.challenge_id} event={req.event_index} "
              f"stage={req.stage_index} vehicle={req.vehicle_id} livery={req.livery_id} "
              f"tyres={req.tyres_remaining} compound={req.tyre_compound}")
        return {"ok": True, "Accepted": True}

    def _stage_complete(self, params: Dict[str, Any]) -> Dict[str, Any]:
        req = StageCompleteRequest.from_egonet(params)
        print(f"[STAGE] Complete: challenge={req.challenge_id} event={req.event_index} "
              f"stage={req.stage_index} time={req.stage_time:.3f}s "
              f"distance={req.meters_driven}m status={req.race_status} "
              f"wheel={req.using_wheel} assists={req.using_assists}")

        if self.api_client is not None and req.race_status == 0:
            # Only submit clean (non-retired) runs.
            # We need a string event_id and a username — for now we derive the
            # event_id from the challenge_id and use a placeholder username
            # until auth integration is wired up end-to-end.
            event_id = str(req.challenge_id)
            username = getattr(self, "_current_username", "unknown")
            time_ms = int(req.stage_time * 1000)
            try:
                self.api_client.submit_stage(
                    event_id=event_id,
                    username=username,
                    stage_index=req.stage_index,
                    time_ms=time_ms,
                    vehicle_id=req.vehicle_id if req.vehicle_id else None,
                )
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
