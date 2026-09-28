import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FieldConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")
    label: str = Field(min_length=1, max_length=80)
    type: Literal["text", "select"] = "text"
    required: bool = False
    options: list[str] = Field(default_factory=list, max_length=30)


class CustomerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    organization: str = Field(min_length=1, max_length=120)
    primary_color: str = Field(default="#1E4FA3", pattern=r"^#[0-9A-Fa-f]{6}$")
    member_fields: list[FieldConfig] = Field(default_factory=list, max_length=20)
    entitlement_type: str = Field(default="food", min_length=1, max_length=40)
    default_options: list[str] = Field(default_factory=lambda: ["Veg", "Jain"])
    consent_version: str = Field(default="persistent-draft-v1", min_length=1, max_length=64)
    consent_purpose: str = Field(
        default="Identify members at community events with staff confirmation",
        min_length=1,
        max_length=256,
    )
    consent_text: str = (
        "Face registration is optional. We store encrypted face templates and one small "
        "reference photo for staff to identify you at events. You can use your member ID "
        "instead and ask an organizer to withdraw consent or delete your record. "
        "For anyone under 18, a parent or guardian must agree before capture."
    )
    experimental_face: bool = False
    counter_result_seconds: float = Field(default=2.5, ge=1, le=10)
    counter_sounds: bool = True

    @model_validator(mode="after")
    def unique_fields(self) -> "CustomerConfig":
        channels = [int(self.primary_color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        luminance = sum(
            c * weight for c, weight in zip(linear, (0.2126, 0.7152, 0.0722), strict=True)
        )
        if (0.956 + 0.05) / (luminance + 0.05) < 4.5:
            raise ValueError("Brand colour must contrast with white and near-white at 4.5:1")
        if (
            not self.default_options
            or len(self.default_options) > 12
            or any(not value.strip() or len(value) > 80 for value in self.default_options)
        ):
            raise ValueError("Provide 1–12 nonempty default option labels")
        keys = [field.key for field in self.member_fields]
        if len(keys) != len(set(keys)) or set(keys) & {"name", "mobile", "is_minor", "member_code"}:
            raise ValueError("Member field keys must be unique and not reserved")
        if any(field.type == "select" and not field.options for field in self.member_fields):
            raise ValueError("Select fields need options")
        return self


def load_config(path: Path) -> CustomerConfig:
    return CustomerConfig.model_validate(json.loads(path.read_text()))
