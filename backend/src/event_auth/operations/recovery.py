"""Docker PostgreSQL backup and isolated restore. No plaintext dump on disk."""

import argparse
import getpass
import hashlib
import json
import os
import selectors
import subprocess
import time
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import Engine, func, select, text
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.orm import Session

from event_auth.adapters.backup import MAX_BYTES, seal, unseal, write_private
from event_auth.adapters.crypto import Vault
from event_auth.adapters.database.models import (
    Audit,
    ConsentRecord,
    Coupon,
    FaceTemplate,
    Member,
    Staff,
    StaffSession,
    now,
)
from event_auth.adapters.database.session import Base, make_engine
from event_auth.adapters.signing import load_signer, verify
from event_auth.config.settings import CustomerConfig
from event_auth.core.security.roles import Action, Role, require_permission
from event_auth.services.auth import login

ROOT = Path(__file__).resolve().parents[4]
EXCLUDED = {"staff_sessions", "login_buckets", "checkin_tickets"}
TARGETS = {
    "db": ("event_auth", 5432),
    "test-db": ("event_auth_test", 5433),
    "restore-db": ("event_auth_restore", 5434),
}


def validate_target(url: str, service: str) -> None:
    value = make_url(url)
    name, port = TARGETS[service]
    if (
        value.drivername != "postgresql+psycopg"
        or value.host != "127.0.0.1"
        or value.port != port
        or value.database != name
        or value.username != name
    ):
        raise ValueError("Database URL must match the selected local Compose service")


def pg(service: str, program: str, options: list[str], data: bytes | None = None) -> bytes:
    name, _ = TARGETS[service]
    command = [
        "docker",
        "compose",
        "-f",
        str(ROOT / "compose.yaml"),
        "exec",
        "-T",
        service,
        program,
        "-U",
        name,
        "-d",
        name,
        *options,
    ]
    # Never forward pg errors: they can contain schema data or private connection details.
    with subprocess.Popen(
        command,
        stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    ) as process:
        try:
            if data is not None:
                output, _ = process.communicate(data, timeout=180)
            else:
                assert process.stdout is not None
                output_buffer = bytearray()
                deadline = time.monotonic() + 180
                with selectors.DefaultSelector() as selector:
                    selector.register(process.stdout, selectors.EVENT_READ)
                    while True:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0 or not selector.select(remaining):
                            raise ValueError("PostgreSQL dump timed out")
                        chunk = os.read(process.stdout.fileno(), 65536)
                        if not chunk:
                            break
                        output_buffer.extend(chunk)
                        if len(output_buffer) > MAX_BYTES:
                            raise ValueError("Dump exceeds pilot backup size limit")
                output = bytes(output_buffer)
                process.wait(timeout=max(1, deadline - time.monotonic()))
        except BaseException:
            process.kill()
            process.wait()
            raise
        if process.returncode:
            raise ValueError(
                "PostgreSQL recovery command failed; check service and database version"
            )
        return output


def authenticate(engine: Engine, username: str, pin: str) -> UUID:
    # Use persistent login throttling without leaving a CLI session behind.
    actor = None
    with Session(engine) as db, db.begin():
        result = login(db, username, pin, "local-recovery-cli")
        if result:
            session, _ = result
            staff = db.get(Staff, session.staff_id)
            if staff and staff.role == "admin":
                actor = staff.id
            db.delete(session)
    if actor is None:
        raise PermissionError("Administrator authentication failed or is temporarily limited")
    return actor


def counts(connection: Connection) -> dict[str, int]:
    return {
        name: int(connection.scalar(select(func.count()).select_from(table)) or 0)
        for name, table in Base.metadata.tables.items()
        if name not in EXCLUDED
    }


def check_data(db: Session, vault: Vault, signer: Ed25519PrivateKey) -> None:
    for model, fields in [
        (Member, ["personal", "thumbnail"]),
        (ConsentRecord, ["guardian"]),
        (FaceTemplate, ["embedding"]),
        (Coupon, ["encrypted_document", "encrypted_reason"]),
    ]:
        for row in db.scalars(select(model)):
            for field in fields:
                value = getattr(row, field)
                if value is not None:
                    decoded = vault.open(value)
                    if field == "encrypted_document" and isinstance(row, Coupon):
                        body = verify(signer, decoded["qr"])
                        if body["c"] != row.code or body["e"] != str(row.event_id):
                            raise ValueError("Coupon recovery verification failed")


def create_backup(
    engine: Engine,
    service: str,
    actor: UUID,
    storage: Path,
    signing: Path,
    config: Path,
    output: Path,
    passphrase: str,
) -> UUID:
    if service not in {"db", "test-db"}:
        raise ValueError("Select the live or test source database")
    validate_target(engine.url.render_as_string(hide_password=False), service)
    vault, signer = Vault.from_file(storage), load_signer(signing)
    config_raw = config.read_bytes()
    CustomerConfig.model_validate_json(config_raw)
    backup_id = uuid4()
    with Session(engine) as db, db.begin():
        staff = db.get(Staff, actor)
        if staff is None:
            raise PermissionError("Administrator required")
        require_permission(Role(staff.role), Action.MANAGE)
        db.add(Audit(actor_id=actor, action="backup_started", entity_id=backup_id))
    # Export the same repeatable-read snapshot used for counts and decryptability checks.
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        with connection.begin():
            revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
            if revision != "0004":
                raise ValueError("Backup requires supported schema 0004")
            snapshot = str(connection.scalar(text("SELECT pg_export_snapshot()")))
            with Session(bind=connection) as db:
                check_data(db, vault, signer)
            manifest: dict[str, Any] = {
                "format": 1,
                "schema": revision,
                "backup_id": str(backup_id),
                "actor_id": str(actor),
                "created_at": now().isoformat(),
                "counts": counts(connection),
            }
            dump = pg(
                service,
                "pg_dump",
                [
                    "--format=custom",
                    "--no-owner",
                    "--no-acl",
                    "--snapshot=" + snapshot,
                    *["--exclude-table-data=public." + t for t in sorted(EXCLUDED)],
                ],
            )
    files = {
        "database.dump": dump,
        "storage.key": storage.read_bytes(),
        "signing.key": signing.read_bytes(),
        "config.json": config_raw,
        "models.json": (ROOT / "assets/models/manifest.json").read_bytes(),
        "thresholds.json": (ROOT / "assets/models/thresholds.example.json").read_bytes(),
    }
    manifest["sha256"] = {name: hashlib.sha256(value).hexdigest() for name, value in files.items()}
    files["manifest.json"] = json.dumps(manifest, sort_keys=True).encode()
    write_private(output, seal(files, passphrase))
    with Session(engine) as db, db.begin():
        db.add(Audit(actor_id=actor, action="backup_created", entity_id=backup_id))
    return backup_id


def restore_backup(
    engine: Engine, archive: Path, destination: Path, passphrase: str
) -> dict[str, Any]:
    # No production-target flag exists: restore always uses the separate recovery service.
    validate_target(engine.url.render_as_string(hide_password=False), "restore-db")
    if destination.resolve().is_relative_to(ROOT) or destination.exists():
        raise ValueError("Use a new recovery directory outside the project")
    with archive.open("rb") as source:
        files = unseal(source.read(MAX_BYTES + 1), passphrase)
    manifest = json.loads(files["manifest.json"])
    if manifest["format"] != 1 or manifest["schema"] != "0004":
        raise ValueError("Unsupported recovery version; use the matching application build")
    if set(manifest["sha256"]) != set(files) - {"manifest.json"} or any(
        hashlib.sha256(files[name]).hexdigest() != digest
        for name, digest in manifest["sha256"].items()
    ):
        raise ValueError("Recovery contents do not match manifest")
    config = CustomerConfig.model_validate_json(files["config.json"])
    vault = Vault(files["storage.key"].strip())
    signer = Ed25519PrivateKey.from_private_bytes(files["signing.key"])
    actor, backup_id = UUID(manifest["actor_id"]), UUID(manifest["backup_id"])
    # Serialize restore attempts, then refuse any existing user tables, views or sequences.
    with engine.connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock(4912175)"))
        try:
            occupied = connection.scalar(
                text("""SELECT count(*) FROM pg_class c
                JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname <> 'information_schema'""")
            )
            if occupied:
                raise ValueError("Restore target is not empty; existing data was not changed")
            destination.mkdir(mode=0o700, parents=False)
            for name in [
                "storage.key",
                "signing.key",
                "config.json",
                "models.json",
                "thresholds.json",
            ]:
                write_private(destination / name, files[name])
            pg(
                "restore-db",
                "pg_restore",
                ["--single-transaction", "--no-owner", "--no-acl"],
                files["database.dump"],
            )
            connection.commit()
            with Session(engine) as db, db.begin():
                if counts(db.connection()) != manifest["counts"]:
                    raise ValueError(
                        "Restored counts differ; keep recovery offline for investigation"
                    )
                check_data(db, vault, signer)
                if db.scalar(select(func.count()).select_from(StaffSession)):
                    raise ValueError("Restored sessions must be empty")
                db.add(Audit(actor_id=actor, action="backup_restored", entity_id=backup_id))
            report = {
                "backup_id": str(backup_id),
                "schema": manifest["schema"],
                "counts_verified": True,
                "encrypted_records_verified": True,
                "coupon_signatures_verified": True,
                "sessions_revoked": True,
                "experimental_face": config.experimental_face,
            }
            write_private(destination / "verified.json", json.dumps(report, indent=2).encode())
            return report
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(4912175)"))
            connection.commit()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Encrypted backup or isolated recovery; no live restore"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    backup = commands.add_parser("backup")
    backup.add_argument("--username", required=True)
    backup.add_argument("--output", type=Path, required=True)
    backup.add_argument("--service", choices=["db", "test-db"], default="db")
    restore = commands.add_parser("restore")
    restore.add_argument("--archive", type=Path, required=True)
    restore.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    engine = None
    try:
        url = os.environ["DATABASE_URL" if args.command == "backup" else "RESTORE_DATABASE_URL"]
        validate_target(url, args.service if args.command == "backup" else "restore-db")
        engine = make_engine(url)
        if args.command == "backup":
            actor = authenticate(engine, args.username, getpass.getpass("Admin PIN: "))
            phrase = getpass.getpass("Backup passphrase (12+ characters): ")
            if phrase != getpass.getpass("Repeat backup passphrase: "):
                raise ValueError("Passphrases did not match")
            create_backup(
                engine,
                args.service,
                actor,
                Path(os.environ["EVENT_AUTH_KEY_FILE"]).expanduser(),
                Path(os.environ["EVENT_AUTH_SIGNING_KEY_FILE"]).expanduser(),
                Path(
                    os.environ.get("EVENT_AUTH_CONFIG", ROOT / "assets/config/customer_config.json")
                ),
                args.output.expanduser(),
                phrase,
            )
            print("Encrypted backup created. Keep passphrase separately; test an isolated restore.")
        else:
            restore_backup(
                engine,
                args.archive.expanduser(),
                args.directory.expanduser(),
                getpass.getpass("Backup passphrase: "),
            )
            print("Restore verified. Recovery stays offline; do not run two serving servers.")
    except (Exception, KeyboardInterrupt):
        # Database/crypto exceptions can expose SQL parameters; keep CLI output generic.
        parser.exit(
            1,
            "Recovery failed. Check credentials, paths, service, archive and empty target.\n",
        )
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    main()
