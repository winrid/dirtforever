from __future__ import annotations

import secrets
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union

from .account_store import AccountStore
from .egonet import Int64, Timestamp, UInt32, UInt8


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
        """Return test club challenges matching upstream Clubs.GetClubs types exactly."""

        _empty_item = {
            "ItemType": UInt8(0),
            "Booster": {"BoosterId": UInt32(0), "IsStarted": False, "StartedAt": Timestamp(0), "Id": Int64(0)},
            "Entitlement": {"EntitlementId": UInt32(0), "Id": Int64(0)},
            "Livery": {"LiveryId": UInt32(0), "Id": Int64(0)},
            "Upgrade": {"UpgradeId": UInt32(0), "Id": Int64(0)},
            "Vehicle": {
                "VehicleId": UInt32(0), "LiveryId": UInt32(0), "TuningId": UInt32(0),
                "UpgAvailable": 0, "UpgEnabled": 0, "TuningReady": 0, "TuningPurchased": 0,
                "IsNew": False, "IsRepairFree": False, "IsSellable": False, "SellPrice": 0,
                "ResearchTarget": UInt32(0), "ResearchPercent": 0.0,
                "IsLocked": False, "LockChallengeId": 0, "LockEntity": Int64(0),
                "LockReason": 0, "LockExpiry": Timestamp(0), "LockLocation": UInt32(0),
                "DistanceDriven": 0, "Podiums": 0, "EventsEntered": 0, "EventsFinished": 0,
                "Terminals": 0, "Id": Int64(0),
            },
        }
        _empty_tier = {
            "Item": _empty_item,
            "MinSoftCurrency": 0, "MaxSoftCurrency": 0,
            "PercentLimit": 10, "BarrierTime": 0.0,
        }

        def make_stage(stage_id: int, track_model_id: int, has_service: bool = True, lb_id: int = 0) -> dict:
            return {
                "StageId": stage_id, "TrackModelId": UInt32(track_model_id),
                "HasServiceArea": has_service, "NumberPractises": 0,
                "StageConditions": UInt32(1), "WeatherPresetId": UInt32(1),
                "TimeOfDayId": UInt32(4), "SurfaceCondId": UInt32(1),
                "SurfaceDegrad": 0.25, "AmbientTemp": 0.0, "TrackTemp": 0.0,
                "DryingTime": 3600, "StageType": 0, "NumberLaps": 0,
                "LeaderboardId": lb_id, "DeltaTime": 0.0, "SvcSettingsId": UInt32(2),
            }

        now = int(time.time())
        entry_window = {
            "Visible": Timestamp(now - 172800),
            "Start": Timestamp(now - 86400),
            "LastEntry": Timestamp(now + 86400),
            "End": Timestamp(now + 86400),
        }

        def make_challenge(name: str, cid: int, club_id: int, loc_id: int, stages: list, entrants: int = 10) -> dict:
            return {
                "Name": name, "ChallengeType": 2, "ScoringType": 2, "ChallengeID": cid,
                "Requirements": [{"Type": 1, "Value": UInt32(100)}],
                "Events": [{
                    "EventId": cid, "LocationId": UInt32(loc_id), "DisciplineId": UInt32(1),
                    "NumberRestarts": 0, "NumberEntrants": 0, "NumberClasses": 1,
                    "Stages": stages, "LeaderboardId": cid + 900000,
                }],
                "NumEntrants": entrants, "DifficultyLevel": 0,
                "EntryWindow": entry_window, "State": 0,
                "Reward": {"SoftCurrency": 0, "TierRewards": [_empty_tier]},
                "MinEventCredits": 0, "MaxEventCredits": 10000,
                "LeaderboardId": cid + 800000,
                "IsHardcore": True, "ExteriorCams": True,
                "AllowAssists": True, "UnxpectdMoments": True,
                "DirtPlusSeason": 0, "IsPromo": False,
                "Category": UInt8(4), "Mode": UInt8(1),
                "UseInvVehicle": False, "ClubId": Int64(club_id),
                "EsportsMonthId": 0, "AttemptsAllowed": 1,
            }

        def make_club(club_id: int, name: str, creator: str, events: int = 1, upcoming: bool = False) -> dict:
            return {
                "Id": Int64(club_id), "CreatorName": creator, "Name": name,
                "HasStandings": True, "IsOtherPlatform": False,
                "AmountOfEvents": events, "EventIndex": 0, "IsUpcoming": upcoming,
            }

        return {
            "ok": True,
            "Challenges": [
                make_challenge("Community Rally - New Zealand", 100001, 1001, 16, [
                    make_stage(0, 590, True, 3000001), make_stage(1, 591, False, 3000002),
                    make_stage(2, 585, True, 3000003), make_stage(3, 586, False, 3000004),
                ], entrants=12),
                make_challenge("Community Rally - Argentina", 100002, 1002, 5, [
                    make_stage(0, 480, True, 3000005), make_stage(1, 481, False, 3000006),
                ], entrants=8),
                make_challenge("Community Rally - Spain", 100003, 1003, 36, [
                    make_stage(0, 614, True, 3000007), make_stage(1, 615, False, 3000008),
                    make_stage(2, 610, True, 3000009),
                ], entrants=15),
            ],
            "Progress": [],
            "Clubs": [
                make_club(1001, "Community Rally NZ", "CommunityServer"),
                make_club(1002, "Community Rally ARG", "CommunityServer"),
                make_club(1003, "Community Rally ESP", "CommunityServer"),
            ],
        }

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
            "entries": [],
            "page": 1,
            "page_size": params.get("page_size", 50),
            "total": 0,
        }

    @staticmethod
    def _time_trial_id(params: Dict[str, Any]) -> Dict[str, Any]:
        return {"ok": True, "leaderboard_id": "community-time-trial"}

    @staticmethod
    def _post_time(params: Dict[str, Any]) -> Dict[str, Any]:
        return {"ok": True, "accepted": True, "entry_id": secrets.token_hex(8)}

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
