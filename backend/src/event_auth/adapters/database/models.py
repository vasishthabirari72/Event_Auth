from datetime import UTC, datetime
from datetime import date as calendar_date
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from event_auth.adapters.database.session import Base


def now() -> datetime:
    return datetime.now(UTC)


class Identity:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Staff(Identity, Base):
    __tablename__ = "staff_users"
    username: Mapped[str] = mapped_column(String(40), unique=True)
    role: Mapped[str] = mapped_column(String(16))
    pin_hash: Mapped[str] = mapped_column(String(256))


class LoginBucket(Base):
    __tablename__ = "login_buckets"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    until: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class StaffSession(Base):
    __tablename__ = "staff_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    staff_id: Mapped[UUID] = mapped_column(ForeignKey("staff_users.id", ondelete="CASCADE"))
    csrf: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Member(Identity, Base):
    __tablename__ = "members"
    member_code: Mapped[str] = mapped_column(String(24), unique=True)
    personal: Mapped[bytes] = mapped_column(LargeBinary)
    thumbnail: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class ConsentRecord(Identity, Base):
    __tablename__ = "consents"
    member_id: Mapped[UUID] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"))
    given_by: Mapped[str] = mapped_column(String(16))
    guardian: Mapped[bytes] = mapped_column(LargeBinary)
    purpose: Mapped[str] = mapped_column(String(256))
    text_version: Mapped[str] = mapped_column(String(64))
    captured_by: Mapped[UUID] = mapped_column(ForeignKey("staff_users.id"))
    withdrawn: Mapped[bool] = mapped_column(Boolean, default=False)


class FaceTemplate(Identity, Base):
    __tablename__ = "face_templates"
    member_id: Mapped[UUID] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"))
    consent_id: Mapped[UUID] = mapped_column(ForeignKey("consents.id", ondelete="CASCADE"))
    model_version: Mapped[str] = mapped_column(String(64))
    embedding: Mapped[bytes] = mapped_column(LargeBinary)


class Event(Identity, Base):
    __tablename__ = "events"
    name: Mapped[str] = mapped_column(String(120))
    date: Mapped[calendar_date] = mapped_column(Date)
    venue: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(16), default="DRAFT")
    revision: Mapped[int] = mapped_column(Integer, default=1)


class Slot(Identity, Base):
    __tablename__ = "entitlement_slots"
    __table_args__ = (UniqueConstraint("event_id", "code"),)
    event_id: Mapped[UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(24))
    label: Mapped[str] = mapped_column(String(80))


class Option(Identity, Base):
    __tablename__ = "entitlement_options"
    __table_args__ = (UniqueConstraint("slot_id", "code"),)
    slot_id: Mapped[UUID] = mapped_column(ForeignKey("entitlement_slots.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(24))
    label: Mapped[str] = mapped_column(String(80))
    entitlement_type: Mapped[str] = mapped_column(String(40))


class Counter(Identity, Base):
    __tablename__ = "counters"
    event_id: Mapped[UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(String(80))


class CounterOption(Base):
    __tablename__ = "counter_options"
    counter_id: Mapped[UUID] = mapped_column(
        ForeignKey("counters.id", ondelete="CASCADE"), primary_key=True
    )
    option_id: Mapped[UUID] = mapped_column(
        ForeignKey("entitlement_options.id", ondelete="CASCADE"), primary_key=True
    )


class Registration(Identity, Base):
    __tablename__ = "event_registrations"
    __table_args__ = (UniqueConstraint("event_id", "member_id"),)
    event_id: Mapped[UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    member_id: Mapped[UUID] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"))


class Selection(Identity, Base):
    __tablename__ = "selections"
    __table_args__ = (UniqueConstraint("registration_id", "slot_id"),)
    registration_id: Mapped[UUID] = mapped_column(
        ForeignKey("event_registrations.id", ondelete="CASCADE")
    )
    slot_id: Mapped[UUID] = mapped_column(ForeignKey("entitlement_slots.id"))
    option_id: Mapped[UUID] = mapped_column(ForeignKey("entitlement_options.id"))


class Audit(Identity, Base):
    __tablename__ = "audit_log"
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("staff_users.id"))
    action: Mapped[str] = mapped_column(String(48))
    entity_id: Mapped[UUID] = mapped_column()
    related_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)


class Coupon(Identity, Base):
    __tablename__ = "coupons"
    __table_args__ = (
        Index(
            "one_current_coupon",
            "member_id",
            "slot_id",
            unique=True,
            postgresql_where=text("status != 'VOID'"),
        ),
    )
    member_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("members.id", ondelete="SET NULL"), nullable=True
    )
    event_id: Mapped[UUID] = mapped_column(ForeignKey("events.id"))
    slot_id: Mapped[UUID] = mapped_column(ForeignKey("entitlement_slots.id"))
    option_id: Mapped[UUID] = mapped_column(ForeignKey("entitlement_options.id"))
    code: Mapped[str] = mapped_column(String(24), unique=True)
    claim_id: Mapped[UUID] = mapped_column(default=uuid4)
    subject_id: Mapped[UUID] = mapped_column(default=uuid4)
    replacement_of: Mapped[UUID | None] = mapped_column(
        ForeignKey("coupons.id"), unique=True, nullable=True
    )
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    redeemed_counter_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("counters.id"), nullable=True
    )
    redeemed_by: Mapped[UUID | None] = mapped_column(ForeignKey("staff_users.id"), nullable=True)
    encrypted_reason: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    status: Mapped[str] = mapped_column(String(16), default="ISSUED")
    method: Mapped[str] = mapped_column(String(16))
    issued_by: Mapped[UUID] = mapped_column(ForeignKey("staff_users.id"))
    # Vault ciphertext only; never store a PDF or plaintext member details.
    encrypted_document: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    print_count: Mapped[int] = mapped_column(Integer, default=0)
    last_printed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CheckinTicket(Identity, Base):
    __tablename__ = "checkin_tickets"
    member_id: Mapped[UUID] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"))
    slot_id: Mapped[UUID] = mapped_column(ForeignKey("entitlement_slots.id"))
    option_id: Mapped[UUID] = mapped_column(ForeignKey("entitlement_options.id"))
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("staff_users.id"))
    method: Mapped[str] = mapped_column(String(16))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    coupon_id: Mapped[UUID | None] = mapped_column(ForeignKey("coupons.id"), nullable=True)


class OperationReceipt(Identity, Base):
    __tablename__ = "operation_receipts"
    __table_args__ = (UniqueConstraint("actor_id", "action", "request_id"),)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("staff_users.id"))
    action: Mapped[str] = mapped_column(String(32))
    request_id: Mapped[UUID] = mapped_column()
    fingerprint: Mapped[str] = mapped_column(String(64))
    # States and record IDs only, never names or QR payloads.
    result: Mapped[dict[str, object]] = mapped_column(JSONB)
