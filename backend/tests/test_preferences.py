from uuid import UUID

import pytest
from event_auth.adapters.database.models import Member
from test_m2 import add_member, event_input, import_data, system  # noqa: F401

pytestmark = pytest.mark.postgres


def member(client, code="PRE1", preference="Veg"):
    response = client.post(
        "/api/members",
        json={"name": "Test Preference", "member_code": code, "default_option": preference},
    )
    assert response.status_code == 200, response.text
    return response.json()


def event(client):
    data = event_input()
    for slot in data["slots"]:
        slot["options"] = [{"code": "O1", "label": "Veg"}, {"code": "O2", "label": "Jain"}]
    data["counters"][0]["serves"].append("S2/O2")
    response = client.post("/api/events", json=data)
    assert response.status_code == 200, response.text
    return response.json()


def test_defaults_snapshots_overrides_and_late_members(system):  # noqa: F811
    client, factory, vault, _ = system
    first = member(client)
    second = member(client, "PRE2", "Jain")
    one, two = event(client), event(client)
    assert len(one["registrations"]) == 2
    assert all(not r["needs_choice"] for r in one["registrations"])
    slot = one["slots"][0]
    override = slot["options"][1]["id"]
    assert (
        client.post(
            f"/api/events/{one['id']}/choices",
            json={"member_id": first["id"], "choices": {slot["id"]: override}},
        ).status_code
        == 200
    )
    before = client.get(f"/api/events/{one['id']}").json()
    assert client.post(f"/api/events/{one['id']}/defaults").json() == before
    assert client.get(f"/api/events/{two['id']}").json() == two
    updated = client.put(
        f"/api/members/{first['id']}",
        json={"name": "Test Preference", "revision": first["revision"], "default_option": "Jain"},
    ).json()
    assert client.get(f"/api/events/{two['id']}").json() == two
    three = event(client)
    assert all(
        o["count"] == 2 for s in three["slots"] for o in s["options"] if o["label"] == "Jain"
    )
    legacy_edit = client.put(
        f"/api/members/{first['id']}", json={"name": "Test Rename", "revision": updated["revision"]}
    )
    assert legacy_edit.json()["default_option"] == "Jain"
    with factory() as db:
        record = db.get(Member, UUID(first["id"]))
        assert b"Jain" not in record.personal
        assert vault.open(record.personal)["default_option"] == "Jain"
    member(client, "PRE3")
    assert len(client.get(f"/api/events/{one['id']}").json()["registrations"]) == 2
    extended = client.post(f"/api/events/{one['id']}/defaults").json()
    assert len(extended["registrations"]) == 3
    assert (
        client.get(f"/api/events/{one['id']}/members/{first['id']}/choices").json()["choices"][
            slot["id"]
        ]
        == override
    )
    assert second["default_option"] == "Jain"


def test_missing_defaults_block_ready_and_can_be_filled(system):  # noqa: F811
    client, _, _, _ = system
    person = add_member(client)
    value = event(client)
    assert value["registrations"][0]["needs_choice"]
    assert client.post(f"/api/events/{value['id']}/ready").json()["detail"] == "choices_missing"
    assert (
        client.put(
            f"/api/members/{person['id']}",
            json={"name": "Test Member", "revision": 1, "default_option": "Veg"},
        ).status_code
        == 200
    )
    fixed = client.post(f"/api/events/{value['id']}/defaults").json()
    assert not fixed["registrations"][0]["needs_choice"]
    assert client.post(f"/api/events/{value['id']}/ready").status_code == 200


def test_import_default_validation_and_permissions(system):  # noqa: F811
    client, _, _, _ = system
    csv = b"member_code,name,mobile,is_minor,default_option\nPRE1,Test Preference,,false,Veg\n"
    assert import_data(client, csv).json()["errors"] == []
    assert client.get("/api/members").json() == []
    assert import_data(client, csv, preview=False).json()["committed"]
    assert client.get("/api/members").json()[0]["default_option"] == "Veg"
    assert (
        client.post(
            "/api/members", json={"name": "Test Invalid", "default_option": "Unknown"}
        ).status_code
        == 409
    )
    value = event(client)
    person = client.get("/api/members").json()[0]
    for role in ("checkin", "counter"):
        login = client.post("/api/auth/login", json={"username": "test_" + role, "pin": "123456"})
        client.headers["X-CSRF-Token"] = login.json()["csrf"]
        assert client.post(f"/api/events/{value['id']}/defaults").status_code == 403
        assert (
            client.get(f"/api/events/{value['id']}/members/{person['id']}/choices").status_code
            == 403
        )


def test_pending_late_member_cannot_break_checkin_search(system):  # noqa: F811
    client, _, _, _ = system
    person = member(client)
    value = event(client)
    assert client.post(f"/api/events/{value['id']}/ready").status_code == 200
    late = add_member(client, "LATE-01")
    client.post(f"/api/events/{value['id']}/defaults")
    assert (
        client.post(f"/api/checkin/events/{value['id']}/start").json()["detail"]
        == "choices_missing"
    )
    client.post(
        f"/api/events/{value['id']}/choices",
        json={
            "member_id": late["id"],
            "choices": {s["id"]: s["options"][0]["id"] for s in value["slots"]},
        },
    )
    assert client.post(f"/api/checkin/events/{value['id']}/start").status_code == 200
    add_member(client, "LATE-02")
    client.post(f"/api/events/{value['id']}/defaults")
    result = client.post(
        f"/api/checkin/slots/{value['slots'][0]['id']}/search", json={"query": "Test"}
    )
    assert result.status_code == 200
    assert len(result.json()) == 2
    assert person["id"] in {m["id"] for m in result.json()}


def test_unavailable_or_ambiguous_default_is_never_guessed(system):  # noqa: F811
    client, _, _, _ = system
    member(client)
    data = event_input()
    value = client.post("/api/events", json=data).json()
    assert value["registrations"][0]["needs_choice"]
    assert value["registrations"][0]["choices"] == {}
    data["slots"][0]["options"][0]["label"] = "Veg"
    data["slots"][0]["options"][1]["label"] = " veg "
    value = client.post("/api/events", json=data).json()
    assert value["registrations"][0]["choices"] == {}
