import csv
import io
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import Field

from event_auth.adapters.qr import decode_qr
from event_auth.api.admin_routes import DB, Actor
from event_auth.api.schemas import Input, SearchInput
from event_auth.services.counter import CounterService

router = APIRouter(prefix="/api/counter")


def service(request: Request, db: DB, actor: Actor) -> CounterService:
    state = request.app.state
    return CounterService(db, actor, state.vault, state.config, state.signer)


CounterApp = Annotated[CounterService, Depends(service, scope="function")]


class RedeemInput(Input):
    counter_id: UUID
    slot_id: UUID
    qr: str = Field(min_length=1, max_length=2000)
    request_id: UUID


class LookupInput(Input):
    counter_id: UUID
    slot_id: UUID
    coupon_id: UUID
    request_id: UUID
    confirmed: Literal[True]


class ReasonInput(Input):
    reason: str = Field(min_length=1, max_length=256)
    request_id: UUID
    confirmed: Literal[True]


class CloseInput(Input):
    request_id: UUID
    confirmed: Literal[True]


class QrInput(Input):
    frame: str = Field(min_length=1, max_length=2_000_000)


@router.get("/settings")
def settings(counter: CounterApp) -> dict[str, Any]:
    return {
        "result_seconds": counter.config.counter_result_seconds,
        "sounds": counter.config.counter_sounds,
    }


@router.get("/events")
def catalog(counter: CounterApp) -> list[dict[str, Any]]:
    return counter.catalog()


@router.post("/decode")
def decode(data: QrInput, counter: CounterApp) -> dict[str, str | None]:
    return {"qr": decode_qr(data.frame)}


@router.post("/redeem")
def redeem(data: RedeemInput, counter: CounterApp) -> dict[str, Any]:
    return counter.redeem(data.counter_id, data.slot_id, data.qr, data.request_id)


@router.post("/lookup-redeem")
def lookup_redeem(data: LookupInput, counter: CounterApp) -> dict[str, Any]:
    return counter.redeem(data.counter_id, data.slot_id, "", data.request_id, data.coupon_id)


@router.post("/events/{event_id}/lookup")
def lookup(event_id: UUID, data: SearchInput, counter: CounterApp) -> list[dict[str, Any]]:
    return counter.lookup(event_id, data.query)


@router.post("/coupons/{coupon_id}/replace")
def replace(coupon_id: UUID, data: ReasonInput, counter: CounterApp) -> dict[str, Any]:
    return counter.replace(coupon_id, data.reason, data.request_id)


@router.post("/coupons/{coupon_id}/void")
def void(coupon_id: UUID, data: ReasonInput, counter: CounterApp) -> dict[str, Any]:
    return counter.replace(coupon_id, data.reason, data.request_id, void_only=True)


@router.post("/events/{event_id}/close")
def close(event_id: UUID, data: CloseInput, counter: CounterApp) -> dict[str, Any]:
    return counter.close(event_id, data.request_id)


@router.get("/events/{event_id}/dashboard")
def dashboard(event_id: UUID, counter: CounterApp) -> dict[str, Any]:
    return counter.dashboard(event_id)


@router.get("/events/{event_id}/counts.csv")
def counts(event_id: UUID, counter: CounterApp) -> Response:
    data = counter.dashboard(event_id)
    output = io.StringIO()
    writer = csv.writer(output)
    # Validated codes and numbers only: free-text labels may contain formulas.
    writer.writerow(["slot_code", "option_code", "issued", "served"])
    for row in data["options"]:
        writer.writerow([row["slot_code"], row["option_code"], row["issued"], row["served"]])
    counter.audit("counts_export", event_id, [])
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="event-counts.csv"'},
    )
