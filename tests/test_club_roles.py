"""Club roles: owner / admin / member.

Admins run the club (edit, review requests, build championships); only the
owner can promote or demote them. Championship drafts are shared per
club, so a second admin can open a draft the first one generated.
"""
from __future__ import annotations

import importlib
import os
import sys
import tempfile
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parents[1] / "web"


def _load():
    if "server" not in sys.modules:
        # The migration runner's tests read the deploy .env into os.environ,
        # so a plain setdefault could point a fresh import at the live store.
        os.environ["DATA_DIR"] = tempfile.mkdtemp()
    os.environ.setdefault("SECRET_KEY", "test-secret")
    os.environ.setdefault("WTF_CSRF_ENABLED", "0")
    while str(WEB_DIR) in sys.path:
        sys.path.remove(str(WEB_DIR))
    sys.path.insert(0, str(WEB_DIR))
    mod = sys.modules.get("server")
    if mod is None or not hasattr(mod, "user_is_admin"):
        sys.modules.pop("server", None)
        mod = importlib.import_module("server")
    mod.app.config["WTF_CSRF_ENABLED"] = False
    mod.app.config["TESTING"] = True
    return mod


def _user(server, uname):
    if not server.get_user(uname):
        server.create_user(uname, f"{uname}@example.com", "pw", email_verified=True)


def _client(server, uname):
    client = server.app.test_client()
    with client.session_transaction() as sess:
        sess["username"] = uname
    return client


def _club(server, club_id, owner, members=(), admins=(), **extra):
    for u in [owner, *members]:
        _user(server, u)
    club = {
        "id": club_id, "name": club_id, "created_by": owner,
        "members": [owner, *members], "admins": list(admins),
        "created_at": "2026-01-01T00:00:00", **extra,
    }
    server.save_club(club)
    return club


def test_role_helpers() -> None:
    server = _load()
    club = {"created_by": "own", "members": ["own", "adm", "mem"], "admins": ["adm"]}
    assert server.club_role(club, "own") == "owner"
    assert server.club_role(club, "adm") == "admin"
    assert server.club_role(club, "mem") == "member"
    assert server.club_role(club, "nobody") is None
    assert server.user_is_admin(club, "own") and server.user_is_admin(club, "adm")
    assert not server.user_is_admin(club, "mem") and not server.user_is_admin(club, None)
    # Legacy clubs have no admins key at all.
    assert not server.user_is_admin({"created_by": "own", "members": ["x"]}, "x")


def test_member_cannot_open_builder_but_admin_can() -> None:
    server = _load()
    _club(server, "roleclub1", "r1own", members=["r1adm", "r1mem"], admins=["r1adm"])
    assert _client(server, "r1mem").get("/clubs/roleclub1/championship/new").status_code == 403
    assert _client(server, "r1adm").get("/clubs/roleclub1/championship/new").status_code == 200
    assert _client(server, "r1own").get("/clubs/roleclub1/championship/new").status_code == 200


def test_drafts_are_shared_between_admins() -> None:
    server = _load()
    _club(server, "roleclub2", "r2own", members=["r2adm", "r2mem"], admins=["r2adm"])
    r = _client(server, "r2adm").post("/clubs/roleclub2/championship/new",
                                      data={"num_events": "1", "num_stages": "1"})
    assert r.status_code == 302
    draft_url = r.headers["Location"]
    assert _client(server, "r2own").get(draft_url).status_code == 200
    assert _client(server, "r2mem").get(draft_url).status_code == 403
    # A draft from another club is still invisible even to an admin.
    _club(server, "roleclub2b", "r2own")
    other = draft_url.replace("roleclub2", "roleclub2b")
    assert _client(server, "r2own").get(other).status_code == 404


def test_only_owner_can_promote() -> None:
    server = _load()
    _club(server, "roleclub3", "r3own", members=["r3adm", "r3mem", "r3mem2"], admins=["r3adm"])
    for who in ("r3mem", "r3adm"):
        assert _client(server, who).post("/clubs/roleclub3/admins/r3mem2/promote").status_code == 403
    assert server.get_club("roleclub3")["admins"] == ["r3adm"]

    r = _client(server, "r3own").post("/clubs/roleclub3/admins/r3mem/promote")
    assert r.status_code == 302
    assert server.get_club("roleclub3")["admins"] == ["r3adm", "r3mem"]
    notifs = server.get_user("r3mem").get("notifications") or []
    assert any(n["type"] == "club_admin_granted" and n["club_id"] == "roleclub3" for n in notifs)

    # Promoting the owner, an existing admin, or a non-member changes nothing.
    own = _client(server, "r3own")
    for target in ("r3own", "r3adm", "stranger"):
        assert own.post(f"/clubs/roleclub3/admins/{target}/promote").status_code == 302
    assert server.get_club("roleclub3")["admins"] == ["r3adm", "r3mem"]


def test_only_owner_can_demote() -> None:
    server = _load()
    _club(server, "roleclub4", "r4own", members=["r4adm", "r4adm2"], admins=["r4adm", "r4adm2"])
    assert _client(server, "r4adm").post("/clubs/roleclub4/admins/r4adm2/demote").status_code == 403
    assert server.get_club("roleclub4")["admins"] == ["r4adm", "r4adm2"]

    assert _client(server, "r4own").post("/clubs/roleclub4/admins/r4adm2/demote").status_code == 302
    assert server.get_club("roleclub4")["admins"] == ["r4adm"]
    notifs = server.get_user("r4adm2").get("notifications") or []
    assert any(n["type"] == "club_admin_revoked" for n in notifs)
    # Demoted admin loses the builder.
    assert _client(server, "r4adm2").get("/clubs/roleclub4/championship/new").status_code == 403


def test_admin_manages_club_and_requests() -> None:
    server = _load()
    _club(server, "roleclub5", "r5own", members=["r5adm"], admins=["r5adm"],
          join_policy="approval", pending_requests=[])
    _user(server, "r5req")
    assert _client(server, "r5req").post("/clubs/roleclub5/request").status_code == 302
    # Both the owner and the admin were told about the request.
    for reviewer in ("r5own", "r5adm"):
        notifs = server.get_user(reviewer).get("notifications") or []
        assert any(n["type"] == "club_join_request" and n["from_username"] == "r5req"
                   for n in notifs), reviewer

    adm = _client(server, "r5adm")
    assert adm.post("/clubs/roleclub5/requests/r5req/approve").status_code == 302
    club = server.get_club("roleclub5")
    assert "r5req" in club["members"]
    assert club["pending_requests"] == []
    for reviewer in ("r5own", "r5adm"):
        notifs = server.get_user(reviewer).get("notifications") or []
        assert not any(n["type"] == "club_join_request" and n["from_username"] == "r5req"
                       for n in notifs), reviewer

    assert adm.post("/clubs/roleclub5/edit", data={
        "name": "Renamed", "visibility": "private", "join_policy": "open",
    }).status_code == 302
    club = server.get_club("roleclub5")
    assert club["name"] == "Renamed"
    assert club["join_policy"] == "open"
    assert club.get("visibility", "public") == "public", "admin changed visibility"
    assert b'name="visibility"' not in adm.get("/clubs/roleclub5").data

    assert _client(server, "r5own").post("/clubs/roleclub5/edit", data={
        "name": "Renamed", "visibility": "private",
    }).status_code == 302
    assert server.get_club("roleclub5")["visibility"] == "private"
    assert _client(server, "r5req").post("/clubs/roleclub5/edit",
                                         data={"name": "Nope"}).status_code == 403

    page = adm.get("/clubs/roleclub5")
    assert page.status_code == 200
    assert b"Create Championship" in page.data
    assert b"Make admin" not in page.data
    assert b"Remove admin" not in page.data
    owner_page = _client(server, "r5own").get("/clubs/roleclub5")
    assert b"Make admin" in owner_page.data
    assert b"Remove admin" in owner_page.data


def test_leaving_drops_admin_role() -> None:
    server = _load()
    _club(server, "roleclub6", "r6own", members=["r6adm"], admins=["r6adm"])
    assert _client(server, "r6adm").post("/clubs/roleclub6/leave").status_code == 302
    club = server.get_club("roleclub6")
    assert "r6adm" not in club["members"]
    assert club["admins"] == []
