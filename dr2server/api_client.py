"""HTTP client for communicating with the dirtforever.net web API.

The game server calls this module to sync club/event data and submit
stage completions.  All requests use the stdlib ``urllib.request`` so
there are no third-party dependencies.

String-to-integer ID mapping
-----------------------------
The web API uses human-readable string identifiers:
  - Locations: "Argentina", "New Zealand", "Wales", …
  - Car classes: "Group A", "R5", "NR4/R4", …

The game server needs integer IDs (LocationId, VehicleClassId).  This
module builds lookup tables from the game_data enums at import time and
applies them when converting API data to EgoNet-compatible structures.

Tracks are chosen by picking the first Track that belongs to the mapped
Location.  This is intentionally simple; the full track selection can
be refined once real event data flows through the system.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from .game_data import Location, Track, VehicleClass, VERIFIED_TRACK_IDS

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Build lookup tables from game_data enums
# ---------------------------------------------------------------------------

# location display_name (case-insensitive) -> Location int ID
_LOCATION_BY_NAME: Dict[str, int] = {}
for _loc in Location:
    _LOCATION_BY_NAME[_loc.display_name.lower()] = int(_loc)
# Extra aliases used in the web seed data
_EXTRA_LOCATION_ALIASES: Dict[str, int] = {
    "usa":           int(Location.NEW_ENGLAND),
    "new england":   int(Location.NEW_ENGLAND),
    "norway":        int(Location.HELL),
    "portugal":      int(Location.MONTALEGRE),
    "england":       int(Location.LYDDEN_HILL),
    "france":        int(Location.LOHEAC),
    "ribadelles":    int(Location.SPAIN),
    "barcelona":     int(Location.BARCELONA),
}
_LOCATION_BY_NAME.update(_EXTRA_LOCATION_ALIASES)


def _location_id_for(name: str) -> Optional[int]:
    """Return the integer LocationId for a display-name string, or None."""
    return _LOCATION_BY_NAME.get(name.strip().lower())


# vehicle class label (case-insensitive) -> VehicleClass int ID
_VCLASS_BY_LABEL: Dict[str, int] = {}
for _vc in VehicleClass:
    _VCLASS_BY_LABEL[_vc.label.lower()] = int(_vc)
# Normalisation aliases so web UI names (with various formats) match game IDs
_EXTRA_VCLASS_ALIASES: Dict[str, int] = {
    "h1 (fwd)":       int(VehicleClass.H1_FWD),
    "h2 (fwd)":       int(VehicleClass.H2_FWD),
    "h2 (rwd)":       int(VehicleClass.H2_RWD),
    "h3 (rwd)":       int(VehicleClass.H3_RWD),
    "group b (4wd)":  int(VehicleClass.GROUP_B_4WD),
    "group b (awd)":  int(VehicleClass.GROUP_B_4WD),
    "group b (rwd)":  int(VehicleClass.GROUP_B_RWD),
    "group b rallycross": int(VehicleClass.GROUP_B_RX),
    "f2 kit cars":    int(VehicleClass.F2_KIT_CAR),
    "rally gt":       int(VehicleClass.NR4_R4),  # no confirmed Rally GT ID
    "2000cc 4wd":     int(VehicleClass.CC_4WD),
    "4wd <= 2000cc":  int(VehicleClass.CC_4WD),
    "cross kart":     int(VehicleClass.CROSS_KART),
}
_VCLASS_BY_LABEL.update(_EXTRA_VCLASS_ALIASES)


def _vclass_id_for(label: str) -> Optional[int]:
    """Return the integer VehicleClassId for a car-class label, or None."""
    return _VCLASS_BY_LABEL.get(label.strip().lower())


# location ID -> list[int] of VERIFIED Track IDs for that location.
# Unverified tracks are excluded — if the game receives an unverified
# TrackModelId it loads the wrong stage (different location from what was
# picked).  See game_data.VERIFIED_TRACK_IDS for the allow-list.
#
# Set DR2_DISCOVERY_MODE=1 in the environment to bypass the verified-track
# filter.  This is required for the enum-mapping testing round: the game
# renders an unverified TrackModelId's real stage name in the event detail
# screen, so we serve the unverified IDs deliberately and OCR the result.
import os as _os
_DISCOVERY_MODE = _os.environ.get("DR2_DISCOVERY_MODE") == "1"

_TRACKS_BY_LOCATION: Dict[int, List[int]] = {}
for _track in Track:
    if not _DISCOVERY_MODE and int(_track) not in VERIFIED_TRACK_IDS:
        continue
    _loc_id = int(_track.location)
    _TRACKS_BY_LOCATION.setdefault(_loc_id, []).append(int(_track))


def _default_tracks_for_location(location_id: int) -> List[int]:
    """Return Track IDs for a location.  Empty list if none known.

    In discovery mode all claimed tracks are returned (for UI observation);
    otherwise only entries in game_data.VERIFIED_TRACK_IDS.
    """
    return _TRACKS_BY_LOCATION.get(location_id, [])


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class DirtForeverClient:
    """Thin HTTP client for the dirtforever.net game API."""

    def __init__(self, base_url: str = "https://dirtforever.net", api_token: Optional[str] = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def _auth_headers(self) -> Dict[str, str]:
        h = {"Accept": "application/json"}
        if self.api_token:
            h["Authorization"] = f"Bearer {self.api_token}"
        return h

    def _get(self, path: str) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}{path}"
        try:
            req = urllib.request.Request(url, headers=self._auth_headers())
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read()
            return json.loads(raw)
        except urllib.error.HTTPError as exc:
            log.error("GET %s -> HTTP %s", url, exc.code)
        except urllib.error.URLError as exc:
            log.error("GET %s -> network error: %s", url, exc.reason)
        except Exception as exc:
            log.error("GET %s -> unexpected error: %s", url, exc)
        return None

    def _post(self, path: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}{path}"
        body = json.dumps(payload).encode("utf-8")
        try:
            headers = self._auth_headers()
            headers["Content-Type"] = "application/json"
            req = urllib.request.Request(
                url,
                data=body,
                method="POST",
                headers=headers,
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read()
            return json.loads(raw)
        except urllib.error.HTTPError as exc:
            log.error("POST %s -> HTTP %s", url, exc.code)
        except urllib.error.URLError as exc:
            log.error("POST %s -> network error: %s", url, exc.reason)
        except Exception as exc:
            log.error("POST %s -> unexpected error: %s", url, exc)
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def test_token(self) -> Optional[str]:
        """Test if the current token is valid. Returns username or None."""
        data = self._get("/api/game/token-test")
        if data and data.get("ok"):
            return data.get("username")
        return None

    def get_clubs(self) -> Dict[str, Any]:
        """Fetch clubs and active events from the web API.

        Returns a dict with keys ``"clubs"`` and ``"events"`` (both lists).
        On error, returns empty lists so the caller can fall back gracefully.
        """
        result = self._get("/api/game/clubs")
        if not result or not result.get("ok"):
            log.warning("get_clubs: empty or error response, returning empty")
            return {"clubs": [], "events": []}
        return {
            "clubs": result.get("clubs", []),
            "events": result.get("events", []),
        }

    def submit_stage_begin(
        self,
        event_id: str,
        stage_index: int,
        vehicle_id: Optional[int] = None,
        livery_id: int = 0,
        tuning_setup_b64: str = "",
        tyre_compound: int = 2,
        tyres_remaining: int = 3,
        nationality_id: int = 0,
    ) -> bool:
        """Store pre-stage setup data on the web server before a stage starts.

        Returns True on success, False on any error.
        """
        payload: Dict[str, Any] = {
            "event_id": event_id,
            "stage_index": stage_index,
            "livery_id": livery_id,
            "tuning_setup_b64": tuning_setup_b64,
            "tyre_compound": tyre_compound,
            "tyres_remaining": tyres_remaining,
            "nationality_id": nationality_id,
        }
        if vehicle_id is not None:
            payload["vehicle_id"] = vehicle_id
        result = self._post("/api/game/stage-begin", payload)
        if result and result.get("ok"):
            return True
        log.warning(
            "submit_stage_begin: failed for event=%s stage=%d",
            event_id, stage_index,
        )
        return False

    def submit_stage(
        self,
        event_id: str,
        username: str,
        stage_index: int,
        time_ms: int,
        vehicle_id: Optional[int] = None,
        penalties_ms: int = 0,
        meters_driven: int = 0,
        distance_driven: int = 0,
        vehicle_mud: Optional[Dict[str, Any]] = None,
        comp_damage: Optional[Dict[str, Any]] = None,
        using_wheel: bool = False,
        using_assists: bool = False,
        race_status: int = 0,
        nationality_id: int = 0,
        livery_id: int = 0,
        has_repaired: bool = False,
        repair_penalty_ms: int = 0,
        tuning_setup_b64: str = "",
        tyre_compound: int = 2,
        tyres_remaining: int = 3,
        **extra: Any,
    ) -> bool:
        """Submit a completed stage to the web API.

        Returns True on success, False on any error.
        """
        payload: Dict[str, Any] = {
            "event_id": event_id,
            "username": username,
            "stage_index": stage_index,
            "time_ms": time_ms,
            "penalties_ms": penalties_ms,
            "meters_driven": meters_driven,
            "distance_driven": distance_driven,
            "using_wheel": using_wheel,
            "using_assists": using_assists,
            "race_status": race_status,
            "nationality_id": nationality_id,
            "livery_id": livery_id,
            "has_repaired": has_repaired,
            "repair_penalty_ms": repair_penalty_ms,
            "tuning_setup_b64": tuning_setup_b64,
            "tyre_compound": tyre_compound,
            "tyres_remaining": tyres_remaining,
        }
        if vehicle_id is not None:
            payload["vehicle_id"] = vehicle_id
        if vehicle_mud is not None:
            payload["vehicle_mud"] = vehicle_mud
        if comp_damage is not None:
            payload["comp_damage"] = comp_damage
        payload.update(extra)

        result = self._post("/api/game/stage-complete", payload)
        if result and result.get("ok"):
            return True
        log.warning(
            "submit_stage: failed for event=%s user=%s stage=%d",
            event_id, username, stage_index,
        )
        return False

    def get_my_progress(self) -> Optional[Dict[str, Any]]:
        """Fetch the authenticated user's full progress across all events.

        Returns the response dict (with key ``"events"``) or None on error.
        """
        result = self._get("/api/game/my-progress")
        if not result or not result.get("ok"):
            log.warning("get_my_progress: empty or error response")
            return None
        return result

    def get_leaderboard(self, event_id: str) -> List[Dict[str, Any]]:
        """Return leaderboard entries for an event.

        Each entry has at minimum: rank, username, total_time_ms.
        Returns an empty list on error.
        """
        result = self._get(f"/api/game/leaderboard/{event_id}")
        if not result or not result.get("ok"):
            log.warning("get_leaderboard: empty or error response for event=%s", event_id)
            return []
        return result.get("entries", [])

    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Return event details dict, or None on error / not found."""
        result = self._get(f"/api/game/events/{event_id}")
        if not result or not result.get("ok"):
            log.warning("get_event: not found or error for event=%s", event_id)
            return None
        return result.get("event")

    def get_profile(self) -> Optional[Dict[str, Any]]:
        """Fetch the authenticated user's game profile from the web API.

        Returns the profile dict (with keys username, display_name, country,
        soft_currency, hard_currency, garage_slots) or None on error.
        """
        result = self._get("/api/game/profile")
        if not result or not result.get("ok"):
            log.warning("get_profile: empty or error response")
            return None
        return result

    def submit_time_trial(
        self,
        vehicle_class_id: int,
        track_model_id: int,
        conditions_id: int,
        category: int,
        vehicle_id: int,
        livery_id: int,
        stage_time_ms: int,
        nationality_id: int,
        using_wheel: bool,
        using_assists: bool,
        ghost_data_b64: str,
    ) -> bool:
        """Submit a time trial result to the web API.

        Returns True on success, False on any error.
        """
        payload: Dict[str, Any] = {
            "vehicle_class_id": vehicle_class_id,
            "track_model_id": track_model_id,
            "conditions_id": conditions_id,
            "category": category,
            "vehicle_id": vehicle_id,
            "livery_id": livery_id,
            "stage_time_ms": stage_time_ms,
            "nationality_id": nationality_id,
            "using_wheel": using_wheel,
            "using_assists": using_assists,
            "ghost_data_b64": ghost_data_b64,
        }
        result = self._post("/api/game/time-trial-submit", payload)
        if result and result.get("ok"):
            return True
        log.warning(
            "submit_time_trial: failed vclass=%d track=%d conditions=%d cat=%d",
            vehicle_class_id, track_model_id, conditions_id, category,
        )
        return False

    def get_time_trial_leaderboard(
        self,
        vclass: int,
        track: int,
        conditions: int,
        category: int,
    ) -> List[Dict[str, Any]]:
        """Return time trial leaderboard entries for the given 4-tuple.

        Returns an empty list on error.
        """
        path = (
            f"/api/game/time-trial-leaderboard"
            f"?vclass={vclass}&track={track}&conditions={conditions}&category={category}"
        )
        result = self._get(path)
        if not result or not result.get("ok"):
            log.warning(
                "get_time_trial_leaderboard: empty or error response for "
                "vclass=%d track=%d conditions=%d cat=%d",
                vclass, track, conditions, category,
            )
            return []
        return result.get("entries", [])

    def get_time_trial_leaderboard_id(
        self,
        vclass: int,
        track: int,
        conditions: int,
        category: int,
    ) -> Optional[int]:
        """Return a stable integer LeaderboardId for the given 4-tuple.

        Returns None on error.
        """
        path = (
            f"/api/game/time-trial-leaderboard-id"
            f"?vclass={vclass}&track={track}&conditions={conditions}&category={category}"
        )
        result = self._get(path)
        if not result or not result.get("ok"):
            log.warning(
                "get_time_trial_leaderboard_id: empty or error response for "
                "vclass=%d track=%d conditions=%d cat=%d",
                vclass, track, conditions, category,
            )
            return None
        lb_id = result.get("leaderboard_id")
        return int(lb_id) if lb_id is not None else None

    def auth(self, steam_name: str, account_id: Optional[int] = None) -> Dict[str, Any]:
        """Validate / link a Steam account.

        Returns the API response dict (always contains ``"ok"`` key).
        On network error returns ``{"ok": False}``.
        """
        payload: Dict[str, Any] = {"steam_name": steam_name}
        if account_id is not None:
            payload["account_id"] = account_id
        result = self._post("/api/game/auth", payload)
        if result is None:
            return {"ok": False}
        return result

    # ------------------------------------------------------------------
    # Conversion helpers (web format -> EgoNet model parameters)
    # ------------------------------------------------------------------

    def resolve_location_id(self, location_name: str) -> Optional[int]:
        """Map a web-API location string to an integer LocationId."""
        return _location_id_for(location_name)

    def resolve_vclass_id(self, car_class_label: str) -> Optional[int]:
        """Map a web-API car class string to an integer VehicleClassId."""
        return _vclass_id_for(car_class_label)

    def tracks_for_location(self, location_id: int) -> List[int]:
        """Return all Track IDs (TrackModelId) for a given LocationId."""
        return _default_tracks_for_location(location_id)
