"""Overlay .txt files are cleared on shutdown.

Streamers want their OBS / SimHub text sources to go blank when DirtForever
isn't running instead of holding the last race's values (issue #26). The
StreamingWriter writes the FILES map into the output dir while running and
clears them via clear_files() on shutdown.

The exit behavior is configurable (issue #36): the default "clear" blanks the
files in place because OBS reports missing files as an error on startup;
"delete" removes them entirely, the pre-#36 behavior.
"""
from __future__ import annotations

from pathlib import Path

from dr2server.streaming import (
    DEFAULT_EXIT_BEHAVIOR,
    EXIT_BEHAVIOR_CLEAR,
    EXIT_BEHAVIOR_DELETE,
    FILES,
    StreamingWriter,
)


def _make_writer(out_dir: Path, exit_behavior: str | None = None) -> StreamingWriter:
    # clear_files() only touches the output dir and the logger, so a dummy
    # dispatcher and a no-op logger are enough.
    writer = StreamingWriter(dispatcher=object(), logger=lambda _m: None)
    writer.set_output_dir(out_dir)
    if exit_behavior is not None:
        writer.set_exit_behavior(exit_behavior)
    return writer


def test_default_exit_behavior_is_clear() -> None:
    assert DEFAULT_EXIT_BEHAVIOR == EXIT_BEHAVIOR_CLEAR


def test_clear_files_blanks_all_overlay_files_by_default(tmp_path: Path) -> None:
    # Default behavior: files stay on disk (OBS errors on missing files) but
    # their contents are emptied so overlays go blank.
    for filename in FILES.values():
        (tmp_path / filename).write_text("stale", encoding="utf-8")

    _make_writer(tmp_path).clear_files()

    for filename in FILES.values():
        path = tmp_path / filename
        assert path.exists(), f"{filename} was deleted in clear mode"
        assert path.read_text(encoding="utf-8") == "", f"{filename} not blanked"


def test_clear_mode_does_not_create_missing_files(tmp_path: Path) -> None:
    # Only one overlay file exists; blanking must not create the others.
    sample = next(iter(FILES.values()))
    (tmp_path / sample).write_text("stale", encoding="utf-8")

    _make_writer(tmp_path).clear_files()

    assert (tmp_path / sample).read_text(encoding="utf-8") == ""
    for filename in FILES.values():
        if filename != sample:
            assert not (tmp_path / filename).exists(), (
                f"clear mode created {filename} out of thin air"
            )


def test_delete_mode_removes_all_overlay_files(tmp_path: Path) -> None:
    for filename in FILES.values():
        (tmp_path / filename).write_text("stale", encoding="utf-8")

    _make_writer(tmp_path, EXIT_BEHAVIOR_DELETE).clear_files()

    for filename in FILES.values():
        assert not (tmp_path / filename).exists(), f"{filename} not deleted"


def test_unknown_exit_behavior_falls_back_to_clear(tmp_path: Path) -> None:
    sample = next(iter(FILES.values()))
    (tmp_path / sample).write_text("stale", encoding="utf-8")

    _make_writer(tmp_path, "obliterate").clear_files()

    assert (tmp_path / sample).exists()
    assert (tmp_path / sample).read_text(encoding="utf-8") == ""


def test_clear_files_removes_leftover_tmp_in_both_modes(tmp_path: Path) -> None:
    # _atomic_write writes "<name>.tmp" then os.replace()s it; a crash mid-write
    # can leave the .tmp behind, so clear_files must remove those too.
    sample = next(iter(FILES.values()))
    for behavior in (EXIT_BEHAVIOR_CLEAR, EXIT_BEHAVIOR_DELETE):
        (tmp_path / sample).write_text("done", encoding="utf-8")
        (tmp_path / (sample + ".tmp")).write_text("half-written", encoding="utf-8")

        _make_writer(tmp_path, behavior).clear_files()

        assert not (tmp_path / (sample + ".tmp")).exists(), (
            f".tmp left behind in {behavior} mode"
        )
        if behavior == EXIT_BEHAVIOR_DELETE:
            assert not (tmp_path / sample).exists()
        else:
            assert (tmp_path / sample).read_text(encoding="utf-8") == ""
            (tmp_path / sample).unlink()


def test_clear_files_leaves_unrelated_files_alone(tmp_path: Path) -> None:
    for behavior in (EXIT_BEHAVIOR_CLEAR, EXIT_BEHAVIOR_DELETE):
        keep = tmp_path / "my notes.txt"
        keep.write_text("user file", encoding="utf-8")
        (tmp_path / next(iter(FILES.values()))).write_text("overlay", encoding="utf-8")

        _make_writer(tmp_path, behavior).clear_files()

        assert keep.exists(), f"clear_files deleted a file it does not own ({behavior})"
        assert keep.read_text(encoding="utf-8") == "user file"


def test_clear_files_is_safe_when_nothing_to_clear(tmp_path: Path) -> None:
    # No overlay files present (and dir empty), must not raise in either mode.
    _make_writer(tmp_path).clear_files()
    _make_writer(tmp_path, EXIT_BEHAVIOR_DELETE).clear_files()


def test_clear_files_is_safe_when_dir_missing(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    _make_writer(missing).clear_files()
    assert not missing.exists(), "clear_files should not create the output dir"
    _make_writer(missing, EXIT_BEHAVIOR_DELETE).clear_files()
    assert not missing.exists()


class _NoStateDispatcher:
    """Dispatcher whose streaming state makes _tick a no-op (no clubs_snapshot),
    so a running writer never writes or clears files on its own."""

    api_client = None

    def get_streaming_state(self):
        return {}


def test_set_output_dir_clears_old_dir_when_running(tmp_path: Path) -> None:
    # Repointing the output folder while the writer is running must clear the
    # overlay files left behind in the previous directory, so OBS / SimHub
    # stop showing stale values from the old folder. The exit behavior applies
    # here too: default mode blanks them in place.
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    old_dir.mkdir()

    writer = StreamingWriter(dispatcher=_NoStateDispatcher(), logger=lambda _m: None)
    writer.start(interval=60, output_dir=old_dir)
    try:
        for filename in FILES.values():
            (old_dir / filename).write_text("stale", encoding="utf-8")

        writer.set_output_dir(new_dir)

        for filename in FILES.values():
            path = old_dir / filename
            assert path.exists(), f"{filename} deleted from old dir in clear mode"
            assert path.read_text(encoding="utf-8") == "", (
                f"{filename} left stale in old dir"
            )
    finally:
        writer.stop()


def test_set_output_dir_deletes_old_dir_files_in_delete_mode(tmp_path: Path) -> None:
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    old_dir.mkdir()

    writer = StreamingWriter(dispatcher=_NoStateDispatcher(), logger=lambda _m: None)
    writer.set_exit_behavior(EXIT_BEHAVIOR_DELETE)
    writer.start(interval=60, output_dir=old_dir)
    try:
        for filename in FILES.values():
            (old_dir / filename).write_text("stale", encoding="utf-8")

        writer.set_output_dir(new_dir)

        for filename in FILES.values():
            assert not (old_dir / filename).exists(), f"{filename} left in old dir"
    finally:
        writer.stop()


def test_set_output_dir_does_not_clear_when_not_running(tmp_path: Path) -> None:
    # The initial start() calls set_output_dir() before the writer thread is
    # alive; that path must never touch files in the previous directory.
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    old_dir.mkdir()
    keep = old_dir / next(iter(FILES.values()))
    keep.write_text("not running", encoding="utf-8")

    writer = StreamingWriter(dispatcher=object(), logger=lambda _m: None)
    writer.set_output_dir(old_dir)  # not running -> no clear
    writer.set_output_dir(new_dir)  # still not running -> no clear

    assert keep.read_text(encoding="utf-8") == "not running", (
        "set_output_dir touched old dir while not running"
    )


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
    # after shutdown was signalled must not repopulate files clear_files()
    # just blanked. With _stop set, _tick must write nothing.
    writer = StreamingWriter(dispatcher=_StubDispatcher(), logger=lambda _m: None)
    writer.set_output_dir(tmp_path)
    club_file = tmp_path / FILES["club"]

    # Sanity: without stop set, this tick writes the club file.
    writer._tick(1)
    assert club_file.read_text(encoding="utf-8") == "Test Club"

    writer.clear_files()
    assert club_file.read_text(encoding="utf-8") == ""

    # Now simulate shutdown signalled mid-tick: the next tick must not write.
    writer._stop.set()
    writer._tick(2)
    assert club_file.read_text(encoding="utf-8") == "", (
        "_tick wrote after stop was requested, repopulating cleared files"
    )
