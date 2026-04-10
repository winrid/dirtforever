"""Build script — produces dist/DirtForever.exe via PyInstaller.

Run:
    python build_exe.py

Requirements:
    pip install pyinstaller cryptography
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent


def check_pyinstaller() -> None:
    """Ensure PyInstaller is installed; offer to install it if missing."""
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("[build] PyInstaller not found.")
        answer = input("Install it now? (pip install pyinstaller) [y/N] ").strip().lower()
        if answer == "y":
            subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
        else:
            print("[build] Aborted — PyInstaller is required.")
            sys.exit(1)


def build() -> None:
    check_pyinstaller()

    # ------------------------------------------------------------------
    # Data files bundled inside the exe.
    # PyInstaller --add-data syntax: <src_path><sep><dest_dir_in_bundle>
    # On Windows the separator is ";", on other platforms ":".
    # We pass the whole upstream_templates directory; PyInstaller copies all
    # its contents to data/upstream_templates inside the bundle, which is
    # exactly where dirtforever.py looks for them via _data_dir().
    # ------------------------------------------------------------------
    templates_src = ROOT / "data" / "upstream_templates"
    sep = ";" if sys.platform == "win32" else ":"
    add_data = [
        f"{templates_src}{sep}data/upstream_templates",
    ]

    # ------------------------------------------------------------------
    # Hidden imports that PyInstaller's static analysis might miss.
    # ------------------------------------------------------------------
    hidden_imports = [
        # cryptography internals (used by cert generation)
        "cryptography.hazmat.primitives.asymmetric.rsa",
        "cryptography.hazmat.primitives.hashes",
        "cryptography.hazmat.primitives.serialization",
        "cryptography.x509",
        "cryptography.x509.oid",
        # dr2server package and sub-modules
        "dr2server",
        "dr2server.httpd",
        "dr2server.dispatcher",
        "dr2server.egonet",
        "dr2server.models",
        "dr2server.game_data",
        "dr2server.api_client",
        "dr2server.account_store",
    ]

    cmd: list[str] = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "DirtForever",
        # Request administrator privileges at startup (needed for hosts/cert).
        "--uac-admin",
        # Clean build artefacts from previous runs.
        "--clean",
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT),
    ]

    # Data files
    for entry in add_data:
        cmd += ["--add-data", entry]

    # Hidden imports
    for imp in hidden_imports:
        cmd += ["--hidden-import", imp]

    # Optional icon
    icon_path = ROOT / "icon.ico"
    if icon_path.exists():
        cmd += ["--icon", str(icon_path)]
    else:
        print(f"[build] No icon found at {icon_path} — skipping --icon.")

    # Entry point
    cmd.append(str(ROOT / "dirtforever.py"))

    print("[build] Running PyInstaller …")
    print("[build] Command:", " ".join(cmd))
    print()

    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        print(f"\n[build] PyInstaller failed (exit {result.returncode}).")
        sys.exit(result.returncode)

    exe = ROOT / "dist" / "DirtForever.exe"
    print()
    if exe.exists():
        size_mb = exe.stat().st_size / (1024 * 1024)
        print(f"[build] Success!  {exe}  ({size_mb:.1f} MB)")
    else:
        print(f"[build] Warning: expected output not found at {exe}")


if __name__ == "__main__":
    build()
