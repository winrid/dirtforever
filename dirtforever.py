"""DirtForever — unified entry point for the DiRT Rally 2.0 community server.

Usage
-----
    dirtforever.exe          first run: setup wizard, then start server
    dirtforever.exe          subsequent runs: start server directly
    dirtforever.exe --setup  force re-run the setup wizard
    dirtforever.exe --server start server only (skip setup check)

PyInstaller compiles this file into a single executable via build_exe.py.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import time
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Resource-path helpers (transparent in dev, works inside PyInstaller bundle)
# ---------------------------------------------------------------------------

def _bundle_root() -> Path:
    """Return the directory where bundled data files live.

    When running from a PyInstaller onefile exe, sys._MEIPASS points to the
    temporary extraction directory.  In a normal Python interpreter the file
    lives next to this script.
    """
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).parent


def _data_dir() -> Path:
    """Return the path to the bundled data/ directory."""
    return _bundle_root() / "data"


# ---------------------------------------------------------------------------
# Paths used at runtime (user-writable locations, NOT inside the bundle)
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


# ---------------------------------------------------------------------------
# Admin elevation
# ---------------------------------------------------------------------------

def is_admin() -> bool:
    """Return True when the process has Windows administrator privileges."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin() -> None:
    """Re-launch the current executable elevated via PowerShell and exit."""
    exe = sys.executable
    args = " ".join(f'"{a}"' for a in sys.argv)
    # Use PowerShell Start-Process with -Verb RunAs to trigger UAC prompt.
    cmd = (
        f'Start-Process -FilePath "{exe}" '
        f'-ArgumentList {args!r} '
        f'-Verb RunAs -Wait'
    )
    subprocess.run(["powershell", "-Command", cmd], check=False)
    sys.exit(0)


# ---------------------------------------------------------------------------
# TLS certificate generation (uses cryptography library, same as generate_dev_cert.py)
# ---------------------------------------------------------------------------

def generate_cert(cert_path: Path, key_path: Path, hosts: list[str]) -> None:
    """Generate a self-signed TLS certificate covering *hosts* and write PEM files."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    cert_path.parent.mkdir(parents=True, exist_ok=True)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "DirtForever"),
            x509.NameAttribute(NameOID.COMMON_NAME, hosts[0]),
        ]
    )
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(h) for h in hosts]),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )

    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    print(f"[cert] Generated certificate: {cert_path}")
    print(f"[cert] Generated private key:  {key_path}")


# ---------------------------------------------------------------------------
# Certificate trust store
# ---------------------------------------------------------------------------

def install_cert_trust(cert_path: Path) -> None:
    """Install *cert_path* into the Windows Root trust store via certutil."""
    print(f"[cert] Installing certificate into Windows Root store …")
    result = subprocess.run(
        ["certutil", "-addstore", "Root", str(cert_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"[cert] certutil failed (exit {result.returncode}):")
        print(result.stdout)
        print(result.stderr)
        raise RuntimeError("Failed to install certificate into trust store.")
    print("[cert] Certificate trusted.")


# ---------------------------------------------------------------------------
# Hosts file management
# ---------------------------------------------------------------------------

def _read_hosts() -> str:
    try:
        return HOSTS_FILE.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return HOSTS_FILE.read_text(encoding="latin-1")


def _strip_dirtforever_block(content: str) -> str:
    """Remove the existing DirtForever hosts block if present."""
    lines = content.splitlines(keepends=True)
    out: list[str] = []
    inside = False
    for line in lines:
        stripped = line.strip()
        if stripped == HOSTS_BEGIN:
            inside = True
            continue
        if stripped == HOSTS_END:
            inside = False
            continue
        if not inside:
            out.append(line)
    return "".join(out)


def setup_hosts(ip: str = SERVER_IP) -> None:
    """Add redirect entries for all Codemasters domains."""
    print(f"[hosts] Updating {HOSTS_FILE} …")
    existing = _read_hosts()
    cleaned = _strip_dirtforever_block(existing).rstrip("\r\n")

    block_lines = [HOSTS_BEGIN]
    for domain in REDIRECT_DOMAINS:
        block_lines.append(f"{ip}\t{domain}")
    block_lines.append(HOSTS_END)
    block = "\r\n".join(block_lines)

    new_content = (cleaned + "\r\n\r\n" + block + "\r\n") if cleaned else (block + "\r\n")
    HOSTS_FILE.write_bytes(new_content.encode("utf-8"))
    print(f"[hosts] Redirected {len(REDIRECT_DOMAINS)} domains to {ip}.")


def hosts_configured() -> bool:
    """Return True when at least one redirect domain points to SERVER_IP in the hosts file."""
    try:
        content = _read_hosts()
    except OSError:
        return False
    return REDIRECT_DOMAINS[0] in content and HOSTS_BEGIN in content


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config() -> Optional[dict]:
    """Load config from %APPDATA%/DirtForever/config.json, or None if missing."""
    if not CONFIG_PATH.exists():
        return None
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def save_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(f"[config] Saved to {CONFIG_PATH}")


# ---------------------------------------------------------------------------
# Setup wizard
# ---------------------------------------------------------------------------

def run_setup() -> dict:
    """Run the first-time setup wizard. Returns the saved config dict."""
    print("=" * 60)
    print("  DirtForever — First-Time Setup")
    print("=" * 60)
    print()

    # --- Admin check ---
    if not is_admin():
        print("[setup] Administrator privileges are required to update the")
        print("        hosts file and install the TLS certificate.")
        print("[setup] Re-launching with UAC elevation …")
        relaunch_as_admin()
        # If we're still here on Windows the relaunch should have happened;
        # on non-Windows this is a no-op guard.
        sys.exit(1)

    # --- TLS certificate ---
    if not CERT_PATH.exists() or not KEY_PATH.exists():
        print("[setup] Generating TLS certificate …")
        hosts = REDIRECT_DOMAINS + ["localhost"]
        generate_cert(CERT_PATH, KEY_PATH, hosts)
    else:
        print(f"[setup] Certificate already exists: {CERT_PATH}")

    # --- Trust store ---
    print("[setup] Installing certificate into Windows trust store …")
    install_cert_trust(CERT_PATH)

    # --- Hosts file ---
    print("[setup] Configuring Windows hosts file …")
    setup_hosts()

    # --- Game token ---
    print()
    print("[setup] Opening dirtforever.net dashboard in your browser …")
    print("        If the browser does not open, visit:")
    print(f"        {DASHBOARD_URL}")
    print()
    try:
        webbrowser.open(DASHBOARD_URL)
    except Exception:
        pass  # Non-fatal; user can open manually.

    token = ""
    while not token.strip():
        token = input("Paste your game token from dirtforever.net: ").strip()
        if not token:
            print("Token cannot be empty. Please try again.")

    # --- Save config ---
    config = {
        "game_token": token,
        "cert_path": str(CERT_PATH),
        "key_path": str(KEY_PATH),
        "api_url": "https://dirtforever.net",
        "setup_complete": True,
    }
    save_config(config)

    print()
    print("[setup] Setup complete!")
    print("        You can now launch DiRT Rally 2.0 and enjoy community races.")
    print()
    return config


# ---------------------------------------------------------------------------
# Server startup
# ---------------------------------------------------------------------------

def start_server(config: dict) -> int:
    """Start the game server using the given config."""
    import sys as _sys

    cert = config.get("cert_path", str(CERT_PATH))
    key = config.get("key_path", str(KEY_PATH))
    api_url = config.get("api_url")

    # Inject the bundled data directory so the server finds upstream templates.
    data_root = _data_dir()

    # Build argv for httpd.main() so the arg parser picks up our values.
    extra_args = [
        "--ssl-cert", cert,
        "--ssl-key", key,
        "--data-dir", str(data_root),
    ]
    if api_url:
        extra_args += ["--api-url", api_url]

    # Temporarily override sys.argv so httpd.build_arg_parser() gets our values.
    original_argv = _sys.argv[:]
    _sys.argv = [_sys.argv[0]] + extra_args

    try:
        from dr2server.httpd import main as httpd_main

        print()
        print("DirtForever server running.")
        print("Launch DiRT Rally 2.0 to play.")
        print("Press Ctrl+C to stop the server.")
        print()

        return httpd_main()
    finally:
        _sys.argv = original_argv


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="DirtForever — DiRT Rally 2.0 community server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "First run performs one-time setup (cert, hosts, token).\n"
            "Subsequent runs start the server immediately."
        ),
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Force re-run the setup wizard even if already configured.",
    )
    parser.add_argument(
        "--server",
        action="store_true",
        help="Skip setup checks and start the server directly.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.server:
        # Explicit server-only mode: load config or bail.
        config = load_config()
        if config is None:
            print("[error] No config found. Run without --server first to complete setup.")
            return 1
        return start_server(config)

    config = load_config()
    needs_setup = args.setup or config is None or not config.get("setup_complete")

    if needs_setup:
        config = run_setup()
    else:
        # Sanity-check that the environment is still correctly configured.
        if not CERT_PATH.exists():
            print("[warn] Certificate missing — run with --setup to regenerate.")
        if not hosts_configured():
            print("[warn] Hosts file entries missing — run with --setup to re-add them.")

    return start_server(config)


if __name__ == "__main__":
    raise SystemExit(main())
