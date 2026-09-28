from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from event_auth.adapters.database.models import (
    Audit,
    Counter,
    CounterOption,
    Coupon,
    OperationReceipt,
    Staff,
)
from event_auth.core.members.rules import RuleViolation
from event_auth.services.counter import CounterService
from sqlalchemy import func, select
from test_m2 import system  # noqa: F401
from test_m3 import checkin, issue, prepare  # noqa: F401

pytestmark = pytest.mark.postgres


@pytest.fixture
def redemption(checkin):  # noqa: F811
    client, factory, vault, _, member, event, slot = checkin
    coupon = issue(client, prepare(client, slot, member)["ticket"]).json()
    with factory() as db:
        row = db.get(Coupon, UUID(coupon["id"]))
        qr = vault.open(row.encrypted_document)["qr"]
        counter = str(db.scalar(select(Counter.id).where(Counter.event_id == UUID(event["id"]))))
    return client, factory, vault, member, event, slot, coupon, qr, counter


def scan(client, slot, qr, counter, request=None):
    return client.post(
        "/api/counter/redeem",
        json={
            "qr": qr,
            "slot_id": slot,
            "counter_id": counter,
            "request_id": str(request or uuid4()),
        },
    )


def test_single_use_replay_privacy_and_dashboard(redemption):
    client, factory, _, _, event, slot, _, qr, counter = redemption
    request = uuid4()
    first = scan(client, slot, qr, counter, request)
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "SERVE"
    assert not {"photo", "thumbnail", "embedding", "mobile", "member_code"} & first.json().keys()
    recovered = scan(client, slot, qr, counter, request).json()
    assert recovered == {"status": "RECOVERED", "previous_status": "SERVE", "recovered": True}
    assert scan(client, slot, qr, counter).json()["status"] == "ALREADY_USED"
    assert scan(client, slot, qr + "x", counter, request).status_code == 409
    stats = client.get(f"/api/counter/events/{event['id']}/dashboard").json()
    assert stats["issued"] == stats["served"] == stats["fallback"] == 1
    with factory() as db:
        assert (
            db.scalar(
                select(func.count()).select_from(Audit).where(Audit.action == "coupon_redeem")
            )
            == 1
        )
        assert all("name" not in r.result for r in db.scalars(select(OperationReceipt)))


def test_invalid_wrong_slot_and_counter(redemption):
    client, factory, _, _, event, slot, coupon, qr, counter = redemption
    assert scan(client, slot, qr + "x", counter).json()["status"] == "INVALID"
    assert scan(client, event["slots"][1]["id"], qr, counter).json()["status"] == "INVALID"
    with factory.begin() as db:
        wrong = Counter(event_id=UUID(event["id"]), label="Test Wrong Counter")
        db.add(wrong)
        db.flush()
        wrong_id = str(wrong.id)
    result = scan(client, slot, qr, wrong_id).json()
    assert result["status"] == "WRONG_COUNTER" and result["go_to"]
    with factory() as db:
        assert db.get(Coupon, UUID(coupon["id"])).status == "ISSUED"


def test_replace_void_expiry_and_counts(redemption):
    client, factory, vault, _, event, slot, coupon, qr, counter = redemption
    body = {"reason": "Test replacement reason", "request_id": str(uuid4()), "confirmed": True}
    endpoint = f"/api/counter/coupons/{coupon['id']}/replace"
    replacement = client.post(endpoint, json=body)
    assert replacement.status_code == 200, replacement.text
    new_id = replacement.json()["coupon_id"]
    assert client.post(endpoint, json=body).json()["coupon_id"] == new_id
    assert scan(client, slot, qr, counter).json()["status"] == "CANCELLED"
    with factory() as db:
        original = db.get(Coupon, UUID(coupon["id"]))
        new = db.get(Coupon, UUID(new_id))
        assert original.claim_id == new.claim_id
        assert b"Test replacement" not in original.encrypted_reason
        new_qr = vault.open(new.encrypted_document)["qr"]
    assert client.get(f"/api/counter/events/{event['id']}/dashboard").json()["issued"] == 1
    closed = client.post(
        f"/api/counter/events/{event['id']}/close",
        json={"request_id": str(uuid4()), "confirmed": True},
    )
    assert closed.status_code == 200
    assert scan(client, slot, new_qr, counter).json()["status"] == "EXPIRED"
    assert client.post(f"/api/checkin/events/{event['id']}/start").status_code == 409
    assert client.post(f"/api/counter/coupons/{new_id}/replace", json=body).status_code == 409


def test_admin_lookup_and_counter_permissions(redemption):
    client, _, _, member, event, slot, coupon, _, counter = redemption
    values = client.post(
        f"/api/counter/events/{event['id']}/lookup", json={"query": member["member_code"]}
    ).json()
    assert values[0]["coupon_id"] == coupon["id"]
    data = {
        "coupon_id": coupon["id"],
        "counter_id": counter,
        "slot_id": slot,
        "request_id": str(uuid4()),
        "confirmed": True,
    }
    assert client.post("/api/counter/lookup-redeem", json=data).json()["status"] == "SERVE"
    login = client.post("/api/auth/login", json={"username": "test_counter", "pin": "123456"})
    client.headers["X-CSRF-Token"] = login.json()["csrf"]
    assert client.get("/api/counter/events").status_code == 200
    assert client.post("/api/counter/lookup-redeem", json=data).status_code == 403
    assert client.get(f"/api/counter/events/{event['id']}/dashboard").status_code == 403
    assert (
        client.post(f"/api/counter/events/{event['id']}/lookup", json={"query": "TEST"}).status_code
        == 403
    )


def worker(redemption, action, request=None, counter_override=None):
    client, factory, vault, _, event, slot, coupon, qr, counter = redemption
    with factory.begin() as db:
        actor = db.scalar(select(Staff).where(Staff.username == "test_admin"))
        service = CounterService(db, actor, vault, client.app.state.config, client.app.state.signer)
        if action == "redeem":
            return service.redeem(
                UUID(counter_override or counter), UUID(slot), qr, request or uuid4()
            )["status"]
        if action == "close":
            return service.close(UUID(event["id"]), uuid4())["status"]
        try:
            return service.replace(UUID(coupon["id"]), "Test reason", uuid4())["status"]
        except RuleViolation:
            return "blocked"


@pytest.mark.parametrize("opponent", ["redeem", "close", "replace"])
def test_redemption_races(redemption, opponent):
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda action: worker(redemption, action), ["redeem", opponent]))
    assert outcomes.count("SERVE") <= 1
    if opponent == "redeem":
        assert sorted(outcomes) == ["ALREADY_USED", "SERVE"]
    if opponent == "replace" and outcomes[0] == "SERVE":
        assert outcomes[1] == "blocked"
    if opponent == "close":
        assert outcomes[0] in {"SERVE", "EXPIRED"}


def test_same_request_race_recovers(redemption):
    request = uuid4()
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: worker(redemption, "redeem", request), range(2)))
    assert sorted(outcomes) == ["RECOVERED", "SERVE"]


def test_void_and_member_deletion(redemption):
    client, factory, _, member, _, slot, coupon, qr, counter = redemption
    response = client.post(
        f"/api/counter/coupons/{coupon['id']}/void",
        json={"reason": "Test reason", "request_id": str(uuid4()), "confirmed": True},
    )
    assert response.status_code == 200
    assert scan(client, slot, qr, counter).json()["status"] == "CANCELLED"
    assert client.delete(f"/api/members/{member['id']}").status_code == 200
    with factory() as db:
        row = db.get(Coupon, UUID(coupon["id"]))
        assert (
            row.encrypted_document is None
            and row.encrypted_reason is None
            and row.member_id is None
        )
    assert scan(client, slot, qr, counter).json()["status"] == "INVALID"


def test_two_distinct_counters_have_one_serve(redemption):
    _, factory, _, _, event, _, coupon, _, _ = redemption
    with factory.begin() as db:
        counter = Counter(event_id=UUID(event["id"]), label="Test Second Counter")
        db.add(counter)
        db.flush()
        row = db.get(Coupon, UUID(coupon["id"]))
        db.add(CounterOption(counter_id=counter.id, option_id=row.option_id))
        second = str(counter.id)
    with ThreadPoolExecutor(max_workers=2) as pool:
        one = pool.submit(worker, redemption, "redeem")
        two = pool.submit(worker, redemption, "redeem", None, second)
        assert sorted([one.result(), two.result()]) == ["ALREADY_USED", "SERVE"]


def test_redemption_audit_failure_rolls_back(redemption, monkeypatch):
    client, factory, _, _, _, slot, coupon, qr, counter = redemption
    original = CounterService.audit

    def broken(self, action, entity, related):
        self.db.add(Audit(actor_id=uuid4(), action=action, entity_id=entity))

    monkeypatch.setattr(CounterService, "audit", broken)
    request = uuid4()
    assert scan(client, slot, qr, counter, request).status_code == 409
    with factory() as db:
        assert db.get(Coupon, UUID(coupon["id"])).status == "ISSUED"
        assert db.scalar(select(func.count()).select_from(OperationReceipt)) == 0
    monkeypatch.setattr(CounterService, "audit", original)
    assert scan(client, slot, qr, counter, request).json()["status"] == "SERVE"


def test_multi_slot_counts_survive_deletion_and_migration(redemption):
    import os
    import subprocess

    client, factory, _, member, event, _, _, _, _ = redemption
    second_slot = event["slots"][1]["id"]
    assert issue(client, prepare(client, second_slot, member)["ticket"]).status_code == 200
    endpoint = f"/api/counter/events/{event['id']}/dashboard"
    stats = client.get(endpoint).json()
    assert stats["issued"] == 2 and stats["checked_in"] == 1
    # Only the isolated test database is used; existing coupon rows exercise backfill.
    env = {**os.environ, "DATABASE_URL": os.environ["TEST_DATABASE_URL"]}
    for revision in ["0003", "head"]:
        command = "downgrade" if revision == "0003" else "upgrade"
        subprocess.run(
            [".venv/bin/alembic", command, revision], env=env, check=True, capture_output=True
        )
    stats = client.get(endpoint).json()
    assert stats["issued"] == 2 and stats["checked_in"] == 1
    assert client.delete(f"/api/members/{member['id']}").status_code == 200
    stats = client.get(endpoint).json()
    assert stats["issued"] == 2 and stats["checked_in"] == 1 and stats["registered"] == 0
