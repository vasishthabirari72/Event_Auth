from dataclasses import asdict
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import select
from sqlalchemy.orm import Session

from event_auth.adapters.crypto import Vault
from event_auth.adapters.database.models import (
    Audit,
    CheckinTicket,
    ConsentRecord,
    Coupon,
    Event,
    FaceTemplate,
    Member,
    Option,
    Registration,
    Selection,
    Slot,
    Staff,
    now,
)
from event_auth.adapters.signing import sign
from event_auth.config.settings import CustomerConfig
from event_auth.core.documents import CouponDocument, DocumentOutput
from event_auth.core.face.contracts import Template
from event_auth.core.face.matching import identify
from event_auth.core.members.rules import RuleViolation
from event_auth.core.security.roles import Action, Role, require_permission
from event_auth.services.enrollment import Enrollment


class CheckinService:
    def __init__(
        self,
        db: Session,
        actor: Staff,
        vault: Vault,
        config: CustomerConfig,
        enrollment: Enrollment,
        signer: Ed25519PrivateKey | None,
        output: DocumentOutput,
    ) -> None:
        require_permission(Role(actor.role), Action.CHECK_IN)
        self.db, self.actor, self.vault, self.config = db, actor, vault, config
        self.enrollment, self.signer, self.output = enrollment, signer, output

    def audit(self, action: str, entity: UUID, related: list[UUID]) -> None:
        self.db.add(
            Audit(
                actor_id=self.actor.id,
                action=action,
                entity_id=entity,
                related_ids=[str(value) for value in related],
            )
        )

    def event(self, event_id: UUID) -> Event:
        event = self.db.scalar(select(Event).where(Event.id == event_id).with_for_update())
        if event is None:
            raise LookupError("not_found")
        return event

    def slot(self, slot_id: UUID) -> tuple[Slot, Event]:
        slot = self.db.get(Slot, slot_id)
        if slot is None:
            raise LookupError("not_found")
        event = self.event(slot.event_id)
        if event.status != "LIVE":
            raise RuleViolation("event_not_live")
        return slot, event

    def events(self) -> list[dict[str, Any]]:
        return [
            {
                "id": str(e.id),
                "name": e.name,
                "status": e.status,
                "slots": [
                    {"id": str(s.id), "label": s.label}
                    for s in self.db.scalars(
                        select(Slot).where(Slot.event_id == e.id).order_by(Slot.created_at)
                    )
                ],
            }
            for e in self.db.scalars(
                select(Event)
                .where(Event.status.in_(["READY", "LIVE"]))
                .order_by(Event.date, Event.created_at)
            )
        ]

    def start(self, event_id: UUID) -> None:
        require_permission(Role(self.actor.role), Action.MANAGE)
        event = self.event(event_id)
        if event.status != "READY":
            raise RuleViolation("invalid_transition")
        event.status = "LIVE"
        event.revision += 1
        self.audit("event_live", event.id, [])

    def selection(self, member_id: UUID, slot: Slot) -> Option:
        option = self.db.scalar(
            select(Option)
            .join(Selection, Selection.option_id == Option.id)
            .join(Registration, Registration.id == Selection.registration_id)
            .where(
                Registration.member_id == member_id,
                Registration.event_id == slot.event_id,
                Selection.slot_id == slot.id,
                Option.slot_id == slot.id,
            )
        )
        if option is None:
            raise RuleViolation("not_registered")
        return option

    def member(self, member_id: UUID) -> Member:
        member = self.db.scalar(select(Member).where(Member.id == member_id).with_for_update())
        if member is None:
            raise LookupError("not_found")
        return member

    def card(self, member: Member, option: Option) -> dict[str, Any]:
        return {
            "id": str(member.id),
            "member_code": member.member_code,
            "name": self.vault.open(member.personal)["name"],
            "option": option.label,
            "has_photo": member.thumbnail is not None,
        }

    def search(self, slot_id: UUID, query: str) -> list[dict[str, Any]]:
        slot, _ = self.slot(slot_id)
        needle = query.casefold().strip()
        if not needle:
            return []
        result = []
        for member in self.db.scalars(
            select(Member)
            .join(Registration)
            .where(Registration.event_id == slot.event_id)
            .order_by(Member.member_code)
        ):
            personal = self.vault.open(member.personal)
            if any(
                needle in str(v).casefold()
                for v in [member.member_code, personal["name"], personal["mobile"]]
            ):
                result.append(self.card(member, self.selection(member.id, slot)))
            if len(result) == 30:
                break
        return result

    def prepare(self, slot_id: UUID, member_id: UUID, method: str) -> dict[str, Any]:
        slot, _ = self.slot(slot_id)
        member = self.member(member_id)
        option = self.selection(member_id, slot)
        existing = self.db.scalar(
            select(Coupon)
            .where(Coupon.member_id == member_id, Coupon.slot_id == slot_id)
            .order_by(Coupon.created_at.desc())
            .limit(1)
        )
        result = self.card(member, option)
        if existing is not None:
            return {"member": result, "coupon": self.coupon_view(existing), "already_issued": True}
        ticket = CheckinTicket(
            member_id=member_id,
            slot_id=slot_id,
            option_id=option.id,
            actor_id=self.actor.id,
            method=method,
            expires_at=now() + timedelta(minutes=5),
        )
        self.db.add(ticket)
        self.db.flush()
        return {"member": result, "ticket": str(ticket.id), "already_issued": False}

    def identify(self, slot_id: UUID, frame: str) -> dict[str, Any]:
        slot, _ = self.slot(slot_id)
        if not self.config.experimental_face:
            raise RuleViolation("face_disabled")
        candidates = set(
            self.db.scalars(
                select(Registration.member_id).where(Registration.event_id == slot.event_id)
            )
        )
        templates = [
            Template(t.member_id, t.model_version, tuple(self.vault.open(t.embedding)))
            for t in self.db.scalars(
                select(FaceTemplate)
                .join(ConsentRecord)
                .where(
                    FaceTemplate.member_id.in_(candidates),
                    FaceTemplate.model_version == self.enrollment.version,
                    ConsentRecord.withdrawn.is_(False),
                    ConsentRecord.text_version == self.config.consent_version,
                )
            )
        ]
        if not templates:
            return {"band": "no_match", "experimental": True}
        with self.enrollment.mutex:
            vector = self.enrollment.runtime().embed(self.enrollment.decode(frame))
        match = identify(
            vector, templates, candidates, self.enrollment.version, self.enrollment.thresholds
        )
        if match.member_id is None:
            return {"band": "no_match", "experimental": True}
        result = self.prepare(slot_id, match.member_id, "face")
        return {**result, "band": match.band.value, "experimental": True}

    def photo(self, slot_id: UUID, member_id: UUID) -> str:
        slot, _ = self.slot(slot_id)
        self.selection(member_id, slot)
        member = self.member(member_id)
        if member.thumbnail is None:
            raise LookupError("not_found")
        return str(self.vault.open(member.thumbnail))

    @staticmethod
    def coupon_view(coupon: Coupon) -> dict[str, Any]:
        return {
            "id": str(coupon.id),
            "code": coupon.code,
            "status": coupon.status,
            "issued_at": coupon.created_at.isoformat(),
            "print_count": coupon.print_count,
        }

    def confirm(self, ticket_id: UUID) -> dict[str, Any]:
        # Read routing first; lock order is event -> member -> ticket -> coupon.
        ticket = self.db.get(CheckinTicket, ticket_id)
        if ticket is None or ticket.actor_id != self.actor.id:
            raise LookupError("not_found")
        slot, event = self.slot(ticket.slot_id)
        member = self.member(ticket.member_id)
        self.db.refresh(ticket, with_for_update=True)
        if ticket.coupon_id:
            coupon = self.db.get(Coupon, ticket.coupon_id)
            assert coupon is not None
            return {**self.coupon_view(coupon), "recovered": True}
        if ticket.expires_at <= now():
            raise RuleViolation("confirmation_expired")
        option = self.selection(member.id, slot)
        if option.id != ticket.option_id:
            raise RuleViolation("selection_changed")
        if ticket.method == "face" and not self.db.scalar(
            select(FaceTemplate.id)
            .join(ConsentRecord)
            .where(
                FaceTemplate.member_id == member.id,
                ConsentRecord.withdrawn.is_(False),
                ConsentRecord.text_version == self.config.consent_version,
            )
            .limit(1)
        ):
            raise RuleViolation("consent_required")
        if self.db.scalar(
            select(Coupon.id).where(Coupon.member_id == member.id, Coupon.slot_id == slot.id)
        ):
            raise RuleViolation("already_issued")
        if self.signer is None:
            raise RuleViolation("signing_setup_required")
        issued = now()
        subject_id = (
            self.db.scalar(
                select(Coupon.subject_id)
                .where(Coupon.member_id == member.id, Coupon.event_id == event.id)
                .limit(1)
            )
            or uuid4()
        )
        coupon = Coupon(
            id=uuid4(),
            subject_id=subject_id,
            member_id=member.id,
            event_id=event.id,
            slot_id=slot.id,
            option_id=option.id,
            code=uuid4().hex[:12].upper(),
            method=ticket.method,
            issued_by=self.actor.id,
            created_at=issued,
        )
        qr = sign(
            self.signer,
            {
                "c": coupon.code,
                "e": str(event.id),
                "s": str(slot.id),
                "o": str(option.id),
                "m": member.member_code,
                "t": int(issued.timestamp()),
            },
        )
        document = CouponDocument(
            self.config.organization,
            event.name,
            slot.label,
            option.label,
            self.vault.open(member.personal)["name"],
            member.member_code,
            coupon.code,
            issued.isoformat(timespec="seconds"),
            qr,
        )
        coupon.encrypted_document = self.vault.seal(asdict(document))
        self.db.add(coupon)
        self.db.flush()
        ticket.coupon_id = coupon.id
        self.audit("coupon_issue", coupon.id, [event.id, slot.id, member.id])
        return {**self.coupon_view(coupon), "recovered": False}

    def pdf(self, coupon_id: UUID) -> bytes:
        coupon = self.db.get(Coupon, coupon_id)
        if coupon is None or coupon.member_id is None:
            raise LookupError("not_found")
        self.slot(coupon.slot_id)
        self.member(coupon.member_id)
        self.db.refresh(coupon, with_for_update=True)
        if coupon.status != "ISSUED" or coupon.encrypted_document is None:
            raise RuleViolation("coupon_unavailable")
        document = CouponDocument(**self.vault.open(coupon.encrypted_document))
        pdf = self.output.render(document)
        # Counts completed server renders, not physical prints or acknowledged downloads.
        coupon.print_count += 1
        coupon.last_printed_at = now()
        self.audit("coupon_pdf", coupon.id, [coupon.event_id])
        return pdf
