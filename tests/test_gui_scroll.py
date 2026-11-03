"""The Advanced tab scrolls when its cards are taller than the window.

``dirtforever.py`` redirects stdout at import time and runs the Tk main
loop from ``run_gui()``, so the scroll helper is pulled out of its source
with ``ast`` and driven in a separate process (tests/gui_scroll_probe.py).
Needs a display; skipped headless.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "tests" / "gui_scroll_probe.py"
GUI_SOURCE = (ROOT / "dirtforever.py").read_text(encoding="utf-8")


def test_advanced_tab_is_scrollable_and_wraps_the_capture_label():
    layout = GUI_SOURCE.split("# --- Tabbed layout ---")[1].split("# --- Header ---")[0]
    assert 'notebook.add(advanced_outer, text="Advanced")' in layout
    assert 'text="Logs"' not in layout
    assert "advanced_tab = _scrollable_body(advanced_outer)" in layout
    # The checkbox text that was cut off in v1.9.8 is short and wraps.
    assert 'text="RaceNet capture session",' in GUI_SOURCE
    assert "(only when support asks for it)" not in GUI_SOURCE


@pytest.fixture(scope="module")
def probe():
    proc = subprocess.run(
        [sys.executable, "-I", str(PROBE)],
        capture_output=True, text=True, timeout=120, cwd=str(ROOT),
    )
    if proc.returncode == 3:
        pytest.skip(f"no display: {proc.stdout.strip()}")
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_scroll_helper_exposes_content_taller_than_the_window(probe):
    assert probe["bar_manager"] == "pack"
    assert probe["body_reqheight"] > 560, "probe content must overflow the window"
    assert probe["region_height"] == probe["body_reqheight"]
    top_first, top_last = probe["view_top"]
    assert top_first == 0.0 and top_last < 1.0
    bottom_first, bottom_last = probe["view_bottom"]
    assert bottom_last == 1.0 and bottom_first > 0.0


def test_wheel_events_scroll_the_canvas(probe):
    pos = probe["wheel_positions"]
    assert pos["delta_down"] > pos["start"], "wheel delta < 0 scrolls down"
    assert pos["delta_up"] < pos["delta_down"], "wheel delta > 0 scrolls up"
    if probe["tk_version"] < 9:
        # Tk 8.6 on X11 reports the wheel as Button-5 (down) / Button-4 (up);
        # Tk 9 delivers a delta there too and the synthetic buttons are inert.
        assert pos["button5"] > pos["delta_up"], "X11 Button-5 scrolls down"
        assert pos["button4"] < pos["button5"], "X11 Button-4 scrolls up"
