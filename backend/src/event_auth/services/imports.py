from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from event_auth.adapters.database.models import Member
from event_auth.api.schemas import ImportInput, MemberInput
from event_auth.core.members.rules import RuleViolation
from event_auth.modules.data_import.reader import read_rows
from event_auth.services.admin import AdminService


def import_rows(service: AdminService, data: ImportInput) -> dict[str, Any]:
    rows = read_rows(data.content, data.format)
    fields = {field.key for field in service.config.member_fields}
    view = service.event_view(data.event_id) if data.kind == "choices" and data.event_id else None
    if data.kind == "choices" and view is None:
        raise RuleViolation("event_required")
    errors = []
    seen: set[str] = set()
    with service.db.begin_nested() as batch:
        for number, row in enumerate(rows, start=2):
            try:
                with service.db.begin_nested():
                    code = row.get("member_code", "")
                    if not code or code in seen:
                        raise RuleViolation("duplicate_code")
                    seen.add(code)
                    if data.kind == "members":
                        if (
                            set(row) - {"default_option"}
                            != {"member_code", "name", "mobile", "is_minor"} | fields
                        ):
                            raise RuleViolation("invalid_columns")
                        if row["is_minor"].lower() not in {"true", "false"}:
                            raise RuleViolation("invalid_minor")
                        service.save_member(
                            MemberInput(
                                member_code=code,
                                name=row["name"],
                                mobile=row["mobile"],
                                default_option=row.get("default_option") or None,
                                is_minor=row["is_minor"].lower() == "true",
                                custom_fields={field: row[field] for field in fields},
                            )
                        )
                    else:
                        assert view is not None and data.event_id is not None
                        if set(row) != {"member_code"} | {s["code"] for s in view["slots"]}:
                            raise RuleViolation("invalid_columns")
                        member = service.db.scalar(select(Member).where(Member.member_code == code))
                        if member is None:
                            raise RuleViolation("member_not_found")
                        choices = {}
                        for slot in view["slots"]:
                            option = next(
                                (o for o in slot["options"] if o["code"] == row[slot["code"]]), None
                            )
                            if option is None:
                                raise RuleViolation("invalid_option")
                            choices[slot["id"]] = option["id"]
                        service.choose(data.event_id, member.id, choices)
            except (RuleViolation, ValidationError, IntegrityError) as exc:
                code = str(exc) if isinstance(exc, RuleViolation) else "invalid_or_duplicate_row"
                errors.append({"row": number, "code": code})
        if data.preview or errors:
            batch.rollback()
        else:
            service.audit("import_" + data.kind, data.event_id or service.actor.id)
    return {"rows": len(rows), "errors": errors, "committed": not data.preview and not errors}
