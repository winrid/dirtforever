"""Load a stage per candidate StageConditions id and capture how it renders.

Two ids can share a label but select different lighting files (16 wants
sunset_dry, 42 wants sunset_overcast), so a location loads only the twin whose
file it ships -- the other tears the sky into streaks while still showing the
right label in the UI. Only actually loading the stage tells them apart.

Serves one debug club per test, drives Clubs -> vehicle -> Service Area ->
Start, screenshots the intro flyby where the corruption is obvious, then quits
back to the Clubs list ready for the next one. The captures are for a human
(or model) to inspect: a clean sky versus green horizontal smearing is
unmistakable, and no threshold has to be tuned to see it.

Usage:
    python scripts/probe_twin_lighting.py plan.json
where plan.json is [{"name": "PL 016", "location_id": 36,
                     "track_model_id": 614, "stage_conditions": 16}, ...]
The server must be running with DR2_DEBUG_CLUBS_FILE pointing at
runtime/discovery/probe_twins.json, which this script rewrites per test.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import probe_all_conditions as nav          # noqa: E402
import probe_condition_labels as lbl        # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dr2server.game_data import STAGE_CONDITIONS_LABELS as LABELS  # noqa: E402
DISC = ROOT / 'runtime/discovery'
SERVED = DISC / 'probe_twins.json'
OUT = DISC / 'twin_shots'
BOX_SKIP = (1650, 955, 1820, 1005)   # intro-flyby "Skip" prompt
BOX_MODAL = (600, 380, 1500, 460)    # centred dialog title
BOX_TILES = (100, 300, 1900, 900)    # the tile grid, for reading its labels


# Poll interval for every wait below. Kept under a second so a state change is
# noticed promptly; each OCR read already costs a screenshot, so this is the
# floor rather than a tuning knob.
POLL = 0.5


def wait_header(want: str, timeout: float = 60) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if want in nav.header():
            return True
        time.sleep(POLL)
    return False


def wait_skip(present: bool, timeout: float = 90) -> bool:
    """Wait for the intro-flyby Skip prompt to appear (or disappear)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if ('skip' in lbl._ocr(BOX_SKIP).lower()) == present:
            return True
        time.sleep(POLL)
    return False


def serve(probe: dict) -> None:
    """Rewrite the debug clubs file; the next GetClubs picks it up."""
    SERVED.write_text(json.dumps({'probes': [probe]}, indent=2), encoding='utf-8')


def to_main_menu(tries: int = 6) -> bool:
    for _ in range(tries):
        st = screen()
        if st == 'MAIN MENU':
            return True
        if st == 'MODAL':
            nav.press('Enter', 1, 1200)     # dismiss / confirm
            continue
        nav.press('Escape', 1, 900)
    return screen() == 'MAIN MENU'


def on_freeplay_tab() -> bool:
    """True when the tile grid is Freeplay's.

    Matched on tiles unique to it -- "RACENET" alone is ambiguous, since the
    Options & Extras tab has a RaceNet account tile and matching that walks
    into Settings.
    """
    tiles = lbl._ocr(BOX_TILES, psm='6').upper()
    return any(t in tiles for t in ('TIME TRIAL', 'FREE ROAM', 'HISTORIC'))


def enter_clubs() -> bool:
    """Re-enter the Clubs list so the rewritten probe file is fetched.

    The main menu keeps whichever tab was last used -- a restart lands on My
    Team -- and both axes of the tile grid wrap, so no fixed key sequence lands
    on a known tile. Find the Freeplay tab by its labels, then walk its tiles
    until one opens the Clubs list.
    """
    if not to_main_menu():
        return False
    for _ in range(6):                      # F4 cycles the tab bar
        if on_freeplay_tab():
            break
        nav.press('F4', 1, 700)
    else:
        return False
    for i in range(6):
        nav.press('Enter', 1, 1200)
        if wait_header('CLUBS', 12):
            return True
        if not to_main_menu():
            return False
        if i == 2:                          # walked one row; drop to the other
            nav.press('Down', 1, 400)
        nav.press('Right', 1, 400)
    return False


MODAL_TITLES = ('CHAMPIONSHIP RESET', 'CONNECTION FAILED', 'ARE YOU SURE',
                'QUIT', 'EXIT GAME')


def screen() -> str:
    """Classify the current screen, including the ones with no breadcrumb."""
    # Modals dim the breadcrumb, so they have to be checked before it.
    title = lbl._ocr(BOX_MODAL, psm='6').upper()
    if any(t in title for t in MODAL_TITLES):
        return 'MODAL'
    h = nav.header()
    for name in ('CLUBS', 'VEHICLE SELECT', 'SERVICE AREA', 'CURRENT EVENT',
                 'MAIN MENU'):
        if name in h:
            return name
    if 'skip' in lbl._ocr(BOX_SKIP).lower():
        return 'FLYBY'
    return 'LOADING'          # loading screens show no breadcrumb


def run_one(probe: dict, out_dir: Path) -> str:
    """Drive one probe to a rendered stage, capture it, and come back.

    Reacts to whichever screen is up rather than following a fixed key
    sequence: load times vary enormously and a mis-timed step used to derail
    every later test.
    """
    serve(probe)
    if not enter_clubs():
        return 'could not reach the Clubs list'

    shot = out_dir / f"{probe['name'].replace(' ', '_')}.png"
    verified = False
    deadline = time.time() + 420
    while time.time() < deadline:
        st = screen()
        if st == 'CLUBS':
            if not verified:
                nav.press('F1', 1, 1000)          # Event Details
                continue
            nav.press('Enter', 1, 1200)           # -> vehicle select
        elif st == 'CURRENT EVENT':
            # Confirm the game is showing the id we just served; attributing a
            # render to the wrong id would be worse than failing here.
            nav.press('Up', 1, 700)               # focus stage 01
            shown = lbl.read_label()
            want = LABELS.get(probe['stage_conditions'], '')
            if want and shown and shown.lower() != want.lower():
                return f'served {want!r} but game shows {shown!r}'
            verified = True
            nav.press('Escape', 1, 900)
        elif st == 'VEHICLE SELECT':
            nav.press('Enter', 1, 1500)
        elif st == 'SERVICE AREA':
            nav.press('Enter', 1, 1500)           # Start (already highlighted)
        elif st == 'FLYBY':
            # Let the flyby camera move off its opening frame before capturing;
            # polling cannot help here, there is no state to observe.
            time.sleep(1)
            nav._grab()
            shutil.copy(nav.SHOT, shot)
            return quit_to_clubs(str(shot))
        elif st == 'MODAL':
            nav.press('Enter', 1, 1200)
        elif st == 'MAIN MENU':
            return 'fell back to the main menu'
        else:
            time.sleep(POLL)                      # still loading
    return 'timed out'


def quit_to_clubs(result: str, timeout: float = 120) -> str:
    """Skip the flyby, then Quit to Main Menu -- which lands on the Clubs list.

    Bounded by wall-clock rather than iteration count: most passes through here
    only poll, so a fixed count would expire in seconds while a stage is still
    unloading.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        st = screen()
        if st == 'CLUBS':
            return result
        if st == 'SERVICE AREA':
            nav.press('Down', 7, 250)
            nav.press('Enter', 1, 1200)           # Quit to Main Menu
            nav.press('Up', 1, 400)               # YES
            nav.press('Enter', 1, 1500)
        elif st == 'FLYBY':
            nav.press('Enter', 1, 1500)           # skip -> service area
        elif st == 'MODAL':
            nav.press('Enter', 1, 1200)
        elif st == 'MAIN MENU':
            return result + '  (ended on main menu)'
        else:
            time.sleep(POLL)
    return result + '  (could not return to Clubs)'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('plan', help='JSON list of probes to load-test')
    ap.add_argument('--out', default=str(OUT))
    args = ap.parse_args()

    plan = json.loads(Path(args.plan).read_text(encoding='utf-8'))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    for i, probe in enumerate(plan, 1):
        probe.setdefault('vehicle_class_id', 100)
        print(f"[{i}/{len(plan)}] {probe['name']}: loc {probe['location_id']} "
              f"track {probe['track_model_id']} cond {probe['stage_conditions']}",
              flush=True)
        print('   ', run_one(probe, out_dir), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
