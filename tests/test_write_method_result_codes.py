"""Write/lifecycle EgoNet methods must answer with a SUCCESS result code.

The client treats X-EgoNet-Result=1 as a fatal "server unavailable" for the
Service-Area / Vehicle-Preparation write actions and for the end-of-race
persistence calls, surfacing in-game as the "CONNECTION FAILED" screen.

Two independent guarantees are pinned here:

  1. The specific methods behind the reported rallycross failures — picking a
     non-stock livery (Repairs.SetLivery), applying an engine upgrade
     (Repairs.FitTuning), and the post-race calls — are registered and return
     result 0.

  2. The root cause: ANY unhandled/stubbed method now returns result 0, not 1
     (the httpd stub path used to drop the "ok" flag and emit 1).

Deliberately-failing reads (Status.GetNextStatusEvent -> 1) must keep working.
"""
from __future__ import annotations

import http.client
from pathlib import Path

import pytest

from dr2server.egonet import decode_stream, encode_stream
from dr2server.httpd import App, create_server

RPC_PATH = "/RP17/1.18.0/STEAM/"

# The methods that were unhandled before the fix and caused the connection-
# failed screen when the player performed the corresponding action.
WRITE_METHODS = [
    "Repairs.SetLivery",
    "Repairs.FitTuning",
    "Repairs.PurchaseTuning",
    "Repairs.PurchaseUpgrade",
    "Repairs.PerformRepairs",
    "Repairs.ApplyDamage",
    "RaceNetInventory.Purchase",
    "RaceNetInventory.Sell",
    "Clubs.UpdateVehicleDamage",
    "RaceNetChallenges.StartChallenge",
    "RaceNetChallenges.ResumeChallenge",
    "RaceNetChallenges.AbortChallenge",
    "RaceNetCareerLadder.RallyStageBegin",
    "RaceNetCareerLadder.RallyStageComplete",
    "RaceNetCareerLadder.RallycrossStageBegin",
    "RaceNetCareerLadder.RallycrossStageComplete",
]


@pytest.fixture()
def server(tmp_path: Path):
    # No api_url -> no api_client; these handlers don't need one.
    app = App(data_root=tmp_path / "data", capture_root=tmp_path / "captures")
    srv = create_server("127.0.0.1", 0, app)
    import threading

    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield srv.server_address  # (host, port)
    finally:
        srv.shutdown()
        thread.join(timeout=5)


def _call(addr, method: str, params: dict | None = None):
    """POST an egonet request; return (X-EgoNet-Result header, decoded body)."""
    host, port = addr
    body = encode_stream(params or {})
    conn = http.client.HTTPConnection(host, port, timeout=10)
    try:
        conn.request(
            "POST",
            RPC_PATH,
            body=body,
            headers={
                "Content-Type": "application/egonet-stream",
                "X-EgoNet-Function": method,
                "Content-Length": str(len(body)),
            },
        )
        resp = conn.getresponse()
        raw = resp.read()
        code = {k.lower(): v for k, v in resp.getheaders()}.get("x-egonet-result")
        try:
            decoded = decode_stream(raw)
        except Exception:
            decoded = {}
        return code, decoded
    finally:
        conn.close()


@pytest.mark.parametrize("method", WRITE_METHODS)
def test_write_methods_return_success(server, method):
    code, _ = _call(server, method)
    assert code == "0", f"{method} must return result 0, not a failure"


# The client validates the RESPONSE BODY of these (not just the result code):
# it wants a {"Result": 0} envelope, not the {"Accepted": true} ack.  Shapes
# ground-truthed against real upstream.
def test_setlivery_body_has_result(server):
    code, body = _call(server, "Repairs.SetLivery",
                       {"VehicleInstId": 2, "LiveryId": 3413})
    assert code == "0"
    assert body.get("Result") == 0
    assert "Accepted" not in body


def test_fittuning_body_has_result_and_cost(server):
    code, body = _call(server, "Repairs.FitTuning",
                       {"VehicleInstId": 2, "EngineTuningId": 164})
    assert code == "0"
    assert body.get("Result") == 0
    assert "Cost" in body


def test_performrepairs_body_has_result_and_damage(server):
    code, body = _call(server, "Repairs.PerformRepairs", {"Engine": 2})
    assert code == "0"
    assert body.get("Result") == 0
    # Client applies the returned (zeroed) damage to the repaired car.
    assert "Damage" in body and "CompDamage" in body


def test_unknown_method_returns_success(server):
    # The root-cause regression: a method with no handler at all must still
    # answer with result 0 (the stub path used to emit 1).
    code, _ = _call(server, "Some.BrandNewUnhandledMethod")
    assert code == "0"


def test_status_event_still_reports_no_event(server):
    # Guard against over-correcting: this read intentionally answers 1.
    code, _ = _call(server, "Status.GetNextStatusEvent")
    assert code == "1"
