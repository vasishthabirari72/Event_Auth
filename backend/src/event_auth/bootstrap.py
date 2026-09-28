import argparse
import getpass
import os
from pathlib import Path

from cryptography.fernet import Fernet
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from event_auth.adapters.crypto import Vault, pin_hash
from event_auth.adapters.database.models import Audit, Member, Staff
from event_auth.adapters.database.session import make_engine


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create the first local administrator; no default PIN."
    )
    parser.add_argument("--username", required=True)
    args = parser.parse_args()
    from event_auth.api.schemas import LoginInput

    pin = getpass.getpass("Choose a 6–12 digit admin PIN: ")
    if pin != getpass.getpass("Repeat PIN: "):
        parser.error("PINs did not match")
    from pydantic import ValidationError

    try:
        data = LoginInput(username=args.username, pin=pin)
    except ValidationError:
        parser.error("Use a lowercase staff username and a 6–12 digit PIN")
    path = Path(os.environ["EVENT_AUTH_KEY_FILE"]).expanduser().resolve()
    project = Path(__file__).resolve().parents[3]
    if not path.is_absolute() or path.is_relative_to(project):
        parser.error("Keep the encryption key outside the project directory")
    engine = make_engine(os.environ["DATABASE_URL"])
    try:
        with Session(engine) as db, db.begin():
            from event_auth.services.auth import lock

            lock(db, "bootstrap")
            if db.scalar(select(func.count()).select_from(Staff)):
                parser.error("An administrator already exists; use authenticated staff management")
            if not path.exists():
                if db.scalar(select(func.count()).select_from(Member)):
                    parser.error("Existing data requires its original encryption key")
                path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, "wb") as key_file:
                    key_file.write(Fernet.generate_key())
            Vault.from_file(path)
            staff = Staff(username=data.username, role="admin", pin_hash=pin_hash(data.pin))
            db.add(staff)
            db.flush()
            db.add(Audit(actor_id=staff.id, action="staff_bootstrap", entity_id=staff.id))
        print("Administrator created. Start the local server and sign in.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
