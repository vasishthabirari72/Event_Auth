from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LoginInput(Input):
    username: str = Field(min_length=1, max_length=40, pattern=r"^[a-z0-9_-]+$")
    pin: str = Field(min_length=6, max_length=12, pattern=r"^[0-9]+$")


class StaffInput(LoginInput):
    role: Literal["admin", "checkin", "counter"]


class PinInput(Input):
    pin: str = Field(min_length=6, max_length=12, pattern=r"^[0-9]+$")


class SearchInput(Input):
    query: str = Field(default="", max_length=160)


class MemberInput(Input):
    name: str = Field(min_length=1, max_length=120)
    mobile: str = Field(default="", max_length=32)
    is_minor: bool = False
    default_option: str | None = Field(default=None, min_length=1, max_length=80)
    custom_fields: dict[str, str] = Field(default_factory=dict)
    member_code: str | None = Field(default=None, pattern=r"^[A-Z0-9-]{3,24}$")
    revision: int = Field(default=1, ge=1)


class ConsentInput(Input):
    given_by: Literal["self", "guardian"]
    guardian_name: str = Field(default="", max_length=120)
    text_version: str = Field(min_length=1, max_length=64)
    agreed: Literal[True]


class FrameInput(Input):
    consent_id: UUID
    frame: str = Field(min_length=1, max_length=2_000_000)


class EnrollmentInput(Input):
    consent_id: UUID
    frames: list[str] = Field(min_length=3, max_length=3)
    reviewed_duplicate_ids: list[UUID] = Field(default_factory=list, max_length=100)


class OptionInput(Input):
    code: str = Field(pattern=r"^[A-Z0-9_-]{1,24}$")
    label: str = Field(min_length=1, max_length=80)


class SlotInput(OptionInput):
    options: list[OptionInput] = Field(min_length=1, max_length=12)


class CounterInput(Input):
    label: str = Field(min_length=1, max_length=80)
    serves: list[str] = Field(min_length=1, max_length=72)


class EventInput(Input):
    name: str = Field(min_length=1, max_length=120)
    date: date
    venue: str = Field(default="", max_length=160)
    slots: list[SlotInput] = Field(min_length=1, max_length=6)
    counters: list[CounterInput] = Field(min_length=1, max_length=2)
    revision: int = Field(default=1, ge=1)


class ChoiceInput(Input):
    member_id: UUID
    choices: dict[str, str]


class ImportInput(Input):
    kind: Literal["members", "choices"]
    format: Literal["csv", "xlsx"]
    content: str = Field(min_length=1, max_length=3_000_000)
    event_id: UUID | None = None
    preview: bool = True
