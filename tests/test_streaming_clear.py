"""Overlay .txt files are deleted on shutdown.

Streamers want their OBS / SimHub text sources to go blank when DirtForever
isn't running instead of holding the last race's values (issue #26). The
StreamingWriter writes the FILES map into the output dir while running and
clears them via clear_files() on shutdown.
"""
from __future__ import annotations

from pathlib import Path

from dr2server.streaming import FILES, StreamingWriter


def _make_writer(out_dir: Path) -> StreamingWriter:
    # clear_files() only touches the output dir and the logger, so a dummy
    # dispatcher and a no-op logger are enough.
    writer = StreamingWriter(dispatcher=object(), logger=lambda _m: None)
    writer.set_output_dir(out_dir)
    return writer


def test_clear_files_removes_all_overlay_files(tmp_path: Path) -> None:
    for filename in FILES.values():
        (tmp_path / filename).write_text("stale", encoding="utf-8")

    _make_writer(tmp_path).clear_files()

    for filename in FILES.values():
        assert not (tmp_path / filename).exists(), f"{filename} not deleted"


def test_clear_files_removes_leftover_tmp(tmp_path: Path) -> None:
    # _atomic_write writes "<name>.tmp" then os.replace()s it; a crash mid-write
    # can leave the .tmp behind, so clear_files must remove those too.
    sample = next(iter(FILES.values()))
    (tmp_path / sample).write_text("done", encoding="utf-8")
    (tmp_path / (sample + ".tmp")).write_text("half-written", encoding="utf-8")

    _make_writer(tmp_path).clear_files()

    assert not (tmp_path / sample).exists()
    assert not (tmp_path / (sample + ".tmp")).exists()


def test_clear_files_leaves_unrelated_files_alone(tmp_path: Path) -> None:
    keep = tmp_path / "my notes.txt"
    keep.write_text("user file", encoding="utf-8")
    (tmp_path / next(iter(FILES.values()))).write_text("overlay", encoding="utf-8")

    _make_writer(tmp_path).clear_files()

    assert keep.exists(), "clear_files deleted a file it does not own"
    assert keep.read_text(encoding="utf-8") == "user file"


def test_clear_files_is_safe_when_nothing_to_clear(tmp_path: Path) -> None:
    # No overlay files present (and dir empty) — must not raise.
    _make_writer(tmp_path).clear_files()


def test_clear_files_is_safe_when_dir_missing(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    _make_writer(missing).clear_files()
    assert not missing.exists(), "clear_files should not create the output dir"


class _StubDispatcher:
    """Dispatcher whose streaming state would write the 'club' overlay file."""

    api_client = None

    def get_streaming_state(self):
        return {
            "clubs_snapshot": {
                "clubs": [{"id": "c1", "name": "Test Club"}],
                "events": [{"id": "e1", "club_id": "c1"}],
            },
            "event_id": "e1",
            "club_id": "c1",
            "vehicle_id": None,
        }


def test_tick_does_not_write_after_stop_requested(tmp_path: Path) -> None:
    # Regression: a tick that resumes (e.g. from a slow leaderboard fetch)
    # after shutdown was signalled must not re-create files clear_files()
    # just deleted. With _stop set, _tick must write nothing.
    writer = StreamingWriter(dispatcher=_StubDispatcher(), logger=lambda _m: None)
    writer.set_output_dir(tmp_path)

    # Sanity: without stop set, this tick writes the club file.
    writer._tick(1)
    assert (tmp_path / FILES["club"]).exists()

    writer.clear_files()
    assert not (tmp_path / FILES["club"]).exists()

    # Now simulate shutdown signalled mid-tick: the next tick must not write.
    writer._stop.set()
    writer._tick(2)
    assert not (tmp_path / FILES["club"]).exists(), (
        "_tick wrote after stop was requested, re-creating cleared files"
    )
