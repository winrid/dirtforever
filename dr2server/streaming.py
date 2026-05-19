"""Streaming overlay file writer for OBS / SimHub.

Polls RpcDispatcher state on an interval and writes a handful of plain .txt
files into a target directory (defaults to ~/dirtforever/). OBS Text (GDI+)
and SimHub Text sources can read these files directly to display the player's
current club, event, car, etc. on stream.

Idle behaviour: when no current event is known the writer skips writing rather
than blanking the files, so overlays keep their last known values between
sessions.
"""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Set

from .game_data import VEHICLES


# Filename map. Keys are internal field names; values are the on-disk filenames
# OBS / SimHub will be pointed at. Filenames are intentionally human-readable
# with spaces to make picking them in OBS source dialogs easier.
FILES: Dict[str, str] = {
    "club":         "Current Club.txt",
    "club_owner":   "Club Owner.txt",
    "members":      "Number of members.txt",
    "stages":       "Number of Stages.txt",
    "location":     "Location.txt",
    "car":          "Car.txt",
    "car_class":    "Car Class.txt",
    "leaderboard":  "Leaderboard.txt",
}

MIN_INTERVAL_SECONDS = 2.0
DEFAULT_INTERVAL_SECONDS = 5.0

# Leaderboard fetches go to the web API. Cap the refresh rate so that a fast
# tick interval doesn't hammer the server with one request per user every 2s.
LEADERBOARD_MIN_REFRESH_SECONDS = 10.0
LEADERBOARD_TOP_N = 10


def _atomic_write(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def _format_time_ms(ms: int) -> str:
    if ms is None or ms < 0:
        return "--:--.---"
    total_seconds, millis = divmod(int(ms), 1000)
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}:{seconds:02d}.{millis:03d}"


def _format_leaderboard(entries: List[Dict[str, Any]], limit: int = LEADERBOARD_TOP_N) -> str:
    if not entries:
        return ""
    lines: List[str] = []
    name_width = max(
        (len(str(e.get("username", ""))) for e in entries[:limit]),
        default=0,
    )
    name_width = max(name_width, 8)
    for e in entries[:limit]:
        rank = e.get("rank") or (len(lines) + 1)
        name = str(e.get("username", ""))
        t = _format_time_ms(int(e.get("total_time_ms", 0) or 0))
        lines.append(f"{rank:>2}. {name.ljust(name_width)}  {t}")
    return "\n".join(lines)


class StreamingWriter:
    def __init__(
        self,
        dispatcher: Any,
        logger: Optional[Callable[[str], None]] = None,
        verbose: Optional[Callable[[], bool]] = None,
    ) -> None:
        self._dispatcher = dispatcher
        self._log = logger or (lambda m: print(m))
        # Verbose-mode getter (called each tick). False -> per-tick state /
        # skip-reason lines are suppressed; errors and lifecycle events
        # always go through self._log.
        self._verbose = verbose or (lambda: False)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._interval: float = DEFAULT_INTERVAL_SECONDS
        self._output_dir: Path = Path.home() / "dirtforever"
        self._last_written: Dict[str, str] = {}
        self._enabled: Set[str] = set(FILES.keys())
        self._lb_cache_text: Optional[str] = None
        self._lb_cache_ts: float = 0.0
        self._lb_cache_event_id: Optional[str] = None

    def _vlog(self, msg: str) -> None:
        """Verbose log — only emits when the verbose flag is on."""
        try:
            if self._verbose():
                self._log(msg)
        except Exception:
            pass

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def set_interval(self, seconds: float) -> None:
        with self._lock:
            self._interval = max(MIN_INTERVAL_SECONDS, float(seconds))

    def set_output_dir(self, output_dir: Path) -> None:
        with self._lock:
            self._output_dir = Path(output_dir)
        # New directory invalidates the change-detection cache so the first
        # tick into a fresh dir actually writes the files.
        self._last_written.clear()

    def set_enabled(self, enabled: Iterable[str]) -> None:
        with self._lock:
            self._enabled = {k for k in enabled if k in FILES}
        # Drop change-detection entries for disabled keys so the next enable
        # forces a rewrite (in case the file on disk was edited externally).
        self._last_written = {
            k: v for k, v in self._last_written.items() if k in self._enabled
        }

    def _current_interval(self) -> float:
        with self._lock:
            return self._interval

    def _current_output_dir(self) -> Path:
        with self._lock:
            return self._output_dir

    def _current_enabled(self) -> Set[str]:
        with self._lock:
            return set(self._enabled)

    def start(self, interval: float, output_dir: Path) -> None:
        self.set_interval(interval)
        self.set_output_dir(output_dir)
        if self.is_running():
            return
        try:
            self._output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._log(f"[STREAM] failed to create {self._output_dir}: {exc}")
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="StreamingWriter", daemon=True,
        )
        self._thread.start()
        self._log(
            f"[STREAM] writer started, dir={self._output_dir} "
            f"interval={self._current_interval()}s"
        )

    def stop(self, timeout: float = 3.0) -> None:
        if not self.is_running():
            self._thread = None
            return
        self._stop.set()
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.join(timeout=timeout)
        self._log("[STREAM] writer stopped")

    def _loop(self) -> None:
        self._vlog(
            f"[STREAM] loop entered; interval={self._current_interval()}s "
            f"dir={self._current_output_dir()} "
            f"enabled={sorted(self._current_enabled())}"
        )
        tick_n = 0
        while not self._stop.is_set():
            tick_n += 1
            try:
                self._tick(tick_n)
            except Exception as exc:
                import traceback
                self._log(f"[STREAM] tick {tick_n} error: {exc}\n{traceback.format_exc()}")
            self._stop.wait(self._current_interval())

    def _maybe_fetch_leaderboard(self, event_id: str) -> Optional[str]:
        """Return a formatted leaderboard string, fetching if cache is stale.

        Returns None when no data is available and nothing should be written.
        """
        client = getattr(self._dispatcher, "api_client", None)
        if client is None or not event_id:
            return None

        now = time.time()
        cache_stale = (
            self._lb_cache_event_id != event_id
            or (now - self._lb_cache_ts) >= LEADERBOARD_MIN_REFRESH_SECONDS
        )
        if not cache_stale:
            return self._lb_cache_text

        try:
            entries = client.get_leaderboard(event_id) or []
        except Exception as exc:
            self._log(f"[STREAM] get_leaderboard({event_id}) failed: {exc}")
            return self._lb_cache_text  # serve stale rather than blank

        text = _format_leaderboard(entries)
        self._lb_cache_text = text or self._lb_cache_text
        self._lb_cache_event_id = event_id
        self._lb_cache_ts = now
        return self._lb_cache_text

    def _tick(self, tick_n: int = 0) -> None:
        state = self._dispatcher.get_streaming_state()
        snapshot = state.get("clubs_snapshot")
        if not snapshot:
            self._vlog(
                f"[STREAM] tick {tick_n}: skip — no clubs_snapshot yet "
                f"(event_id={state.get('event_id')!r} "
                f"club_id={state.get('club_id')!r} "
                f"vehicle_id={state.get('vehicle_id')!r})"
            )
            return

        enabled = self._current_enabled()
        if not enabled:
            self._vlog(f"[STREAM] tick {tick_n}: skip — no files enabled")
            return

        events_by_id: Dict[str, Dict[str, Any]] = {
            e.get("id", ""): e for e in (snapshot.get("events") or []) if e.get("id")
        }
        clubs_by_id: Dict[str, Dict[str, Any]] = {
            c.get("id", ""): c for c in (snapshot.get("clubs") or []) if c.get("id")
        }

        event_id = state.get("event_id") or ""
        event = events_by_id.get(event_id)
        club_id = state.get("club_id") or (event.get("club_id") if event else None)
        club = clubs_by_id.get(club_id or "")
        vehicle_id = state.get("vehicle_id")

        self._vlog(
            f"[STREAM] tick {tick_n}: state event_id={event_id!r} "
            f"club_id={club_id!r} vehicle_id={vehicle_id!r} "
            f"snapshot_events={len(events_by_id)} snapshot_clubs={len(clubs_by_id)} "
            f"event_found={event is not None} club_found={club is not None}"
        )

        values: Dict[str, str] = {}

        if club:
            if "club" in enabled:
                name = club.get("name")
                if name:
                    values["club"] = str(name)
            if "club_owner" in enabled:
                owner = club.get("created_by")
                if owner:
                    values["club_owner"] = str(owner)
            if "members" in enabled:
                members = club.get("members") or []
                values["members"] = f"{len(members)} members"

        if event:
            if "stages" in enabled:
                stages = event.get("stages") or []
                values["stages"] = f"{len(stages)} Stages"
            if "location" in enabled:
                location = event.get("location")
                if location:
                    values["location"] = str(location)
            if "car_class" in enabled:
                car_class = event.get("car_class")
                if car_class:
                    values["car_class"] = str(car_class)

        if "car" in enabled and isinstance(vehicle_id, int) and vehicle_id in VEHICLES:
            name = VEHICLES[vehicle_id].get("name")
            if name:
                values["car"] = str(name)

        if "leaderboard" in enabled and event_id:
            lb_text = self._maybe_fetch_leaderboard(event_id)
            if lb_text:
                values["leaderboard"] = lb_text

        out_dir = self._current_output_dir()
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._log(f"[STREAM] mkdir {out_dir} failed: {exc}")
            return

        if not values:
            self._vlog(
                f"[STREAM] tick {tick_n}: nothing to write — built no values "
                f"(enabled={sorted(enabled)})"
            )
            return

        wrote: List[str] = []
        skipped_unchanged: List[str] = []
        for key, content in values.items():
            filename = FILES.get(key)
            if not filename:
                continue
            if self._last_written.get(key) == content:
                skipped_unchanged.append(key)
                continue
            try:
                _atomic_write(out_dir / filename, content)
                self._last_written[key] = content
                wrote.append(key)
            except OSError as exc:
                self._log(f"[STREAM] write {filename} failed: {exc}")
        if wrote or skipped_unchanged:
            self._vlog(
                f"[STREAM] tick {tick_n}: wrote={wrote} "
                f"unchanged={skipped_unchanged} dir={out_dir}"
            )
