"""Build script — produces a single-file binary via PyInstaller.

Run:
    python build_exe.py

Output:
    Windows  -> dist/DirtForever.exe
    Linux    -> dist/DirtForever-linux-x86_64

Requirements:
    pip install pyinstaller cryptography
"""
from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
IS_WIN = sys.platform == "win32"
IS_LINUX = sys.platform == "linux"

if IS_WIN:
    APP_NAME = "DirtForever"           # PyInstaller appends .exe
    OUTPUT_NAME = "DirtForever.exe"
elif IS_LINUX:
    # Honest arch tag — CI publishes x86_64 only, but a local build on
    # aarch64 would otherwise produce a misnamed binary.
    APP_NAME = f"DirtForever-linux-{platform.machine()}"
    OUTPUT_NAME = APP_NAME
else:
    APP_NAME = "DirtForever"
    OUTPUT_NAME = "DirtForever"


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
        f"{ROOT / 'VERSION'}{sep}.",
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
        "--name", APP_NAME,
        # No --uac-admin: the app elevates only when needed (hosts/cert),
        # not on every launch. This avoids the UAC prompt just to see the GUI.
        "--windowed",  # No console window (GUI app)
        # Clean build artefacts from previous runs.
        "--clean",
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT),
    ]
    if IS_LINUX:
        # Smaller ELF; harmless on Windows but only meaningful on Linux/macOS.
        cmd.append("--strip")

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

    exe = ROOT / "dist" / OUTPUT_NAME
    print()
    if exe.exists():
        size_mb = exe.stat().st_size / (1024 * 1024)
        print(f"[build] Success!  {exe}  ({size_mb:.1f} MB)")
    else:
        print(f"[build] Warning: expected output not found at {exe}")


if __name__ == "__main__":
    build()
