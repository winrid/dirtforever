"""End-to-end tests for the `--admin-helper` elevation path.

These guard the regression where `DirtForever.exe` (PyInstaller --windowed
--onefile) was being re-launched elevated with a `.py` helper path as argv,
which the bootloader silently ignored — so users saw a phantom second GUI
and hosts/cert never got configured. The fix routes elevation through
`<self> --admin-helper start|stop`, handled at the top of `__main__`
before any Tk code runs.

The tests run the real script as a subprocess against a temp hosts file,
which is exactly how the elevated child runs in production (just without
the UAC prompt). On Windows CI the runner is already admin, so the same
test can also exercise the real PowerShell elevation path — see the CI
workflow.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


DIRTFOREVER_PY = Path(__file__).resolve().parent.parent / "dirtforever.py"


def _run_helper(op: str, hosts_file: Path, cfg_dir: Path) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "DIRTFOREVER_HOSTS_FILE": str(hosts_file),
        "XDG_CONFIG_HOME": str(cfg_dir),
        "APPDATA": str(cfg_dir),
    }
    return subprocess.run(
        [sys.executable, str(DIRTFOREVER_PY), "--admin-helper", op],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.fixture
def temp_hosts(tmp_path: Path) -> Path:
    hosts = tmp_path / "hosts"
    hosts.write_text(
        "127.0.0.1 localhost\n"
        "::1 localhost\n"
        "127.0.1.1 myhost\n",
        encoding="utf-8",
    )
    return hosts


def test_admin_helper_start_writes_block(temp_hosts: Path, tmp_path: Path) -> None:
    result = _run_helper("start", temp_hosts, tmp_path / "cfg")
    assert result.returncode == 0, result.stderr
    content = temp_hosts.read_text(encoding="utf-8")
    assert "# BEGIN DIRTFOREVER" in content
    assert "# END DIRTFOREVER" in content
    assert "127.0.0.1\tprod.egonet.codemasters.com" in content
    assert "127.0.0.1\tqa.egonet.codemasters.com" in content
    assert "127.0.0.1\tterms.codemasters.com" in content
    assert "127.0.0.1\taurora.codemasters.local" in content
    assert "127.0.0.1 localhost" in content


def test_admin_helper_stop_removes_block(temp_hosts: Path, tmp_path: Path) -> None:
    cfg = tmp_path / "cfg"
    assert _run_helper("start", temp_hosts, cfg).returncode == 0
    assert "# BEGIN DIRTFOREVER" in temp_hosts.read_text(encoding="utf-8")

    result = _run_helper("stop", temp_hosts, cfg)
    assert result.returncode == 0, result.stderr
    content = temp_hosts.read_text(encoding="utf-8")
    assert "BEGIN DIRTFOREVER" not in content
    assert "END DIRTFOREVER" not in content
    assert "prod.egonet.codemasters.com" not in content
    # Original entries preserved.
    assert "127.0.0.1 localhost" in content
    assert "127.0.1.1 myhost" in content


def test_admin_helper_start_is_idempotent(temp_hosts: Path, tmp_path: Path) -> None:
    cfg = tmp_path / "cfg"
    assert _run_helper("start", temp_hosts, cfg).returncode == 0
    assert _run_helper("start", temp_hosts, cfg).returncode == 0
    content = temp_hosts.read_text(encoding="utf-8")
    assert content.count("# BEGIN DIRTFOREVER") == 1
    assert content.count("# END DIRTFOREVER") == 1


def test_admin_helper_unknown_op_fails(temp_hosts: Path, tmp_path: Path) -> None:
    result = _run_helper("explode", temp_hosts, tmp_path / "cfg")
    assert result.returncode != 0
    # Hosts unchanged.
    assert "BEGIN DIRTFOREVER" not in temp_hosts.read_text(encoding="utf-8")


def test_admin_helper_does_not_open_gui(temp_hosts: Path, tmp_path: Path) -> None:
    """The elevated child must exit without ever touching Tk — otherwise users
    see a phantom second window (the original Win11 symptom)."""
    result = _run_helper("start", temp_hosts, tmp_path / "cfg")
    assert result.returncode == 0
    combined = (result.stdout + result.stderr).lower()
    # If Tk got initialized without a display we'd see TclError / "no display".
    assert "tclerror" not in combined
    assert "no display" not in combined


def test_self_invocation_args_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    """Frozen builds re-launch DirtForever.exe directly — never with a .py arg,
    because the PyInstaller bootloader doesn't know how to run one."""
    import importlib
    import dirtforever as df
    monkeypatch.setattr(df.sys, "frozen", True, raising=False)
    monkeypatch.setattr(df.sys, "executable", "C:/whatever/DirtForever.exe")
    args = df._self_invocation_args()
    assert args == ["C:/whatever/DirtForever.exe"]


def test_self_invocation_args_source(monkeypatch: pytest.MonkeyPatch) -> None:
    """Source mode passes the .py path explicitly so python.exe can find it."""
    import dirtforever as df
    if hasattr(df.sys, "frozen"):
        monkeypatch.delattr(df.sys, "frozen", raising=False)
    if hasattr(df.sys, "_MEIPASS"):
        monkeypatch.delattr(df.sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(df.sys, "executable", "/usr/bin/python3")
    args = df._self_invocation_args()
    assert args[0] == "/usr/bin/python3"
    assert args[1].endswith("dirtforever.py")
    assert len(args) == 2
