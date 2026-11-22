from datetime import time
from uuid import UUID

import pytest

from app.domain.projects.settings import DurationMode, ProjectSettings, StudyCycle, TimeMode
from app.domain.scheduling.constraints import (
    AllowedDaysParameters,
    ClockTimeParameters,
    ConstraintKind,
    ConstraintScope,
    ConstraintScopeKind,
    EveryWeekParameters,
    ExtraConstraintSnapshot,
    FixedDayParameters,
    MinimumGapParameters,
    RelatedWorkloadParameters,
    TimeRangeParameters,
)
from app.domain.scheduling.job import ResultOptions
from app.domain.scheduling.problem import (
    ScheduleProblem,
    WorkloadSnapshot,
    WorkloadTarget,
    WorkloadTargetKind,
)
from app.domain.scheduling.resources import (
    GroupSnapshot,
    SubgroupSnapshot,
    SubjectSnapshot,
    TeacherSnapshot,
    TeachingCapability,
    WeeklyWindow,
)
from app.domain.scheduling.schedule import LessonFormat
from app.domain.scheduling.solver import SolverStatus
from app.domain.shared.week import Weekday
from app.scheduling.solver import FeasibleScheduleSolver

SUBJECT = UUID(int=1)
TEACHER = UUID(int=2)
GROUP = UUID(int=3)
OTHER_GROUP = UUID(int=4)
SUBGROUP = UUID(int=5)
FIRST = UUID(int=11)
SECOND = UUID(int=12)
THIRD = UUID(int=13)
MONDAY = Weekday.MONDAY
TUESDAY = Weekday.TUESDAY


class RecordingControl:
    def __init__(self) -> None:
        self.progress = []

    def is_cancel_requested(self) -> bool:
        return False

    def report_progress(self, progress) -> None:
        self.progress.append(progress)


def workload(
    identifier: UUID = FIRST,
    occurrences: int = 1,
    target: UUID = GROUP,
    kind: WorkloadTargetKind = WorkloadTargetKind.GROUP,
) -> WorkloadSnapshot:
    return WorkloadSnapshot(
        identifier,
        WorkloadTarget(kind, target),
        SUBJECT,
        "LECTURE",
        LessonFormat.REMOTE,
        occurrences,
        1,
    )


def constraint(
    kind: ConstraintKind,
    parameters,
    source: UUID | None = FIRST,
    identifier: int = 100,
    scope_kind: ConstraintScopeKind | None = None,
) -> ExtraConstraintSnapshot:
    scope = ConstraintScope(
        scope_kind
        or (ConstraintScopeKind.PROJECT if source is None else ConstraintScopeKind.WORKLOAD),
        source,
    )
    return ExtraConstraintSnapshot(UUID(int=identifier), kind, scope, parameters)


def problem(
    *,
    workloads: tuple[WorkloadSnapshot, ...] = (workload(),),
    constraints: tuple[ExtraConstraintSnapshot, ...] = (),
    groups: tuple[GroupSnapshot, ...] = (GroupSnapshot(GROUP, "А", 20),),
    subgroups: tuple[SubgroupSnapshot, ...] = (),
) -> ScheduleProblem:
    windows = (
        WeeklyWindow("ANY", MONDAY, time(8), time(13)),
        WeeklyWindow("ANY", TUESDAY, time(8), time(13)),
    )
    return ScheduleProblem(
        settings=ProjectSettings(
            StudyCycle((MONDAY, TUESDAY), (MONDAY, TUESDAY)),
            TimeMode.hour_start(),
            DurationMode.uniform(60),
        ),
        subjects=(SubjectSnapshot(SUBJECT, "Математика"),),
        teachers=(TeacherSnapshot(
            TEACHER, "Преподаватель", (TeachingCapability(SUBJECT, "LECTURE"),), windows
        ),),
        groups=groups,
        subgroups=subgroups,
        workloads=workloads,
        constraints=constraints,
    )


def solve(source: ScheduleProblem):
    return FeasibleScheduleSolver().solve(source, ResultOptions(), RecordingControl())


def test_minimum_start_and_maximum_end_apply_together() -> None:
    source = problem(constraints=(
        constraint(ConstraintKind.MIN_START_TIME, ClockTimeParameters(time(9)), identifier=100),
        constraint(ConstraintKind.MAX_END_TIME, ClockTimeParameters(time(10)), identifier=101),
    ))
    result = solve(source)

    assert result.status is SolverStatus.SOLVED
    entry = result.variants[0].entries[0]
    assert (entry.start_time, entry.end_time) == (time(9), time(10))


def test_allowed_days_and_time_ranges_are_intersected() -> None:
    source = problem(constraints=(
        constraint(ConstraintKind.ALLOWED_DAYS, AllowedDaysParameters((TUESDAY,))),
        constraint(
            ConstraintKind.TIME_RANGE,
            TimeRangeParameters((WeeklyWindow("ANY", TUESDAY, time(10), time(12)),)),
            identifier=101,
        ),
    ))
    result = solve(source)

    assert result.status is SolverStatus.SOLVED
    entry = result.variants[0].entries[0]
    assert (entry.weekday, entry.start_time) == (TUESDAY, time(10))


def test_fixed_day_can_select_a_specific_week() -> None:
    source = problem(constraints=(
        constraint(ConstraintKind.FIXED_DAY, FixedDayParameters(TUESDAY, "EVEN")),
    ))
    entry = solve(source).variants[0].entries[0]

    assert (entry.week, entry.weekday) == ("EVEN", TUESDAY)


def test_every_week_distributes_two_occurrences() -> None:
    source = problem(
        workloads=(workload(occurrences=2),),
        constraints=(constraint(ConstraintKind.EVERY_WEEK, EveryWeekParameters()),),
    )
    result = solve(source)

    assert result.status is SolverStatus.SOLVED
    assert {entry.week for entry in result.variants[0].entries} == {"ODD", "EVEN"}


@pytest.mark.parametrize(
    ("kind", "parameters", "expected"),
    [
        (ConstraintKind.CONSECUTIVE, RelatedWorkloadParameters(SECOND), time(9)),
        (ConstraintKind.NOT_CONSECUTIVE, RelatedWorkloadParameters(SECOND), time(10)),
        (ConstraintKind.MIN_GAP, MinimumGapParameters(SECOND, 90), time(11)),
    ],
)
def test_related_lessons_respect_adjacency_and_gap(kind, parameters, expected) -> None:
    source = problem(
        workloads=(workload(FIRST), workload(SECOND)),
        constraints=(constraint(kind, parameters),),
    )
    result = solve(source)

    assert result.status is SolverStatus.SOLVED
    entries = {entry.workload_id: entry for entry in result.variants[0].entries}
    assert entries[FIRST].start_time == time(8)
    assert entries[SECOND].start_time == expected


def test_before_can_force_a_later_sorted_workload_to_run_first() -> None:
    source = problem(
        workloads=(workload(FIRST), workload(SECOND)),
        constraints=(
            constraint(ConstraintKind.BEFORE, RelatedWorkloadParameters(FIRST), SECOND),
        ),
    )
    result = solve(source)

    assert result.status is SolverStatus.SOLVED
    entries = {entry.workload_id: entry for entry in result.variants[0].entries}
    assert entries[SECOND].end_time <= entries[FIRST].start_time


def test_group_scope_also_applies_to_subgroup_but_not_other_groups() -> None:
    source = problem(
        workloads=(
            workload(FIRST),
            workload(SECOND, target=SUBGROUP, kind=WorkloadTargetKind.SUBGROUP),
            workload(THIRD, target=OTHER_GROUP),
        ),
        groups=(GroupSnapshot(GROUP, "А", 20), GroupSnapshot(OTHER_GROUP, "Б", 20)),
        subgroups=(SubgroupSnapshot(SUBGROUP, GROUP, "А1", 10),),
        constraints=(
            constraint(
                ConstraintKind.MIN_START_TIME,
                ClockTimeParameters(time(9)),
                GROUP,
                scope_kind=ConstraintScopeKind.GROUP,
            ),
        ),
    )
    result = solve(source)

    assert result.status is SolverStatus.SOLVED
    entries = {entry.workload_id: entry for entry in result.variants[0].entries}
    assert entries[FIRST].start_time >= time(9)
    assert entries[SECOND].start_time >= time(9)
    assert entries[THIRD].start_time == time(8)


def test_conflicting_adjacency_and_gap_returns_identified_constraints() -> None:
    source = problem(
        workloads=(workload(FIRST), workload(SECOND)),
        constraints=(
            constraint(ConstraintKind.CONSECUTIVE, RelatedWorkloadParameters(SECOND)),
            constraint(ConstraintKind.MIN_GAP, MinimumGapParameters(SECOND, 30), identifier=101),
        ),
    )
    result = solve(source)

    assert result.status is SolverStatus.INFEASIBLE
    assert set(result.diagnostics[0].constraint_ids) == {UUID(int=100), UUID(int=101)}


def test_every_week_conflicts_with_fixed_one_week() -> None:
    source = problem(
        workloads=(workload(occurrences=2),),
        constraints=(
            constraint(ConstraintKind.EVERY_WEEK, EveryWeekParameters()),
            constraint(
                ConstraintKind.FIXED_DAY, FixedDayParameters(MONDAY, "ODD"), identifier=101
            ),
        ),
    )
    result = solve(source)

    assert result.status is SolverStatus.INFEASIBLE
    assert set(result.diagnostics[0].constraint_ids) == {UUID(int=100), UUID(int=101)}


def test_disjoint_allowed_days_and_time_windows_are_infeasible() -> None:
    source = problem(constraints=(
        constraint(ConstraintKind.ALLOWED_DAYS, AllowedDaysParameters((TUESDAY,))),
        constraint(
            ConstraintKind.TIME_RANGE,
            TimeRangeParameters((WeeklyWindow("ANY", MONDAY, time(9), time(11)),)),
            identifier=101,
        ),
    ))
    result = solve(source)

    assert result.status is SolverStatus.INFEASIBLE
    assert result.diagnostics[0].workload_ids == (FIRST,)
    assert set(result.diagnostics[0].constraint_ids) == {UUID(int=100), UUID(int=101)}


def test_missing_related_workload_is_reported_without_exception() -> None:
    missing = UUID(int=999)
    source = problem(constraints=(
        constraint(ConstraintKind.BEFORE, RelatedWorkloadParameters(missing)),
    ))
    result = solve(source)

    assert result.status is SolverStatus.INFEASIBLE
    assert result.diagnostics[0].constraint_ids == (UUID(int=100),)


def test_same_workload_cannot_precede_itself() -> None:
    source = problem(constraints=(
        constraint(ConstraintKind.BEFORE, RelatedWorkloadParameters(FIRST)),
    ))
    result = solve(source)

    assert result.status is SolverStatus.INFEASIBLE
    assert result.diagnostics[0].workload_ids == (FIRST,)


def test_unconstrained_repeated_lessons_still_share_one_week() -> None:
    source = problem(workloads=(workload(occurrences=2),))
    result = solve(source)

    assert result.status is SolverStatus.SOLVED
    assert {entry.week for entry in result.variants[0].entries} == {"ODD"}
