"""Garage engine-tuning / livery selections must persist.

Fitting engine tuning or a livery in the garage sends Repairs.FitTuning /
Repairs.SetLivery.  Those used to be answered with a bare success and nothing
was stored, so RaceNetInventory.GetInventory always reported TuningId/LiveryId
0 and the selection was lost on the next inventory sync / restart.

Now the selection is persisted per VehicleInstId on the web user record and
read back into GetInventory.  These tests cover both the dispatcher wiring
(with a stub api_client) and the full chain through the real web app.
"""
from __future__ import annotations

import http.client
import json
from unittest.mock import MagicMock

import pytest

from dr2server.dispatcher import RpcDispatcher
from dr2server.egonet import UInt32, decode_stream, encode_stream

from .conftest import GAME_TOKEN, GAME_USER

RPC_PATH = "/RP17/1.18.0/STEAM/"


# --------------------------------------------------------------------------
# Dispatcher wiring (stub api_client, no web)
# --------------------------------------------------------------------------

class _GarageStub:
    """api_client double that records set_garage() and echoes the garage back
    through get_profile(), mimicking the real round-trip."""

    def __init__(self) -> None:
        self.garage: dict = {}

    def set_garage(self, inst, tuning_id=None, livery_id=None) -> bool:
        entry = self.garage.setdefault(str(inst), {})
        if tuning_id is not None:
            entry["tuning_id"] = int(tuning_id)
        if livery_id is not None:
            entry["livery_id"] = int(livery_id)
        return True

    def get_profile(self):
        return {
            "ok": True, "soft_currency": 500000, "hard_currency": 0,
            "garage_slots": 8, "garage": self.garage,
        }


def _disp() -> RpcDispatcher:
    return RpcDispatcher(account_store=MagicMock(), api_client=_GarageStub())


def _vehicle(disp: RpcDispatcher, inst_id: int) -> dict:
    inv = disp._inventory({})
    for v in inv["Inventory"]["Vehicles"]:
        if v["Id"].value == inst_id:
            return v
    raise AssertionError(f"no vehicle with Id {inst_id}")


def test_fit_tuning_persists_and_reads_back() -> None:
    d = _disp()
    resp = d._repairs_fit_tuning({"VehicleInstId": UInt32(55), "EngineTuningId": UInt32(282)})
    assert resp == {"ok": True, "Result": 0, "Cost": 0}
    assert d.api_client.garage["55"] == {"tuning_id": 282}
    assert _vehicle(d, 55)["TuningId"].value == 282


def test_set_livery_persists_and_reads_back() -> None:
    d = _disp()
    resp = d._repairs_set_livery({"VehicleInstId": UInt32(55), "LiveryId": UInt32(3413)})
    assert resp == {"ok": True, "Result": 0}
    assert _vehicle(d, 55)["LiveryId"].value == 3413


def test_livery_and_tuning_coexist_on_same_vehicle() -> None:
    d = _disp()
    d._repairs_fit_tuning({"VehicleInstId": UInt32(55), "EngineTuningId": UInt32(282)})
    d._repairs_set_livery({"VehicleInstId": UInt32(55), "LiveryId": UInt32(3413)})
    # Fitting a livery must not clear the previously-fitted tuning.
    assert d.api_client.garage["55"] == {"tuning_id": 282, "livery_id": 3413}
    v = _vehicle(d, 55)
    assert (v["TuningId"].value, v["LiveryId"].value) == (282, 3413)


def test_untouched_vehicle_stays_stock() -> None:
    d = _disp()
    d._repairs_fit_tuning({"VehicleInstId": UInt32(55), "EngineTuningId": UInt32(282)})
    other = _vehicle(d, 10)
    assert (other["TuningId"].value, other["LiveryId"].value) == (0, 0)


def test_transient_instance_id_not_persisted() -> None:
    # In-event/current-vehicle markers (<= 0, e.g. -2) must not be stored.
    d = _disp()
    d._repairs_fit_tuning({"VehicleInstId": -2, "EngineTuningId": UInt32(99)})
    d._repairs_set_livery({"VehicleInstId": 0, "LiveryId": UInt32(99)})
    assert d.api_client.garage == {}


def test_no_api_client_still_succeeds() -> None:
    # Local-dev mode (no web backend): still answer success, just don't persist.
    d = RpcDispatcher(account_store=MagicMock(), api_client=None)
    assert d._repairs_fit_tuning({"VehicleInstId": UInt32(55), "EngineTuningId": UInt32(282)}) == {
        "ok": True, "Result": 0, "Cost": 0,
    }
    assert d._repairs_set_livery({"VehicleInstId": UInt32(55), "LiveryId": UInt32(1)}) == {
        "ok": True, "Result": 0,
    }


# --------------------------------------------------------------------------
# Full chain: egonet -> dispatcher -> web endpoint -> on-disk -> GetInventory
# --------------------------------------------------------------------------

def _egonet(host: str, port: int, method: str, params: dict) -> dict:
    body = encode_stream(params)
    conn = http.client.HTTPConnection(host, port, timeout=10)
    try:
        conn.request("POST", RPC_PATH, body=body, headers={
            "Content-Type": "application/egonet-stream",
            "X-EgoNet-Function": method,
            "Content-Length": str(len(body)),
        })
        resp = conn.getresponse()
        raw = resp.read()
        return decode_stream(raw)
    finally:
        conn.close()


def test_full_chain_tuning_and_livery_persist(dr2_server) -> None:
    host, port, _app, web_app = dr2_server

    _egonet(host, port, "Repairs.FitTuning",
            {"VehicleInstId": UInt32(55), "EngineTuningId": UInt32(282)})
    _egonet(host, port, "Repairs.SetLivery",
            {"VehicleInstId": UInt32(55), "LiveryId": UInt32(3413)})

    # Persisted on the web user record.
    user = json.loads(
        (web_app.data_dir / "users" / f"{GAME_USER}.json").read_text(encoding="utf-8")
    )
    assert user["garage"]["55"] == {"tuning_id": 282, "livery_id": 3413}

    # And reflected back through GetInventory.
    inv = _egonet(host, port, "RaceNetInventory.GetInventory", {})
    v55 = next(v for v in inv["Inventory"]["Vehicles"] if v["Id"].value == 55)
    assert v55["TuningId"].value == 282
    assert v55["LiveryId"].value == 3413


def test_web_garage_endpoint_merges_and_ignores_transient(web_app) -> None:
    web_app.reset()
    web_app.seed_user(GAME_USER, game_token=GAME_TOKEN)

    def call(method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", web_app.port, timeout=10)
        headers = {"Authorization": f"Bearer {GAME_TOKEN}"}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        try:
            conn.request(method, path, body=data, headers=headers)
            resp = conn.getresponse()
            return resp.status, json.loads(resp.read())
        finally:
            conn.close()

    status, body = call("POST", "/api/game/garage", {"vehicle_inst_id": 55, "tuning_id": 282})
    assert status == 200 and body["stored"] is True
    # A later livery-only update must not wipe the tuning.
    _, body = call("POST", "/api/game/garage", {"vehicle_inst_id": 55, "livery_id": 3413})
    assert body["garage"]["55"] == {"tuning_id": 282, "livery_id": 3413}
    # Profile surfaces it for GetInventory.
    _, prof = call("GET", "/api/game/profile", None)
    assert prof["garage"]["55"] == {"tuning_id": 282, "livery_id": 3413}
    # Transient instance ids are acknowledged but not stored.
    _, body = call("POST", "/api/game/garage", {"vehicle_inst_id": -2, "tuning_id": 99})
    assert body["stored"] is False
    _, prof = call("GET", "/api/game/profile", None)
    assert "-2" not in prof["garage"]
