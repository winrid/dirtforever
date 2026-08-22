"""Migration 0003: rallycross stages get the circuit's captured TrackModelId."""
from __future__ import annotations

import json
import sys
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parents[1] / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

import migrations  # noqa: E402
from migrations import m0003_rallycross_track_ids as m0003  # noqa: E402

from dr2server.game_data import Track  # noqa: E402

LYDDEN = int(Track.LYDDEN_HILL)
HOLJES = int(Track.HOLJES)


def _store(tmp_path: Path, events: dict[str, dict]) -> Path:
    (tmp_path / "events").mkdir(parents=True)
    (tmp_path / "championship_drafts").mkdir(parents=True)
    for name, doc in events.items():
        (tmp_path / "events" / f"{name}.json").write_text(json.dumps(doc), encoding="utf-8")
    return tmp_path


def _read(data_dir: Path, name: str) -> dict:
    return json.loads((data_dir / "events" / f"{name}.json").read_text(encoding="utf-8"))


def test_stale_rallycross_ids_are_rewritten(tmp_path: Path) -> None:
    # 131 is what PR #19's enum stored for Lydden Hill; 141 for Holjes.
    data = _store(tmp_path, {"evt-rx": {
        "id": "evt-rx", "location": "Lydden Hill",
        "events": [
            {"location": "Lydden Hill", "stages": [{"track_id": 131, "conditions_id": 1},
                                                    {"track_id": 131, "conditions_id": 1}]},
            {"location": "Höljes", "stages": [{"track_id": 141, "conditions_id": 1}]},
        ],
    }})
    result = m0003.run(data)
    assert result.changed == 1
    doc = _read(data, "evt-rx")
    assert [s["track_id"] for s in doc["events"][0]["stages"]] == [LYDDEN, LYDDEN]
    assert doc["events"][1]["stages"][0]["track_id"] == HOLJES
    assert len(result.changes) == 3
    assert result.changes[0]["before"] == {"track_id": 131}
    assert result.changes[0]["after"] == {"track_id": LYDDEN}


def test_missing_track_id_on_rallycross_stage_is_filled(tmp_path: Path) -> None:
    data = _store(tmp_path, {"evt-rx": {
        "id": "evt-rx", "location": "Lydden Hill",
        "stages": [{"name": "Lydden Hill", "conditions_id": 1}],
    }})
    m0003.run(data)
    assert _read(data, "evt-rx")["stages"][0]["track_id"] == LYDDEN


def test_rally_stages_and_correct_rallycross_stages_are_untouched(tmp_path: Path) -> None:
    data = _store(tmp_path, {
        "evt-rally": {"id": "evt-rally", "location": "Germany",
                      "events": [{"location": "Germany",
                                  "stages": [{"track_id": 131, "conditions_id": 38}]}]},
        "evt-rx": {"id": "evt-rx", "location": "Lydden Hill",
                   "events": [{"location": "Lydden Hill",
                               "stages": [{"track_id": LYDDEN, "conditions_id": 1}]}]},
    })
    result = m0003.run(data)
    assert result.changed == 0 and result.changes == []
    # A rally stage keeps whatever it had, even an id that looks like the old RX ones.
    assert _read(data, "evt-rally")["events"][0]["stages"][0]["track_id"] == 131


def test_idempotent(tmp_path: Path) -> None:
    data = _store(tmp_path, {"evt-rx": {
        "id": "evt-rx", "location": "Lydden Hill",
        "events": [{"location": "Lydden Hill", "stages": [{"track_id": 131}]}],
    }})
    assert m0003.run(data).changed == 1
    assert m0003.run(data).changed == 0


def test_registered_with_the_runner(tmp_path: Path) -> None:
    data = _store(tmp_path, {})
    migrations.run_pending(data, log=lambda _m: None)
    assert m0003.ID in migrations.applied_ids(data)
