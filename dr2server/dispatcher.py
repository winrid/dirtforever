from __future__ import annotations

import secrets
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union

from .account_store import AccountStore
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

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "data" / "upstream_templates"


def _load_template(method: str) -> Optional[bytes]:
    """Load a captured upstream binary response template for the given method."""
    safe_name = method.replace(".", "_") + ".bin"
    path = TEMPLATE_DIR / safe_name
    if path.is_file():
        return path.read_bytes()
    return None


class RpcDispatcher:
    def __init__(self, account_store: AccountStore) -> None:
        self.account_store = account_store
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
            "Clubs.GetClubs": self._template_or_stub("Clubs.GetClubs", self._empty_clubs),
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
            "RaceNetInventory.GetInventory": self._template_or_stub("RaceNetInventory.GetInventory", self._inventory),
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

    @staticmethod
    def _empty_clubs(params: Dict[str, Any]) -> Dict[str, Any]:
        """Return test club challenges using typed models."""
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

    @staticmethod
    def _leaderboard(params: Dict[str, Any]) -> Dict[str, Any]:
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

    @staticmethod
    def _inventory(params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "ok": True,
            "HardCurrency": 0,
            "SoftCurrency": 0,
            "Boosters": [],
            "Vehicles": [],
            "Upgrades": [],
            "Liveries": [],
            "Entitlements": [],
            "SeasonFlags": 0,
        }

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

    @staticmethod
    def _stage_complete(params: Dict[str, Any]) -> Dict[str, Any]:
        req = StageCompleteRequest.from_egonet(params)
        print(f"[STAGE] Complete: challenge={req.challenge_id} event={req.event_index} "
              f"stage={req.stage_index} time={req.stage_time:.3f}s "
              f"distance={req.meters_driven}m status={req.race_status} "
              f"wheel={req.using_wheel} assists={req.using_assists}")
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
