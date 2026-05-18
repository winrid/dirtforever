"""End-to-end test for the built executable's `--admin-helper` path.

Run as:  python integration_admin_helper_exe.py <path-to-DirtForever[.exe]>

This is the test that would have caught the Win11 (and silent Win10) bug:
the prior elevation flow re-launched DirtForever.exe with a `.py` helper
path as argv, and the PyInstaller bootloader silently ignored it — the
elevated child opened a second GUI instead of writing hosts. By driving
the *built* binary (not a source-mode subprocess) we exercise the real
bootloader path that ships to users.

Driven directly (not through pytest) so it can run from a CI step with
minimal setup. Exits non-zero on any failure.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


REDIRECT_DOMAINS = [
    "prod.egonet.codemasters.com",
    "qa.egonet.codemasters.com",
    "terms.codemasters.com",
    "aurora.codemasters.local",
]


def _run(exe: Path, op: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(exe), "--admin-helper", op],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <path-to-built-binary>", file=sys.stderr)
        return 2

    exe = Path(sys.argv[1]).resolve()
    if not exe.is_file():
        print(f"built binary not found: {exe}", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        hosts = tmp / "hosts"
        hosts.write_text(
            "127.0.0.1 localhost\n"
            "::1 localhost\n"
            "127.0.1.1 ci-runner\n",
            encoding="utf-8",
        )
        cfg = tmp / "cfg"
        cfg.mkdir()

        env = {
            **os.environ,
            "DIRTFOREVER_HOSTS_FILE": str(hosts),
            "XDG_CONFIG_HOME": str(cfg),
            "APPDATA": str(cfg),
        }

        print(f"[integration] start: {exe} --admin-helper start")
        result = _run(exe, "start", env)
        print(f"  exit={result.returncode}")
        if result.stdout:
            print(f"  stdout: {result.stdout.strip()}")
        if result.stderr:
            print(f"  stderr: {result.stderr.strip()}")
        if result.returncode != 0:
            print("FAIL: --admin-helper start exited non-zero", file=sys.stderr)
            return 1

        content = hosts.read_text(encoding="utf-8")
        print(f"[integration] hosts after start:\n{content}")
        if "# BEGIN DIRTFOREVER" not in content:
            print("FAIL: BEGIN marker missing — bootloader probably ignored argv", file=sys.stderr)
            return 1
        if "# END DIRTFOREVER" not in content:
            print("FAIL: END marker missing", file=sys.stderr)
            return 1
        for domain in REDIRECT_DOMAINS:
            if domain not in content:
                print(f"FAIL: missing redirect domain {domain}", file=sys.stderr)
                return 1
        if "127.0.0.1 localhost" not in content:
            print("FAIL: original hosts entries were clobbered", file=sys.stderr)
            return 1

        print(f"[integration] stop: {exe} --admin-helper stop")
        result = _run(exe, "stop", env)
        print(f"  exit={result.returncode}")
        if result.returncode != 0:
            print("FAIL: --admin-helper stop exited non-zero", file=sys.stderr)
            return 1

        content = hosts.read_text(encoding="utf-8")
        if "BEGIN DIRTFOREVER" in content:
            print("FAIL: BEGIN marker still present after stop", file=sys.stderr)
            return 1
        if "127.0.0.1 localhost" not in content:
            print("FAIL: original hosts entries lost during stop", file=sys.stderr)
            return 1

    print("OK: built binary correctly handles --admin-helper start/stop")
    return 0


if __name__ == "__main__":
    sys.exit(main())
