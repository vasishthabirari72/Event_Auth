from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from event_auth.adapters.crypto import Vault, pin_hash
from event_auth.adapters.database.models import (
    Audit,
    ConsentRecord,
    Counter,
    CounterOption,
    Coupon,
    Event,
    FaceTemplate,
    Member,
    Option,
    Registration,
    Selection,
    Slot,
    Staff,
)
from event_auth.api.schemas import ConsentInput, EventInput, MemberInput, StaffInput
from event_auth.config.settings import CustomerConfig
from event_auth.core.members.rules import (
    Consent,
    RuleViolation,
    ensure_editable,
    validate_choices,
    validate_consent,
)
from event_auth.core.security.roles import Action, Role, require_permission
from event_auth.modules.preferences import match_defaults


class AdminService:
    def __init__(self, db: Session, actor: Staff, vault: Vault, config: CustomerConfig) -> None:
        require_permission(Role(actor.role), Action.MANAGE)
        self.db, self.actor, self.vault, self.config = db, actor, vault, config

    def audit(self, action: str, entity_id: UUID, related: list[UUID] | None = None) -> None:
        self.db.add(
            Audit(
                actor_id=self.actor.id,
                action=action,
                entity_id=entity_id,
                related_ids=[str(value) for value in related or []],
            )
        )

    def member(self, member_id: UUID) -> Member:
        value = self.db.scalar(select(Member).where(Member.id == member_id).with_for_update())
        if value is None:
            raise LookupError("not_found")
        return value

    def member_view(self, value: Member) -> dict[str, Any]:
        return {
            "id": str(value.id),
            "member_code": value.member_code,
            "default_option": None,
            **self.vault.open(value.personal),
            "has_face": value.thumbnail is not None,
            "revision": value.revision,
        }

    def members(self, query: str = "") -> list[dict[str, Any]]:
        values = [
            self.member_view(value)
            for value in self.db.scalars(select(Member).order_by(Member.member_code))
        ]
        needle = query.casefold()
        return [
            value
            for value in values
            if not needle
            or any(
                needle in str(value[key]).casefold() for key in ("member_code", "name", "mobile")
            )
        ]

    def save_member(self, data: MemberInput, member_id: UUID | None = None) -> dict[str, Any]:
        fields = {field.key: field for field in self.config.member_fields}
        if set(data.custom_fields) - fields.keys():
            raise RuleViolation("invalid_fields")
        for key, field in fields.items():
            value = data.custom_fields.get(key, "").strip()
            if (
                len(value) > 160
                or (field.required and not value)
                or (value and field.type == "select" and value not in field.options)
            ):
                raise RuleViolation("invalid_fields")
        personal = data.model_dump(exclude={"member_code", "revision"})
        previous = self.vault.open(self.member(member_id).personal) if member_id else {}
        if member_id and "default_option" not in data.model_fields_set:
            personal["default_option"] = previous.get("default_option")
        preference = personal["default_option"]
        if preference and preference != previous.get("default_option"):
            matches = [
                option
                for option in self.config.default_options
                if option.strip().casefold() == preference.casefold()
            ]
            if len(matches) != 1:
                raise RuleViolation("invalid_default_option")
            personal["default_option"] = matches[0]

        if member_id:
            member = self.member(member_id)
            if member.revision != data.revision:
                raise RuleViolation("stale_record")
            if data.member_code and data.member_code != member.member_code:
                raise RuleViolation("member_code_immutable")
            if self.vault.open(member.personal)["is_minor"] != data.is_minor:
                self.withdraw(member_id)
            member.personal = self.vault.seal(personal)
            member.revision += 1
        else:
            member = Member(
                member_code=data.member_code or ("M-" + uuid4().hex[:10].upper()),
                personal=self.vault.seal(personal),
            )
            self.db.add(member)
        self.db.flush()
        self.audit("member_edit" if member_id else "member_register", member.id)
        return self.member_view(member)

    def delete_member(self, member_id: UUID) -> None:
        member = self.member(member_id)
        # Erase coupon snapshots too; retained rows contain only anonymous counts.
        self.db.execute(
            update(Coupon)
            .where(Coupon.member_id == member_id)
            .values(encrypted_document=None, encrypted_reason=None, member_id=None)
        )
        self.audit("member_delete", member.id)
        self.db.delete(member)

    def consent(self, member_id: UUID, data: ConsentInput) -> dict[str, str]:
        member = self.member(member_id)
        if data.text_version != self.config.consent_version:
            raise RuleViolation("consent_changed")
        consent = Consent(
            data.given_by, data.guardian_name, self.config.consent_purpose, data.text_version
        )
        validate_consent(self.vault.open(member.personal)["is_minor"], consent)
        record = ConsentRecord(
            member_id=member.id,
            given_by=data.given_by,
            guardian=self.vault.seal(data.guardian_name),
            purpose=consent.purpose,
            text_version=consent.text_version,
            captured_by=self.actor.id,
        )
        self.db.add(record)
        self.db.flush()
        self.audit("consent_record", record.id, [member.id])
        return {"id": str(record.id)}

    def withdraw(self, member_id: UUID) -> None:
        member = self.member(member_id)
        member.thumbnail = None
        self.db.execute(delete(FaceTemplate).where(FaceTemplate.member_id == member_id))
        for record in self.db.scalars(
            select(ConsentRecord).where(
                ConsentRecord.member_id == member_id, ConsentRecord.withdrawn.is_(False)
            )
        ):
            record.withdrawn = True
            self.audit("consent_withdraw", record.id, [member_id])

    def require_consent(self, member_id: UUID, consent_id: UUID) -> Member:
        member = self.member(member_id)
        record = self.db.get(ConsentRecord, consent_id)
        if record is None or record.member_id != member_id or record.withdrawn:
            raise RuleViolation("consent_required")
        validate_consent(
            self.vault.open(member.personal)["is_minor"],
            Consent(
                record.given_by,
                self.vault.open(record.guardian),
                record.purpose,
                record.text_version,
            ),
        )
        if record.text_version != self.config.consent_version:
            raise RuleViolation("consent_changed")
        return member

    def staff(self) -> list[dict[str, str]]:
        return [
            {"id": str(s.id), "username": s.username, "role": s.role}
            for s in self.db.scalars(select(Staff).order_by(Staff.username))
        ]

    def add_staff(self, data: StaffInput) -> dict[str, str]:
        value = Staff(username=data.username, role=data.role, pin_hash=pin_hash(data.pin))
        self.db.add(value)
        self.db.flush()
        self.audit("staff_create", value.id)
        return {"id": str(value.id), "username": value.username, "role": value.role}

    def event(self, event_id: UUID) -> Event:
        value = self.db.scalar(select(Event).where(Event.id == event_id).with_for_update())
        if value is None:
            raise LookupError("not_found")
        return value

    def events(self) -> list[dict[str, Any]]:
        return [
            {
                "id": str(e.id),
                "name": e.name,
                "date": e.date.isoformat(),
                "venue": e.venue,
                "status": e.status,
                "revision": e.revision,
            }
            for e in self.db.scalars(select(Event).order_by(Event.date.desc()))
        ]

    def save_event(self, data: EventInput, event_id: UUID | None = None) -> dict[str, Any]:
        if len({slot.code for slot in data.slots}) != len(data.slots):
            raise RuleViolation("duplicate_code")
        paths = {slot.code + "/" + option.code for slot in data.slots for option in slot.options}
        if any(len({o.code for o in s.options}) != len(s.options) for s in data.slots):
            raise RuleViolation("duplicate_code")
        served = {path for counter in data.counters for path in counter.serves}
        if served != paths:
            raise RuleViolation("counter_options")
        if event_id:
            event = self.event(event_id)
            if event.status != "DRAFT" or self.db.scalar(
                select(func.count())
                .select_from(Registration)
                .where(Registration.event_id == event_id)
            ):
                raise RuleViolation("event_structure_locked")
            if event.revision != data.revision:
                raise RuleViolation("stale_record")
            self.db.execute(delete(Counter).where(Counter.event_id == event_id))
            self.db.execute(delete(Slot).where(Slot.event_id == event_id))
            event.revision += 1
        else:
            event = Event()
            self.db.add(event)
        event.name, event.date, event.venue = data.name, data.date, data.venue
        self.db.flush()
        option_map: dict[str, UUID] = {}
        for source in data.slots:
            slot = Slot(event_id=event.id, code=source.code, label=source.label)
            self.db.add(slot)
            self.db.flush()
            for item in source.options:
                option = Option(
                    slot_id=slot.id,
                    code=item.code,
                    label=item.label,
                    entitlement_type=self.config.entitlement_type,
                )
                self.db.add(option)
                self.db.flush()
                option_map[source.code + "/" + item.code] = option.id
        for item_counter in data.counters:
            counter = Counter(event_id=event.id, label=item_counter.label)
            self.db.add(counter)
            self.db.flush()
            for path in set(item_counter.serves):
                self.db.add(CounterOption(counter_id=counter.id, option_id=option_map[path]))
        self.audit("event_edit" if event_id else "event_create", event.id)
        self.db.flush()
        if event_id is None:
            self.apply_defaults(event.id)
        return self.event_view(event.id)

    def event_view(self, event_id: UUID) -> dict[str, Any]:
        event = self.event(event_id)
        slots = list(
            self.db.scalars(select(Slot).where(Slot.event_id == event_id).order_by(Slot.created_at))
        )
        options = list(
            self.db.scalars(select(Option).where(Option.slot_id.in_([s.id for s in slots])))
        )
        registrations = list(
            self.db.scalars(select(Registration).where(Registration.event_id == event_id))
        )
        selections = list(
            self.db.scalars(
                select(Selection).where(
                    Selection.registration_id.in_([r.id for r in registrations])
                )
            )
        )
        return {
            "id": str(event.id),
            "name": event.name,
            "date": event.date.isoformat(),
            "venue": event.venue,
            "status": event.status,
            "revision": event.revision,
            "slots": [
                {
                    "id": str(s.id),
                    "code": s.code,
                    "label": s.label,
                    "options": [
                        {
                            "id": str(o.id),
                            "code": o.code,
                            "label": o.label,
                            "count": sum(c.option_id == o.id for c in selections),
                        }
                        for o in options
                        if o.slot_id == s.id
                    ],
                }
                for s in slots
            ],
            "registrations": [
                {
                    "member_id": str(r.member_id),
                    "needs_choice": sum(c.registration_id == r.id for c in selections)
                    != len(slots),
                    "choices": {
                        str(c.slot_id): str(c.option_id)
                        for c in selections
                        if c.registration_id == r.id
                    },
                }
                for r in registrations
            ],
            "counters": [
                {
                    "id": str(c.id),
                    "label": c.label,
                    "serves": [
                        str(o.option_id)
                        for o in self.db.scalars(
                            select(CounterOption).where(CounterOption.counter_id == c.id)
                        )
                    ],
                }
                for c in self.db.scalars(select(Counter).where(Counter.event_id == event_id))
            ],
        }

    def choice_view(self, event_id: UUID, member_id: UUID) -> dict[str, Any]:
        view = self.event_view(event_id)
        member = self.member(member_id)
        preference = self.vault.open(member.personal).get("default_option")
        choices = match_defaults(view["slots"], preference)
        for registration in view["registrations"]:
            if registration["member_id"] == str(member_id):
                choices.update(registration["choices"])
        return {"choices": choices, "default_option": preference}

    def apply_defaults(self, event_id: UUID) -> None:
        event = self.event(event_id)
        ensure_editable(event.status)
        view = self.event_view(event_id)
        registrations = {
            r.member_id: r
            for r in self.db.scalars(select(Registration).where(Registration.event_id == event_id))
        }
        saved = {r["member_id"]: r["choices"] for r in view["registrations"]}
        members = list(self.db.scalars(select(Member).order_by(Member.id).with_for_update()))
        for member in members:
            registration = registrations.get(member.id)
            if registration is None:
                registration = Registration(id=uuid4(), event_id=event_id, member_id=member.id)
                self.db.add(registration)
                self.db.flush()
                self.audit("event_member_add", registration.id, [event_id, member.id])
            choices = match_defaults(
                view["slots"], self.vault.open(member.personal).get("default_option")
            )
            for slot, option in choices.items():
                if slot in saved.get(str(member.id), {}):
                    continue
                selection = Selection(
                    id=uuid4(),
                    registration_id=registration.id,
                    slot_id=UUID(slot),
                    option_id=UUID(option),
                )
                self.db.add(selection)
                self.audit(
                    "selection_default",
                    selection.id,
                    [event_id, member.id, registration.id, UUID(slot), UUID(option)],
                )
        self.db.flush()

    def choose(self, event_id: UUID, member_id: UUID, choices: dict[str, str]) -> None:
        event = self.event(event_id)
        ensure_editable(event.status)
        self.member(member_id)
        view = self.event_view(event_id)
        choices = {**self.choice_view(event_id, member_id)["choices"], **choices}
        validate_choices(
            {s["id"] for s in view["slots"]},
            choices,
            {s["id"]: {o["id"] for o in s["options"]} for s in view["slots"]},
        )
        registration = self.db.scalar(
            select(Registration).where(
                Registration.event_id == event_id, Registration.member_id == member_id
            )
        )
        if registration is None:
            registration = Registration(event_id=event_id, member_id=member_id)
            self.db.add(registration)
            self.db.flush()
        self.db.execute(delete(Selection).where(Selection.registration_id == registration.id))
        for slot, option in choices.items():
            selection = Selection(
                registration_id=registration.id, slot_id=UUID(slot), option_id=UUID(option)
            )
            self.db.add(selection)
            self.db.flush()
            self.audit(
                "selection_change",
                selection.id,
                [event_id, member_id, registration.id, UUID(slot), UUID(option)],
            )

    def ready(self, event_id: UUID) -> None:
        event = self.event(event_id)
        if event.status != "DRAFT":
            raise RuleViolation("invalid_transition")
        if not self.db.scalar(
            select(func.count()).select_from(Registration).where(Registration.event_id == event_id)
        ):
            raise RuleViolation("no_registrations")
        if any(
            registration["needs_choice"]
            for registration in self.event_view(event_id)["registrations"]
        ):
            raise RuleViolation("choices_missing")
        event.status = "READY"
        self.audit("event_ready", event.id)
