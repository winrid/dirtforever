"""DirtForever — DiRT Rally 2.0 community server with GUI.

A tkinter GUI with START / STOP buttons that handles cert generation,
hosts file management, and the game server lifecycle.

PyInstaller compiles this file into a single executable via build_exe.py.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

IS_WIN = sys.platform == "win32"
IS_LINUX = sys.platform == "linux"

if IS_WIN:
    import ctypes

DR2_STEAM_APPID = 690790

# Cap elevation calls at 5 minutes — if polkit/UAC hangs, surface it as a
# failure in the GUI log instead of leaving the worker thread stuck forever.
ELEVATION_TIMEOUT_SECONDS = 300

UI_FONT = "Segoe UI" if IS_WIN else "DejaVu Sans"
MONO_FONT = "Consolas" if IS_WIN else "DejaVu Sans Mono"

def _read_version() -> str:
    """Read version from VERSION file (bundled or local)."""
    for base in [Path(getattr(sys, "_MEIPASS", "")), Path(__file__).parent]:
        vf = base / "VERSION"
        if vf.is_file():
            return vf.read_text().strip()
    return "dev"

VERSION = _read_version()

# ---------------------------------------------------------------------------
# Resource-path helpers (PyInstaller bundle detection)
# ---------------------------------------------------------------------------

def _bundle_root() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).parent


def _data_dir() -> Path:
    return _bundle_root() / "data"


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

if IS_WIN:
    APPDATA = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    DIRTFOREVER_DIR = APPDATA / "DirtForever"
    HOSTS_FILE = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "drivers" / "etc" / "hosts"
    HOSTS_NEWLINE = "\r\n"
else:
    _xdg = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    DIRTFOREVER_DIR = Path(_xdg) / "dirtforever"
    HOSTS_FILE = Path("/etc/hosts")
    HOSTS_NEWLINE = "\n"

CONFIG_PATH = DIRTFOREVER_DIR / "config.json"
CERTS_DIR = DIRTFOREVER_DIR / "certs"
CERT_PATH = CERTS_DIR / "dr2server-cert.pem"
KEY_PATH = CERTS_DIR / "dr2server-key.pem"

REDIRECT_DOMAINS = [
    "prod.egonet.codemasters.com",
    "qa.egonet.codemasters.com",
    "terms.codemasters.com",
    "aurora.codemasters.local",
]

HOSTS_BEGIN = "# BEGIN DIRTFOREVER"
HOSTS_END = "# END DIRTFOREVER"
SERVER_IP = "127.0.0.1"
DASHBOARD_URL = "https://dirtforever.net/dashboard"
API_URL = "https://dirtforever.net"


# ---------------------------------------------------------------------------
# Admin helpers
# ---------------------------------------------------------------------------

def is_admin() -> bool:
    if IS_WIN:
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    return os.geteuid() == 0


def run_as_admin(args: list[str]) -> int:
    """Run a subprocess elevated. Returns exit code."""
    if IS_WIN:
        exe = sys.executable
        quoted = " ".join(f'"{a}"' for a in args)
        cmd = f'Start-Process -FilePath "{exe}" -ArgumentList \'{quoted}\' -Verb RunAs -Wait'
        result = subprocess.run(
            ["powershell", "-Command", cmd], capture_output=True,
            timeout=ELEVATION_TIMEOUT_SECONDS,
        )
        return result.returncode
    # Linux: pkexec runs the literal argv as root. First arg should be an executable.
    result = subprocess.run(["pkexec", *args], timeout=ELEVATION_TIMEOUT_SECONDS)
    return result.returncode


# ---------------------------------------------------------------------------
# TLS certificate
# ---------------------------------------------------------------------------

def generate_cert() -> None:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    CERTS_DIR.mkdir(parents=True, exist_ok=True)
    hosts = REDIRECT_DOMAINS + ["localhost"]
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "DirtForever"),
        x509.NameAttribute(NameOID.COMMON_NAME, hosts[0]),
    ])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject).issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(h) for h in hosts]), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    CERT_PATH.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    KEY_PATH.write_bytes(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ))


def cert_exists() -> bool:
    return CERT_PATH.exists() and KEY_PATH.exists()


def install_cert_trust() -> bool:
    """Install cert into Windows Root store. Returns True on success."""
    result = subprocess.run(
        ["certutil", "-addstore", "Root", str(CERT_PATH)],
        capture_output=True, text=True,
    )
    return result.returncode == 0


# ---------------------------------------------------------------------------
# Linux: cert trust into DR2's Proton prefix
# ---------------------------------------------------------------------------

def _find_dr2_proton_prefix() -> Optional[Path]:
    home = Path.home()
    candidates = [
        home / ".steam" / "steam" / "steamapps" / "compatdata" / str(DR2_STEAM_APPID) / "pfx",
        home / ".local" / "share" / "Steam" / "steamapps" / "compatdata" / str(DR2_STEAM_APPID) / "pfx",
        home / ".steam" / "root" / "steamapps" / "compatdata" / str(DR2_STEAM_APPID) / "pfx",
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return None


def _find_proton_wine() -> Optional[Path]:
    """Locate the newest Proton-bundled wine binary."""
    home = Path.home()
    roots = [
        home / ".steam" / "steam" / "steamapps" / "common",
        home / ".local" / "share" / "Steam" / "steamapps" / "common",
    ]
    matches: list[Path] = []
    for r in roots:
        if not r.is_dir():
            continue
        for entry in sorted(r.iterdir()):
            if not entry.name.startswith("Proton"):
                continue
            wine = entry / "files" / "bin" / "wine"
            if wine.is_file():
                matches.append(wine)
    if not matches:
        return None
    # Sort by parent dir name (e.g. "Proton 10.0") so newer Proton wins.
    matches.sort(key=lambda p: p.parent.parent.parent.name)
    return matches[-1]


def install_cert_into_dr2_prefix(cert_path: Path) -> tuple[bool, str]:
    """Trust the cert inside DR2's Proton/Wine prefix. Returns (ok, message).

    The message is either a success summary or a copy-pasteable manual command.
    """
    # Prefer protontricks-launch when available — it handles prefix discovery
    # and picks the correct Proton wine for this AppID automatically.
    if shutil.which("protontricks-launch"):
        try:
            result = subprocess.run(
                [
                    "protontricks-launch", "--appid", str(DR2_STEAM_APPID),
                    "certutil", "-addstore", "Root", str(cert_path),
                ],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0:
                return True, "Cert trusted via protontricks-launch."
        except subprocess.TimeoutExpired:
            pass  # Fall through to the wine-direct path below.

    pfx = _find_dr2_proton_prefix()
    if pfx is None:
        manual = (
            "Could not locate DR2's Proton prefix at "
            "~/.steam/steam/steamapps/compatdata/690790/pfx. "
            "Launch DiRT Rally 2.0 once via Steam (Proton) to create it, then click START again. "
            f"Manual command:\n  WINEPREFIX=<dr2-pfx> wine certutil -addstore Root {cert_path}"
        )
        return False, manual

    wine = _find_proton_wine()
    if wine is None:
        wine_path = shutil.which("wine")
        if wine_path:
            wine = Path(wine_path)
    if wine is None:
        manual = (
            "No Proton wine binary found under ~/.steam/.../common/Proton*/files/bin/wine "
            "and no system 'wine' on PATH. "
            f"Manual command:\n  WINEPREFIX={pfx} wine certutil -addstore Root {cert_path}"
        )
        return False, manual

    env = os.environ.copy()
    env["WINEPREFIX"] = str(pfx)
    env["WINEDLLOVERRIDES"] = "mscoree=,mshtml="
    env.setdefault("WINEDEBUG", "-all")
    result = subprocess.run(
        [str(wine), "certutil", "-addstore", "Root", str(cert_path)],
        env=env, capture_output=True, text=True, timeout=120,
    )
    if result.returncode == 0:
        return True, f"Cert trusted in {pfx} via {wine}."
    err = (result.stderr or result.stdout or "").strip().splitlines()[-1:] or [""]
    manual = (
        f"wine certutil failed ({err[0]}). Try manually:\n"
        f"  WINEPREFIX={pfx} '{wine}' certutil -addstore Root {cert_path}"
    )
    return False, manual


# ---------------------------------------------------------------------------
# Hosts file
# ---------------------------------------------------------------------------

def _read_hosts() -> str:
    try:
        return HOSTS_FILE.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return HOSTS_FILE.read_text(encoding="latin-1")


def _strip_block(content: str) -> str:
    lines = content.splitlines(keepends=True)
    out, inside = [], False
    for line in lines:
        s = line.strip()
        if s == HOSTS_BEGIN:
            inside = True; continue
        if s == HOSTS_END:
            inside = False; continue
        if not inside:
            out.append(line)
    return "".join(out)


def hosts_configured() -> bool:
    try:
        content = _read_hosts()
    except OSError:
        return False
    return HOSTS_BEGIN in content and REDIRECT_DOMAINS[0] in content


def add_hosts() -> None:
    existing = _read_hosts()
    cleaned = _strip_block(existing).rstrip("\r\n")
    nl = HOSTS_NEWLINE
    block = [HOSTS_BEGIN] + [f"{SERVER_IP}\t{d}" for d in REDIRECT_DOMAINS] + [HOSTS_END]
    new = (cleaned + nl + nl + nl.join(block) + nl) if cleaned else (nl.join(block) + nl)
    HOSTS_FILE.write_bytes(new.encode("utf-8"))


def remove_hosts() -> None:
    existing = _read_hosts()
    cleaned = _strip_block(existing)
    HOSTS_FILE.write_bytes(cleaned.encode("utf-8"))


# ---------------------------------------------------------------------------
# Linux: port-443 capability via setcap
# ---------------------------------------------------------------------------

def _is_pyinstaller_bundle() -> bool:
    return hasattr(sys, "_MEIPASS") or getattr(sys, "frozen", False)


def _elevation_target_binary() -> Path:
    """The binary that needs cap_net_bind_service.

    For PyInstaller --onefile this is the bootloader ELF (sys.executable).
    For source runs (`python dirtforever.py`) this is the python interpreter.
    Either way: setcap on `sys.executable` is correct and scoped.
    """
    return Path(sys.executable).resolve()


def _system_python_for_helper() -> Optional[Path]:
    """A real Python interpreter to run the elevated helper script.

    sys.executable is unsuitable in PyInstaller mode because it's the bundled
    bootloader, not a python that can run an arbitrary .py file. Find the
    system python3 instead. In source mode sys.executable is fine.
    """
    if not _is_pyinstaller_bundle():
        return Path(sys.executable)
    for cand in ("python3", "python"):
        path = shutil.which(cand)
        if path:
            return Path(path)
    for cand in ("/usr/bin/python3", "/usr/local/bin/python3"):
        if Path(cand).is_file():
            return Path(cand)
    return None


def _relaunch_with_auto_start() -> None:
    """Re-exec ourselves so a freshly-granted cap_net_bind_service applies.

    File capabilities only attach to a process at execve() time, so a setcap
    we just performed via pkexec doesn't help the currently-running GUI. We
    pass DIRTFOREVER_AUTO_START so the new instance auto-clicks START.
    """
    env = {**os.environ, "DIRTFOREVER_AUTO_START": "1"}
    os.execve(sys.executable, [sys.executable, *sys.argv[1:]], env)


def has_port_capability(binary: Path) -> bool:
    getcap = shutil.which("getcap")
    if not getcap:
        return False
    result = subprocess.run([getcap, str(binary)], capture_output=True, text=True)
    return "cap_net_bind_service" in (result.stdout or "")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_config(config: dict) -> None:
    DIRTFOREVER_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Elevated helper-script content (Windows: invoked via PowerShell RunAs;
# Linux: invoked via pkexec)
# ---------------------------------------------------------------------------

def _windows_admin_start_script() -> str:
    """Helper Python script that installs the cert and writes the hosts block."""
    return (
        "import subprocess, sys\n"
        f"r = subprocess.run(['certutil', '-addstore', 'Root', {str(CERT_PATH)!r}], capture_output=True)\n"
        "print('cert:', 'ok' if r.returncode == 0 else 'fail')\n"
        f"hosts = {str(HOSTS_FILE)!r}\n"
        "try:\n"
        "    content = open(hosts, encoding='utf-8').read()\n"
        "except UnicodeDecodeError:\n"
        "    content = open(hosts, encoding='latin-1').read()\n"
        "lines, out, inside = content.splitlines(True), [], False\n"
        "for l in lines:\n"
        "    s = l.strip()\n"
        f"    if s == {HOSTS_BEGIN!r}: inside = True; continue\n"
        f"    if s == {HOSTS_END!r}: inside = False; continue\n"
        "    if not inside: out.append(l)\n"
        "cleaned = ''.join(out).rstrip('\\r\\n')\n"
        f"block = '\\r\\n'.join([{HOSTS_BEGIN!r}] + "
        f"[{SERVER_IP!r} + '\\t' + d for d in {REDIRECT_DOMAINS!r}] + "
        f"[{HOSTS_END!r}])\n"
        "new = (cleaned + '\\r\\n\\r\\n' + block + '\\r\\n') if cleaned else (block + '\\r\\n')\n"
        "open(hosts, 'wb').write(new.encode('utf-8'))\n"
        "print('hosts: ok')\n"
    )


def _windows_admin_stop_script() -> str:
    return (
        f"hosts = {str(HOSTS_FILE)!r}\n"
        "try:\n"
        "    content = open(hosts, encoding='utf-8').read()\n"
        "except UnicodeDecodeError:\n"
        "    content = open(hosts, encoding='latin-1').read()\n"
        "lines, out, inside = content.splitlines(True), [], False\n"
        "for l in lines:\n"
        "    s = l.strip()\n"
        f"    if s == {HOSTS_BEGIN!r}: inside = True; continue\n"
        f"    if s == {HOSTS_END!r}: inside = False; continue\n"
        "    if not inside: out.append(l)\n"
        "open(hosts, 'wb').write(''.join(out).encode('utf-8'))\n"
        "print('ok')\n"
    )


def _linux_admin_start_script(setcap_target: Path) -> str:
    """Helper Python script (run via pkexec) that:
       1. Grants cap_net_bind_service to setcap_target.
       2. Writes the /etc/hosts block.
    """
    return (
        "import subprocess\n"
        f"target = {str(setcap_target)!r}\n"
        "r = subprocess.run(['setcap', 'cap_net_bind_service=+ep', target], capture_output=True, text=True)\n"
        "print('setcap:', 'ok' if r.returncode == 0 else 'fail ' + (r.stderr or '').strip())\n"
        f"hosts = {str(HOSTS_FILE)!r}\n"
        "try:\n"
        "    content = open(hosts, encoding='utf-8').read()\n"
        "except UnicodeDecodeError:\n"
        "    content = open(hosts, encoding='latin-1').read()\n"
        "lines, out, inside = content.splitlines(True), [], False\n"
        "for l in lines:\n"
        "    s = l.strip()\n"
        f"    if s == {HOSTS_BEGIN!r}: inside = True; continue\n"
        f"    if s == {HOSTS_END!r}: inside = False; continue\n"
        "    if not inside: out.append(l)\n"
        "cleaned = ''.join(out).rstrip('\\n')\n"
        f"block = '\\n'.join([{HOSTS_BEGIN!r}] + "
        f"[{SERVER_IP!r} + '\\t' + d for d in {REDIRECT_DOMAINS!r}] + "
        f"[{HOSTS_END!r}])\n"
        "new = (cleaned + '\\n\\n' + block + '\\n') if cleaned else (block + '\\n')\n"
        "open(hosts, 'wb').write(new.encode('utf-8'))\n"
        "print('hosts: ok')\n"
    )


def _linux_admin_stop_script() -> str:
    return (
        f"hosts = {str(HOSTS_FILE)!r}\n"
        "try:\n"
        "    content = open(hosts, encoding='utf-8').read()\n"
        "except UnicodeDecodeError:\n"
        "    content = open(hosts, encoding='latin-1').read()\n"
        "lines, out, inside = content.splitlines(True), [], False\n"
        "for l in lines:\n"
        "    s = l.strip()\n"
        f"    if s == {HOSTS_BEGIN!r}: inside = True; continue\n"
        f"    if s == {HOSTS_END!r}: inside = False; continue\n"
        "    if not inside: out.append(l)\n"
        "open(hosts, 'wb').write(''.join(out).encode('utf-8'))\n"
        "print('ok')\n"
    )


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

def run_gui():
    import tkinter as tk
    from tkinter import ttk, messagebox

    config = load_config()
    server_thread: Optional[threading.Thread] = None
    server_running = threading.Event()
    shutdown_flag = threading.Event()

    # Colors (matched to dirtforever.net web theme)
    BG = "#08080C"
    BG_CARD = "#14141C"
    BG_ELEVATED = "#1A1A24"
    ACCENT = "#E8720C"
    ACCENT_BRIGHT = "#FF8C2E"
    GREEN = "#22C55E"
    RED = "#EF4444"
    TEXT = "#E8E4DF"
    MUTED = "#8A8992"
    BORDER = "#2A2A36"

    # --- Window setup ---
    root = tk.Tk()
    root.title(f"DirtForever v{VERSION}")
    root.resizable(False, False)
    root.configure(bg=BG)

    # Center on screen
    w, h = 440, 500
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 2
    root.geometry(f"{w}x{h}+{x}+{y}")

    # --- Update check (non-blocking) ---
    GOLD = "#F59E0B"
    update_bar = tk.Frame(root, bg=GOLD)
    update_label = tk.Label(update_bar, text="", font=(UI_FONT, 9, "bold"),
                            fg="#111", bg=GOLD, cursor="hand2")
    update_label.pack(padx=10, pady=4)

    def _check_for_updates():
        import urllib.request
        try:
            req = urllib.request.Request(
                "https://api.github.com/repos/winrid/dirtforever/releases/latest",
                headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "DirtForever"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            remote_tag = data.get("tag_name", "").lstrip("v")
            # Match the canonical asset name exactly — debug builds, signed
            # variants, etc. should not be picked up by the update banner.
            wanted_name = "DirtForever.exe" if IS_WIN else "DirtForever-linux-x86_64"
            dl_url = ""
            for asset in data.get("assets", []):
                if asset.get("name") == wanted_name:
                    dl_url = asset.get("browser_download_url", "")
                    break
            if not remote_tag or not dl_url:
                return
            # Simple version compare (works for semver with same segment count)
            remote_parts = [int(x) for x in remote_tag.split(".")]
            local_parts = [int(x) for x in VERSION.split(".") if x.isdigit()]
            if remote_parts > local_parts:
                def show():
                    update_label.configure(
                        text=f"Update available: v{remote_tag}  —  click to download")
                    update_label.bind("<Button-1>", lambda e: webbrowser.open(dl_url))
                    update_bar.pack(fill="x", padx=20, pady=(5, 0), before=header)
                root.after(0, show)
        except Exception:
            pass  # Silent fail — update check is best-effort

    threading.Thread(target=_check_for_updates, daemon=True).start()

    # --- Header ---
    header = tk.Frame(root, bg=BG)
    header.pack(fill="x", padx=20, pady=(20, 5))
    tk.Label(header, text="DIRTFOREVER", font=(UI_FONT, 18, "bold"),
             fg=ACCENT, bg=BG).pack(side="left")
    tk.Label(header, text="Community Rally Server", font=(UI_FONT, 9),
             fg=MUTED, bg=BG).pack(side="left", padx=(10, 0), pady=(6, 0))

    # --- Token config ---
    token_frame = tk.Frame(root, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1)
    token_frame.pack(fill="x", padx=20, pady=(10, 5))

    tk.Label(token_frame, text="GAME TOKEN", font=(UI_FONT, 8, "bold"),
             fg=MUTED, bg=BG_CARD).pack(anchor="w", padx=12, pady=(8, 2))

    token_input_frame = tk.Frame(token_frame, bg=BG_CARD)
    token_input_frame.pack(fill="x", padx=12, pady=(0, 8))

    token_var = tk.StringVar(value=config.get("game_token", ""))
    token_entry = tk.Entry(
        token_input_frame, textvariable=token_var, font=(MONO_FONT, 9),
        bg=BG, fg=TEXT, insertbackground=TEXT, relief="flat",
        highlightbackground=BORDER, highlightthickness=1,
    )
    token_entry.pack(side="left", fill="x", expand=True, ipady=4)

    def save_token():
        t = token_var.get().strip()
        config["game_token"] = t
        config.setdefault("api_url", API_URL)
        save_config(config)
        if not t:
            token_status_label.configure(text="No token", fg=ACCENT)
            return
        token_status_label.configure(text="Testing token...", fg=MUTED)
        save_btn.configure(state="disabled")

        def verify():
            from dr2server.api_client import DirtForeverClient
            client = DirtForeverClient(base_url=config.get("api_url", API_URL), api_token=t)
            username = client.test_token()
            if username:
                root.after(0, lambda u=username: token_status_label.configure(
                    text=f"\u2713 Token working \u2014 linked to {u}", fg=GREEN))
            else:
                root.after(0, lambda: token_status_label.configure(
                    text="\u2717 Token invalid or server unreachable", fg=RED))
            root.after(0, lambda: save_btn.configure(state="normal"))

        threading.Thread(target=verify, daemon=True).start()

    save_btn = tk.Button(
        token_input_frame, text="Save", font=(UI_FONT, 8, "bold"),
        bg=ACCENT, fg="#111", activebackground=ACCENT_BRIGHT, activeforeground="#111",
        relief="flat", cursor="hand2", padx=10, pady=2,
        command=save_token,
    )
    save_btn.pack(side="right", padx=(5, 0))

    token_status_label = tk.Label(token_frame, text="", font=(UI_FONT, 8), fg=MUTED, bg=BG_CARD)
    token_status_label.pack(anchor="w", padx=12, pady=(0, 6))

    if config.get("game_token"):
        token_status_label.configure(text="Token configured", fg=GREEN)
    else:
        token_status_label.configure(text="Get token at dirtforever.net/dashboard", fg=MUTED)

    # --- Status ---
    status_frame = tk.Frame(root, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1)
    status_frame.pack(fill="x", padx=20, pady=5)

    status_dot = tk.Label(status_frame, text="\u25cf", font=(UI_FONT, 14),
                          fg=MUTED, bg=BG_CARD)
    status_dot.pack(side="left", padx=(15, 5), pady=10)

    status_label = tk.Label(status_frame, text="Stopped", font=(UI_FONT, 12, "bold"),
                            fg=TEXT, bg=BG_CARD)
    status_label.pack(side="left", pady=10)

    status_detail = tk.Label(status_frame, text="", font=(UI_FONT, 9),
                             fg=MUTED, bg=BG_CARD)
    status_detail.pack(side="right", padx=15, pady=10)

    # --- Log area ---
    log_frame = tk.Frame(root, bg=BG)
    log_frame.pack(fill="both", expand=True, padx=20, pady=(5, 5))

    log_text = tk.Text(log_frame, height=5, bg=BG, fg=MUTED,
                       font=(MONO_FONT, 8), relief="flat", wrap="word",
                       state="disabled", borderwidth=0)
    log_text.pack(fill="both", expand=True)

    def log(msg: str):
        log_text.configure(state="normal")
        log_text.insert("end", msg + "\n")
        log_text.see("end")
        log_text.configure(state="disabled")

    # --- Buttons ---
    btn_frame = tk.Frame(root, bg=BG)
    btn_frame.pack(fill="x", padx=20, pady=(5, 8))

    easy_setup_var = tk.BooleanVar(value=config.get("easy_setup", True))
    easy_cb = tk.Checkbutton(
        btn_frame, text="Easy Setup Mode (Requires Admin)",
        variable=easy_setup_var,
        bg=BG, fg=TEXT, activebackground=BG, activeforeground=TEXT,
        selectcolor=BG_ELEVATED, font=(UI_FONT, 9),
        highlightthickness=0, bd=0, anchor="w",
    )
    easy_cb.pack(fill="x", pady=(0, 2))

    manual_link = tk.Label(
        btn_frame, text="Manual setup instructions \u2192",
        font=(UI_FONT, 8, "underline"),
        fg=ACCENT, bg=BG, cursor="hand2", anchor="w",
    )
    manual_link.bind(
        "<Button-1>",
        lambda e: webbrowser.open("https://dirtforever.net/install#manual"),
    )

    def _update_easy_setup():
        if easy_setup_var.get():
            manual_link.pack_forget()
        else:
            manual_link.pack(fill="x", pady=(0, 5), before=start_btn)
        config["easy_setup"] = easy_setup_var.get()
        save_config(config)

    easy_cb.configure(command=_update_easy_setup)

    start_btn = tk.Button(
        btn_frame, text="START", font=(UI_FONT, 11, "bold"),
        bg=GREEN, fg="#111", activebackground="#1a9e4a", activeforeground="#111",
        relief="flat", cursor="hand2", padx=20, pady=10,
    )
    start_btn.pack(fill="x", pady=(0, 5))

    # Show link below checkbox if starting unchecked
    if not easy_setup_var.get():
        manual_link.pack(fill="x", pady=(0, 5), before=start_btn)

    stop_btn = tk.Button(
        btn_frame, text="STOP", font=(UI_FONT, 10, "bold"),
        bg=BG_ELEVATED, fg=MUTED, activebackground="#333", activeforeground=TEXT,
        relief="flat", cursor="hand2", padx=20, pady=8,
        state="disabled",
    )
    stop_btn.pack(fill="x")

    # --- Footer ---
    footer = tk.Frame(root, bg=BG)
    footer.pack(fill="x", padx=20, pady=(0, 12))

    dash_link = tk.Label(footer, text="dirtforever.net/dashboard", font=(UI_FONT, 8, "underline"),
                         fg=ACCENT, bg=BG, cursor="hand2")
    dash_link.pack(side="right")
    dash_link.bind("<Button-1>", lambda e: webbrowser.open(DASHBOARD_URL))

    # --- Server control ---
    def set_status(running: bool, detail: str = ""):
        if running:
            status_dot.configure(fg=GREEN)
            status_label.configure(text="Running")
            status_detail.configure(text=detail or "Launch DR2 to play")
            start_btn.configure(state="disabled", bg=BG_ELEVATED)
            stop_btn.configure(state="normal", bg=RED, fg=TEXT)
        else:
            status_dot.configure(fg=MUTED)
            status_label.configure(text="Stopped")
            status_detail.configure(text=detail)
            start_btn.configure(state="normal", bg=GREEN)
            stop_btn.configure(state="disabled", bg=BG_ELEVATED, fg=MUTED)

    def server_worker():
        """Run the game server in a background thread."""
        try:
            # Import and configure server
            cert = config.get("cert_path", str(CERT_PATH))
            key = config.get("key_path", str(KEY_PATH))
            api_url = config.get("api_url", API_URL)
            api_token = config.get("game_token")
            data_root = str(_data_dir())

            sys.argv = [sys.argv[0],
                        "--ssl-cert", cert,
                        "--ssl-key", key,
                        "--data-dir", data_root]
            if api_url:
                sys.argv += ["--api-url", api_url]
            if api_token:
                sys.argv += ["--api-token", api_token]

            from dr2server.httpd import build_arg_parser, App, create_server
            import ssl
            import time

            args = build_arg_parser().parse_args()
            from dr2server.api_client import DirtForeverClient
            api_client = None
            if args.api_url:
                api_client = DirtForeverClient(
                    base_url=args.api_url,
                    api_token=getattr(args, 'api_token', None),
                )

            app = App(
                data_root=Path(args.data_dir),
                capture_root=Path(args.capture_dir),
                api_url=args.api_url,
            )
            if api_client:
                app.dispatcher.api_client = api_client

            servers = []
            http_server = create_server(args.host, args.port, app)
            servers.append(http_server)

            if args.ssl_cert and args.ssl_key:
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ssl_context.load_cert_chain(certfile=args.ssl_cert, keyfile=args.ssl_key)
                https_server = create_server(args.host, args.https_port, app, ssl_context=ssl_context)
                servers.append(https_server)

            for s in servers:
                threading.Thread(target=s.serve_forever, daemon=True).start()

            server_running.set()
            root.after(0, lambda: set_status(True))
            root.after(0, lambda: log("Server listening on HTTPS :443 and HTTP :8080"))

            # Wait until shutdown is requested
            while not shutdown_flag.is_set():
                shutdown_flag.wait(timeout=1.0)

            for s in servers:
                s.shutdown()
                s.server_close()

        except Exception:
            import traceback
            err = traceback.format_exc()
            root.after(0, lambda e=err: log(f"Server error:\n{e}"))
        finally:
            server_running.clear()
            root.after(0, lambda: set_status(False))

    def on_start():
        nonlocal config, server_thread
        config = load_config()
        start_btn.configure(state="disabled")
        log("Starting DirtForever...")

        def setup_and_start():
            nonlocal config
            try:
                easy_setup = easy_setup_var.get()

                # Generate cert if missing (needed in both modes — server loads it).
                if not cert_exists():
                    root.after(0, lambda: log("Generating TLS certificate..."))
                    generate_cert()
                    config["cert_path"] = str(CERT_PATH)
                    config["key_path"] = str(KEY_PATH)
                    save_config(config)

                if not easy_setup:
                    root.after(0, lambda: log(
                        "Easy Setup off - assuming hosts & cert trust are configured manually. "
                        "See dirtforever.net/install#manual"))
                elif IS_WIN:
                    if not hosts_configured():
                        root.after(0, lambda: log("Setting up hosts & cert trust (admin required)..."))
                        helper = DIRTFOREVER_DIR / "_admin_start.py"
                        helper.write_text(_windows_admin_start_script(), encoding="utf-8")
                        exe = sys.executable
                        ps_cmd = f'Start-Process -FilePath "{exe}" -ArgumentList \'"{helper}"\' -Verb RunAs -Wait'
                        try:
                            subprocess.run(
                                ["powershell", "-Command", ps_cmd],
                                capture_output=True,
                                timeout=ELEVATION_TIMEOUT_SECONDS,
                            )
                        except subprocess.TimeoutExpired:
                            root.after(0, lambda: log(
                                "WARNING: UAC prompt timed out after 5 minutes."))
                        helper.unlink(missing_ok=True)

                        if hosts_configured():
                            root.after(0, lambda: log("Hosts configured, cert trusted."))
                        else:
                            root.after(0, lambda: log("WARNING: Could not configure hosts. Run as admin?"))
                else:
                    # Linux: one pkexec runs setcap (port 443) + writes /etc/hosts.
                    target_bin = _elevation_target_binary()
                    needs_setcap = not has_port_capability(target_bin)
                    needs_hosts = not hosts_configured()
                    if needs_setcap or needs_hosts:
                        helper_python = _system_python_for_helper()
                        if helper_python is None:
                            root.after(0, lambda: log(
                                "WARNING: no python3 on PATH. Install python3 or run setcap "
                                "and the /etc/hosts edit manually - see install docs."))
                        else:
                            steps = []
                            if needs_setcap:
                                steps.append("port-443 capability")
                            if needs_hosts:
                                steps.append("/etc/hosts")
                            root.after(0, lambda s=", ".join(steps): log(
                                f"Authentication required to set up {s}..."))
                            helper = DIRTFOREVER_DIR / "_admin_start.py"
                            helper.write_text(_linux_admin_start_script(target_bin), encoding="utf-8")
                            try:
                                result = subprocess.run(
                                    ["pkexec", str(helper_python), str(helper)],
                                    capture_output=True, text=True,
                                    timeout=ELEVATION_TIMEOUT_SECONDS,
                                )
                            except subprocess.TimeoutExpired:
                                helper.unlink(missing_ok=True)
                                root.after(0, lambda: log(
                                    "WARNING: polkit prompt timed out after 5 minutes."))
                                result = None
                            if result is not None:
                                helper.unlink(missing_ok=True)
                                out = (result.stdout or "").strip()
                                if result.returncode != 0:
                                    err = (result.stderr or out or "no output").strip().splitlines()[-1:] or [""]
                                    root.after(0, lambda e=err[0]: log(
                                        f"WARNING: elevated setup failed ({e}). "
                                        "You can configure /etc/hosts and setcap manually - see install docs."))
                                else:
                                    if out:
                                        root.after(0, lambda o=out: log(o))
                                    root.after(0, lambda: log("Hosts and port-443 capability configured."))
                                    # Re-exec if we just acquired the cap; the
                                    # current process can't use it.
                                    if needs_setcap and has_port_capability(target_bin):
                                        root.after(0, lambda: log(
                                            "Relaunching DirtForever to apply port-443 capability..."))
                                        root.after(1500, _relaunch_with_auto_start)
                                        return

                    # Cert into DR2 prefix (no elevation; user owns the prefix).
                    root.after(0, lambda: log("Installing TLS cert into DR2 Proton prefix..."))
                    ok, msg = install_cert_into_dr2_prefix(CERT_PATH)
                    if ok:
                        root.after(0, lambda m=msg: log(m))
                    else:
                        root.after(0, lambda m=msg: log(f"Cert install: {m}"))

                # Check for token
                if not config.get("game_token"):
                    root.after(0, lambda: log("No game token. Get one at dirtforever.net/dashboard"))
                    webbrowser.open(DASHBOARD_URL)
                    # We'll still start the server - it works without token (local mode)

                # Start server
                shutdown_flag.clear()
                server_thread = threading.Thread(target=server_worker, daemon=True)
                server_thread.start()

            except Exception as exc:
                root.after(0, lambda: log(f"Setup error: {exc}"))
                root.after(0, lambda: set_status(False))

        threading.Thread(target=setup_and_start, daemon=True).start()

    def on_stop():
        stop_btn.configure(state="disabled")
        log("Stopping server...")
        shutdown_flag.set()

        def cleanup():
            # Wait for server to stop
            if server_thread:
                server_thread.join(timeout=5)

            if not easy_setup_var.get():
                root.after(0, lambda: log(
                    "Easy Setup off - leaving hosts unchanged. Remove them manually if desired."))
                root.after(0, lambda: set_status(False, "Stopped"))
                return

            # Remove hosts (needs elevation)
            root.after(0, lambda: log("Removing hosts entries (admin required)..."))
            helper = DIRTFOREVER_DIR / "_admin_stop.py"
            try:
                if IS_WIN:
                    helper.write_text(_windows_admin_stop_script(), encoding="utf-8")
                    exe = sys.executable
                    ps_cmd = f'Start-Process -FilePath "{exe}" -ArgumentList \'"{helper}"\' -Verb RunAs -Wait'
                    subprocess.run(
                        ["powershell", "-Command", ps_cmd], capture_output=True,
                        timeout=ELEVATION_TIMEOUT_SECONDS,
                    )
                else:
                    helper_python = _system_python_for_helper()
                    if helper_python is None:
                        root.after(0, lambda: log(
                            "WARNING: no python3 on PATH; cannot remove hosts entries."))
                    else:
                        helper.write_text(_linux_admin_stop_script(), encoding="utf-8")
                        subprocess.run(
                            ["pkexec", str(helper_python), str(helper)],
                            capture_output=True, text=True,
                            timeout=ELEVATION_TIMEOUT_SECONDS,
                        )
            except subprocess.TimeoutExpired:
                root.after(0, lambda: log(
                    "WARNING: elevation prompt timed out after 5 minutes."))
            helper.unlink(missing_ok=True)

            root.after(0, lambda: log("Stopped. Game will use RaceNet servers now."))
            root.after(0, lambda: set_status(False, "Hosts restored"))

        threading.Thread(target=cleanup, daemon=True).start()

    start_btn.configure(command=on_start)
    stop_btn.configure(command=on_stop)

    # If we were just relaunched after a successful setcap, click START
    # automatically so the user doesn't have to.
    if os.environ.pop("DIRTFOREVER_AUTO_START", "") == "1":
        root.after(800, on_start)

    def on_close():
        if server_running.is_set():
            if messagebox.askyesno("DirtForever", "Server is running. Stop it and exit?"):
                shutdown_flag.set()
                if server_thread:
                    server_thread.join(timeout=3)
                root.destroy()
        else:
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Handle admin helper subprocess calls
    if len(sys.argv) == 2 and sys.argv[1].endswith(".py"):
        # Being called as: python dirtforever.py _admin_start.py
        # This shouldn't happen with current design, but guard against it
        pass

    run_gui()
