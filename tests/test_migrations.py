"""The migration runner, and 0001 (per-location stage conditions).

Stored data is repaired at deploy time rather than converted on read, so these
cover both the framework (ordering, once-only, state, backups) and the actual
value fixes 0001 makes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

WEB_DIR = Path(__file__).resolve().parents[1] / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

import migrations  # noqa: E402
from migrations import m0001_per_location_stage_conditions as m0001  # noqa: E402


def _store(tmp_path: Path, events: dict[str, dict]) -> Path:
    (tmp_path / "events").mkdir(parents=True)
    (tmp_path / "championship_drafts").mkdir(parents=True)
    for name, doc in events.items():
        (tmp_path / "events" / f"{name}.json").write_text(json.dumps(doc), encoding="utf-8")
    return tmp_path


def _read(data_dir: Path, name: str) -> dict:
    return json.loads((data_dir / "events" / f"{name}.json").read_text(encoding="utf-8"))


# ── framework ────────────────────────────────────────────────────────────────

def test_discover_ids_match_filenames() -> None:
    # The runner records ids, so a mismatch would let a migration run twice.
    for mod in migrations.discover():
        assert mod.ID and mod.DESCRIPTION


def test_runs_once_and_records_state(tmp_path: Path) -> None:
    data = _store(tmp_path, {})
    assert migrations.run_pending(data, log=lambda _m: None) == 1
    assert m0001.ID in migrations.applied_ids(data)
    # Second deploy: nothing pending.
    assert migrations.run_pending(data, log=lambda _m: None) == 0


def test_dry_run_changes_nothing(tmp_path: Path) -> None:
    data = _store(tmp_path, {"evt-a": {
        "id": "evt-a", "location": "Germany",
        "events": [{"location": "Germany",
                    "stages": [{"track_id": 489, "conditions_id": 38}]}],
    }})
    migrations.run_pending(data, dry_run=True, log=lambda _m: None)
    assert _read(data, "evt-a")["events"][0]["stages"][0]["conditions_id"] == 38
    assert migrations.applied_ids(data) == set()


def test_missing_data_dir_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        migrations.run_pending(tmp_path / "nope", log=lambda _m: None)


def test_corrupt_state_refuses_to_guess(tmp_path: Path) -> None:
    data = _store(tmp_path, {})
    (data / migrations.STATE_FILE).write_text("{not json", encoding="utf-8")
    with pytest.raises(RuntimeError):
        migrations.run_pending(data, log=lambda _m: None)


def test_backup_is_written(tmp_path: Path) -> None:
    data = _store(tmp_path, {"evt-a": {"id": "evt-a", "location": "Germany",
                                       "stages": [{"track_id": 489, "conditions_id": 38}]}})
    migrations.run_pending(data, log=lambda _m: None)
    backups = list((data / migrations.BACKUP_DIR).glob(f"{m0001.ID}-*/events/evt-a.json"))
    assert len(backups) == 1
    # The backup holds the pre-migration value.
    assert json.loads(backups[0].read_text(encoding="utf-8"))["stages"][0]["conditions_id"] == 38


# ── 0001: per-location stage conditions ──────────────────────────────────────

def test_invalid_id_is_replaced_with_a_valid_one(tmp_path: Path) -> None:
    # 38 = Daytime / Overcast / Dry. Germany ships no midday_overcast lighting,
    # so this is exactly the daily that loaded with a broken skybox, and
    # Germany offers no other id with that label -- so it must fall back.
    data = _store(tmp_path, {"evt-de": {
        "id": "evt-de", "location": "Germany", "conditions": "Daytime / Overcast / Dry",
        "events": [{"location": "Germany", "stages": [
            {"track_id": 489, "conditions_id": 38, "conditions": "Daytime / Overcast / Dry"},
        ]}],
    }})
    migrations.run_pending(data, log=lambda _m: None)

    from dr2server.game_data import stage_conditions_for_location
    doc = _read(data, "evt-de")
    stage = doc["events"][0]["stages"][0]
    assert stage["conditions_id"] in stage_conditions_for_location("Germany")
    # The label follows the id, so the site shows what the game will load.
    assert stage["conditions"] == "Daytime / Clear / Dry"
    assert doc["conditions"] == "Daytime / Clear / Dry"


def test_twin_id_keeps_the_owners_weather(tmp_path: Path) -> None:
    """An unloadable id whose label IS available keeps that weather.

    34 was the old builder's canonical "Sunset / Cloudy / Wet" and no location
    can load it, but 20 renders the identical label at 18 of them. Resetting
    such a stage to Daytime / Clear / Dry would silently rewrite what the owner
    picked when the location can reproduce it exactly.
    """
    data = _store(tmp_path, {"evt-au": {
        "id": "evt-au", "location": "Australia",
        "events": [{"location": "Australia", "stages": [
            {"track_id": 568, "conditions_id": 34, "conditions": "Sunset / Cloudy / Wet"},
        ]}],
    }})
    migrations.run_pending(data, log=lambda _m: None)
    stage = _read(data, "evt-au")["events"][0]["stages"][0]
    assert stage["conditions_id"] == 20
    assert stage["conditions"] == "Sunset / Cloudy / Wet"


def test_twin_id_resolves_to_the_locations_sibling(tmp_path: Path) -> None:
    # 38 and 2 both read "Daytime / Overcast / Dry"; Greece can load 2 but not
    # 38, so a stored 38 there should become 2 rather than lose the weather.
    data = _store(tmp_path, {"evt-gr": {
        "id": "evt-gr", "location": "Greece",
        "events": [{"location": "Greece", "stages": [
            {"track_id": 471, "conditions_id": 38},
        ]}],
    }})
    migrations.run_pending(data, log=lambda _m: None)
    stage = _read(data, "evt-gr")["events"][0]["stages"][0]
    assert stage["conditions_id"] == 2
    assert stage["conditions"] == "Daytime / Overcast / Dry"


def test_unknown_id_falls_back_to_the_stored_label(tmp_path: Path) -> None:
    # A junk id has no label of its own, so the stored label is the only
    # remaining evidence of what was intended.
    data = _store(tmp_path, {"evt-x": {
        "id": "evt-x", "location": "Australia",
        "events": [{"location": "Australia", "stages": [
            {"track_id": 568, "conditions_id": 999, "conditions": "Sunset / Cloudy / Wet"},
        ]}],
    }})
    migrations.run_pending(data, log=lambda _m: None)
    assert _read(data, "evt-x")["events"][0]["stages"][0]["conditions_id"] == 20


def test_valid_id_is_left_alone(tmp_path: Path) -> None:
    # Poland genuinely ships midday_overcast, so 38 must survive there.
    data = _store(tmp_path, {"evt-pl": {
        "id": "evt-pl", "location": "Poland",
        "events": [{"location": "Poland", "stages": [
            {"track_id": 614, "conditions_id": 38, "conditions": "Daytime / Overcast / Dry"},
        ]}],
    }})
    migrations.run_pending(data, log=lambda _m: None)
    assert _read(data, "evt-pl")["events"][0]["stages"][0]["conditions_id"] == 38


def test_legacy_label_without_id_is_resolved(tmp_path: Path) -> None:
    # Pre-id events stored a short label only.
    data = _store(tmp_path, {"evt-old": {
        "id": "evt-old", "location": "Poland", "conditions": "Overcast",
        "stages": [{"name": "X", "conditions": "Overcast"}],
    }})
    migrations.run_pending(data, log=lambda _m: None)
    stage = _read(data, "evt-old")["stages"][0]
    # Poland offers Daytime / Overcast / Dry, so the owner's pick is preserved.
    assert stage["conditions_id"] == 38


def test_legacy_label_the_location_lacks_falls_back_to_its_first_option(tmp_path: Path) -> None:
    data = _store(tmp_path, {"evt-old-de": {
        "id": "evt-old-de", "location": "Germany", "conditions": "Overcast",
        "stages": [{"name": "X", "conditions": "Overcast"}],
    }})
    migrations.run_pending(data, log=lambda _m: None)

    from dr2server.game_data import default_stage_conditions_for_location
    stage = _read(data, "evt-old-de")["stages"][0]
    assert stage["conditions_id"] == default_stage_conditions_for_location("Germany")


def test_unverified_location_is_untouched(tmp_path: Path) -> None:
    # Twin Peaks is not offered in the Freeplay builder, so we have nothing to
    # validate against and must not guess.
    data = _store(tmp_path, {"evt-tp": {
        "id": "evt-tp", "location": "Twin Peaks",
        "events": [{"location": "Twin Peaks", "stages": [{"conditions_id": 99}]}],
    }})
    migrations.run_pending(data, log=lambda _m: None)
    assert _read(data, "evt-tp")["events"][0]["stages"][0]["conditions_id"] == 99


def test_is_idempotent(tmp_path: Path) -> None:
    data = _store(tmp_path, {"evt-de": {
        "id": "evt-de", "location": "Germany",
        "events": [{"location": "Germany", "stages": [{"track_id": 489, "conditions_id": 38}]}],
    }})
    migrations.run_pending(data, log=lambda _m: None)
    once = _read(data, "evt-de")
    # Re-running the migration directly (as a retried deploy would) is a no-op.
    result = m0001.run(data)
    assert result.changed == 0
    assert _read(data, "evt-de") == once


def test_unreadable_file_is_reported_not_fatal(tmp_path: Path) -> None:
    data = _store(tmp_path, {"evt-ok": {
        "id": "evt-ok", "location": "Germany",
        "events": [{"location": "Germany", "stages": [{"conditions_id": 38}]}],
    }})
    (data / "events" / "broken.json").write_text("{oops", encoding="utf-8")
    result = m0001.run(data)
    assert any("unreadable" in n for n in result.notes)
    assert result.changed == 1
