"""Snapshot assertion helper.

`assert_snapshot(name, value, snapshots_dir)` compares `value` against
`<snapshots_dir>/<name>.json`. With env var `UPDATE_SNAPSHOTS=1`, it
writes the snapshot instead of asserting.

On mismatch, raises `AssertionError` with a unified diff between the
stored and current JSON.
"""
from __future__ import annotations

import difflib
import json
import os
from pathlib import Path
from typing import Any


def _format(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)


def assert_snapshot(name: str, value: Any, snapshots_dir: Path) -> None:
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    filename = name if name.endswith(".json") else f"{name}.json"
    path = snapshots_dir / filename
    actual = _format(value) + "\n"

    if os.environ.get("UPDATE_SNAPSHOTS"):
        path.write_text(actual, encoding="utf-8")
        return

    if not path.exists():
        raise AssertionError(
            f"Snapshot missing: {path}\n"
            f"Run with UPDATE_SNAPSHOTS=1 to create it.\n\n"
            f"Current value:\n{actual}"
        )

    expected = path.read_text(encoding="utf-8")
    if expected == actual:
        return

    diff = "".join(
        difflib.unified_diff(
            expected.splitlines(keepends=True),
            actual.splitlines(keepends=True),
            fromfile=f"{path.name} (snapshot)",
            tofile=f"{path.name} (actual)",
        )
    )
    raise AssertionError(
        f"Snapshot mismatch for {name}\n"
        f"  Snapshot path: {path}\n"
        f"  Run with UPDATE_SNAPSHOTS=1 to update.\n\n"
        f"{diff}"
    )
