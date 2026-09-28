import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import UUID

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from event_auth.adapters.database.models import Audit, CheckinTicket, Coupon, Event, Staff, now
from event_auth.adapters.pdf import PdfOutput
from event_auth.core.members.rules import RuleViolation
from event_auth.services.checkin import CheckinService
from sqlalchemy import func, select
from test_m2 import add_event, add_member, choose, consent, enroll, frames, system  # noqa: F401

pytestmark = pytest.mark.postgres


@pytest.fixture
def checkin(system):  # noqa: F811
    client, factory, vault, fake = system
    client.app.state.signer = Ed25519PrivateKey.generate()
    member = add_member(client)
    event = add_event(client)
    assert choose(client, event, member).status_code == 200
    assert client.post(f"/api/events/{event['id']}/ready").status_code == 200
    assert client.post(f"/api/checkin/events/{event['id']}/start").status_code == 200
    slot = event["slots"][0]["id"]
    return client, factory, vault, fake, member, event, slot


def prepare(client, slot, member):
    response = client.post(f"/api/checkin/slots/{slot}/fallback", json={"member_id": member["id"]})
    assert response.status_code == 200, response.text
    return response.json()


def issue(client, ticket):
    return client.post(f"/api/checkin/confirm/{ticket}", json={"confirmed": True})


def test_confirmation_encryption_pdf_retry_and_delete(checkin):
    client, factory, vault, _, member, _, slot = checkin
    ticket = prepare(client, slot, member)["ticket"]
    assert (
        client.post(f"/api/checkin/confirm/{ticket}", json={"confirmed": False}).status_code == 422
    )
    first = issue(client, ticket)
    assert first.status_code == 200, first.text
    value = first.json()
    assert issue(client, ticket).json()["id"] == value["id"]
    pdf = client.post(f"/api/checkin/coupons/{value['id']}/pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")
    assert client.post(f"/api/checkin/coupons/{value['id']}/pdf").content == pdf.content
    assert prepare(client, slot, member)["already_issued"]
    with factory() as db:
        coupon = db.get(Coupon, UUID(value["id"]))
        assert coupon.print_count == 2 and coupon.last_printed_at is not None
        assert coupon.method == "fallback"
        assert member["name"].encode() not in coupon.encrypted_document
        document = vault.open(coupon.encrypted_document)
        assert set(document) == {
            "organization",
            "event",
            "slot",
            "option",
            "member_name",
            "member_code",
            "coupon_code",
            "issued_at",
            "qr",
        }
        _, payload, signature = document["qr"].split(".")

        def decode(s):
            return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))

        client.app.state.signer.public_key().verify(decode(signature), decode(payload))
        assert db.scalar(select(func.count()).select_from(Coupon)) == 1
        assert (
            db.scalar(select(func.count()).select_from(Audit).where(Audit.action == "coupon_issue"))
            == 1
        )
    assert client.delete(f"/api/members/{member['id']}").status_code == 200
    with factory() as db:
        coupon = db.get(Coupon, UUID(value["id"]))
        assert coupon.member_id is None and coupon.encrypted_document is None
        assert db.scalar(select(func.count()).select_from(CheckinTicket)) == 0
    assert client.post(f"/api/checkin/coupons/{value['id']}/pdf").status_code == 404


def test_face_scope_and_consent(checkin):
    client, factory, vault, fake, member, _, slot = checkin
    other = add_member(client, "TEST-OTHER")
    enroll(client, other, consent(client, other))
    endpoint = f"/api/checkin/slots/{slot}/face"
    data = {"frame": frames()[0], "consent_confirmed": True}
    assert client.post(endpoint, json=data).json()["band"] == "no_match"
    assert fake.calls > 0
    enroll(client, member, consent(client, member), reviewed=[other["id"]])
    assert client.post(endpoint, json={"frame": frames()[0]}).status_code == 422
    result = client.post(endpoint, json=data).json()
    assert result["band"] == "high" and result["member"]["id"] == member["id"]
    assert "mobile" not in result["member"]
    assert client.delete(f"/api/members/{member['id']}/consents").status_code == 200
    assert issue(client, result["ticket"]).json()["detail"] == "consent_required"
    assert client.post(endpoint, json=data).json()["band"] == "no_match"


def test_role_and_ticket_binding(checkin):
    client, _, _, _, member, event, slot = checkin
    ticket = prepare(client, slot, member)["ticket"]
    for role in ["counter", "checkin"]:
        login = client.post("/api/auth/login", json={"username": "test_" + role, "pin": "123456"})
        client.headers["X-CSRF-Token"] = login.json()["csrf"]
        if role == "counter":
            assert client.get("/api/checkin/events").status_code == 403
            assert issue(client, ticket).status_code == 403
            assert (
                client.post(f"/api/checkin/slots/{slot}/search", json={"query": "TEST"}).status_code
                == 403
            )
        else:
            assert issue(client, ticket).status_code == 404
            assert client.post(f"/api/checkin/events/{event['id']}/start").status_code == 403
            assert client.get("/api/members").status_code == 403
            own = prepare(client, slot, member)
            assert issue(client, own["ticket"]).status_code == 200


def test_expiry_choice_change_and_closed_event(checkin):
    client, factory, _, _, member, event, slot = checkin
    ticket = prepare(client, slot, member)["ticket"]
    with factory.begin() as db:
        db.get(CheckinTicket, UUID(ticket)).expires_at = now() - timedelta(seconds=1)
    assert issue(client, ticket).json()["detail"] == "confirmation_expired"
    ticket = prepare(client, slot, member)["ticket"]
    choices = {s["id"]: s["options"][-1]["id"] for s in event["slots"]}
    assert (
        client.post(
            f"/api/events/{event['id']}/choices",
            json={"member_id": member["id"], "choices": choices},
        ).status_code
        == 200
    )
    assert issue(client, ticket).json()["detail"] == "selection_changed"
    with factory.begin() as db:
        db.get(Event, UUID(event["id"])).status = "CLOSED"
    assert issue(client, ticket).json()["detail"] == "event_not_live"


def test_parallel_issuance_has_one_winner(checkin):
    client, factory, vault, _, member, _, slot = checkin
    tickets = [prepare(client, slot, member)["ticket"] for _ in range(2)]
    state = client.app.state

    def run(ticket):
        try:
            with factory.begin() as db:
                actor = db.scalar(select(Staff).where(Staff.username == "test_admin"))
                service = CheckinService(
                    db, actor, vault, state.config, state.enrollment, state.signer, PdfOutput()
                )
                return service.confirm(UUID(ticket))["id"]
        except RuleViolation as error:
            return str(error)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, tickets))
    assert results.count("already_issued") == 1
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Coupon)) == 1


def test_failed_pdf_keeps_issued_coupon(checkin):
    client, factory, _, _, member, _, slot = checkin
    value = issue(client, prepare(client, slot, member)["ticket"]).json()

    class FailingOutput:
        def render(self, document):
            raise RuleViolation("output_unavailable")

    client.app.state.document_output = FailingOutput()
    assert client.post(f"/api/checkin/coupons/{value['id']}/pdf").status_code == 409
    with factory() as db:
        coupon = db.get(Coupon, UUID(value["id"]))
        assert coupon.status == "ISSUED" and coupon.print_count == 0
    client.app.state.document_output = PdfOutput()
    assert client.post(f"/api/checkin/coupons/{value['id']}/pdf").status_code == 200


def test_redeemed_coupon_cannot_issue_again(checkin):
    client, factory, _, _, member, _, slot = checkin
    value = issue(client, prepare(client, slot, member)["ticket"]).json()
    with factory.begin() as db:
        db.get(Coupon, UUID(value["id"])).status = "REDEEMED"
    assert prepare(client, slot, member)["already_issued"]
    assert client.post(f"/api/checkin/coupons/{value['id']}/pdf").status_code == 409


def test_medium_requires_confirmation_and_no_match_does_not_issue(checkin):
    client, factory, _, fake, member, _, slot = checkin
    enroll(client, member, consent(client, member))
    endpoint = f"/api/checkin/slots/{slot}/face"
    fake.embed = lambda image: (0.5, 0.8660254037844386)
    result = client.post(endpoint, json={"frame": frames()[0], "consent_confirmed": True}).json()
    assert result["band"] == "medium"
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Coupon)) == 0
    fake.embed = lambda image: (0.0, 1.0)
    unmatched = client.post(endpoint, json={"frame": frames()[0], "consent_confirmed": True}).json()
    assert unmatched["band"] == "no_match" and "ticket" not in unmatched
    assert issue(client, result["ticket"]).status_code == 200


def test_missing_signer_does_not_issue_or_consume_ticket(checkin):
    client, factory, _, _, member, _, slot = checkin
    signer = client.app.state.signer
    client.app.state.signer = None
    ticket = prepare(client, slot, member)["ticket"]
    assert issue(client, ticket).json()["detail"] == "signing_setup_required"
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Coupon)) == 0
    client.app.state.signer = signer
    assert issue(client, ticket).status_code == 200


def test_new_app_recovers_persisted_coupon(checkin):
    from event_auth.api.app import create_app
    from fastapi.testclient import TestClient

    client, factory, vault, _, member, _, slot = checkin
    value = issue(client, prepare(client, slot, member)["ticket"]).json()
    state = client.app.state
    app = create_app(
        sessions=factory,
        vault=vault,
        config=state.config,
        enrollment=state.enrollment,
        signer=state.signer,
    )
    with TestClient(app, headers={"Origin": "http://testserver"}) as restarted:
        login = restarted.post("/api/auth/login", json={"username": "test_admin", "pin": "123456"})
        restarted.headers["X-CSRF-Token"] = login.json()["csrf"]
        assert prepare(restarted, slot, member)["coupon"]["id"] == value["id"]
        assert restarted.post(f"/api/checkin/coupons/{value['id']}/pdf").status_code == 200
