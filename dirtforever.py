"""DirtForever — DiRT Rally 2.0 community server with GUI.

A tkinter GUI with START / STOP buttons that handles cert generation,
hosts file management, and the game server lifecycle.

PyInstaller compiles this file into a single executable via build_exe.py.
"""
from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import threading
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

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

APPDATA = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
DIRTFOREVER_DIR = APPDATA / "DirtForever"
CONFIG_PATH = DIRTFOREVER_DIR / "config.json"
CERTS_DIR = DIRTFOREVER_DIR / "certs"
CERT_PATH = CERTS_DIR / "dr2server-cert.pem"
KEY_PATH = CERTS_DIR / "dr2server-key.pem"

HOSTS_FILE = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "drivers" / "etc" / "hosts"

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
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def run_as_admin(args: list[str]) -> int:
    """Run a subprocess elevated via PowerShell. Returns exit code."""
    exe = sys.executable
    quoted = " ".join(f'"{a}"' for a in args)
    cmd = f'Start-Process -FilePath "{exe}" -ArgumentList \'{quoted}\' -Verb RunAs -Wait'
    result = subprocess.run(["powershell", "-Command", cmd], capture_output=True)
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
    block = [HOSTS_BEGIN] + [f"{SERVER_IP}\t{d}" for d in REDIRECT_DOMAINS] + [HOSTS_END]
    new = (cleaned + "\r\n\r\n" + "\r\n".join(block) + "\r\n") if cleaned else ("\r\n".join(block) + "\r\n")
    HOSTS_FILE.write_bytes(new.encode("utf-8"))


def remove_hosts() -> None:
    existing = _read_hosts()
    cleaned = _strip_block(existing)
    HOSTS_FILE.write_bytes(cleaned.encode("utf-8"))


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
# Admin helper script — runs elevated to do cert install + hosts changes
# ---------------------------------------------------------------------------

def _admin_action(action: str) -> tuple[bool, str]:
    """Run an admin action in an elevated subprocess. Returns (success, message)."""
    result = subprocess.run(
        [sys.executable, __file__, f"--admin-{action}"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        return True, result.stdout.strip()
    return False, result.stderr.strip() or result.stdout.strip() or "Unknown error"


def _do_admin_start() -> int:
    """Called in elevated subprocess: install cert + add hosts."""
    if not cert_exists():
        generate_cert()
    install_cert_trust()
    add_hosts()
    print("OK")
    return 0


def _do_admin_stop() -> int:
    """Called in elevated subprocess: remove hosts."""
    remove_hosts()
    print("OK")
    return 0


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
    root.title("DirtForever")
    root.resizable(False, False)
    root.configure(bg=BG)

    # Center on screen
    w, h = 440, 500
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 2
    root.geometry(f"{w}x{h}+{x}+{y}")

    # --- Header ---
    header = tk.Frame(root, bg=BG)
    header.pack(fill="x", padx=20, pady=(20, 5))
    tk.Label(header, text="DIRTFOREVER", font=("Segoe UI", 18, "bold"),
             fg=ACCENT, bg=BG).pack(side="left")
    tk.Label(header, text="DiRT Rally 2.0 Community Server", font=("Segoe UI", 9),
             fg=MUTED, bg=BG).pack(side="left", padx=(10, 0), pady=(6, 0))

    # --- Token config ---
    token_frame = tk.Frame(root, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1)
    token_frame.pack(fill="x", padx=20, pady=(10, 5))

    tk.Label(token_frame, text="GAME TOKEN", font=("Segoe UI", 8, "bold"),
             fg=MUTED, bg=BG_CARD).pack(anchor="w", padx=12, pady=(8, 2))

    token_input_frame = tk.Frame(token_frame, bg=BG_CARD)
    token_input_frame.pack(fill="x", padx=12, pady=(0, 8))

    token_var = tk.StringVar(value=config.get("game_token", ""))
    token_entry = tk.Entry(
        token_input_frame, textvariable=token_var, font=("Consolas", 9),
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
        token_input_frame, text="Save", font=("Segoe UI", 8, "bold"),
        bg=ACCENT, fg="#111", activebackground=ACCENT_BRIGHT, activeforeground="#111",
        relief="flat", cursor="hand2", padx=10, pady=2,
        command=save_token,
    )
    save_btn.pack(side="right", padx=(5, 0))

    token_status_label = tk.Label(token_frame, text="", font=("Segoe UI", 8), fg=MUTED, bg=BG_CARD)
    token_status_label.pack(anchor="w", padx=12, pady=(0, 6))

    if config.get("game_token"):
        token_status_label.configure(text="Token configured", fg=GREEN)
    else:
        token_status_label.configure(text="Get token at dirtforever.net/dashboard", fg=MUTED)

    # --- Status ---
    status_frame = tk.Frame(root, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1)
    status_frame.pack(fill="x", padx=20, pady=5)

    status_dot = tk.Label(status_frame, text="\u25cf", font=("Segoe UI", 14),
                          fg=MUTED, bg=BG_CARD)
    status_dot.pack(side="left", padx=(15, 5), pady=10)

    status_label = tk.Label(status_frame, text="Stopped", font=("Segoe UI", 12, "bold"),
                            fg=TEXT, bg=BG_CARD)
    status_label.pack(side="left", pady=10)

    status_detail = tk.Label(status_frame, text="", font=("Segoe UI", 9),
                             fg=MUTED, bg=BG_CARD)
    status_detail.pack(side="right", padx=15, pady=10)

    # --- Log area ---
    log_frame = tk.Frame(root, bg=BG)
    log_frame.pack(fill="both", expand=True, padx=20, pady=(5, 5))

    log_text = tk.Text(log_frame, height=5, bg=BG, fg=MUTED,
                       font=("Consolas", 8), relief="flat", wrap="word",
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

    start_btn = tk.Button(
        btn_frame, text="START DIRTFOREVER", font=("Segoe UI", 11, "bold"),
        bg=GREEN, fg="#111", activebackground="#1a9e4a", activeforeground="#111",
        relief="flat", cursor="hand2", padx=20, pady=10,
    )
    start_btn.pack(fill="x", pady=(0, 5))

    stop_btn = tk.Button(
        btn_frame, text="STOP", font=("Segoe UI", 10, "bold"),
        bg=BG_ELEVATED, fg=MUTED, activebackground="#333", activeforeground=TEXT,
        relief="flat", cursor="hand2", padx=20, pady=8,
        state="disabled",
    )
    stop_btn.pack(fill="x")

    # --- Footer ---
    footer = tk.Frame(root, bg=BG)
    footer.pack(fill="x", padx=20, pady=(0, 12))

    dash_link = tk.Label(footer, text="dirtforever.net/dashboard", font=("Segoe UI", 8, "underline"),
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
                # Generate cert if missing
                if not cert_exists():
                    root.after(0, lambda: log("Generating TLS certificate..."))
                    generate_cert()
                    config["cert_path"] = str(CERT_PATH)
                    config["key_path"] = str(KEY_PATH)
                    save_config(config)

                # Check if admin actions needed (cert trust + hosts)
                needs_admin = not hosts_configured()
                # Always try to ensure cert is trusted and hosts are set
                if needs_admin or not hosts_configured():
                    root.after(0, lambda: log("Setting up hosts & cert trust (admin required)..."))
                    # Write a helper script and run it elevated
                    helper = DIRTFOREVER_DIR / "_admin_start.py"
                    helper.write_text(
                        f"import subprocess, sys\n"
                        f"r = subprocess.run(['certutil', '-addstore', 'Root', r'{CERT_PATH}'], capture_output=True)\n"
                        f"print('cert:', 'ok' if r.returncode == 0 else 'fail')\n"
                        f"# Add hosts\n"
                        f"hosts = r'{HOSTS_FILE}'\n"
                        f"try:\n"
                        f"    content = open(hosts, encoding='utf-8').read()\n"
                        f"except UnicodeDecodeError:\n"
                        f"    content = open(hosts, encoding='latin-1').read()\n"
                        f"# Strip old block\n"
                        f"lines, out, inside = content.splitlines(True), [], False\n"
                        f"for l in lines:\n"
                        f"    s = l.strip()\n"
                        f"    if s == '{HOSTS_BEGIN}': inside = True; continue\n"
                        f"    if s == '{HOSTS_END}': inside = False; continue\n"
                        f"    if not inside: out.append(l)\n"
                        f"cleaned = ''.join(out).rstrip('\\r\\n')\n"
                        f"block = '\\r\\n'.join(['{HOSTS_BEGIN}'] + "
                        f"['{SERVER_IP}\\t' + d for d in {REDIRECT_DOMAINS!r}] + "
                        f"['{HOSTS_END}'])\n"
                        f"new = (cleaned + '\\r\\n\\r\\n' + block + '\\r\\n') if cleaned else (block + '\\r\\n')\n"
                        f"open(hosts, 'wb').write(new.encode('utf-8'))\n"
                        f"print('hosts: ok')\n",
                        encoding="utf-8",
                    )
                    # Run elevated
                    exe = sys.executable
                    ps_cmd = f'Start-Process -FilePath "{exe}" -ArgumentList \'"{helper}"\' -Verb RunAs -Wait'
                    subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)
                    helper.unlink(missing_ok=True)

                    if hosts_configured():
                        root.after(0, lambda: log("Hosts configured, cert trusted."))
                    else:
                        root.after(0, lambda: log("WARNING: Could not configure hosts. Run as admin?"))

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

            # Remove hosts (needs admin)
            root.after(0, lambda: log("Removing hosts entries (admin required)..."))
            helper = DIRTFOREVER_DIR / "_admin_stop.py"
            helper.write_text(
                f"hosts = r'{HOSTS_FILE}'\n"
                f"try:\n"
                f"    content = open(hosts, encoding='utf-8').read()\n"
                f"except UnicodeDecodeError:\n"
                f"    content = open(hosts, encoding='latin-1').read()\n"
                f"lines, out, inside = content.splitlines(True), [], False\n"
                f"for l in lines:\n"
                f"    s = l.strip()\n"
                f"    if s == '{HOSTS_BEGIN}': inside = True; continue\n"
                f"    if s == '{HOSTS_END}': inside = False; continue\n"
                f"    if not inside: out.append(l)\n"
                f"open(hosts, 'wb').write(''.join(out).encode('utf-8'))\n"
                f"print('ok')\n",
                encoding="utf-8",
            )
            exe = sys.executable
            ps_cmd = f'Start-Process -FilePath "{exe}" -ArgumentList \'"{helper}"\' -Verb RunAs -Wait'
            subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)
            helper.unlink(missing_ok=True)

            root.after(0, lambda: log("Stopped. Game will use RaceNet servers now."))
            root.after(0, lambda: set_status(False, "Hosts restored"))

        threading.Thread(target=cleanup, daemon=True).start()

    start_btn.configure(command=on_start)
    stop_btn.configure(command=on_stop)

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
