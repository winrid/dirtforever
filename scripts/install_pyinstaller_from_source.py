"""Install PyInstaller with a bootloader compiled on this machine.

Why: AV heuristics (e.g. Trojan:Win32/Wacatac.B!ml) fingerprint the byte
patterns of PyInstaller's stock bootloader, which also ships in real malware,
so exes built with it get flagged as false positives. A locally compiled
bootloader has different bytes and avoids those detections.

Note that `pip install --no-binary pyinstaller` is NOT enough: the PyPI sdist
ships precompiled bootloaders (PyInstaller/bootloader/<platform>/), so a
source install still packages the stock stub. This script downloads the
sdist, deletes the shipped bootloaders, compiles fresh ones with waf, and
installs the result.

Requires a C toolchain: MSVC on Windows, gcc + zlib headers (zlib1g-dev)
on Linux.

Run:
    python scripts/install_pyinstaller_from_source.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="pyinstaller-src-"))
    run([
        sys.executable, "-m", "pip", "download", "pyinstaller",
        "--no-binary", "pyinstaller", "--no-deps", "-d", str(tmp),
    ])
    sdist = next(tmp.glob("pyinstaller-*.tar.gz"))
    with tarfile.open(sdist) as tf:
        tf.extractall(tmp)
    srcdir = next(
        p for p in tmp.iterdir()
        if p.is_dir() and p.name.startswith("pyinstaller-")
    )

    # Delete the precompiled bootloaders so the build below is the only
    # possible source; if compilation silently failed we would otherwise
    # package the stock (fingerprinted) ones.
    shutil.rmtree(srcdir / "PyInstaller" / "bootloader")

    run([sys.executable, "./waf", "all"], cwd=srcdir / "bootloader")

    built = sorted(
        p.name for p in (srcdir / "PyInstaller" / "bootloader").rglob("run*")
    )
    if not built:
        sys.exit("[bootloader] waf produced no binaries; refusing to install.")
    print(f"[bootloader] Compiled: {', '.join(built)}")

    run([sys.executable, "-m", "pip", "install", str(srcdir)])


if __name__ == "__main__":
    main()
