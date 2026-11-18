from uuid import uuid4

import pytest

from app.application.constraints.codec import (
    parameters_to_json,
    parse_parameters,
    scope_from_json,
    scope_to_json,
)
from app.domain.scheduling.constraints import ConstraintKind, ConstraintScope, ConstraintScopeKind
from app.domain.scheduling.problem import OptimizationCriterionSnapshot
from app.domain.shared.errors import InvalidValue


@pytest.mark.parametrize(
    ("kind", "parameters"),
    [
        ("MIN_START_TIME", {"time": "09:30"}),
        ("MAX_END_TIME", {"time": "18:00"}),
        ("ALLOWED_DAYS", {"days": ["MONDAY", "TUESDAY"]}),
        ("EVERY_WEEK", {}),
        ("CONSECUTIVE", {"workload_id": str(uuid4())}),
        ("NOT_CONSECUTIVE", {"workload_id": str(uuid4())}),
        ("MIN_GAP", {"workload_id": str(uuid4()), "minutes": 30}),
        ("BEFORE", {"workload_id": str(uuid4())}),
        ("FIXED_DAY", {"day": "MONDAY", "week": "EVEN"}),
        (
            "TIME_RANGE",
            {
                "windows": [
                    {"week": "ODD", "day": "MONDAY", "start": "09:00", "end": "12:00"}
                ]
            },
        ),
    ],
)
def test_every_parameter_type_roundtrips(kind: str, parameters: dict) -> None:
    parsed = parse_parameters(ConstraintKind(kind), parameters)

    assert parameters_to_json(parsed) == parameters
    assert parse_parameters(ConstraintKind(kind), parameters_to_json(parsed)) == parsed


@pytest.mark.parametrize(
    ("kind", "parameters"),
    [
        ("MIN_START_TIME", {"time": "25:15"}),
        ("MAX_END_TIME", {"time": "12:00", "extra": 1}),
        ("ALLOWED_DAYS", {"days": []}),
        ("ALLOWED_DAYS", {"days": ["MONDAY", "MONDAY"]}),
        ("EVERY_WEEK", {"days": ["MONDAY"]}),
        ("CONSECUTIVE", {"workload_id": "invalid"}),
        ("MIN_GAP", {"workload_id": str(uuid4()), "minutes": 0}),
        ("MIN_GAP", {"workload_id": str(uuid4()), "minutes": True}),
        ("FIXED_DAY", {"day": "MONDAY", "week": "THIRD"}),
        ("TIME_RANGE", {"windows": []}),
        (
            "TIME_RANGE",
            {
                "windows": [
                    {"week": "ODD", "day": "MONDAY", "start": "12:00", "end": "09:00"}
                ]
            },
        ),
    ],
)
def test_invalid_parameters_raise_domain_error(kind: str, parameters: dict) -> None:
    with pytest.raises(InvalidValue):
        parse_parameters(ConstraintKind(kind), parameters)


def test_scope_roundtrips_with_and_without_resource() -> None:
    for scope in (
        ConstraintScope(ConstraintScopeKind.PROJECT),
        ConstraintScope(ConstraintScopeKind.GROUP, uuid4()),
    ):
        assert scope_from_json(scope_to_json(scope)) == scope


def test_unknown_criterion_is_rejected() -> None:
    with pytest.raises(InvalidValue):
        OptimizationCriterionSnapshot("NOT_A_CRITERION", 1)
