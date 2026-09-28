"""Explicit, authenticated creation of obviously fake ID-only demo records."""

import argparse
import getpass
import os
from datetime import date
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from event_auth.adapters.crypto import Vault
from event_auth.adapters.database.models import Staff
from event_auth.adapters.database.session import make_engine
from event_auth.api.schemas import CounterInput, EventInput, MemberInput, OptionInput, SlotInput
from event_auth.config.settings import load_config
from event_auth.services.admin import AdminService
from event_auth.services.auth import login


def seed_demo(service: AdminService) -> dict[str, Any]:
    members = []
    fields = {
        field.key: field.options[0] if field.type == "select" else "TEST"
        for field in service.config.member_fields
    }
    for index in range(1, 13):
        members.append(
            service.save_member(
                MemberInput(
                    name=f"Test Member {index:02}",
                    member_code=f"DEMO-{index:03}",
                    custom_fields=fields,
                    is_minor=index == 12,
                )
            )
        )
    options = [
        OptionInput(code=f"O{i}", label=label)
        for i, label in enumerate(service.config.default_options, start=1)
    ]
    event = service.save_event(
        EventInput(
            name="Test Demo Event",
            date=date.today(),
            venue="Test Demo Venue",
            slots=[SlotInput(code="S1", label="Test Slot", options=options)],
            counters=[CounterInput(label="Test Counter", serves=["S1/" + o.code for o in options])],
        )
    )
    slot = event["slots"][0]
    for index, member in enumerate(members):
        service.choose(
            UUID(event["id"]),
            UUID(member["id"]),
            {slot["id"]: slot["options"][index % len(options)]["id"]},
        )
    return event


def main() -> None:
    parser = argparse.ArgumentParser(description="Add 12 fake ID-only members and one demo event.")
    parser.add_argument("--username", required=True)
    args = parser.parse_args()
    pin = getpass.getpass("Admin PIN: ")
    engine = make_engine(os.environ["DATABASE_URL"])
    try:
        with Session(engine) as db, db.begin():
            result = login(db, args.username, pin, "local-demo-cli")
            if result is None:
                db.commit()
                parser.error("Sign-in failed; repeated failures require a five-minute wait")
            session, _ = result
            staff = db.get(Staff, session.staff_id)
            assert staff is not None
            service = AdminService(
                db,
                staff,
                Vault.from_file(Path(os.environ["EVENT_AUTH_KEY_FILE"]).expanduser()),
                load_config(
                    Path(os.environ.get("EVENT_AUTH_CONFIG", "assets/config/customer_config.json"))
                ),
            )
            seed_demo(service)
            db.delete(session)
        print(
            "Created 12 fake ID-only members and one demo event. No face data or consent created."
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
