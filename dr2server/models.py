"""Data models for DiRT Rally 2.0 server structures.

Each model's `to_egonet()` returns a dict using the correct EgoNet type
wrappers (UInt32, UInt8, Int64, Timestamp) so the binary encoder produces
byte-compatible output with the real Codemasters server.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .egonet import Int64, Timestamp, UInt8, UInt32


# ---------------------------------------------------------------------------
# Stage / Event / Challenge building blocks
# ---------------------------------------------------------------------------

@dataclass
class Stage:
    stage_id: int = 0
    track_model_id: int = 590
    has_service_area: bool = True
    number_practises: int = 0
    stage_conditions: int = 1
    weather_preset_id: int = 1
    time_of_day_id: int = 4
    surface_cond_id: int = 1
    surface_degrad: float = 0.25
    ambient_temp: float = 0.0
    track_temp: float = 0.0
    drying_time: int = 3600
    stage_type: int = 0
    number_laps: int = 0
    leaderboard_id: int = 0
    delta_time: float = 0.0
    svc_settings_id: int = 2

    def to_egonet(self) -> Dict[str, Any]:
        return {
            "StageId": self.stage_id,
            "TrackModelId": UInt32(self.track_model_id),
            "HasServiceArea": self.has_service_area,
            "NumberPractises": self.number_practises,
            "StageConditions": UInt32(self.stage_conditions),
            "WeatherPresetId": UInt32(self.weather_preset_id),
            "TimeOfDayId": UInt32(self.time_of_day_id),
            "SurfaceCondId": UInt32(self.surface_cond_id),
            "SurfaceDegrad": self.surface_degrad,
            "AmbientTemp": self.ambient_temp,
            "TrackTemp": self.track_temp,
            "DryingTime": self.drying_time,
            "StageType": self.stage_type,
            "NumberLaps": self.number_laps,
            "LeaderboardId": self.leaderboard_id,
            "DeltaTime": self.delta_time,
            "SvcSettingsId": UInt32(self.svc_settings_id),
        }


@dataclass
class Event:
    event_id: int = 0
    location_id: int = 0
    discipline_id: int = 1
    number_restarts: int = 0
    number_entrants: int = 0
    number_classes: int = 1
    leaderboard_id: int = 0
    stages: List[Stage] = field(default_factory=list)

    def to_egonet(self) -> Dict[str, Any]:
        return {
            "EventId": self.event_id,
            "LocationId": UInt32(self.location_id),
            "DisciplineId": UInt32(self.discipline_id),
            "NumberRestarts": self.number_restarts,
            "NumberEntrants": self.number_entrants,
            "NumberClasses": self.number_classes,
            "Stages": [s.to_egonet() for s in self.stages],
            "LeaderboardId": self.leaderboard_id,
        }


@dataclass
class EntryWindow:
    visible: int = 0
    start: int = 0
    last_entry: int = 0
    end: int = 0

    def to_egonet(self) -> Dict[str, Any]:
        return {
            "Visible": Timestamp(self.visible),
            "Start": Timestamp(self.start),
            "LastEntry": Timestamp(self.last_entry),
            "End": Timestamp(self.end),
        }


@dataclass
class Vehicle:
    """Default empty vehicle for reward/item structures."""
    vehicle_id: int = 0
    livery_id: int = 0
    tuning_id: int = 0

    def to_egonet(self) -> Dict[str, Any]:
        return {
            "VehicleId": UInt32(self.vehicle_id),
            "LiveryId": UInt32(self.livery_id),
            "TuningId": UInt32(self.tuning_id),
            "UpgAvailable": 0, "UpgEnabled": 0,
            "TuningReady": 0, "TuningPurchased": 0,
            "IsNew": False, "IsRepairFree": False, "IsSellable": False,
            "SellPrice": 0, "ResearchTarget": UInt32(0), "ResearchPercent": 0.0,
            "IsLocked": False, "LockChallengeId": 0, "LockEntity": Int64(0),
            "LockReason": 0, "LockExpiry": Timestamp(0), "LockLocation": UInt32(0),
            "DistanceDriven": 0, "Podiums": 0,
            "EventsEntered": 0, "EventsFinished": 0, "Terminals": 0,
            "Id": Int64(0),
        }


@dataclass
class Item:
    """Reward item wrapper matching upstream structure."""
    item_type: int = 0

    def to_egonet(self) -> Dict[str, Any]:
        return {
            "ItemType": UInt8(self.item_type),
            "Booster": {
                "BoosterId": UInt32(0), "IsStarted": False,
                "StartedAt": Timestamp(0), "Id": Int64(0),
            },
            "Entitlement": {"EntitlementId": UInt32(0), "Id": Int64(0)},
            "Livery": {"LiveryId": UInt32(0), "Id": Int64(0)},
            "Upgrade": {"UpgradeId": UInt32(0), "Id": Int64(0)},
            "Vehicle": Vehicle().to_egonet(),
        }


@dataclass
class TierReward:
    min_soft_currency: int = 0
    max_soft_currency: int = 0
    percent_limit: int = 10
    barrier_time: float = 0.0
    item: Item = field(default_factory=Item)

    def to_egonet(self) -> Dict[str, Any]:
        return {
            "Item": self.item.to_egonet(),
            "MinSoftCurrency": self.min_soft_currency,
            "MaxSoftCurrency": self.max_soft_currency,
            "PercentLimit": self.percent_limit,
            "BarrierTime": self.barrier_time,
        }


@dataclass
class Reward:
    soft_currency: int = 0
    tier_rewards: List[TierReward] = field(default_factory=lambda: [TierReward()])

    def to_egonet(self) -> Dict[str, Any]:
        return {
            "SoftCurrency": self.soft_currency,
            "TierRewards": [t.to_egonet() for t in self.tier_rewards],
        }


@dataclass
class Challenge:
    """A club challenge (event series)."""
    name: str = ""
    challenge_type: int = 2
    scoring_type: int = 2
    challenge_id: int = 0
    club_id: int = 0
    requirements: List[Dict[str, Any]] = field(default_factory=lambda: [{"Type": 1, "Value": UInt32(100)}])
    events: List[Event] = field(default_factory=list)
    num_entrants: int = 0
    difficulty_level: int = 0
    entry_window: EntryWindow = field(default_factory=EntryWindow)
    state: int = 0
    reward: Reward = field(default_factory=Reward)
    min_event_credits: int = 0
    max_event_credits: int = 10000
    leaderboard_id: int = 0
    is_hardcore: bool = True
    exterior_cams: bool = True
    allow_assists: bool = True
    unxpectd_moments: bool = True
    dirt_plus_season: int = 0
    is_promo: bool = False
    category: int = 4
    mode: int = 1
    use_inv_vehicle: bool = False
    esports_month_id: int = 0
    attempts_allowed: int = 1

    def to_egonet(self) -> Dict[str, Any]:
        return {
            "Name": self.name,
            "ChallengeType": self.challenge_type,
            "ScoringType": self.scoring_type,
            "ChallengeID": self.challenge_id,
            "Requirements": self.requirements,
            "Events": [e.to_egonet() for e in self.events],
            "NumEntrants": self.num_entrants,
            "DifficultyLevel": self.difficulty_level,
            "EntryWindow": self.entry_window.to_egonet(),
            "State": self.state,
            "Reward": self.reward.to_egonet(),
            "MinEventCredits": self.min_event_credits,
            "MaxEventCredits": self.max_event_credits,
            "LeaderboardId": self.leaderboard_id,
            "IsHardcore": self.is_hardcore,
            "ExteriorCams": self.exterior_cams,
            "AllowAssists": self.allow_assists,
            "UnxpectdMoments": self.unxpectd_moments,
            "DirtPlusSeason": self.dirt_plus_season,
            "IsPromo": self.is_promo,
            "Category": UInt8(self.category),
            "Mode": UInt8(self.mode),
            "UseInvVehicle": self.use_inv_vehicle,
            "ClubId": Int64(self.club_id),
            "EsportsMonthId": self.esports_month_id,
            "AttemptsAllowed": self.attempts_allowed,
        }


@dataclass
class Club:
    """A club listing entry."""
    id: int = 0
    name: str = ""
    creator_name: str = ""
    has_standings: bool = True
    is_other_platform: bool = False
    amount_of_events: int = 1
    event_index: int = 0
    is_upcoming: bool = False

    def to_egonet(self) -> Dict[str, Any]:
        return {
            "Id": Int64(self.id),
            "CreatorName": self.creator_name,
            "Name": self.name,
            "HasStandings": self.has_standings,
            "IsOtherPlatform": self.is_other_platform,
            "AmountOfEvents": self.amount_of_events,
            "EventIndex": self.event_index,
            "IsUpcoming": self.is_upcoming,
        }


# ---------------------------------------------------------------------------
# Stage lifecycle (request parsing)
# ---------------------------------------------------------------------------

@dataclass
class VehicleMud:
    dirt: float = 0.0
    wheel_mud_0: float = 0.0
    wheel_mud_1: float = 0.0
    wheel_mud_2: float = 0.0
    wheel_mud_3: float = 0.0
    mud: float = 0.0
    clean_height: float = 0.0
    clean_dirt: float = 0.0
    clean_mud: float = 0.0

    @classmethod
    def from_egonet(cls, data: Dict[str, Any]) -> VehicleMud:
        return cls(
            dirt=float(_val(data.get("Dirt", 0))),
            wheel_mud_0=float(_val(data.get("WheelMud0", 0))),
            wheel_mud_1=float(_val(data.get("WheelMud1", 0))),
            wheel_mud_2=float(_val(data.get("WheelMud2", 0))),
            wheel_mud_3=float(_val(data.get("WheelMud3", 0))),
            mud=float(_val(data.get("Mud", 0))),
            clean_height=float(_val(data.get("CleanHeight", 0))),
            clean_dirt=float(_val(data.get("CleanDirt", 0))),
            clean_mud=float(_val(data.get("CleanMud", 0))),
        )


@dataclass
class CompDamage:
    quick_repairs: int = 0
    bodywork: int = 0
    brakes: int = 0
    clutch: float = 0.0
    dampers: int = 0
    diff_wear: int = 0
    diff_impact: int = 0
    engine: float = 0.0
    exhaust: float = 0.0
    gearbox: int = 0
    lights: float = 0.0
    radiator: float = 0.0
    springs: int = 0
    turbo: int = 0
    wheels_wear: int = 0
    wheels_impact: int = 0

    @classmethod
    def from_egonet(cls, data: Dict[str, Any]) -> CompDamage:
        return cls(
            quick_repairs=_val(data.get("QuickRepairs", 0)),
            bodywork=_val(data.get("Bodywork", 0)),
            brakes=_val(data.get("Brakes", 0)),
            clutch=float(_val(data.get("Clutch", 0))),
            dampers=_val(data.get("Dampers", 0)),
            diff_wear=_val(data.get("DiffWear", 0)),
            diff_impact=_val(data.get("DiffImpact", 0)),
            engine=float(_val(data.get("Engine", 0))),
            exhaust=float(_val(data.get("Exhaust", 0))),
            gearbox=_val(data.get("Gearbox", 0)),
            lights=float(_val(data.get("Lights", 0))),
            radiator=float(_val(data.get("Radiator", 0))),
            springs=_val(data.get("Springs", 0)),
            turbo=_val(data.get("Turbo", 0)),
            wheels_wear=_val(data.get("WheelsWear", 0)),
            wheels_impact=_val(data.get("WheelsImpact", 0)),
        )


def _val(v: Any) -> Any:
    """Unwrap EgoNet type wrappers to plain Python values."""
    if isinstance(v, (UInt32, UInt8, Int64, Timestamp)):
        return v.value
    return v


@dataclass
class StageBeginRequest:
    vehicle_id: int = 0
    vehicle_inst_id: int = 0
    livery_id: int = 0
    stage_index: int = 0
    event_index: int = 0
    tuning_setup: bytes = b""
    challenge_id: int = 0
    nationality_id: int = 0
    tyres_remaining: int = 0
    tyre_compound: int = 0

    @classmethod
    def from_egonet(cls, data: Dict[str, Any]) -> StageBeginRequest:
        tuning = data.get("TuningSetup", {})
        if isinstance(tuning, dict):
            import base64
            tuning = base64.b64decode(tuning.get("blob_base64", ""))
        return cls(
            vehicle_id=_val(data.get("VehicleId", 0)),
            vehicle_inst_id=_val(data.get("VehicleInstId", 0)),
            livery_id=_val(data.get("LiveryId", 0)),
            stage_index=_val(data.get("StageIndex", 0)),
            event_index=_val(data.get("EventIndex", 0)),
            tuning_setup=tuning if isinstance(tuning, bytes) else b"",
            challenge_id=_val(data.get("ChallengeId", 0)),
            nationality_id=_val(data.get("NationalityId", 0)),
            tyres_remaining=_val(data.get("TyresRemaining", 0)),
            tyre_compound=_val(data.get("TyreCompound", 0)),
        )


@dataclass
class StageCompleteRequest:
    vehicle_id: int = 0
    vehicle_inst_id: int = 0
    livery_id: int = 0
    stage_index: int = 0
    event_index: int = 0
    challenge_id: int = 0
    nationality_id: int = 0
    stage_time: float = 0.0
    champ_rank: int = 0
    event_rank: int = 0
    meters_driven: int = 0
    distance_driven: int = 0
    using_wheel: bool = False
    using_assists: bool = False
    race_status: int = 0
    vehicle_mud: VehicleMud = field(default_factory=VehicleMud)
    comp_damage: CompDamage = field(default_factory=CompDamage)
    recov_to_service: bool = False

    @classmethod
    def from_egonet(cls, data: Dict[str, Any]) -> StageCompleteRequest:
        mud_data = data.get("VehicleMud", {})
        dmg_data = data.get("CompDamage", {})
        return cls(
            vehicle_id=_val(data.get("VehicleId", 0)),
            vehicle_inst_id=_val(data.get("VehicleInstId", 0)),
            livery_id=_val(data.get("LiveryId", 0)),
            stage_index=_val(data.get("StageIndex", 0)),
            event_index=_val(data.get("EventIndex", 0)),
            challenge_id=_val(data.get("ChallengeId", 0)),
            nationality_id=_val(data.get("NationalityId", 0)),
            stage_time=float(data.get("StageTime", 0)),
            champ_rank=_val(data.get("ChampRank", 0)),
            event_rank=_val(data.get("EventRank", 0)),
            meters_driven=_val(data.get("MetersDriven", 0)),
            distance_driven=_val(data.get("DistanceDriven", 0)),
            using_wheel=bool(data.get("UsingWheel", False)),
            using_assists=bool(data.get("UsingAssists", False)),
            race_status=_val(data.get("RaceStatus", 0)),
            vehicle_mud=VehicleMud.from_egonet(mud_data) if isinstance(mud_data, dict) else VehicleMud(),
            comp_damage=CompDamage.from_egonet(dmg_data) if isinstance(dmg_data, dict) else CompDamage(),
            recov_to_service=bool(data.get("RecovToService", False)),
        )


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------

@dataclass
class LeaderboardEntry:
    rank: int = 0
    name: str = ""
    vehicle_id: int = 0
    stage_time: float = 0.0
    diff_first: float = 0.0
    nationality_id: int = 0
    platform: int = 0

    def to_egonet(self) -> Dict[str, Any]:
        return {
            "Rank": self.rank,
            "Name": self.name,
            "VehicleId": UInt32(self.vehicle_id),
            "StageTime": self.stage_time,
            "DiffFirst": self.diff_first,
            "NationalityId": self.nationality_id,
            "Platform": self.platform,
        }
