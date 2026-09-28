import pytest
from event_auth.core.redemption import redemption_state


@pytest.mark.parametrize(
    ("event", "coupon", "scope", "serves", "active", "expected"),
    [
        ("LIVE", "ISSUED", True, True, True, "SERVE"),
        ("LIVE", "REDEEMED", True, True, True, "ALREADY_USED"),
        ("LIVE", "VOID", True, True, True, "CANCELLED"),
        ("CLOSED", "ISSUED", True, True, True, "EXPIRED"),
        ("LIVE", "EXPIRED", True, True, True, "EXPIRED"),
        ("LIVE", "ISSUED", False, True, True, "INVALID"),
        ("LIVE", "ISSUED", True, True, False, "INVALID"),
        ("READY", "ISSUED", True, True, True, "INVALID"),
        ("LIVE", "ISSUED", True, False, True, "WRONG_COUNTER"),
    ],
)
def test_redemption_rules(event, coupon, scope, serves, active, expected):
    assert redemption_state(event, coupon, scope, serves, active) == expected
