from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    CHECKIN = "checkin"
    COUNTER = "counter"


class Action(StrEnum):
    MANAGE = "manage"
    CHECK_IN = "check_in"
    REDEEM = "redeem"
    REDEEM_BY_LOOKUP = "redeem_by_lookup"


def require_permission(role: Role, action: Action) -> None:
    allowed = {
        Role.ADMIN: frozenset(Action),
        Role.CHECKIN: frozenset({Action.CHECK_IN}),
        Role.COUNTER: frozenset({Action.REDEEM}),
    }
    if action not in allowed.get(role, frozenset()):
        raise PermissionError("Action is not permitted")
