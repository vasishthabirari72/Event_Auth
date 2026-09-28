import secrets
from datetime import timedelta
from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from event_auth.adapters.crypto import pin_hash, pin_matches, token_hash
from event_auth.adapters.database.models import Audit, LoginBucket, Staff, StaffSession, now
from event_auth.core.security.roles import Action, Role, require_permission


def lock(db: Session, resource: str) -> None:
    key = int(token_hash(resource)[:15], 16)
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


DUMMY_PIN_HASH = pin_hash("000000")


def login(db: Session, username: str, pin: str, peer: str) -> tuple[StaffSession, str] | None:
    # Both account and client buckets are persistent and shared across server workers.
    keys = sorted({token_hash("account:" + username), token_hash("peer:" + peer)})
    buckets = []
    for key in keys:
        lock(db, key)
        bucket = db.get(LoginBucket, key)
        if bucket is None:
            bucket = LoginBucket(key=key, failures=0, until=now() + timedelta(minutes=5))
            db.add(bucket)
        if bucket.until <= now():
            bucket.failures = 0
            bucket.until = now() + timedelta(minutes=5)
        buckets.append(bucket)
    if any(bucket.failures >= 5 for bucket in buckets):
        return None
    staff = db.scalar(select(Staff).where(Staff.username == username))
    # Equal KDF work for unknown accounts; invalid attempts never reveal account existence.
    encoded = staff.pin_hash if staff else DUMMY_PIN_HASH
    valid = pin_matches(pin, encoded)
    if staff is None or not valid:
        for bucket in buckets:
            bucket.failures += 1
        return None
    for bucket in buckets:
        bucket.failures = 0
    token = secrets.token_urlsafe(32)
    session = StaffSession(
        token_hash=token_hash(token),
        staff_id=staff.id,
        csrf=secrets.token_urlsafe(32),
        expires_at=now() + timedelta(hours=8),
    )
    db.execute(delete(StaffSession).where(StaffSession.expires_at <= now()))
    db.add(session)
    db.add(Audit(actor_id=staff.id, action="staff_login", entity_id=staff.id))
    db.flush()
    return session, token


def reset_pin(db: Session, actor: Staff, staff_id: UUID, pin: str) -> None:
    require_permission(Role(actor.role), Action.MANAGE)
    target = db.get(Staff, staff_id)
    if target is None:
        raise LookupError("not_found")
    target.pin_hash = pin_hash(pin)
    db.execute(delete(StaffSession).where(StaffSession.staff_id == staff_id))
    db.add(Audit(actor_id=actor.id, action="staff_pin_reset", entity_id=staff_id))
