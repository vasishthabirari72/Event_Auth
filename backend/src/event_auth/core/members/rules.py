from dataclasses import dataclass


class RuleViolation(ValueError):
    """Stable error codes; never include personal data in errors."""


@dataclass(frozen=True)
class Consent:
    given_by: str
    guardian_name: str
    purpose: str
    text_version: str


def validate_consent(is_minor: bool, consent: Consent) -> None:
    if consent.given_by not in {"self", "guardian"}:
        raise RuleViolation("consent_required")
    if is_minor and consent.given_by != "guardian":
        raise RuleViolation("guardian_required")
    if consent.given_by == "guardian" and not consent.guardian_name.strip():
        raise RuleViolation("guardian_required")
    if not consent.purpose.strip() or not consent.text_version.strip():
        raise RuleViolation("consent_required")


def validate_pin(pin: str) -> None:
    if not pin.isascii() or not pin.isdigit() or not 6 <= len(pin) <= 12:
        raise RuleViolation("invalid_pin")


def ensure_editable(status: str) -> None:
    if status not in {"DRAFT", "READY", "LIVE"}:
        raise RuleViolation("event_closed")


def validate_choices(
    slot_ids: set[str], choices: dict[str, str], options: dict[str, set[str]]
) -> None:
    if set(choices) != slot_ids:
        raise RuleViolation("choose_each_slot")
    if any(option not in options.get(slot, set()) for slot, option in choices.items()):
        raise RuleViolation("invalid_option")
