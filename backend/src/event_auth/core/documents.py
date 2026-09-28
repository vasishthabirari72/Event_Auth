from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CouponDocument:
    organization: str
    event: str
    slot: str
    option: str
    member_name: str
    member_code: str
    coupon_code: str
    issued_at: str
    qr: str


class DocumentOutput(Protocol):
    """Rendering never issues an entitlement; future printer adapters use this port."""

    def render(self, document: CouponDocument) -> bytes: ...
