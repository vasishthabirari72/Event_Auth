import base64
import io
import json
import os
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet, InvalidToken
from event_auth.adapters.crypto import Vault, pin_hash, pin_matches
from event_auth.adapters.database.models import (
    Audit,
    ConsentRecord,
    Event,
    FaceTemplate,
    Member,
    Registration,
    Selection,
    Staff,
    StaffSession,
    now,
)
from event_auth.adapters.database.session import Base, make_engine
from event_auth.adapters.face.sface import CaptureRejected
from event_auth.api.app import create_app
from event_auth.config.settings import CustomerConfig
from event_auth.services.enrollment import Enrollment
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import delete, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.postgres


class FakeFace:
    def __init__(self):
        self.calls = 0

    def embed(self, image):
        self.calls += 1
        if image.startswith(b"bad"):
            raise CaptureRejected("Hold still")
        return (1.0, 0.0) if image.startswith(b"a") else (0.0, 1.0)

    def thumbnail(self, image):
        return b"test-thumbnail"


@pytest.fixture
def system(monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not configured")
    assert make_url(url).database == "event_auth_test", "Refusing non-test database"
    engine = make_engine(url)
    factory = sessionmaker(engine, expire_on_commit=False)
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(delete(table))
    with factory.begin() as db:
        for role in ("admin", "checkin", "counter"):
            db.add(Staff(username="test_" + role, role=role, pin_hash=pin_hash("123456")))
    monkeypatch.setenv("EVENT_AUTH_COOKIE_SECURE", "false")
    vault = Vault(Fernet.generate_key())
    fake = FakeFace()
    config = CustomerConfig(organization="Test Organization", experimental_face=True)
    enrollment = Enrollment(Path("assets/models"), fake)
    app = create_app(sessions=factory, vault=vault, config=config, enrollment=enrollment)
    with TestClient(app, headers={"Origin": "http://testserver"}) as client:
        result = client.post("/api/auth/login", json={"username": "test_admin", "pin": "123456"})
        assert result.status_code == 200, result.text
        client.headers["X-CSRF-Token"] = result.json()["csrf"]
        yield client, factory, vault, fake
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(delete(table))
    engine.dispose()


def add_member(client, code="TEST-01", minor=False):
    result = client.post(
        "/api/members",
        json={
            "name": "Test Member " + code,
            "mobile": "TEST-NO-PHONE",
            "member_code": code,
            "is_minor": minor,
            "custom_fields": {},
        },
    )
    assert result.status_code == 200, result.text
    return result.json()


def consent(client, member, guardian=False):
    result = client.post(
        "/api/members/" + member["id"] + "/consents",
        json={
            "agreed": True,
            "text_version": "persistent-draft-v1",
            "given_by": "guardian" if guardian else "self",
            "guardian_name": "Test Guardian" if guardian else "",
        },
    )
    assert result.status_code == 200, result.text
    return result.json()["id"]


def frames(prefix="a"):
    return [base64.b64encode((prefix + str(i)).encode()).decode() for i in range(3)]


def enroll(client, member, consent_id, prefix="a", reviewed=None):
    return client.post(
        "/api/members/" + member["id"] + "/face",
        json={
            "consent_id": consent_id,
            "frames": frames(prefix),
            "reviewed_duplicate_ids": reviewed or [],
        },
    )


def event_input():
    return {
        "name": "Test Event",
        "date": "2026-10-01",
        "venue": "Test Venue",
        "slots": [
            {
                "code": "S1",
                "label": "Test Slot 1",
                "options": [
                    {"code": "O1", "label": "Test Option 1"},
                    {"code": "O2", "label": "Test Option 2"},
                ],
            },
            {
                "code": "S2",
                "label": "Test Slot 2",
                "options": [{"code": "O1", "label": "Test Option 1"}],
            },
        ],
        "counters": [{"label": "Test Counter", "serves": ["S1/O1", "S1/O2", "S2/O1"]}],
    }


def add_event(client):
    result = client.post("/api/events", json=event_input())
    assert result.status_code == 200, result.text
    return result.json()


def choose(client, event, member):
    return client.post(
        "/api/events/" + event["id"] + "/choices",
        json={
            "member_id": member["id"],
            "choices": {s["id"]: s["options"][0]["id"] for s in event["slots"]},
        },
    )


def import_data(client, content, kind="members", event_id=None, preview=True, format="csv"):
    return client.post(
        "/api/imports",
        json={
            "kind": kind,
            "event_id": event_id,
            "preview": preview,
            "format": format,
            "content": base64.b64encode(content).decode(),
        },
    )


def test_session_csrf_expiry_and_error_privacy(system):
    client, factory, _, _ = system
    response = client.get("/api/auth/session")
    assert response.headers["cache-control"] == "no-store"
    assert "pin" not in response.text
    client.headers.pop("X-CSRF-Token")
    assert client.post("/api/members", json={"name": "Test"}).status_code == 403
    assert (
        client.post(
            "/api/auth/login",
            json={"username": "test_admin", "pin": "123456"},
            headers={"Origin": "http://evil.invalid"},
        ).status_code
        == 403
    )
    invalid = client.post("/api/auth/login", json={"username": "test_admin", "pin": "secret"})
    assert invalid.status_code == 422 and "secret" not in invalid.text
    with factory.begin() as db:
        for value in db.scalars(select(StaffSession)):
            value.expires_at = now() - timedelta(seconds=1)
    assert client.get("/api/members").status_code == 401


@pytest.mark.parametrize("role", ["counter", "checkin"])
def test_role_boundaries_cover_read_and_write(system, role):
    client, _, _, fake = system
    member = add_member(client)
    event = add_event(client)
    result = client.post("/api/auth/login", json={"username": "test_" + role, "pin": "123456"})
    client.headers["X-CSRF-Token"] = result.json()["csrf"]
    for path in [
        "/members",
        "/config",
        "/events",
        "/staff",
        "/imports/template.csv",
        "/members/" + member["id"] + "/photo",
        "/events/" + event["id"],
        "/events/" + event["id"] + "/counts.csv",
    ]:
        assert client.get("/api" + path).status_code == 403, path
    assert client.post("/api/members", json={"name": "Test"}).status_code == 403
    assert client.delete("/api/members/" + member["id"]).status_code == 403
    assert client.post("/api/events", json=event_input()).status_code == 403
    assert enroll(client, member, str(uuid4())).status_code == 403
    assert fake.calls == 0


def test_pin_reset_revokes_sessions_and_audits(system):
    client, factory, _, _ = system
    with TestClient(client.app, headers={"Origin": "http://testserver"}) as other:
        result = other.post("/api/auth/login", json={"username": "test_counter", "pin": "123456"})
        staff_id = result.json()["id"]
        assert (
            client.post("/api/staff/" + staff_id + "/pin", json={"pin": "654321"}).status_code
            == 200
        )
        assert other.get("/api/auth/session").status_code == 401
        assert (
            other.post(
                "/api/auth/login", json={"username": "test_counter", "pin": "123456"}
            ).status_code
            == 401
        )
        assert (
            other.post(
                "/api/auth/login", json={"username": "test_counter", "pin": "654321"}
            ).status_code
            == 200
        )
    with factory() as db:
        assert (
            db.scalar(
                select(func.count()).select_from(Audit).where(Audit.action == "staff_pin_reset")
            )
            == 1
        )
        value = db.get(Staff, UUID(staff_id))
        assert value.pin_hash != "654321" and pin_matches("654321", value.pin_hash)


def test_rate_limit_persists_across_clients(system):
    client, _, _, _ = system
    for _ in range(5):
        assert (
            client.post(
                "/api/auth/login", json={"username": "test_admin", "pin": "000000"}
            ).status_code
            == 401
        )
    with TestClient(client.app, headers={"Origin": "http://testserver"}) as other:
        assert (
            other.post(
                "/api/auth/login", json={"username": "test_admin", "pin": "123456"}
            ).status_code
            == 401
        )


def test_encryption_consent_duplicate_review_and_full_deletion(system):
    client, factory, vault, _ = system
    first = add_member(client, minor=True)
    bad = client.post(
        "/api/members/" + first["id"] + "/consents",
        json={"given_by": "self", "agreed": True, "text_version": "persistent-draft-v1"},
    )
    assert bad.status_code == 409 and bad.json()["detail"] == "guardian_required"
    assert enroll(client, first, str(uuid4())).status_code == 409
    consent_id = consent(client, first, guardian=True)
    assert enroll(client, first, consent_id).json()["saved"]
    second = add_member(client, "TEST-02")
    second_consent = consent(client, second)
    review = enroll(client, second, second_consent).json()
    assert not review["saved"] and review["duplicates"][0]["id"] == first["id"]
    assert enroll(client, second, second_consent, reviewed=[first["id"]]).json()["saved"]
    event = add_event(client)
    assert choose(client, event, first).status_code == 200
    with factory() as db:
        member = db.get(Member, UUID(first["id"]))
        assert b"Test Member" not in member.personal
        assert b"test-thumbnail" not in member.thumbnail
        for value in db.scalars(select(FaceTemplate)):
            assert b"[1.0" not in value.embedding
            assert vault.open(value.embedding) == [1.0, 0.0]
        record = db.get(ConsentRecord, UUID(consent_id))
        assert b"Test Guardian" not in record.guardian
        assert record.captured_by and record.created_at and record.purpose and record.text_version
        with pytest.raises(InvalidToken):
            Vault(Fernet.generate_key()).open(member.personal)
    assert client.delete("/api/members/" + first["id"]).status_code == 200
    with factory() as db:
        assert db.get(Member, UUID(first["id"])) is None
        for model in (ConsentRecord, FaceTemplate, Registration):
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(model.member_id == UUID(first["id"]))
                )
                == 0
            )
        assert db.scalar(select(func.count()).select_from(Selection)) == 0
        audits = [
            {"action": a.action, "entity": str(a.entity_id), "related": a.related_ids}
            for a in db.scalars(select(Audit))
        ]
        serialized = json.dumps(audits)
        assert "Test Member" not in serialized and "Test Guardian" not in serialized
        assert any(a["action"] == "duplicate_override" for a in audits)
        assert any(a["action"] == "member_delete" for a in audits)


def test_quality_and_withdrawal_never_save_partial_face(system):
    client, factory, _, fake = system
    member = add_member(client)
    assert enroll(client, member, str(uuid4())).status_code == 409
    assert fake.calls == 0
    cid = consent(client, member)
    assert enroll(client, member, cid, "bad").json()["detail"] == "hold_still"
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(FaceTemplate)) == 0
    assert enroll(client, member, cid).json()["saved"]
    assert client.delete("/api/members/" + member["id"] + "/consents").status_code == 200
    assert enroll(client, member, cid).status_code == 409
    assert client.get("/api/members/" + member["id"] + "/photo").status_code == 404
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(FaceTemplate)) == 0


def test_id_only_edit_revision_search_and_minor_change(system):
    client, _, _, _ = system
    member = add_member(client)
    assert not member["has_face"]
    assert len(client.post("/api/members/search", json={"query": "TEST-NO-PHONE"}).json()) == 1
    payload = {"name": "Test Changed", "is_minor": True, "revision": 1}
    updated = client.put("/api/members/" + member["id"], json=payload)
    assert updated.status_code == 200 and updated.json()["revision"] == 2
    assert (
        client.put("/api/members/" + member["id"], json=payload).json()["detail"] == "stale_record"
    )


def test_events_choices_counts_ready_and_closed(system):
    client, factory, _, _ = system
    member = add_member(client)
    event = add_event(client)
    assert client.post("/api/events/" + event["id"] + "/ready").status_code == 409
    assert choose(client, event, member).status_code == 200
    assert choose(client, event, member).status_code == 200
    view = client.get("/api/events/" + event["id"]).json()
    assert len(view["registrations"]) == 1
    assert sum(o["count"] for s in view["slots"] for o in s["options"]) == 2
    invalid = client.post(
        "/api/events/" + event["id"] + "/choices",
        json={
            "member_id": member["id"],
            "choices": {s["id"]: str(uuid4()) for s in event["slots"]},
        },
    )
    assert invalid.status_code == 409
    assert client.put("/api/events/" + event["id"], json=event_input()).status_code == 409
    exported = client.get("/api/events/" + event["id"] + "/counts.csv")
    assert "Test Member" not in exported.text and "TEST-NO-PHONE" not in exported.text
    assert "S1,O1,1" in exported.text
    assert client.post("/api/events/" + event["id"] + "/ready").status_code == 200
    with factory.begin() as db:
        db.get(Event, UUID(event["id"])).status = "CLOSED"
    assert choose(client, event, member).json()["detail"] == "event_closed"


def test_import_preview_rollback_confirmation_and_choices(system):
    client, factory, _, _ = system
    csv = (
        b"member_code,name,mobile,is_minor\n"
        b"TEST-01,Test Member 01,,false\nTEST-02,Test Member 02,,true\n"
    )
    preview = import_data(client, csv)
    assert preview.json() == {"rows": 2, "errors": [], "committed": False}
    assert client.get("/api/members").json() == []
    bad = csv.replace(b"true", b"maybe")
    assert import_data(client, bad, preview=False).json()["errors"][0]["row"] == 3
    assert client.get("/api/members").json() == []
    assert import_data(client, csv, preview=False).json()["committed"]
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(ConsentRecord)) == 0
    event = add_event(client)
    choices = b"member_code,S1,S2\nTEST-01,O2,O1\nTEST-02,O1,O1\n"
    assert import_data(client, choices, "choices", event["id"], False).json()["committed"]
    assert len(client.get("/api/events/" + event["id"]).json()["registrations"]) == 2
    assert not import_data(client, csv, preview=False).json()["committed"]
    assert len(client.get("/api/members").json()) == 2


def test_excel_import_and_formula_rejection(system):
    client, _, _, _ = system
    book = Workbook()
    sheet = book.active
    sheet.append(["member_code", "name", "mobile", "is_minor"])
    sheet.append(["TEST-X", "Test Excel", "", "false"])
    output = io.BytesIO()
    book.save(output)
    assert import_data(client, output.getvalue(), preview=False, format="xlsx").json()["committed"]
    sheet["B2"] = "=1+1"
    output = io.BytesIO()
    book.save(output)
    assert import_data(client, output.getvalue(), format="xlsx").status_code == 409


def test_service_role_check_without_http(system):
    from event_auth.services.admin import AdminService

    client, factory, vault, _ = system
    with factory() as db:
        staff = db.scalar(select(Staff).where(Staff.role == "counter"))
        with pytest.raises(PermissionError):
            AdminService(db, staff, vault, client.app.state.config)


def test_schema_revision_and_constraints(system):
    _, factory, _, _ = system
    with factory() as db:
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == "0004"
        tables = set(db.scalars(text("SELECT tablename FROM pg_tables WHERE schemaname='public'")))
        assert {"members", "face_templates", "consents", "selections", "staff_sessions"} <= tables


def test_demo_data_is_id_only_and_duplicate_run_rolls_back(system):
    from event_auth.demo import seed_demo
    from event_auth.services.admin import AdminService
    from sqlalchemy.exc import IntegrityError

    client, factory, vault, _ = system
    with factory.begin() as db:
        actor = db.scalar(select(Staff).where(Staff.role == "admin"))
        seed_demo(AdminService(db, actor, vault, client.app.state.config))
    assert len(client.get("/api/members").json()) == 12
    assert all(not m["has_face"] for m in client.get("/api/members").json())
    with pytest.raises(IntegrityError), factory.begin() as db:
        actor = db.scalar(select(Staff).where(Staff.role == "admin"))
        seed_demo(AdminService(db, actor, vault, client.app.state.config))
    assert len(client.get("/api/members").json()) == 12
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(ConsentRecord)) == 0


def test_commit_failure_is_reported_and_member_is_rolled_back(system, monkeypatch):
    from event_auth.services.admin import AdminService

    client, factory, _, _ = system

    def broken_audit(self, action, entity_id, related=None):
        self.db.add(Audit(actor_id=uuid4(), action=action, entity_id=entity_id))

    monkeypatch.setattr(AdminService, "audit", broken_audit)
    response = client.post("/api/members", json={"name": "Test Transaction"})
    assert response.status_code == 409
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Member)) == 0


def test_concurrent_registration_has_one_winner(system):
    from concurrent.futures import ThreadPoolExecutor

    client, factory, _, _ = system

    def create():
        with TestClient(client.app, headers=dict(client.headers), cookies=client.cookies) as other:
            return other.post(
                "/api/members",
                json={
                    "name": "Test Concurrent",
                    "member_code": "TEST-RACE",
                },
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: create(), range(2)))
    assert sorted(outcomes) == [200, 409]
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Member)) == 1


def test_reconsent_does_not_erase_existing_face_until_saved(system):
    client, factory, _, _ = system
    member = add_member(client)
    old = consent(client, member)
    assert enroll(client, member, old).json()["saved"]
    consent(client, member)
    assert client.get("/api/members/" + member["id"] + "/photo").status_code == 200
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(FaceTemplate)) == 3


def test_default_face_gate_cannot_be_bypassed(system):
    client, _, _, fake = system
    client.app.state.config.experimental_face = False
    member = add_member(client)
    cid = consent(client, member)
    assert enroll(client, member, cid).json()["detail"] == "face_disabled"
    assert fake.calls == 0


def test_imported_member_enrollment_preserves_identity_and_event_choices(system):
    client, factory, _, fake = system
    source = b"member_code,name,mobile,is_minor\nTEST-IMPORTED,Test Imported Member,,false\n"
    assert import_data(client, source, preview=False).json()["committed"]
    member = client.get("/api/members").json()[0]
    event = add_event(client)
    assert choose(client, event, member).status_code == 200
    before = client.get("/api/events/" + event["id"]).json()
    assert enroll(client, member, str(uuid4())).status_code == 409
    assert fake.calls == 0
    cid = consent(client, member)
    assert enroll(client, member, cid).json()["saved"]
    members = client.get("/api/members").json()
    assert len(members) == 1
    assert members[0]["id"] == member["id"]
    assert members[0]["member_code"] == "TEST-IMPORTED"
    assert members[0]["has_face"]
    assert client.get("/api/events/" + event["id"]).json() == before
    with factory() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(FaceTemplate)
                .where(FaceTemplate.member_id == UUID(member["id"]))
            )
            == 3
        )
