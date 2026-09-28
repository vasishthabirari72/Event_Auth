import pytest
from event_auth.core.members.rules import (
    Consent,
    RuleViolation,
    ensure_editable,
    validate_choices,
    validate_consent,
    validate_pin,
)


@pytest.mark.parametrize(
    "minor,consent",
    [
        (False, Consent("self", "", "events", "v1")),
        (True, Consent("guardian", "Test Guardian", "events", "v1")),
    ],
)
def test_valid_consent(minor, consent):
    validate_consent(minor, consent)


@pytest.mark.parametrize(
    "minor,consent",
    [
        (False, Consent("other", "", "events", "v1")),
        (True, Consent("self", "", "events", "v1")),
        (True, Consent("guardian", " ", "events", "v1")),
        (False, Consent("self", "", "", "v1")),
        (False, Consent("self", "", "events", "")),
    ],
)
def test_consent_rejects_missing_authority_or_purpose(minor, consent):
    with pytest.raises(RuleViolation):
        validate_consent(minor, consent)


@pytest.mark.parametrize("pin", ["12345", "1234567890123", "１２３４５６", "secret", "123 45"])
def test_pin_format(pin):
    with pytest.raises(RuleViolation):
        validate_pin(pin)
    validate_pin("123456")


def test_choices_and_closed_event():
    for status in ("DRAFT", "READY", "LIVE"):
        ensure_editable(status)
    with pytest.raises(RuleViolation):
        ensure_editable("CLOSED")
    validate_choices({"s"}, {"s": "o"}, {"s": {"o"}})
    with pytest.raises(RuleViolation):
        validate_choices({"s"}, {}, {"s": {"o"}})
    with pytest.raises(RuleViolation):
        validate_choices({"s"}, {"s": "foreign"}, {"s": {"o"}})
