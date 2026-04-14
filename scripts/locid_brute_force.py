"""Single-probe auto-relaunch loop to discover valid LocationIds.

For each candidate LocationId:
  1. Write a single-probe clubs file with (LocationId=X, track=580)
  2. Restart the server with DR2_DEBUG_CLUBS_FILE pointing at that file
  3. If the game is dead, launch it and wait for the start screen
  4. Navigate to Racenet Clubs
  5. Wait and check: did the game survive, or did it crash?
  6. If alive: OCR the club tile to extract the country name shown
     (or the event detail header if we enter the club)
  7. If dead: record "invalid", kill the crash reporter, mark game as dead

Writes results to runtime/discovery/locid_results.json (append-style, so
interrupted runs don't lose data).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

AHK = "C:/Program Files/AutoHotkey/v2/AutoHotkey64.exe"
SEND = "C:/Users/winrid/dr2server/scripts/send_key.ahk"
CROP = "C:/Users/winrid/dr2server/scripts/crop.py"
TESS = "C:/Program Files/Tesseract-OCR/tesseract.exe"
NIRCMD = "C:/Users/winrid/Downloads/nircmd-x64/nircmd.exe"
GAME_EXE = "F:/Steam/steamapps/common/DiRT Rally 2.0/dirtrally2.exe"
DISC = "C:/Users/winrid/dr2server/runtime/discovery"
PROBE_FILE = f"{DISC}/locid_probe.json"
RESULTS_FILE = f"{DISC}/locid_results.json"

# Candidate LocationIds to sweep.  Skip the 18 already-confirmed.
KNOWN_LOCS = {2, 3, 5, 9, 10, 13, 14, 16, 17, 18, 19, 20, 31, 34, 36, 37, 38, 46}
CANDIDATES = [v for v in range(1, 61) if v not in KNOWN_LOCS]

# Honor DR2_BRUTE_MAX env var to limit scan length (smoke testing).
_max = int(os.environ.get("DR2_BRUTE_MAX", "0") or 0)
if _max > 0:
    CANDIDATES = CANDIDATES[:_max]


def run_bg(cmd: list, stdout_file: str) -> subprocess.Popen:
    """Start a background process, redirecting stdout/stderr to a file."""
    f = open(stdout_file, "wb")
    return subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT)


def kill_process(name: str) -> None:
    subprocess.run(["cmd", "/c", f"taskkill /F /IM {name}"],
                   capture_output=True, text=True)


def is_running(name: str) -> bool:
    r = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {name}"],
                       capture_output=True, text=True)
    return name.lower() in r.stdout.lower()


def write_probe(loc_id: int) -> None:
    with open(PROBE_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "probes": [
                {
                    "name": f"L{loc_id:03d}",
                    "location_id": loc_id,
                    "track_model_id": 580,
                    "stage_conditions": 1,
                }
            ]
        }, f, indent=2)


SERVER_PROC: Optional[subprocess.Popen] = None


def kill_listener_on_port(port: int) -> None:
    """Kill whichever process is listening on the given local port."""
    r = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
    for line in r.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 5 and f"127.0.0.1:{port}" in parts[1] and "LISTENING" in line:
            pid = parts[-1]
            subprocess.run(["cmd", "/c", f"taskkill /F /PID {pid}"],
                           capture_output=True, text=True)


def restart_server() -> None:
    global SERVER_PROC
    if SERVER_PROC and SERVER_PROC.poll() is None:
        SERVER_PROC.terminate()
        try:
            SERVER_PROC.wait(timeout=3)
        except subprocess.TimeoutExpired:
            SERVER_PROC.kill()
    # Kill whoever is sitting on 443 (stale server from earlier session)
    # BUT DO NOT kill all python.exe — that would take down this driver.
    kill_listener_on_port(443)
    kill_listener_on_port(8080)
    time.sleep(0.5)

    env = os.environ.copy()
    env["DR2_DEBUG_CLUBS_FILE"] = PROBE_FILE
    env["DR2_DISCOVERY_MODE"] = "1"
    env["PYTHONUNBUFFERED"] = "1"

    cmd = [
        "python", "-m", "dr2server.httpd",
        "--ssl-cert", "C:/Users/winrid/AppData/Roaming/DirtForever/certs/dr2server-cert.pem",
        "--ssl-key",  "C:/Users/winrid/AppData/Roaming/DirtForever/certs/dr2server-key.pem",
        "--data-dir", "data",
        "--capture-dir", "captures",
        "--api-url", "https://dirtforever.net",
        "--api-token", "df_eabcf8c9db828ab400824dba6a020521",
    ]
    f = open(f"{DISC}/server_loop.log", "ab")
    SERVER_PROC = subprocess.Popen(
        cmd, stdout=f, stderr=subprocess.STDOUT, env=env,
        cwd="C:/Users/winrid/dr2server",
    )
    time.sleep(1.5)  # give server time to start


def send_key(key: str, count: int = 1, delay_ms: int = 1500) -> None:
    subprocess.run([AHK, SEND, key, str(count), str(delay_ms)], check=False)


def shot(name: str) -> str:
    out = os.path.join(DISC, f"{name}.png")
    subprocess.run([NIRCMD, "savescreenshotfull", out], check=False)
    return out


def crop(src: str, out: str, rect: tuple) -> None:
    subprocess.run(["python", CROP, src, out, *(str(v) for v in rect)],
                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def ocr(image_path: str) -> str:
    base = image_path.removesuffix(".png")
    subprocess.run([TESS, image_path, base, "--psm", "6"],
                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        with open(f"{base}.txt", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def launch_game() -> None:
    kill_process("dirtrally2.exe")
    kill_process("CrashSender1405.exe")
    time.sleep(0.5)
    subprocess.Popen([GAME_EXE],
                     creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    time.sleep(1.0)


def wait_for_press_start(timeout: float = 45.0) -> bool:
    """Block until the game is at the PRESS START OR ENTER screen.

    The game takes ~20s to reach the splash screen after launch. We sleep
    an initial 22 seconds, then poll every 2s for up to `timeout` more.
    """
    if not is_running("dirtrally2.exe"):
        return False
    time.sleep(22)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not is_running("dirtrally2.exe"):
            return False
        p = shot("tmp_press_start")
        # Crop to the game window area only, to avoid desktop OCR noise.
        game_path = f"{DISC}/tmp_press_start_game.png"
        crop(p, game_path, (456, 125, 1496, 932))
        txt = ocr(game_path).lower()
        if "press start" in txt or "press enter" in txt or "main menu" in txt:
            return True
        time.sleep(2)
    return False


def dismiss_press_start() -> None:
    send_key("Enter", delay_ms=3500)
    time.sleep(1.5)


def navigate_to_clubs() -> None:
    send_key("F4", delay_ms=1500)
    send_key("Right", delay_ms=1500)
    send_key("Right", delay_ms=1500)
    send_key("Down", delay_ms=1500)
    send_key("Enter", delay_ms=5000)
    time.sleep(2.0)


def back_out_to_freeplay() -> None:
    """From inside clubs list, Escape once → back to Freeplay menu."""
    send_key("Escape", delay_ms=1500)
    time.sleep(0.5)


def reenter_clubs() -> None:
    """From Freeplay menu with RACENET CLUBS highlighted, Enter to re-open."""
    send_key("Enter", delay_ms=5000)
    time.sleep(2.0)


def probe_one(loc_id: int, game_fresh: bool) -> Dict[str, Any]:
    write_probe(loc_id)
    restart_server()

    if game_fresh:
        launch_game()
        # Game takes ~18-22s from launch to PRESS START screen.
        time.sleep(25)
        # Dismiss PRESS START (goes to server contact, then main menu).
        send_key("Enter", delay_ms=4000)
        time.sleep(1.5)
        # Navigate to Racenet Clubs.
        send_key("F4",    delay_ms=1500)
        send_key("Right", delay_ms=1500)
        send_key("Right", delay_ms=1500)
        send_key("Down",  delay_ms=1500)
        send_key("Enter", delay_ms=5000)
        time.sleep(2.5)
    else:
        # Game alive — must be at the Freeplay menu with RACENET CLUBS
        # highlighted (where back_out_to_freeplay leaves us).
        send_key("Enter", delay_ms=5000)
        time.sleep(2.5)

    alive = is_running("dirtrally2.exe")
    crashed = not alive or is_running("CrashSender1405.exe")
    if crashed:
        kill_process("CrashSender1405.exe")
        return {"loc_id": loc_id, "status": "crashed"}

    # Game alive — enter Event Details (F1) so the right-hand panel shows
    # "<CITY> / <COUNTRY>" at the top-right (where Jämsä / FINLAND was
    # displayed in earlier Finland probes).
    send_key("F1", delay_ms=2500)
    time.sleep(1.5)

    # Verify game still alive after entering details (some invalid states
    # might crash here instead of on clubs list render).
    if not is_running("dirtrally2.exe"):
        kill_process("CrashSender1405.exe")
        return {"loc_id": loc_id, "status": "crashed_on_details"}

    # Screenshot and OCR the header region where country name appears.
    # Header text ("CITY / COUNTRY") sits at approx (1100-1250, 390-445) in
    # 1920x1080 full-screen coords (verified from Monte Carlo probe).
    full = shot(f"locid_{loc_id:03d}")
    header_path = f"{DISC}/locid_{loc_id:03d}_header.png"
    crop(full, header_path, (1080, 380, 1500, 460))
    header_ocr = ocr(header_path)

    # Back out: Event Details -> Clubs list -> Freeplay.
    send_key("Escape", delay_ms=1500)
    time.sleep(0.5)
    back_out_to_freeplay()

    return {
        "loc_id": loc_id,
        "status": "ok",
        "header_ocr": header_ocr.strip(),
    }


def main() -> None:
    os.makedirs(DISC, exist_ok=True)
    results: List[Dict[str, Any]] = []
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, encoding="utf-8") as f:
            try:
                results = json.load(f)
            except Exception:
                results = []

    done_ids = {r["loc_id"] for r in results}
    game_fresh = not is_running("dirtrally2.exe")

    for loc_id in CANDIDATES:
        if loc_id in done_ids:
            continue
        print(f"[loc {loc_id}] probing...", flush=True)
        result = probe_one(loc_id, game_fresh=game_fresh)
        print(f"[loc {loc_id}] {result['status']}", flush=True)
        results.append(result)
        with open(RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        # If crashed, next iteration must do a fresh launch.
        game_fresh = result["status"] in {"crashed", "game_launch_failed"}


if __name__ == "__main__":
    main()
