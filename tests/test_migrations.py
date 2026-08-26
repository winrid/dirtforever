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
from migrations import __main__ as mmain  # noqa: E402
from migrations import m0001_per_location_stage_conditions as m0001  # noqa: E402
from migrations import m0002_nearest_stage_conditions as m0002  # noqa: E402
from migrations import m0004_club_admins as m0004  # noqa: E402


def _store(tmp_path: Path, events: dict[str, dict]) -> Path:
    (tmp_path / "events").mkdir(parents=True)
    (tmp_path / "championship_drafts").mkdir(parents=True)
    for name, doc in events.items():
        (tmp_path / "events" / f"{name}.json").write_text(json.dumps(doc), encoding="utf-8")
    return tmp_path


def _read(data_dir: Path, name: str) -> dict:
    return json.loads((data_dir / "events" / f"{name}.json").read_text(encoding="utf-8"))


def _log_for(data_dir: Path, migration_id: str) -> Path:
    """One migration's changes.json. Each run writes its own, so a test that
    reverts has to name the one it means."""
    return next((data_dir / migrations.BACKUP_DIR).glob(f"{migration_id}*/changes.json"))


# ── framework ────────────────────────────────────────────────────────────────

def test_discover_ids_match_filenames() -> None:
    # The runner records ids, so a mismatch would let a migration run twice.
    for mod in migrations.discover():
        assert mod.ID and mod.DESCRIPTION


def test_runs_once_and_records_state(tmp_path: Path) -> None:
    data = _store(tmp_path, {})
    assert migrations.run_pending(data, log=lambda _m: None) == len(migrations.discover())
    assert {m0001.ID, m0002.ID} <= migrations.applied_ids(data)
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
    # The label follows the id, so the site shows what the game will load,
    # and 0002 keeps it on the dry surface it was written with.
    assert stage["conditions"] == "Sunset / Cloudy / Dry"
    assert doc["conditions"] == stage["conditions"]


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


def test_legacy_label_the_location_lacks_lands_on_its_closest_option(tmp_path: Path) -> None:
    # Germany has no midday overcast. 0001 reset this to the location's first
    # option; 0002 keeps it on the closest dry option instead.
    data = _store(tmp_path, {"evt-old-de": {
        "id": "evt-old-de", "location": "Germany", "conditions": "Overcast",
        "stages": [{"name": "X", "conditions": "Overcast"}],
    }})
    migrations.run_pending(data, log=lambda _m: None)

    from dr2server.game_data import stage_conditions_for_location
    stage = _read(data, "evt-old-de")["stages"][0]
    assert stage["conditions_id"] in stage_conditions_for_location("Germany")
    assert stage["conditions"].endswith("/ Dry")


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


# -- change log and revert ---------------------------------------------------

def test_changes_file_records_before_and_after(tmp_path: Path) -> None:
    """Every rewritten value is logged, and only rewritten values are.

    The directory backup restores the whole store; this is the per-value record
    of what actually moved, so a run can be read back afterwards.
    """
    data = _store(tmp_path, {"evt-de": {
        "id": "evt-de", "location": "Germany", "conditions": "Daytime / Overcast / Dry",
        "events": [{"location": "Germany", "stages": [
            {"track_id": 489, "conditions_id": 38, "conditions": "Daytime / Overcast / Dry"},
            # Already valid at Germany, so it must NOT appear in the log.
            {"track_id": 472, "conditions_id": 9, "conditions": "Daytime / Heavy Rain / Wet"},
        ]}],
    }})
    migrations.run_pending(data, log=lambda _m: None)

    doc = json.loads(_log_for(data, m0001.ID).read_text(encoding="utf-8"))
    assert doc["migration"] == m0001.ID
    assert doc["count"] == len(doc["changes"])

    paths = {c["path"] for c in doc["changes"]}
    assert "events[0].stages[0]" in paths
    assert "events[0].stages[1]" not in paths, "logged a stage it did not change"

    stage = next(c for c in doc["changes"] if c["path"] == "events[0].stages[0]")
    assert stage["before"]["conditions_id"] == 38
    assert stage["after"]["conditions_id"] == 1
    assert stage["location"] == "Germany"


def test_revert_restores_the_original_file(tmp_path: Path) -> None:
    """The log must be sufficient to put the data back exactly as it was."""
    original = {
        "id": "evt-mix", "location": "Germany", "conditions": "Daytime / Overcast / Dry",
        "events": [{"location": "Germany", "stages": [
            {"track_id": 489, "conditions_id": 38, "conditions": "Daytime / Overcast / Dry"},
            {"track_id": 472, "conditions_id": 9, "conditions": "Daytime / Heavy Rain / Wet"},
        ]}],
    }
    data = _store(tmp_path, {"evt-mix": json.loads(json.dumps(original))})
    migrations.run_pending(data, log=lambda _m: None)
    assert _read(data, "evt-mix") != original          # it really did change

    log_file = _log_for(data, m0001.ID)
    migrations.revert(data, log_file, log=lambda _m: None)
    assert _read(data, "evt-mix") == original


def test_revert_restores_a_field_that_did_not_exist(tmp_path: Path) -> None:
    # A stage with no conditions_id gains one; reverting must remove the key
    # again rather than leave a null behind.
    original = {"id": "evt-bare", "location": "Poland",
                "stages": [{"name": "X", "conditions": "Overcast"}]}
    data = _store(tmp_path, {"evt-bare": json.loads(json.dumps(original))})
    migrations.run_pending(data, log=lambda _m: None)
    assert "conditions_id" in _read(data, "evt-bare")["stages"][0]

    log_file = _log_for(data, m0001.ID)
    migrations.revert(data, log_file, log=lambda _m: None)
    assert _read(data, "evt-bare") == original


def test_revert_leaves_unrelated_edits_alone(tmp_path: Path) -> None:
    """Reverting is value-by-value, not a file restore.

    Anything written after the migration -- a rename, a new entrant -- has to
    survive, which copying the directory backup wholesale would discard.
    """
    data = _store(tmp_path, {"evt-later": {
        "id": "evt-later", "location": "Germany", "name": "Before",
        "events": [{"location": "Germany",
                    "stages": [{"track_id": 489, "conditions_id": 38}]}],
    }})
    migrations.run_pending(data, log=lambda _m: None)

    doc = _read(data, "evt-later")
    doc["name"] = "Renamed after the migration"
    (data / "events" / "evt-later.json").write_text(json.dumps(doc), encoding="utf-8")

    log_file = _log_for(data, m0001.ID)
    migrations.revert(data, log_file, log=lambda _m: None)

    after = _read(data, "evt-later")
    assert after["name"] == "Renamed after the migration"
    assert after["events"][0]["stages"][0]["conditions_id"] == 38


def test_revert_survives_a_deleted_file(tmp_path: Path) -> None:
    data = _store(tmp_path, {"evt-gone": {
        "id": "evt-gone", "location": "Germany",
        "events": [{"location": "Germany",
                    "stages": [{"track_id": 489, "conditions_id": 38}]}],
    }})
    migrations.run_pending(data, log=lambda _m: None)
    (data / "events" / "evt-gone.json").unlink()

    log_file = _log_for(data, m0001.ID)
    assert migrations.revert(data, log_file, log=lambda _m: None) == 0


# ── the runner's DATA_DIR (regression: PR #53 deploy) ────────────────────────

def test_default_data_dir_comes_from_the_deploy_dotenv(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Nothing sources .env into the service environment, so a runner that only
    # read os.environ resolved web/data, which does not exist on a deploy --
    # `set -e` in run.sh then took the whole service down instead of migrating.
    env_file = tmp_path / ".env"
    env_file.write_text("# comment\nSECRET_KEY=x\nDATA_DIR=/srv/store\n",
                        encoding="utf-8")
    monkeypatch.setattr(mmain, "ENV_FILE", env_file)
    monkeypatch.delenv("DATA_DIR", raising=False)

    assert mmain._default_data_dir() == "/srv/store"


def test_real_env_wins_over_the_dotenv(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("DATA_DIR=/srv/store\n", encoding="utf-8")
    monkeypatch.setattr(mmain, "ENV_FILE", env_file)
    monkeypatch.setenv("DATA_DIR", "/explicit")

    assert mmain._default_data_dir() == "/explicit"


def test_missing_dotenv_falls_back_to_web_data(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mmain, "ENV_FILE", tmp_path / "absent.env")
    monkeypatch.delenv("DATA_DIR", raising=False)

    assert mmain._default_data_dir() == str(WEB_DIR / "data")


# ── 0002: keep the surface instead of resetting to the location default ──────

def test_0002_puts_back_the_wet_that_0001_flattened(tmp_path: Path) -> None:
    # Argentina cannot load 9 (Daytime / Heavy Rain / Wet), so 0001 reset the
    # stage to the location's dry first option. It ships three wet options, and
    # the stage was deliberately made wet.
    data = _store(tmp_path, {"evt-ar": {
        "id": "evt-ar", "location": "Argentina",
        "conditions": "Daytime / Heavy Rain / Wet",
        "events": [{"location": "Argentina", "stages": [
            {"track_id": 1, "conditions_id": 9, "conditions": "Daytime / Heavy Rain / Wet"},
        ]}],
    }})
    migrations.run_pending(data, log=lambda _m: None)

    doc = _read(data, "evt-ar")
    stage = doc["events"][0]["stages"][0]
    assert stage["conditions"] == "Daytime / Light Rain / Wet"
    assert stage["conditions_id"] == 21
    # The event-level mirror follows stage 1, as it did under 0001.
    assert doc["conditions"] == stage["conditions"]


def test_0002_leaves_a_stage_edited_since_alone(tmp_path: Path) -> None:
    """Someone re-picking conditions after 0001 outranks the repair."""
    data = _store(tmp_path, {"evt-ar": {
        "id": "evt-ar", "location": "Argentina",
        "events": [{"location": "Argentina", "stages": [
            {"track_id": 1, "conditions_id": 9, "conditions": "Daytime / Heavy Rain / Wet"},
            {"track_id": 2, "conditions_id": 9, "conditions": "Daytime / Heavy Rain / Wet"},
        ]}],
    }})
    # Apply 0001 alone, exactly as the runner does, so 0002 is still pending
    # when the edit lands.
    first = m0001.run(data)
    migrations.write_changes(data, m0001.ID, first)
    migrations.record(data, m0001.ID, first)
    assert m0002.ID not in migrations.applied_ids(data)

    doc = _read(data, "evt-ar")
    doc["events"][0]["stages"][0] = {"track_id": 1, "conditions_id": 3,
                                     "conditions": "Night / Clear / Dry"}
    (data / "events" / "evt-ar.json").write_text(json.dumps(doc), encoding="utf-8")

    migrations.run_pending(data, log=lambda _m: None)
    stages = _read(data, "evt-ar")["events"][0]["stages"]
    assert stages[0]["conditions_id"] == 3, "overwrote a choice made after 0001 ran"
    # ...while the stage nobody touched still gets repaired, so the skip above
    # is the check doing the work and not a migration that did nothing.
    assert stages[1]["conditions_id"] == 21


def test_0002_is_a_no_op_without_0001s_log(tmp_path: Path) -> None:
    # Nothing to re-resolve: the store no longer records what was asked for, so
    # guessing from the current value would be inventing intent.
    data = _store(tmp_path, {"evt-pl": {
        "id": "evt-pl", "location": "Poland",
        "events": [{"location": "Poland", "stages": [{"conditions_id": 1}]}],
    }})
    result = m0002.run(data)
    assert result.changed == 0
    assert result.changes == []
    assert _read(data, "evt-pl")["events"][0]["stages"][0]["conditions_id"] == 1


def test_0002_is_idempotent(tmp_path: Path) -> None:
    data = _store(tmp_path, {"evt-ar": {
        "id": "evt-ar", "location": "Argentina",
        "events": [{"location": "Argentina", "stages": [
            {"track_id": 1, "conditions_id": 9, "conditions": "Daytime / Heavy Rain / Wet"},
        ]}],
    }})
    migrations.run_pending(data, log=lambda _m: None)
    once = _read(data, "evt-ar")

    again = m0002.run(data)
    assert again.changed == 0
    assert _read(data, "evt-ar") == once


def test_0002_reverts_value_by_value(tmp_path: Path) -> None:
    data = _store(tmp_path, {"evt-ar": {
        "id": "evt-ar", "location": "Argentina",
        "events": [{"location": "Argentina", "stages": [
            {"track_id": 1, "conditions_id": 9, "conditions": "Daytime / Heavy Rain / Wet"},
        ]}],
    }})
    migrations.run_pending(data, log=lambda _m: None)
    migrations.revert(data, _log_for(data, m0002.ID), log=lambda _m: None)

    # Back to what 0001 left, not back to the unloadable original.
    stage = _read(data, "evt-ar")["events"][0]["stages"][0]
    assert stage["conditions_id"] == 1


# ── 0004: every club gets an admins list ─────────────────────────────────────

def _club_store(tmp_path: Path, clubs: dict[str, dict]) -> Path:
    data = _store(tmp_path, {})
    (data / "clubs").mkdir()
    for name, doc in clubs.items():
        (data / "clubs" / f"{name}.json").write_text(json.dumps(doc), encoding="utf-8")
    return data


def _read_club(data_dir: Path, name: str) -> dict:
    return json.loads((data_dir / "clubs" / f"{name}.json").read_text(encoding="utf-8"))


def test_0004_backfills_admins_and_keeps_existing(tmp_path: Path) -> None:
    data = _club_store(tmp_path, {
        "old": {"id": "old", "created_by": "a", "members": ["a", "b"]},
        "new": {"id": "new", "created_by": "a", "members": ["a", "b"], "admins": ["b"]},
    })
    migrations.run_pending(data, log=lambda _m: None)
    assert _read_club(data, "old")["admins"] == []
    assert _read_club(data, "new")["admins"] == ["b"]
    assert m0004.ID in migrations.applied_ids(data)


def test_0004_is_idempotent_and_dry_run_safe(tmp_path: Path) -> None:
    data = _club_store(tmp_path, {"old": {"id": "old", "created_by": "a", "members": ["a"]}})
    dry = m0004.run(data, dry_run=True)
    assert dry.changed == 1
    assert "admins" not in _read_club(data, "old")
    assert not (data / migrations.BACKUP_DIR).exists()

    migrations.run_pending(data, log=lambda _m: None)
    once = _read_club(data, "old")
    again = m0004.run(data)
    assert again.changed == 0 and again.changes == []
    assert _read_club(data, "old") == once


def test_0004_revert_removes_the_field(tmp_path: Path) -> None:
    data = _club_store(tmp_path, {"old": {"id": "old", "created_by": "a", "members": ["a"]}})
    migrations.run_pending(data, log=lambda _m: None)
    migrations.revert(data, _log_for(data, m0004.ID), log=lambda _m: None)
    assert "admins" not in _read_club(data, "old")
