"""Smart TT probe — fail fast, never retry blindly.

Rule: do action → screenshot → check state → if wrong, print what
we see and ABORT. No retry loops.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from typing import Optional

AHK = "C:/Program Files/AutoHotkey/v2/AutoHotkey64.exe"
SEND = "C:/Users/winrid/dr2server/scripts/send_key.ahk"
FOCUS = "C:/Users/winrid/dr2server/scripts/focus_game.ahk"
NIRCMD = "C:/Users/winrid/Downloads/nircmd-x64/nircmd.exe"
CROP = "C:/Users/winrid/dr2server/scripts/crop.py"
TESS = "C:/Program Files/Tesseract-OCR/tesseract.exe"
DISC = "C:/Users/winrid/dr2server/runtime/discovery"
CAPDIR = "C:/Users/winrid/dr2server/captures"


def send(key: str, count: int = 1, delay: int = 1000) -> None:
    subprocess.run([AHK, SEND, key, str(count), str(delay)], check=False)
    # send_key.ahk only sleeps BETWEEN presses when count>1. For single
    # presses we also need a settle delay so the game has time to react
    # before the next key. Cap at 1s per no-long-sleeps rule.
    time.sleep(min(delay, 1000) / 1000.0)


def focus_game() -> None:
    """Bring the DR2 window to the foreground via AHK WinActivate."""
    subprocess.run([AHK, FOCUS], check=False, capture_output=True, timeout=10)


def screenshot() -> str:
    os.makedirs(DISC, exist_ok=True)
    p = os.path.join(DISC, "smart_state.png")
    subprocess.run([NIRCMD, "savescreenshotfull", p], check=False)
    return p


_RECT_CACHE: tuple[int, int, int, int] | None = None


def game_client_rect() -> tuple[int, int, int, int]:
    """Return (x, y, w, h) of DR2 client area on screen, or a fallback.
    Cached after first call — window doesn't move during automation.
    """
    global _RECT_CACHE
    if _RECT_CACHE is not None:
        return _RECT_CACHE
    ps = (
        "Add-Type '"
        "using System;using System.Runtime.InteropServices;"
        "public class W{"
        "[DllImport(\"user32.dll\")]public static extern bool GetClientRect(IntPtr h,out RECT r);"
        "[DllImport(\"user32.dll\")]public static extern bool ClientToScreen(IntPtr h,ref POINT p);"
        "[StructLayout(LayoutKind.Sequential)]public struct RECT{public int L,T,R,B;}"
        "[StructLayout(LayoutKind.Sequential)]public struct POINT{public int X,Y;}}"
        "';"
        "$p=Get-Process dirtrally2;$h=$p.MainWindowHandle;"
        "$cr=New-Object W+RECT;[W]::GetClientRect($h,[ref]$cr)|Out-Null;"
        "$pt=New-Object W+POINT;[W]::ClientToScreen($h,[ref]$pt)|Out-Null;"
        "Write-Host ($pt.X,$pt.Y,$cr.R,$cr.B -join ',')"
    )
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           check=False, capture_output=True, text=True, timeout=5)
        x, y, w, h = [int(v) for v in r.stdout.strip().split(",")]
        _RECT_CACHE = (x, y, w, h)
        return _RECT_CACHE
    except Exception:
        _RECT_CACHE = (470, 120, 1024, 768)
        return _RECT_CACHE


def ocr_game_area(full: str) -> str:
    """OCR just the game client area (not the surrounding desktop)."""
    from PIL import Image  # inline import — PIL is already a dep of the crop script
    out = os.path.join(DISC, "state_ocr.png")
    x, y, w, h = game_client_rect()
    x2, y2 = x + w, y + h
    try:
        img = Image.open(full)
        img.crop((x, y, x2, y2)).save(out)
    except Exception:
        return ""
    r = subprocess.run([TESS, out, "stdout", "--psm", "11"],
                       capture_output=True, text=True, encoding="utf-8")
    return r.stdout.strip()


def detect_state() -> tuple[str, str]:
    """Returns (state_name, raw_ocr_text). Always prints what it sees."""
    full = screenshot()
    text = ocr_game_area(full)
    tl = text.lower()

    import re as _re
    state = "UNKNOWN"
    if "exit game" in tl or "are you sure you want to exit" in tl:
        state = "EXIT_DIALOG"
    elif ("location select" in tl
          or "surface types" in tl
          or _re.search(r"\d\s*/\s*26\b", tl)):
        # Location picker: "XX/26" counter OR "Surface Types:" label (plural).
        state = "LOCATION_SEL"
    elif "stage select" in tl:
        state = "STAGE_SEL"
    elif ("vehicle select" in tl
          or "hicle select" in tl
          or "ehicle select" in tl
          or "cylinders" in tl
          or "mini cooper" in tl
          or ("cooper" in tl and "engine" in tl)
          or ("transmission" in tl and ("manual" in tl or "automatic" in tl))):
        state = "VEHICLE_SEL"
    elif "time trial" in tl and "historic" in tl:
        state = "FREEPLAY"
    elif "freeplay" in tl and "historic" in tl:
        state = "FREEPLAY"
    elif "quit to main menu" in tl or ("quit to" in tl and ("main" in tl or "mel" in tl)):
        # Could be pre-race or in-race pause
        if "tires" in tl or "tune vehicle" in tl or "leaderboard" in tl:
            state = "PRE_RACE_PAUSE"
        elif "continue" in tl:
            state = "IN_RACE_PAUSE"
        else:
            state = "SOME_PAUSE"
    elif (("tires" in tl and "leaderboard" in tl)
          or ("tires" in tl and "tune" in tl)
          or ("leaderboard" in tl and "tune" in tl)
          or ("start" in tl and "tires" in tl and "options" in tl)):
        # Pre-race start screen with 6 items: Start/Tires/Tune/Leaderboard/Options/Quit
        state = "PRE_RACE_PAUSE"
    elif "service area" in tl:
        state = "SERVICE_AREA"
    elif "confirm" in tl and ("stage" in tl or "conditions" in tl):
        state = "STAGE_SEL"
    elif ("location conditions" in tl or "stage conditions" in tl or
          ("stages" in tl and "confirm" in tl)):
        # Stage select screen (shows picked stage + conditions + CONFIRM)
        state = "STAGE_SEL"
    elif (any(tok in tl for tok in (
            "province", "county", "jamsa", "baumholder", "argolis", "monte carlo",
            "hawkes", "leczna", "ribadelles", "varmland", "new england", "powys",
            "perth and kinross", "catamarca", "monaro"))
          and ("dry" in tl or "wet" in tl or "damp" in tl)):
        # Stage select screen — rally loc name + condition token (Dry/Wet/Damp)
        state = "STAGE_SEL"
    elif (("mi" in tl and "ft" in tl and "surface" in tl)
          or ("mi" in tl and "gravel" in tl and "elevation" not in tl)
          or ("distance" in tl and "surface" in tl and "elevation" in tl)):
        # Stage select: shows Distance (mi), Elevation (ft), Surface (Gravel/etc)
        state = "STAGE_SEL"
    elif "my team" in tl and ("events" in tl or "garage" in tl):
        state = "MAIN_MENU"
    elif "main menu" in tl and ("historic" in tl or "free roam" in tl or "racenet" in tl or "custom" in tl):
        # Tile screen with HISTORIC / CUSTOM / TIME TRIAL / FREE ROAM / etc.
        state = "FREEPLAY"
    elif "freeplay" in tl and ("colin" in tl or "mcrae" in tl or "options" in tl):
        # Tab bar "My Team | Freeplay | Colin McRae | Store | Options"
        state = "FREEPLAY"
    elif "racenet clubs" in tl or ("historic" in tl and ("rallycross" in tl or "free roam" in tl or "racenet" in tl)):
        # Tile labels (HISTORIC / RALLYCROSS / FREE ROAM / RACENET CLUBS)
        state = "FREEPLAY"
    elif "warning" in tl and ("apply" in tl or "discard" in tl):
        state = "WARNING_DIALOG"
    elif "no leaderboard entries" in tl:
        state = "LEADERBOARD_EMPTY"
    elif ("leaderboard" in tl and "friends" in tl) or ("rivals" in tl and "global" in tl):
        state = "LEADERBOARD_VIEW"
    elif ("surface type" in tl or "elevation change" in tl
          or ("distance" in tl and ("mi" in tl or "ft" in tl))
          or any(c in tl for c in ("finland", "argentina", "australia", "germany",
                                     "greece", "monaco", "poland", "spain", "sweden",
                                     "usa", "wales", "scotland", "new zealand"))):
        state = "LOADING"
    elif "start time" in tl:
        state = "PRE_RACE"

    return state, text


def current_stage_text(text: str) -> str:
    """Extract the current stage name from stage-select OCR.
    The reliable layout: a CAPS location line (e.g. 'CATAMARCA PROVINCE'),
    followed by the stage name on the next non-trivial line.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    loc_keywords = (
        # Rally location names
        "PROVINCE", "COUNTY", "JAMSA", "BAUMHOLDER", "ARGOLIS",
        "MONTE CARLO", "HAWKES BAY", "LECZNA", "RIBADELLES",
        "VARMLAND", "NEW ENGLAND", "POWYS", "PERTH", "CATAMARCA",
        "MONARO", "KINROSS",
        # Country fallbacks (shown on STAGE_SEL too)
        "FINLAND", "ARGENTINA", "AUSTRALIA", "GERMANY", "GREECE",
        "MONACO", "NEW ZEALAND", "POLAND", "SPAIN", "SWEDEN",
        "USA", "WALES", "SCOTLAND",
    )
    for i, l in enumerate(lines):
        upper = l.upper()
        if any(k in upper for k in loc_keywords) and l == upper and len(l) >= 4:
            # Found location line; stage name is the next plausible line
            label_blacklist = {
                "stages", "stage", "conditions", "stage conditions",
                "location conditions", "confirm", "distance", "elevation",
                "surface", "dry", "wet", "damp", "location condit",
            }
            for j in range(i + 1, min(i + 8, len(lines))):
                cand = lines[j].strip()
                if len(cand) < 3:
                    continue
                alnum = sum(1 for c in cand if c.isalnum())
                if alnum < 3:
                    continue
                if cand == cand.upper() and any(k in cand.upper() for k in loc_keywords):
                    continue
                stripped = cand.lstrip("<>|/ \t").rstrip(".,;")
                # Strip leading non-alnum chars (OCR garbage like '�') for blacklist test
                import re as _re
                ascii_only = _re.sub(r"[^a-zA-Z0-9 ]", "", stripped).strip()
                if ascii_only.lower() in label_blacklist:
                    continue
                # If after stripping OCR garbage nothing meaningful remains, skip
                if len(ascii_only) < 3:
                    continue
                return ascii_only
    return ""


def reset_stage_picker(n: int = 15) -> None:
    """Spam Left to park the stage picker at position 0 (Left stops at 0)."""
    subprocess.run([AHK, SEND, "Left", str(n), "250"], check=False)


LOC_NAMES = [
    "CATAMARCA", "MONARO", "JAMSA", "BAUMHOLDER", "ARGOLIS",
    "MONTE CARLO", "HAWKES BAY", "LECZNA", "RIBADELLES",
    "VARMLAND", "NEW ENGLAND", "POWYS", "PERTH",
]
# Per loc_idx, list of acceptable keywords (location name + country fallbacks).
LOC_KEYWORDS = [
    ["CATAMARCA", "ARGENTINA"],
    ["MONARO", "AUSTRALIA"],
    ["JAMSA", "FINLAND"],
    ["BAUMHOLDER", "GERMANY"],
    ["ARGOLIS", "GREECE"],
    ["MONTE CARLO", "MONACO"],
    ["HAWKES BAY", "NEW ZEALAND"],
    ["LECZNA", "POLAND"],
    ["RIBADELLES", "SPAIN"],
    ["VARMLAND", "SWEDEN"],
    ["NEW ENGLAND", "USA"],
    ["POWYS", "WALES"],
    ["PERTH", "SCOTLAND"],
]


def current_location_idx(text: str) -> int:
    """Return the loc_idx currently shown on LOCATION_SEL, or -1."""
    up = text.upper()
    for i, kws in enumerate(LOC_KEYWORDS):
        for kw in kws:
            if kw in up:
                return i
    return -1


def current_location_keyword(text: str) -> str:
    """Back-compat: return the first matched loc keyword or ''."""
    idx = current_location_idx(text)
    return LOC_NAMES[idx] if idx >= 0 else ""


def _stage_ordinal(displayed: str, known_stage_names: list) -> int:
    """Given an OCR-read stage name and the graph's stage list for the current
    location, return the graph index of the best match (or -1 if no match)."""
    if not displayed:
        return -1
    best_idx, best_ratio = -1, 0.0
    for i, name in enumerate(known_stage_names):
        if stage_name_matches(name, displayed):
            # Prefer the best ratio among all fuzzy matches to disambiguate
            # prefix-sharing names like "Kreuzungsring" vs "...Reverse".
            import re
            from difflib import SequenceMatcher
            def norm(s):
                return re.sub(r"[^a-z0-9]", "", s.lower())
            r = SequenceMatcher(None, norm(name), norm(displayed)).ratio()
            if r > best_ratio:
                best_idx, best_ratio = i, r
    return best_idx


def navigate_to_stage(target_name: str, known_stage_names: list) -> str:
    """Navigate to target_name using a two-phase approach:
      1. Anchor: scan Right until we identify the current position by OCR-matching
         against any graph stage. If the first read already matches target, done.
      2. Step: compute delta = target_idx - cur_idx; press Right/Left |delta| times
         deterministically (no per-step OCR — relies on 1s post-press settle).
      3. Verify: one final OCR check to confirm target. If OCR is ambiguous, accept
         based on step count (game's picker is deterministic).
    """
    max_anchor_steps = 14  # enough to walk the whole 12-stage list once
    try:
        target_idx = known_stage_names.index(target_name)
    except ValueError:
        target_idx = -1

    seen_nonempty: list[str] = []
    cur_idx = -1
    displayed = ""

    # Phase 1: anchor
    for step in range(max_anchor_steps):
        _, text = detect_state()
        cand = current_stage_text(text)
        if not cand:
            time.sleep(0.3)
            _, text = detect_state()
            cand = current_stage_text(text)
        if cand:
            displayed = cand
            if stage_name_matches(target_name, cand):
                return cand
            if not seen_nonempty or seen_nonempty[-1] != cand:
                seen_nonempty.append(cand)
            idx = _stage_ordinal(cand, known_stage_names)
            if idx >= 0:
                cur_idx = idx
                break
        send("Right", delay=1000)

    if cur_idx < 0 or target_idx < 0:
        raise SystemExit(
            f"Could not anchor position for '{target_name}'. Seen: {seen_nonempty}")

    # Phase 2: deterministic stepping
    delta = target_idx - cur_idx
    direction = "Right" if delta > 0 else "Left"
    for _ in range(abs(delta)):
        send(direction, delay=1000)

    # Phase 3: verify via OCR (accept ordinal match even if name fuzzy-mismatches
    # — game's picker is deterministic so delta steps land precisely).
    _, text = detect_state()
    displayed = current_stage_text(text) or displayed
    if stage_name_matches(target_name, displayed):
        return displayed
    idx = _stage_ordinal(displayed, known_stage_names)
    if idx == target_idx:
        return displayed
    # OCR might've been empty / ambiguous for this stage. Trust step count.
    print(f"    (OCR ambiguous: displayed='{displayed}', ordinal={idx}; trusting step count)", flush=True)
    return displayed or target_name


def navigate_to_location(target_idx: int) -> None:
    """Starting at LOCATION_SEL (any position), navigate to target rally location.
    Uses OCR-detected location index (via location-name OR country-name match).
    """
    target_name = LOC_NAMES[target_idx]
    max_steps = 40
    stuck_count = 0
    prev_idx = -999
    for _ in range(max_steps):
        _, text = detect_state()
        cur_idx = current_location_idx(text)
        if cur_idx == target_idx:
            return
        if cur_idx == -1:
            time.sleep(0.5)
            continue
        direction = "Right" if target_idx > cur_idx else "Left"
        send(direction, delay=600)
        time.sleep(0.3)
        if cur_idx == prev_idx:
            stuck_count += 1
            if stuck_count > 3:
                raise SystemExit(
                    f"Stuck navigating to {target_name}; stayed on idx {cur_idx}")
        else:
            stuck_count = 0
        prev_idx = cur_idx
    raise SystemExit(f"Could not reach {target_name} after {max_steps} steps")


def stage_name_matches(expected: str, displayed: str) -> bool:
    """Fuzzy match using similarity ratio. Rejects cases like 'Kreuzungsring'
    vs 'Kreuzungsring Reverse' (length-different names that share a prefix).
    Accepts OCR typos (e.g. 'Ruschberg' vs 'Ruschherg'). Threshold 0.85.
    """
    import re
    from difflib import SequenceMatcher
    def norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]", "", s.lower())
    e, d = norm(expected), norm(displayed)
    if not e or not d:
        return False
    if e == d:
        return True
    # Short strings need more slack (OCR noise); long ones less (prefix-sharing
    # variants like "Col de Turini Sprint en descente" vs "...en Montée" must
    # be distinguishable).
    threshold = 0.9 if max(len(e), len(d)) >= 15 else 0.85
    return SequenceMatcher(None, e, d).ratio() >= threshold


def expect(expected: str, context: str) -> str:
    """Detect state and abort if not expected. Returns raw OCR text."""
    state, text = detect_state()
    if state != expected:
        print(f"\n  ABORT: expected {expected}, got {state}", flush=True)
        print(f"  Context: {context}", flush=True)
        # Print first 200 chars of OCR for debugging
        preview = text.replace("\n", " | ")[:200]
        print(f"  OCR: {preview}", flush=True)
        raise SystemExit(f"Unexpected state: {state} (expected {expected})")
    return text


def poll_until(predicate, timeout: float = 120.0, interval: float = 0.5):
    """Poll predicate() every `interval` seconds until it returns truthy
    or `timeout` elapses. Returns the last truthy value or None.
    interval MUST be <= 1s per project rule.
    """
    assert interval <= 1.0, "Poll interval must be <= 1s"
    deadline = time.time() + timeout
    while time.time() < deadline:
        v = predicate()
        if v:
            return v
        time.sleep(interval)
    return None


def quit_to_freeplay(context: str) -> None:
    """After capture, get back to Freeplay via the fastest reliable path.

    Decision tree each poll (every 0.5s):
      - FREEPLAY      -> done
      - PRE_RACE_PAUSE (start menu): Up, Enter, Up, Enter -> dialog quit
      - IN_RACE_PAUSE (Continue/Options/Quit): Down, Down, Enter, Up, Enter
      - STAGE_SEL or LOCATION_SEL: Escape to back out toward Freeplay
      - Otherwise (LOADING, cinematic, in-car, unknown): send Enter to
        advance past loading / skip cinematic / start race, then Escape on
        next tick to open IN_RACE_PAUSE.

    No hardcoded waits; every step re-reads OCR state.
    """
    last_advance_key = 0.0
    next_key = "Enter"  # alternates Enter <-> Escape to push through transitions
    deadline = time.time() + 180

    def done():
        state, _ = detect_state()
        return state == "FREEPLAY"

    while time.time() < deadline:
        state, text = detect_state()
        tl = text.lower()

        if state == "FREEPLAY":
            return

        if state == "PRE_RACE_PAUSE":
            send("Up", delay=200)
            send("Enter", delay=200)
            # Wait for quit dialog (state becomes UNKNOWN with YES/NO visible)
            poll_until(lambda: "are you sure" in detect_state()[1].lower(),
                       timeout=4, interval=0.5)
            send("Up", delay=200)
            send("Enter", delay=200)
            if poll_until(done, timeout=10, interval=0.5):
                return
            continue

        if "continue" in tl and ("options" in tl or "quit" in tl):
            # IN_RACE_PAUSE
            send("Down", delay=200)
            send("Down", delay=200)
            send("Enter", delay=200)
            poll_until(lambda: "are you sure" in detect_state()[1].lower(),
                       timeout=4, interval=0.5)
            send("Up", delay=200)
            send("Enter", delay=200)
            if poll_until(done, timeout=10, interval=0.5):
                return
            continue

        if state in ("STAGE_SEL", "LOCATION_SEL"):
            send("Escape", delay=200)
            time.sleep(0.4)
            continue

        # LOADING / cinematic / in-car view / UNKNOWN:
        # Alternate Enter (skip/start race) and Escape (open pause menu).
        now = time.time()
        if now - last_advance_key > 1.5:
            send(next_key, delay=200)
            next_key = "Escape" if next_key == "Enter" else "Enter"
            last_advance_key = now
        time.sleep(0.5)

    state, text = detect_state()
    print(f"  ABORT: quit loop timed out. state={state}", flush=True)
    print(f"  OCR: {text[:300]}", flush=True)
    raise SystemExit("Quit loop timed out")


def latest_capture():
    for fn in sorted(os.listdir(CAPDIR), reverse=True)[:30]:
        try:
            with open(os.path.join(CAPDIR, fn)) as f:
                d = json.load(f)
        except Exception:
            continue
        if d.get("headers", {}).get("X-EgoNet-Function") != "TimeTrial.GetLeaderboardId":
            continue
        tm = d.get("decoded_body", {}).get("TrackModelId")
        if isinstance(tm, dict):
            tm = tm.get("value", tm)
        return (fn, int(tm) if tm is not None else None)
    return (None, None)


def main() -> None:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from dr2server.game_data import Track as TrackEnum, _TRACK_META

    known_names = set()
    for t in TrackEnum:
        known_names.add(_TRACK_META[t]["display_name"].lower())

    with open(f"{DISC}/tt_location_graph.json", encoding="utf-8") as f:
        graph = json.load(f)

    rally_locs = [(name, stages) for name, stages in graph.items() if len(stages) > 1]
    start_loc = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    end_loc = int(sys.argv[2]) if len(sys.argv) > 2 else len(rally_locs)

    results_path = f"{DISC}/tt_smart_results.json"
    results = {}
    if os.path.exists(results_path):
        with open(results_path) as f:
            results = json.load(f)

    # Picker resets to position 1 (first rally loc) every time we enter TT from Freeplay.
    # So from Freeplay: Enter → LOCATION_SEL@pos1, Right × loc_idx → target location.
    for loc_idx in range(start_loc, min(end_loc, len(rally_locs))):
        loc_name, stage_names = rally_locs[loc_idx]

        if loc_name in results and len(results[loc_name]) == len(stage_names):
            print(f"\n[Loc {loc_idx}] {loc_name}: done, skipping", flush=True)
            continue

        print(f"\n{'='*50}", flush=True)
        print(f"[Loc {loc_idx}] {loc_name} ({len(stage_names)} stages)", flush=True)

        # Enter TT from Freeplay once per location (not per stage).
        # Auto-dismiss EXIT_DIALOG if Escape accidentally triggered it.
        state, text = detect_state()
        if state == "EXIT_DIALOG":
            send("Escape", delay=500)
            state, text = detect_state()
        if state != "FREEPLAY":
            print(f"  ABORT: expected FREEPLAY at loc start, got {state}. OCR: {text[:200]}", flush=True)
            raise SystemExit(1)
        send("Enter", delay=1500)
        expect("LOCATION_SEL", "after Enter for TT")
        navigate_to_location(loc_idx)
        send("Enter", delay=1500)
        expect("STAGE_SEL", "after Enter for location confirm")
        reset_stage_picker(20)

        loc_results = []
        for stage_idx, stage_name in enumerate(stage_names):
            if stage_name.lower().strip() in known_names:
                print(f"  Stage {stage_idx}: {stage_name}... SKIP", flush=True)
                loc_results.append((stage_name, None))
                # Still need to advance picker to keep in sync
                send("Right", delay=500)
                continue

            print(f"  Stage {stage_idx}: {stage_name}...", flush=True)

            # Navigate to this stage from current picker position
            displayed = navigate_to_stage(stage_name, stage_names)
            print(f"    verified stage: '{displayed}'", flush=True)

            before_fn, _ = latest_capture()

            # Down, Down, Enter → VEHICLE_SEL
            send("Down", delay=500)
            send("Down", delay=500)
            send("Enter", delay=1500)

            state, text = detect_state()
            if state == "STAGE_SEL":
                # Needed one more Down
                send("Down", delay=500)
                send("Enter", delay=1500)
                state, text = detect_state()
            if state not in ("VEHICLE_SEL", "UNKNOWN"):
                print(f"  ABORT: expected VEHICLE_SEL after Down+Enter, got {state}. OCR: {text[:200]}", flush=True)
                raise SystemExit(1)

            # F2 opens the Time Trial leaderboard → fires TimeTrial.GetLeaderboardId
            send("F2", delay=800)

            # Poll for capture (~10s budget, 0.5s poll interval)
            tm = None
            deadline = time.time() + 10
            while time.time() < deadline:
                fn, cur_tm = latest_capture()
                if fn and fn != before_fn:
                    tm = cur_tm
                    break
                time.sleep(0.5)

            if tm:
                print(f"  -> T{tm}", flush=True)
            else:
                print(f"  -> (no capture)", flush=True)
            loc_results.append((stage_name, tm))

            # Close leaderboard + VEHICLE_SEL + STAGE_SEL all the way back to
            # LOCATION_SEL — the focus in STAGE_SEL is sticky (lands on a
            # Conditions row after returning from VEHICLE_SEL, which breaks
            # Left/Right stage cycling). Going to LOCATION_SEL and re-entering
            # gives a fresh Stage-row focus.
            close_deadline = time.time() + 15
            reached_location = False
            while time.time() < close_deadline:
                st, _ = detect_state()
                if st == "LOCATION_SEL":
                    reached_location = True
                    break
                if st == "LEADERBOARD_EMPTY":
                    send("Enter", delay=500)
                elif st == "LEADERBOARD_VIEW":
                    send("Escape", delay=500)
                elif st == "VEHICLE_SEL":
                    send("Escape", delay=500)
                elif st == "STAGE_SEL":
                    send("Escape", delay=500)
                else:
                    send("Escape", delay=500)
            if not reached_location:
                st, text = detect_state()
                print(f"  ABORT: could not reach LOCATION_SEL, state={st}. OCR: {text[:200]}", flush=True)
                raise SystemExit(1)

            # Re-enter STAGE_SEL with fresh Stage-row focus.
            send("Enter", delay=1500)
            if not poll_until(lambda: detect_state()[0] == "STAGE_SEL", timeout=6, interval=0.5):
                st, text = detect_state()
                print(f"  ABORT: expected STAGE_SEL after re-entry, got {st}. OCR: {text[:200]}", flush=True)
                raise SystemExit(1)

            # Persist results incrementally
            results[loc_name] = loc_results + [(n, None) for n in stage_names[stage_idx+1:]]
            with open(results_path, "w") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)

        # All stages done in this location. Back out to FREEPLAY.
        send("Escape", delay=400)  # STAGE_SEL → LOCATION_SEL
        send("Escape", delay=400)  # LOCATION_SEL → FREEPLAY
        poll_until(lambda: detect_state()[0] == "FREEPLAY", timeout=8, interval=0.5)

        results[loc_name] = loc_results
        with open(results_path, "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*50}\nDone. Results in {results_path}", flush=True)

    # Summary
    total = sum(len(v) for v in results.values())
    captured = sum(1 for v in results.values() for _, tm in v if tm)
    print(f"Total: {total} stages, {captured} with TrackModelIds", flush=True)


if __name__ == "__main__":
    main()
