import base64
import csv
import hmac
import io
from collections.abc import Iterator
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete
from sqlalchemy.orm import Session

from event_auth.adapters.crypto import token_hash
from event_auth.adapters.database.models import Staff, StaffSession, now
from event_auth.api.schemas import (
    ChoiceInput,
    ConsentInput,
    EnrollmentInput,
    EventInput,
    FrameInput,
    ImportInput,
    LoginInput,
    MemberInput,
    PinInput,
    SearchInput,
    StaffInput,
)
from event_auth.services.admin import AdminService
from event_auth.services.auth import login, reset_pin
from event_auth.services.enrollment import Enrollment
from event_auth.services.imports import import_rows

router = APIRouter(prefix="/api")


def database(request: Request) -> Iterator[Session]:
    factory = getattr(request.app.state, "sessions", None)
    if factory is None:
        raise HTTPException(503, "setup_required")
    with factory() as session:
        with session.begin():
            yield session


DB = Annotated[Session, Depends(database, scope="function")]


def session_identity(request: Request, db: DB) -> StaffSession:
    value = db.get(StaffSession, token_hash(request.cookies.get("event_auth_session", "")))
    if value is None or value.expires_at <= now():
        raise HTTPException(401, "login_required")
    if request.method not in {"GET", "HEAD"} and not hmac.compare_digest(
        request.headers.get("X-CSRF-Token", ""), value.csrf
    ):
        raise HTTPException(403, "invalid_session")
    return value


Identity = Annotated[StaffSession, Depends(session_identity, scope="function")]


def actor(identity: Identity, db: DB) -> Staff:
    staff = db.get(Staff, identity.staff_id)
    if staff is None:
        raise HTTPException(401, "login_required")
    return staff


Actor = Annotated[Staff, Depends(actor, scope="function")]


def service(request: Request, db: DB, staff: Actor) -> AdminService:
    return AdminService(db, staff, request.app.state.vault, request.app.state.config)


Admin = Annotated[AdminService, Depends(service, scope="function")]


@router.post("/auth/login")
def sign_in(data: LoginInput, request: Request, response: Response, db: DB) -> dict[str, str]:
    result = login(db, data.username, data.pin, request.client.host if request.client else "local")
    if result is None:
        # Persist failed-attempt counters even though the HTTP operation is rejected.
        db.commit()
        raise HTTPException(401, "login_failed")
    value, token = result
    response.set_cookie(
        "event_auth_session",
        token,
        httponly=True,
        samesite="strict",
        secure=request.app.state.secure_cookie,
        max_age=8 * 3600,
        path="/",
    )
    staff = db.get(Staff, value.staff_id)
    assert staff is not None
    return {"id": str(staff.id), "username": staff.username, "role": staff.role, "csrf": value.csrf}


@router.get("/auth/session")
def current(identity: Identity, staff: Actor) -> dict[str, str]:
    return {
        "id": str(staff.id),
        "username": staff.username,
        "role": staff.role,
        "csrf": identity.csrf,
    }


@router.post("/auth/logout")
def sign_out(response: Response, db: DB, identity: Identity) -> dict[str, bool]:
    db.execute(delete(StaffSession).where(StaffSession.token_hash == identity.token_hash))
    response.delete_cookie("event_auth_session", path="/")
    return {"ok": True}


@router.get("/config")
def config(admin: Admin) -> dict[str, Any]:
    return admin.config.model_dump()


@router.get("/staff")
def staff_list(admin: Admin) -> list[dict[str, str]]:
    return admin.staff()


@router.post("/staff")
def staff_add(data: StaffInput, admin: Admin) -> dict[str, str]:
    return admin.add_staff(data)


@router.post("/staff/{staff_id}/pin")
def staff_reset(staff_id: UUID, data: PinInput, admin: Admin) -> dict[str, bool]:
    reset_pin(admin.db, admin.actor, staff_id, data.pin)
    return {"ok": True}


@router.get("/members")
def members(admin: Admin) -> list[dict[str, Any]]:
    return admin.members()


@router.post("/members/search")
def search_members(data: SearchInput, admin: Admin) -> list[dict[str, Any]]:
    return admin.members(data.query)


@router.get("/members/{member_id}")
def member_detail(member_id: UUID, admin: Admin) -> dict[str, Any]:
    return admin.member_view(admin.member(member_id))


@router.post("/members")
def add_member(data: MemberInput, admin: Admin) -> dict[str, Any]:
    return admin.save_member(data)


@router.put("/members/{member_id}")
def edit_member(member_id: UUID, data: MemberInput, admin: Admin) -> dict[str, Any]:
    return admin.save_member(data, member_id)


@router.delete("/members/{member_id}")
def delete_member(member_id: UUID, admin: Admin) -> dict[str, bool]:
    admin.delete_member(member_id)
    return {"ok": True}


@router.post("/members/{member_id}/consents")
def consent(member_id: UUID, data: ConsentInput, admin: Admin) -> dict[str, str]:
    return admin.consent(member_id, data)


@router.delete("/members/{member_id}/consents")
def withdraw(member_id: UUID, admin: Admin) -> dict[str, bool]:
    admin.withdraw(member_id)
    return {"ok": True}


@router.get("/members/{member_id}/photo")
def photo(member_id: UUID, admin: Admin) -> Response:
    member = admin.member(member_id)
    if member.thumbnail is None:
        raise HTTPException(404, "not_found")
    return Response(base64.b64decode(admin.vault.open(member.thumbnail)), media_type="image/jpeg")


@router.post("/members/{member_id}/face/check")
def face_check(
    member_id: UUID, data: FrameInput, request: Request, admin: Admin
) -> dict[str, bool]:
    request.app.state.enrollment.check(admin, member_id, data.consent_id, data.frame)
    return {"ok": True}


@router.post("/members/{member_id}/face")
def face_save(
    member_id: UUID, data: EnrollmentInput, request: Request, admin: Admin
) -> dict[str, Any]:
    enrollment: Enrollment = request.app.state.enrollment
    return enrollment.save(
        admin, member_id, data.consent_id, data.frames, data.reviewed_duplicate_ids
    )


@router.get("/events")
def events(admin: Admin) -> list[dict[str, Any]]:
    return admin.events()


@router.post("/events")
def add_event(data: EventInput, admin: Admin) -> dict[str, Any]:
    return admin.save_event(data)


@router.put("/events/{event_id}")
def edit_event(event_id: UUID, data: EventInput, admin: Admin) -> dict[str, Any]:
    return admin.save_event(data, event_id)


@router.get("/events/{event_id}")
def event(event_id: UUID, admin: Admin) -> dict[str, Any]:
    return admin.event_view(event_id)


@router.post("/events/{event_id}/choices")
def choices(event_id: UUID, data: ChoiceInput, admin: Admin) -> dict[str, bool]:
    admin.choose(event_id, data.member_id, data.choices)
    return {"ok": True}


@router.get("/events/{event_id}/members/{member_id}/choices")
def member_choices(event_id: UUID, member_id: UUID, admin: Admin) -> dict[str, Any]:
    return admin.choice_view(event_id, member_id)


@router.post("/events/{event_id}/defaults")
def apply_defaults(event_id: UUID, admin: Admin) -> dict[str, Any]:
    admin.apply_defaults(event_id)
    return admin.event_view(event_id)


@router.post("/events/{event_id}/ready")
def ready(event_id: UUID, admin: Admin) -> dict[str, bool]:
    admin.ready(event_id)
    return {"ok": True}


@router.get("/events/{event_id}/counts.csv")
def counts(event_id: UUID, admin: Admin) -> Response:
    view = admin.event_view(event_id)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["slot_code", "option_code", "count"])
    for slot in view["slots"]:
        for option in slot["options"]:
            writer.writerow([slot["code"], option["code"], option["count"]])
    admin.audit("counts_export", event_id)
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="counts.csv"'},
    )


@router.post("/imports")
def imports(data: ImportInput, admin: Admin) -> dict[str, Any]:
    return import_rows(admin, data)


@router.get("/imports/template.csv")
def template(admin: Admin, event_id: UUID | None = None) -> Response:
    fields = (
        ["member_code"] + [s["code"] for s in admin.event_view(event_id)["slots"]]
        if event_id
        else ["member_code", "name", "mobile", "is_minor", "default_option"]
        + [field.key for field in admin.config.member_fields]
    )
    output = io.StringIO()
    csv.writer(output).writerow(fields)
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="import-template.csv"'},
    )
