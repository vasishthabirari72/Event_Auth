import base64
import hashlib
import json
import os
from uuid import UUID, uuid4

import pytest
from event_auth.adapters.backup import seal, unseal, write_private
from event_auth.adapters.crypto import Vault
from event_auth.adapters.database.models import Coupon, FaceTemplate, Member, Staff, StaffSession
from event_auth.adapters.database.session import make_engine
from event_auth.adapters.signing import load_signer
from event_auth.operations.recovery import (
    authenticate,
    create_backup,
    restore_backup,
    validate_target,
)
from event_auth.services.counter import CounterService
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from test_m2 import consent, enroll, system  # noqa: F401
from test_m3 import checkin  # noqa: F401
from test_m4 import redemption, scan  # noqa: F401

pytestmark = pytest.mark.postgres
PHRASE = "test-only recovery passphrase"


def test_real_dump_restore_and_restart_preserve_state(redemption, tmp_path):  # noqa: F811
    target_url = os.environ.get("RESTORE_DATABASE_URL")
    if not target_url:
        pytest.skip("Separate RESTORE_DATABASE_URL not configured")
    validate_target(target_url, "restore-db")
    target = make_engine(target_url)
    with target.connect() as connection:
        assert (
            connection.scalar(text("SELECT count(*) FROM pg_tables WHERE schemaname='public'")) == 0
        ), "Refuse existing recovery database"
    client, factory, vault, member, event, slot, coupon, qr, counter = redemption
    consent_id = consent(client, member)
    assert enroll(client, member, consent_id, "a").status_code == 200
    request = uuid4()
    assert scan(client, slot, qr, counter, request).json()["status"] == "SERVE"
    engine = factory.kw["bind"]
    actor = authenticate(engine, "test_admin", "123456")
    with pytest.raises(PermissionError):
        authenticate(engine, "test_counter", "123456")
    with pytest.raises(PermissionError):
        authenticate(engine, "test_admin", "654321")
    storage, signing, config = [tmp_path / p for p in ["storage.key", "signing.key", "config.json"]]
    key = base64.urlsafe_b64encode(vault.cipher._signing_key + vault.cipher._encryption_key)
    write_private(storage, key)
    write_private(signing, client.app.state.signer.private_bytes_raw())
    config.write_text(client.app.state.config.model_dump_json())
    backup, destination = tmp_path / "recovery.eab", tmp_path / "restored"
    try:
        create_backup(engine, "test-db", actor, storage, signing, config, backup, PHRASE)
        files = unseal(backup.read_bytes(), PHRASE)
        assert files["database.dump"].startswith(b"PGDMP")
        assert not list(tmp_path.glob("*.dump"))
        with pytest.raises(ValueError, match="Wrong passphrase"):
            restore_backup(target, backup, destination, "wrong passphrase value")
        assert not destination.exists()
        damaged = dict(files)
        damaged["database.dump"] = b"PGDMPinvalid test dump"
        manifest = json.loads(damaged["manifest.json"])
        manifest["sha256"]["database.dump"] = hashlib.sha256(damaged["database.dump"]).hexdigest()
        damaged["manifest.json"] = json.dumps(manifest).encode()
        invalid_archive = tmp_path / "invalid.eab"
        write_private(invalid_archive, seal(damaged, PHRASE))
        with pytest.raises(ValueError, match="PostgreSQL recovery command failed"):
            restore_backup(target, invalid_archive, tmp_path / "failed-restore", PHRASE)
        with target.connect() as connection:
            assert (
                connection.scalar(text("SELECT count(*) FROM pg_tables WHERE schemaname='public'"))
                == 0
            )
        report = restore_backup(target, backup, destination, PHRASE)
        assert report["counts_verified"] and report["coupon_signatures_verified"]
        assert destination.stat().st_mode & 0o777 == 0o700
        restored_vault, signer = (
            Vault.from_file(destination / "storage.key"),
            load_signer(destination / "signing.key"),
        )
        # A new service/session reads real restored rows, not an in-memory mocked snapshot.
        with Session(target) as db, db.begin():
            person = db.get(Member, UUID(member["id"]))
            assert restored_vault.open(person.personal) == vault.open(person.personal)
            assert restored_vault.open(person.thumbnail)
            vectors = list(db.scalars(select(FaceTemplate)))
            assert len(vectors) == 3
            assert all(restored_vault.open(row.embedding) for row in vectors)
            assert db.get(Coupon, UUID(coupon["id"])).status == "REDEEMED"
            assert db.scalar(select(func.count()).select_from(StaffSession)) == 0
            service = CounterService(
                db, db.get(Staff, actor), restored_vault, client.app.state.config, signer
            )
            assert service.redeem(UUID(counter), UUID(slot), qr, request)["status"] == "RECOVERED"
            assert (
                service.redeem(UUID(counter), UUID(slot), qr, uuid4())["status"] == "ALREADY_USED"
            )
        with pytest.raises(ValueError, match="not empty"):
            restore_backup(target, backup, tmp_path / "second", PHRASE)
        assert not (tmp_path / "second").exists()
        assert db.get_bind().url.database == "event_auth_restore"
    finally:
        # The test alone populated this initially empty, explicitly isolated database.
        with target.begin() as connection:
            connection.execute(text("DROP SCHEMA public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
        target.dispose()
