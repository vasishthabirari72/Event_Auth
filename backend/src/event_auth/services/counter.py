import hashlib
import json
from dataclasses import asdict
from typing import Any
from uuid import UUID, uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from event_auth.adapters.crypto import Vault
from event_auth.adapters.database.models import (
    Audit,
    Counter,
    CounterOption,
    Coupon,
    Event,
    Member,
    OperationReceipt,
    Option,
    Registration,
    Selection,
    Slot,
    Staff,
    now,
)
from event_auth.adapters.signing import sign, verify
from event_auth.config.settings import CustomerConfig
from event_auth.core.documents import CouponDocument
from event_auth.core.members.rules import RuleViolation
from event_auth.core.redemption import redemption_state
from event_auth.core.security.roles import Action, Role, require_permission
from event_auth.services.auth import lock


class CounterService:
    def __init__(
        self,
        db: Session,
        actor: Staff,
        vault: Vault,
        config: CustomerConfig,
        signer: Ed25519PrivateKey | None,
    ) -> None:
        require_permission(Role(actor.role), Action.REDEEM)
        self.db, self.actor, self.vault, self.config, self.signer = db, actor, vault, config, signer

    def admin(self) -> None:
        require_permission(Role(self.actor.role), Action.MANAGE)

    def audit(self, action: str, entity: UUID, related: list[UUID]) -> None:
        self.db.add(
            Audit(
                actor_id=self.actor.id,
                action=action,
                entity_id=entity,
                related_ids=[str(value) for value in related],
            )
        )

    def receipt(self, action: str, request: UUID, payload: dict[str, Any]) -> OperationReceipt:
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        lock(self.db, f"{self.actor.id}:{action}:{request}")
        record = self.db.scalar(
            select(OperationReceipt).where(
                OperationReceipt.actor_id == self.actor.id,
                OperationReceipt.action == action,
                OperationReceipt.request_id == request,
            )
        )
        if record is not None:
            if record.fingerprint != fingerprint:
                raise RuleViolation("request_reused")
            return record
        record = OperationReceipt(
            actor_id=self.actor.id,
            action=action,
            request_id=request,
            fingerprint=fingerprint,
            result={},
        )
        self.db.add(record)
        return record

    def event(self, event_id: UUID) -> Event:
        event = self.db.scalar(select(Event).where(Event.id == event_id).with_for_update())
        if event is None:
            raise LookupError("not_found")
        return event

    def locked_coupon(self, coupon_id: UUID) -> tuple[Coupon, Event]:
        coupon = self.db.get(Coupon, coupon_id)
        if coupon is None:
            raise LookupError("not_found")
        event = self.event(coupon.event_id)
        if coupon.member_id is not None:
            self.db.scalar(select(Member).where(Member.id == coupon.member_id).with_for_update())
        self.db.refresh(coupon, with_for_update=True)
        return coupon, event

    def catalog(self) -> list[dict[str, Any]]:
        return [
            {
                "id": str(e.id),
                "name": e.name,
                "status": e.status,
                "slots": [
                    {"id": str(s.id), "label": s.label}
                    for s in self.db.scalars(select(Slot).where(Slot.event_id == e.id))
                ],
                "counters": [
                    {"id": str(c.id), "label": c.label}
                    for c in self.db.scalars(select(Counter).where(Counter.event_id == e.id))
                ],
            }
            for e in self.db.scalars(select(Event).order_by(Event.date.desc()))
        ]

    def details(self, coupon: Coupon) -> dict[str, Any]:
        document = self.vault.open(coupon.encrypted_document) if coupon.encrypted_document else {}
        counter = (
            self.db.get(Counter, coupon.redeemed_counter_id) if coupon.redeemed_counter_id else None
        )
        return {
            "coupon_id": str(coupon.id),
            "code": coupon.code,
            "name": document.get("member_name", ""),
            "option": document.get("option", ""),
            "redeemed_at": coupon.redeemed_at.isoformat() if coupon.redeemed_at else None,
            "counter": counter.label if counter else None,
        }

    def redeem(
        self, counter_id: UUID, slot_id: UUID, qr: str, request: UUID, lookup_id: UUID | None = None
    ) -> dict[str, Any]:
        if lookup_id is not None:
            require_permission(Role(self.actor.role), Action.REDEEM_BY_LOOKUP)
        payload = {
            "counter": str(counter_id),
            "slot": str(slot_id),
            "qr": qr,
            "lookup": str(lookup_id) if lookup_id else None,
        }
        receipt = self.receipt("redeem", request, payload)
        if receipt.result:
            # A recovered acknowledgement must never look like a fresh SERVE instruction.
            return {
                "status": "RECOVERED",
                "previous_status": receipt.result["status"],
                "recovered": True,
            }
        counter = self.db.get(Counter, counter_id)
        slot = self.db.get(Slot, slot_id)
        if counter is None or slot is None or slot.event_id != counter.event_id:
            receipt.result = {"status": "INVALID"}
            return {"status": "INVALID", "recovered": False}
        coupon = None
        if lookup_id:
            coupon = self.db.get(Coupon, lookup_id)
        elif self.signer is not None:
            try:
                body = verify(self.signer, qr)
                coupon = self.db.scalar(select(Coupon).where(Coupon.code == str(body["c"])))
                if coupon is not None and (
                    str(coupon.event_id) != body["e"]
                    or str(coupon.slot_id) != body["s"]
                    or str(coupon.option_id) != body["o"]
                ):
                    coupon = None
            except ValueError:
                pass
        if coupon is None:
            receipt.result = {"status": "INVALID"}
            return {"status": "INVALID", "recovered": False}
        coupon, event = self.locked_coupon(coupon.id)
        serves = self.db.get(CounterOption, (counter_id, coupon.option_id)) is not None
        status = redemption_state(
            event.status,
            coupon.status,
            coupon.event_id == counter.event_id and coupon.slot_id == slot_id,
            serves,
            coupon.member_id is not None,
        )
        response: dict[str, Any] = {"status": status, "recovered": False}
        if status == "SERVE":
            changed = self.db.execute(
                update(Coupon)
                .where(Coupon.id == coupon.id, Coupon.status == "ISSUED")
                .values(
                    status="REDEEMED",
                    redeemed_at=now(),
                    redeemed_by=self.actor.id,
                    redeemed_counter_id=counter_id,
                )
                .returning(Coupon.id)
            )
            if changed.scalar_one_or_none() is None:
                raise RuleViolation("redemption_conflict")
            self.db.refresh(coupon)
            self.audit(
                "coupon_redeem_lookup" if lookup_id else "coupon_redeem",
                coupon.id,
                [counter_id, event.id],
            )
        if status in {"SERVE", "ALREADY_USED", "WRONG_COUNTER"}:
            response.update(self.details(coupon))
        if status == "WRONG_COUNTER":
            response["go_to"] = [
                c.label
                for c in self.db.scalars(
                    select(Counter)
                    .join(CounterOption)
                    .where(
                        Counter.event_id == event.id, CounterOption.option_id == coupon.option_id
                    )
                )
            ]
        receipt.result = {"status": status, "coupon_id": str(coupon.id)}
        return response

    def lookup(self, event_id: UUID, query: str) -> list[dict[str, Any]]:
        self.admin()
        needle = query.casefold().strip()
        if not needle:
            return []
        values = []
        for coupon in self.db.scalars(
            select(Coupon).where(Coupon.event_id == event_id).order_by(Coupon.created_at.desc())
        ):
            doc = self.vault.open(coupon.encrypted_document) if coupon.encrypted_document else {}
            if any(
                needle in str(v).casefold()
                for v in [coupon.code, doc.get("member_name", ""), doc.get("member_code", "")]
            ):
                values.append(
                    {
                        **self.details(coupon),
                        "status": coupon.status,
                        "slot_id": str(coupon.slot_id),
                    }
                )
            if len(values) == 30:
                break
        return values

    def replace(
        self, coupon_id: UUID, reason: str, request: UUID, void_only: bool = False
    ) -> dict[str, Any]:
        self.admin()
        action = "void" if void_only else "replace"
        receipt = self.receipt(action, request, {"coupon": str(coupon_id), "reason": reason})
        if receipt.result:
            return {**receipt.result, "recovered": True}
        coupon, event = self.locked_coupon(coupon_id)
        if (
            event.status != "LIVE"
            or coupon.status not in {"ISSUED", "VOID"}
            or coupon.member_id is None
        ):
            raise RuleViolation("coupon_unavailable")
        if self.db.scalar(select(Coupon.id).where(Coupon.replacement_of == coupon.id)):
            raise RuleViolation("coupon_replaced")
        if void_only:
            if coupon.status != "ISSUED":
                raise RuleViolation("coupon_unavailable")
            coupon.status = "VOID"
            coupon.encrypted_reason = self.vault.seal(reason)
            self.audit("coupon_void", coupon.id, [event.id])
            receipt.result = {"coupon_id": str(coupon.id), "status": "VOID"}
            return {**receipt.result, "recovered": False}
        if self.signer is None:
            raise RuleViolation("signing_setup_required")
        member = self.db.get(Member, coupon.member_id)
        slot = self.db.get(Slot, coupon.slot_id)
        option = self.db.scalar(
            select(Option)
            .join(Selection, Selection.option_id == Option.id)
            .join(Registration, Registration.id == Selection.registration_id)
            .where(
                Registration.member_id == coupon.member_id,
                Registration.event_id == event.id,
                Selection.slot_id == coupon.slot_id,
            )
        )
        if member is None or slot is None or option is None:
            raise RuleViolation("not_registered")
        coupon.status = "VOID"
        coupon.encrypted_reason = self.vault.seal(reason)
        self.db.flush()  # Release partial uniqueness before creating the replacement.
        issued = now()
        new = Coupon(
            id=uuid4(),
            claim_id=coupon.claim_id,
            subject_id=coupon.subject_id,
            replacement_of=coupon.id,
            member_id=member.id,
            event_id=event.id,
            slot_id=slot.id,
            option_id=option.id,
            code=uuid4().hex[:12].upper(),
            method=coupon.method,
            issued_by=self.actor.id,
            created_at=issued,
        )
        qr = sign(
            self.signer,
            {
                "c": new.code,
                "e": str(event.id),
                "s": str(slot.id),
                "o": str(option.id),
                "m": member.member_code,
                "t": int(issued.timestamp()),
            },
        )
        new.encrypted_document = self.vault.seal(
            asdict(
                CouponDocument(
                    self.config.organization,
                    event.name,
                    slot.label,
                    option.label,
                    self.vault.open(member.personal)["name"],
                    member.member_code,
                    new.code,
                    issued.isoformat(timespec="seconds"),
                    qr,
                )
            )
        )
        self.db.add(new)
        self.db.flush()
        self.audit("coupon_replace", new.id, [coupon.id, event.id])
        receipt.result = {"coupon_id": str(new.id), "status": "ISSUED", "code": new.code}
        return {**receipt.result, "recovered": False}

    def close(self, event_id: UUID, request: UUID) -> dict[str, Any]:
        self.admin()
        receipt = self.receipt("close", request, {"event": str(event_id)})
        if receipt.result:
            return {**receipt.result, "recovered": True}
        event = self.event(event_id)
        if event.status != "LIVE":
            raise RuleViolation("invalid_transition")
        self.db.execute(
            update(Coupon)
            .where(Coupon.event_id == event_id, Coupon.status == "ISSUED")
            .values(status="EXPIRED")
        )
        event.status = "CLOSED"
        event.revision += 1
        self.audit("event_close", event.id, [])
        receipt.result = {"status": "CLOSED"}
        return {"status": "CLOSED", "recovered": False}

    def dashboard(self, event_id: UUID) -> dict[str, Any]:
        self.admin()
        event = self.event(event_id)
        coupons = list(self.db.scalars(select(Coupon).where(Coupon.event_id == event_id)))
        latest: dict[UUID, Coupon] = {}
        for coupon in coupons:
            if (
                coupon.claim_id not in latest
                or latest[coupon.claim_id].created_at < coupon.created_at
            ):
                latest[coupon.claim_id] = coupon
        current = list(latest.values())
        return {
            "status": event.status,
            "registered": self.db.scalar(
                select(func.count())
                .select_from(Registration)
                .where(Registration.event_id == event_id)
            ),
            "checked_in": len({c.subject_id for c in current}),
            "issued": len(current),
            "served": sum(c.status == "REDEEMED" for c in current),
            "fallback": sum(c.method == "fallback" for c in current),
            "options": [
                {
                    "slot": s.label,
                    "slot_code": s.code,
                    "option": o.label,
                    "option_code": o.code,
                    "issued": sum(c.option_id == o.id for c in current),
                    "served": sum(c.option_id == o.id and c.status == "REDEEMED" for c in current),
                }
                for s in self.db.scalars(select(Slot).where(Slot.event_id == event_id))
                for o in self.db.scalars(select(Option).where(Option.slot_id == s.id))
            ],
        }
