"""RaceNet capture sessions: proxy flags, folder naming, sanitized export."""
from __future__ import annotations

import json
import time
import zipfile
from pathlib import Path

from dr2server import capture_export as ce
from dr2server.httpd import ProxyAll, build_arg_parser

SESSION = "FDF5FF3F368E4879BE3650110AC9CA48"


def _capture(method: str, body=None, response_body=None) -> dict:
    return {
        "method": "POST",
        "path": "/RP17/1.18.0/STEAM/",
        "headers": {"X-EgoNet-Function": method, "X-EgoNet-SessionID": SESSION,
                    "Content-Type": "application/egonet-stream"},
        "body_text": "vdic...",
        "body_base64": "dmRpYw==",
        "decoded_body": body if body is not None else {"VehicleInstId": 64},
        "response": {
            "proxy": True,
            "upstream_status": 200,
            "headers": {"X-EgoNet-SessionID": SESSION, "X-EgoNet-Result": "0"},
            "body_raw_base64": "dmRpYw==",
            "body_decoded": response_body if response_body is not None else {"Progress": {"State": 1}},
        },
    }


def test_sanitize_scrubs_session_ids_and_keeps_the_game_data():
    original = _capture("RaceNetCareerLadder.RallycrossChampionshipBegin")
    frozen = json.dumps(original, sort_keys=True)
    out = ce.sanitize_capture(original)
    assert json.dumps(original, sort_keys=True) == frozen  # input untouched
    assert out["headers"]["X-EgoNet-SessionID"] == ce.SESSION_PLACEHOLDER
    assert out["response"]["headers"]["X-EgoNet-SessionID"] == ce.SESSION_PLACEHOLDER
    assert out["response"]["headers"]["X-EgoNet-Result"] == "0"
    assert out["decoded_body"] == {"VehicleInstId": 64}
    assert out["response"]["body_decoded"] == {"Progress": {"State": 1}}
    assert out["body_base64"] == "dmRpYw=="


def test_sanitize_drops_login_and_account_bodies_but_not_racenet_game_calls():
    login = _capture("Login.Login", body={"SteamTicket": {"blob_base64": "AAAA", "size": 3}},
                     response_body={"UserName": "someone"})
    out = ce.sanitize_capture(login)
    for key in ("body_text", "body_base64", "decoded_body"):
        assert out[key] == ce.REMOVED
    for key in ("body_raw_base64", "body_decoded"):
        assert out["response"][key] == ce.REMOVED
    assert out["response"]["headers"]["X-EgoNet-SessionID"] == ce.SESSION_PLACEHOLDER
    assert out["response"]["upstream_status"] == 200

    assert ce.sanitize_capture(_capture("RaceNet.SignIn"))["decoded_body"] == ce.REMOVED
    # A ticket anywhere makes the call private whatever its name.
    odd = _capture("Something.Else", body={"SteamTicket": {"blob_base64": "AAAA", "size": 3}})
    assert ce.sanitize_capture(odd)["decoded_body"] == ce.REMOVED
    # The trailing dot matters: the career and club calls are the point.
    keep = ce.sanitize_capture(_capture("RaceNetChallenges.StageComplete"))
    assert keep["decoded_body"] == {"VehicleInstId": 64}


def test_export_zip_packs_sanitized_json_only(tmp_path: Path):
    src = tmp_path / "racenet-20261030-101500"
    src.mkdir()
    (src / "1-login.json").write_text(json.dumps(
        _capture("Login.Login", body={"SteamTicket": {"blob_base64": "AAAA", "size": 3}})))
    (src / "2-begin.json").write_text(json.dumps(_capture("RaceNetCareerLadder.RallyChampionshipBegin")))
    (src / "3-broken.json").write_text("{not json")
    (src / "notes.txt").write_text("ignored")
    out_zip = tmp_path / "out" / "racenet-20261030-101500.zip"

    assert ce.export_capture_zip(src, out_zip) == 3

    with zipfile.ZipFile(out_zip) as zf:
        names = sorted(zf.namelist())
        assert names == ["racenet-20261030-101500/1-login.json",
                         "racenet-20261030-101500/2-begin.json",
                         "racenet-20261030-101500/3-broken.json"]
        login = json.loads(zf.read(names[0]))
        assert login["decoded_body"] == ce.REMOVED
        assert SESSION not in zf.read(names[0]).decode()
        begin = json.loads(zf.read(names[1]))
        assert begin["decoded_body"] == {"VehicleInstId": 64}
        assert SESSION not in zf.read(names[1]).decode()
        broken = json.loads(zf.read(names[2]))
        assert broken["unreadable"] == "3-broken.json"


def test_capture_dir_naming_and_listing(tmp_path: Path):
    now = 1_793_356_800.0
    expected = "racenet-" + time.strftime("%Y%m%d-%H%M%S", time.localtime(now))
    assert ce.new_capture_dir(tmp_path, now) == tmp_path / expected

    assert ce.list_capture_dirs(tmp_path / "missing") == []
    for name in ("racenet-20261030-080000", "racenet-20261030-093000", "other-dir"):
        (tmp_path / name).mkdir()
    (tmp_path / "racenet-20261030-120000.json").write_text("{}")  # a file, not a session
    assert [p.name for p in ce.list_capture_dirs(tmp_path)] == [
        "racenet-20261030-093000", "racenet-20261030-080000"]


def test_racenet_server_args_turn_on_proxy_all():
    args = build_arg_parser().parse_args(ce.racenet_server_args())
    assert args.upstream_ip == ce.RACENET_UPSTREAM_IP == "159.153.126.42"
    assert args.proxy_all is True
    everything = ProxyAll()
    assert "Login.Login" in everything
    assert "RaceNetCareerLadder.GetRallyChampionship" in everything
    assert isinstance(everything, set)
