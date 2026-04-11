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

from .game_data import Location, Track, VehicleClass

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
    "monaco":       int(Location.MONTE_CARLO),
    "monte carlo":  int(Location.MONTE_CARLO),
    "usa":          int(Location.NEW_ENGLAND),
    "new england":  int(Location.NEW_ENGLAND),
}
_LOCATION_BY_NAME.update(_EXTRA_LOCATION_ALIASES)


def _location_id_for(name: str) -> Optional[int]:
    """Return the integer LocationId for a display-name string, or None."""
    return _LOCATION_BY_NAME.get(name.strip().lower())


# vehicle class label (case-insensitive) -> VehicleClass int ID
_VCLASS_BY_LABEL: Dict[str, int] = {}
for _vc in VehicleClass:
    _VCLASS_BY_LABEL[_vc.label.lower()] = int(_vc)
# Normalisation aliases so web UI names match game IDs
_EXTRA_VCLASS_ALIASES: Dict[str, int] = {
    "h2 (rwd)":      int(VehicleClass.H2_RWD),
    "h2 rwd":         int(VehicleClass.H2_RWD),
    "h3 (rwd)":      int(VehicleClass.H3_RWD),
    "h3 rwd":         int(VehicleClass.H3_RWD),
    "h2 (fwd)":      int(VehicleClass.H2_FWD),
    "h2 fwd":         int(VehicleClass.H2_FWD),
    "f2 kit car":    int(VehicleClass.F2_KIT_CAR),
    "f2 kit cars":   int(VehicleClass.F2_KIT_CAR),
    "nr4/r4":        int(VehicleClass.NR4_R4),
    "rx supercars":  int(VehicleClass.RX_SUPERCARS),
    "rx super 1600": int(VehicleClass.RX_SUPER_1600),
}
_VCLASS_BY_LABEL.update(_EXTRA_VCLASS_ALIASES)


def _vclass_id_for(label: str) -> Optional[int]:
    """Return the integer VehicleClassId for a car-class label, or None."""
    return _VCLASS_BY_LABEL.get(label.strip().lower())


# location ID -> list[int] of Track IDs for that location
_TRACKS_BY_LOCATION: Dict[int, List[int]] = {}
for _track in Track:
    _loc_id = int(_track.location)
    _TRACKS_BY_LOCATION.setdefault(_loc_id, []).append(int(_track))


def _default_tracks_for_location(location_id: int) -> List[int]:
    """Return all Track IDs for a location.  Empty list if unknown."""
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

    def submit_stage(
        self,
        event_id: str,
        username: str,
        stage_index: int,
        time_ms: int,
        vehicle_id: Optional[int] = None,
        penalties_ms: int = 0,
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
        }
        if vehicle_id is not None:
            payload["vehicle_id"] = vehicle_id
        payload.update(extra)

        result = self._post("/api/game/stage-complete", payload)
        if result and result.get("ok"):
            return True
        log.warning(
            "submit_stage: failed for event=%s user=%s stage=%d",
            event_id, username, stage_index,
        )
        return False

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
