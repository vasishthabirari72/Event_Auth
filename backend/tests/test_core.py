import math
from uuid import uuid4

import pytest
from event_auth.core.face.contracts import Band, Template
from event_auth.core.face.matching import Thresholds, identify, normalize
from event_auth.core.security.roles import Action, Role, require_permission


@pytest.mark.parametrize("vector", [(), (0.0, 0.0), (math.nan,), (math.inf,)])
def test_invalid_embeddings_rejected(vector):
    with pytest.raises(ValueError):
        normalize(vector)


def test_match_filters_scope_version_and_aggregates_per_member():
    a, b = uuid4(), uuid4()
    templates = [Template(a, "v1", (1.0, 0.0)), Template(b, "v2", (0.0, 1.0))]
    result = identify((1.0, 0.0), templates, {a, b}, "v1", Thresholds(0.4, 0.8))
    assert result.member_id == a and result.band == Band.HIGH
    assert identify((1.0, 0.0), templates, {b}, "v1", Thresholds(0.4, 0.8)).member_id is None
    assert identify((0.0, 1.0), templates, {a}, "v1", Thresholds(0.4, 0.8)).band == Band.NO_MATCH
    templates.append(Template(a, "v1", (0.0, 1.0)))
    assert identify((0.0, 1.0), templates, {a}, "v1", Thresholds(0.4, 0.8)).band == Band.HIGH


def test_medium_and_ties_require_review():
    a, b = uuid4(), uuid4()
    templates = [Template(a, "v1", (0.6, 0.8))]
    assert identify((1.0, 0.0), templates, {a}, "v1", Thresholds(0.4, 0.8)).band == Band.MEDIUM
    templates.append(Template(b, "v1", (0.6, 0.8)))
    assert identify((1.0, 0.0), templates, {a, b}, "v1", Thresholds(0.4, 0.8)).member_id is None


def test_dimension_mismatch():
    member = uuid4()
    with pytest.raises(ValueError):
        identify((1.0,), [Template(member, "v1", (1.0, 0.0))], {member}, "v1", Thresholds(0.4, 0.8))


@pytest.mark.parametrize("values", [(0.8, 0.4), (0.8, 0.8), (-2, 0.5), (0.4, 2), (math.nan, 0.8)])
def test_invalid_thresholds(values):
    with pytest.raises(ValueError):
        Thresholds(*values)


@pytest.mark.parametrize("role", list(Role))
@pytest.mark.parametrize("action", list(Action))
def test_permissions(role, action):
    permitted = role == Role.ADMIN or (role, action) in {
        (Role.CHECKIN, Action.CHECK_IN),
        (Role.COUNTER, Action.REDEEM),
    }
    if permitted:
        require_permission(role, action)
    else:
        with pytest.raises(PermissionError):
            require_permission(role, action)
