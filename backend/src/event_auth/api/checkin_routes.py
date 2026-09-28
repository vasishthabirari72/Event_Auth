import base64
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import Field

from event_auth.api.admin_routes import DB, Actor
from event_auth.api.schemas import Input, SearchInput
from event_auth.services.checkin import CheckinService

router = APIRouter(prefix="/api/checkin")


def service(request: Request, db: DB, actor: Actor) -> CheckinService:
    state = request.app.state
    return CheckinService(
        db, actor, state.vault, state.config, state.enrollment, state.signer, state.document_output
    )


Checkin = Annotated[CheckinService, Depends(service, scope="function")]


class CaptureInput(Input):
    frame: str = Field(min_length=1, max_length=2_000_000)
    consent_confirmed: Literal[True]


class FallbackInput(Input):
    member_id: UUID


class ConfirmInput(Input):
    confirmed: Literal[True]


@router.get("/events")
def events(checkin: Checkin) -> list[dict[str, Any]]:
    return checkin.events()


@router.post("/events/{event_id}/start")
def start(event_id: UUID, checkin: Checkin) -> dict[str, bool]:
    checkin.start(event_id)
    return {"ok": True}


@router.post("/slots/{slot_id}/search")
def search(slot_id: UUID, data: SearchInput, checkin: Checkin) -> list[dict[str, Any]]:
    return checkin.search(slot_id, data.query)


@router.post("/slots/{slot_id}/face")
def face(slot_id: UUID, data: CaptureInput, checkin: Checkin) -> dict[str, Any]:
    return checkin.identify(slot_id, data.frame)


@router.post("/slots/{slot_id}/fallback")
def fallback(slot_id: UUID, data: FallbackInput, checkin: Checkin) -> dict[str, Any]:
    return {**checkin.prepare(slot_id, data.member_id, "fallback"), "band": "fallback"}


@router.get("/slots/{slot_id}/members/{member_id}/photo")
def photo(slot_id: UUID, member_id: UUID, checkin: Checkin) -> Response:
    return Response(base64.b64decode(checkin.photo(slot_id, member_id)), media_type="image/jpeg")


@router.post("/confirm/{ticket_id}")
def confirm(ticket_id: UUID, data: ConfirmInput, checkin: Checkin) -> dict[str, Any]:
    return checkin.confirm(ticket_id)


@router.post("/coupons/{coupon_id}/pdf")
def pdf(coupon_id: UUID, checkin: Checkin) -> Response:
    return Response(
        checkin.pdf(coupon_id),
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="event-coupon.pdf"',
        },
    )
