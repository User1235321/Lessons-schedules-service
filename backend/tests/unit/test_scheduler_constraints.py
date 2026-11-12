from datetime import time
from uuid import uuid4

import pytest

from app.domain.projects.settings import ProjectSettings
from app.domain.scheduling.constraints import (
    AllowedDaysParameters,
    ClockTimeParameters,
    ConstraintKind,
    ConstraintParameters,
    ConstraintScope,
    ConstraintScopeKind,
    EveryWeekParameters,
    ExtraConstraintSnapshot,
    FixedDayParameters,
    MinimumGapParameters,
    RelatedWorkloadParameters,
    TimeRangeParameters,
)
from app.domain.scheduling.problem import ScheduleProblem
from app.domain.scheduling.resources import WeeklyWindow
from app.domain.shared.errors import InvalidValue
from app.domain.shared.week import Weekday


@pytest.mark.parametrize(
    ("kind", "parameters"),
    [
        (ConstraintKind.MIN_START_TIME, ClockTimeParameters(time(9))),
        (ConstraintKind.MAX_END_TIME, ClockTimeParameters(time(18))),
        (ConstraintKind.ALLOWED_DAYS, AllowedDaysParameters((Weekday.MONDAY,))),
        (ConstraintKind.EVERY_WEEK, EveryWeekParameters()),
        (ConstraintKind.CONSECUTIVE, RelatedWorkloadParameters(uuid4())),
        (ConstraintKind.NOT_CONSECUTIVE, RelatedWorkloadParameters(uuid4())),
        (ConstraintKind.MIN_GAP, MinimumGapParameters(uuid4(), 30)),
        (ConstraintKind.BEFORE, RelatedWorkloadParameters(uuid4())),
        (ConstraintKind.FIXED_DAY, FixedDayParameters(Weekday.MONDAY)),
        (
            ConstraintKind.TIME_RANGE,
            TimeRangeParameters(
                (WeeklyWindow("ODD", Weekday.MONDAY, time(10), time(13)),)
            ),
        ),
    ],
)
def test_every_constraint_type_has_structured_parameters(
    kind: ConstraintKind, parameters: ConstraintParameters
) -> None:
    constraint = ExtraConstraintSnapshot(
        uuid4(), kind, ConstraintScope(ConstraintScopeKind.PROJECT), parameters
    )
    problem = ScheduleProblem(ProjectSettings.default(), constraints=(constraint,))

    assert problem.constraints[0].kind == kind
    assert problem.constraints[0].parameters == parameters


def test_constraint_rejects_wrong_parameters() -> None:
    with pytest.raises(InvalidValue):
        ExtraConstraintSnapshot(
            uuid4(),
            ConstraintKind.MIN_GAP,
            ConstraintScope(ConstraintScopeKind.WORKLOAD, uuid4()),
            ClockTimeParameters(time(12)),
        )


def test_constraint_scope_requires_consistent_resource_id() -> None:
    with pytest.raises(InvalidValue):
        ConstraintScope(ConstraintScopeKind.PROJECT, uuid4())
    with pytest.raises(InvalidValue):
        ConstraintScope(ConstraintScopeKind.GROUP)


def test_minimum_gap_must_be_positive() -> None:
    with pytest.raises(InvalidValue):
        MinimumGapParameters(uuid4(), 0)
