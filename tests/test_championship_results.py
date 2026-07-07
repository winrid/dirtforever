"""Stage-3: multi-event championship results must not collide.

Before event_index threading, stage 0 of event 1 would overwrite stage 0 of
event 0 (both stored at flat index 0).  The (event_index, stage_index) -> flat
championship ordinal mapping keeps them in distinct slots, while event_index 0
stays byte-identical to the single-event path.
"""
from __future__ import annotations

import importlib
import os
import sys
import tempfile
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parents[1] / "web"


def _load():
    os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
    os.environ.setdefault("SECRET_KEY", "test-secret")
    os.environ.setdefault("WTF_CSRF_ENABLED", "0")
    while str(WEB_DIR) in sys.path:
        sys.path.remove(str(WEB_DIR))
    sys.path.insert(0, str(WEB_DIR))
    mod = sys.modules.get("server")
    if mod is None or not hasattr(mod, "_global_stage_index"):
        sys.modules.pop("server", None)
        mod = importlib.import_module("server")
    return mod


def _seed_champ_event(server, event_id, club_id, layout):
    events = []
    for ei, n in enumerate(layout):
        events.append({
            "location": "Finland", "car_class": "Group A", "surface": "Gravel",
            "duration": {"days": 1, "hours": 0, "mins": 0},
            "stages": [{"name": f"S{ei}-{si}", "track_id": None, "distance_km": 5.0,
                        "conditions_id": 1, "conditions": "x",
                        "surface_deg": "Medium", "service_area": "Medium"}
                       for si in range(n)],
        })
    ev = {
        "id": event_id, "schema_version": 2, "name": "Champ", "type": "weekly",
        "club_id": club_id, "start_time": "2026-01-01T00:00:00",
        "end_time": "2027-01-01T00:00:00", "active": True, "featured": False,
        "settings": {}, "location": "Finland", "car_class": "Group A",
        "surface": "Gravel", "conditions": "x",
        "stages": events[0]["stages"], "events": events,
    }
    server.save_event(ev)
    return ev


def test_global_stage_index_helper() -> None:
    server = _load()
    ev = {"events": [{"stages": [0, 0, 0]}, {"stages": [0, 0]}, {"stages": [0]}]}
    assert server._global_stage_index(ev, 0, 0) == 0
    assert server._global_stage_index(ev, 0, 2) == 2
    assert server._global_stage_index(ev, 1, 0) == 3
    assert server._global_stage_index(ev, 1, 1) == 4
    assert server._global_stage_index(ev, 2, 0) == 5
    # Legacy single event (no events[]) — pure identity.
    assert server._global_stage_index({"stages": [0, 0, 0, 0]}, 0, 2) == 2


def test_multi_event_results_dont_collide() -> None:
    server = _load()
    server.app.config["WTF_CSRF_ENABLED"] = False
    token = "df_" + "a" * 32
    uname = "rescheck"
    u = server.get_user(uname) or server.create_user(uname, "rc@e.com", "pw", email_verified=True)
    u["game_token"] = token
    u["clubs"] = ["resclub"]
    server.save_user(u)
    server.save_club({"id": "resclub", "name": "R", "created_by": uname,
                      "members": [uname], "created_at": "2026-01-01T00:00:00"})
    eid = "evt-rescheck1"
    _seed_champ_event(server, eid, "resclub", [2, 2])

    c = server.app.test_client()
    hdr = {"Authorization": f"Bearer {token}"}

    def complete(ei, si, t):
        return c.post("/api/game/stage-complete", json={
            "event_id": eid, "event_index": ei, "stage_index": si,
            "time_ms": t, "race_status": 0,
        }, headers=hdr)

    try:
        for (ei, si, t) in [(0, 0, 1000), (0, 1, 2000), (1, 0, 3000), (1, 1, 4000)]:
            r = complete(ei, si, t)
            assert r.status_code == 200, r.data

        res = server.get_results(eid)
        entry = next(e for e in res["entries"] if e["username"] == uname)
        stages = entry["stages"]
        # 2 events x 2 stages -> 4 distinct flat slots, none overwritten.
        assert len(stages) == 4
        assert [s["time_ms"] for s in stages] == [1000, 2000, 3000, 4000]
        assert entry["total_time_ms"] == 10000
        # Routing field must not leak into the stored stage entry.
        assert "event_index" not in stages[2]
    finally:
        for d, name in ((server.EVENTS_DIR, eid), (server.RESULTS_DIR, eid)):
            p = os.path.join(d, name + ".json")
            if os.path.exists(p):
                os.remove(p)
