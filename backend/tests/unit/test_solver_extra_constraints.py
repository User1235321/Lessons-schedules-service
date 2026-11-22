from datetime import time
from uuid import UUID

import pytest

from app.domain.projects.settings import DurationMode, ProjectSettings, StudyCycle, TimeMode
from app.domain.scheduling.constraint_validation import constraint_conflicts
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
from app.domain.scheduling.schedule import LessonFormat, ScheduleEntry
from app.domain.scheduling.solver import SolverStatus
from app.domain.shared.ids import ScheduleEntryId
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


@pytest.mark.parametrize(
    ("kind", "parameters", "expected"),
    [
        (ConstraintKind.CONSECUTIVE, RelatedWorkloadParameters(FIRST), time(9)),
        (ConstraintKind.NOT_CONSECUTIVE, RelatedWorkloadParameters(FIRST), time(10)),
        (ConstraintKind.MIN_GAP, MinimumGapParameters(FIRST, 60), time(10)),
    ],
)
def test_related_constraint_can_target_the_same_repeated_workload(
    kind, parameters, expected
) -> None:
    source = problem(
        workloads=(workload(occurrences=2),),
        constraints=(constraint(kind, parameters),),
    )
    result = solve(source)

    assert result.status is SolverStatus.SOLVED
    assert [entry.start_time for entry in result.variants[0].entries] == [
        time(8), expected
    ]


def test_mutually_opposite_before_constraints_are_infeasible() -> None:
    source = problem(
        workloads=(workload(FIRST), workload(SECOND)),
        constraints=(
            constraint(ConstraintKind.BEFORE, RelatedWorkloadParameters(SECOND)),
            constraint(
                ConstraintKind.BEFORE, RelatedWorkloadParameters(FIRST),
                source=SECOND, identifier=101,
            ),
        ),
    )
    result = solve(source)

    assert result.status is SolverStatus.INFEASIBLE
    assert set(result.diagnostics[0].constraint_ids) == {UUID(int=100), UUID(int=101)}


def test_every_week_requires_at_least_two_occurrences() -> None:
    source = problem(
        constraints=(constraint(ConstraintKind.EVERY_WEEK, EveryWeekParameters()),),
    )
    result = solve(source)

    assert result.status is SolverStatus.INFEASIBLE
    assert result.diagnostics[0].workload_ids == (FIRST,)

def entry(
    identifier: int,
    workload_id: UUID,
    start: int,
    week: str = "ODD",
) -> ScheduleEntry:
    return ScheduleEntry(
        id=ScheduleEntryId(UUID(int=identifier)),
        workload_id=workload_id,
        week=week,
        weekday=MONDAY,
        start_time=time(start),
        end_time=time(start + 1),
    )


@pytest.mark.parametrize(
    ("first_count", "second_count"),
    [(2, 1), (1, 2), (3, 1)],
)
def test_before_supports_different_occurrence_counts(
    first_count: int, second_count: int
) -> None:
    source = problem(
        workloads=(workload(FIRST, first_count), workload(SECOND, second_count)),
        constraints=(constraint(
            ConstraintKind.BEFORE, RelatedWorkloadParameters(SECOND)
        ),),
    )
    result = solve(source)

    assert result.status is SolverStatus.SOLVED
    first = [item for item in result.variants[0].entries if item.workload_id == FIRST]
    second = [item for item in result.variants[0].entries if item.workload_id == SECOND]
    assert len(first) == first_count
    assert len(second) == second_count
    assert max(item.end_time for item in first) <= min(
        item.start_time for item in second
    ) or (
        max((item.week, item.weekday.value, item.end_time) for item in first)
        < min((item.week, item.weekday.value, item.start_time) for item in second)
    )


def test_before_validator_requires_all_source_occurrences_before_first_target() -> None:
    rule = constraint(ConstraintKind.BEFORE, RelatedWorkloadParameters(SECOND))
    first = [entry(1, FIRST, 8), entry(2, FIRST, 9)]
    second = [entry(3, SECOND, 10)]

    assert not list(constraint_conflicts(rule, first, second, True))
    assert list(constraint_conflicts(rule, first + [entry(4, FIRST, 11)], second, True))
    assert list(constraint_conflicts(rule, [entry(5, FIRST, 8, "EVEN")], second, True))


def test_before_with_reversed_fixed_days_identifies_all_constraints() -> None:
    source = problem(
        workloads=(workload(FIRST), workload(SECOND)),
        constraints=(
            constraint(ConstraintKind.BEFORE, RelatedWorkloadParameters(SECOND)),
            constraint(
                ConstraintKind.FIXED_DAY, FixedDayParameters(TUESDAY), identifier=101
            ),
            constraint(
                ConstraintKind.FIXED_DAY, FixedDayParameters(MONDAY),
                source=SECOND, identifier=102,
            ),
        ),
    )
    result = solve(source)

    assert result.status is SolverStatus.INFEASIBLE
    assert set(result.diagnostics[0].workload_ids) == {FIRST, SECOND}
    assert set(result.diagnostics[0].constraint_ids) == {
        UUID(int=100), UUID(int=101), UUID(int=102)
    }


def test_consecutive_with_different_fixed_days_identifies_all_constraints() -> None:
    source = problem(
        workloads=(workload(FIRST), workload(SECOND)),
        constraints=(
            constraint(ConstraintKind.CONSECUTIVE, RelatedWorkloadParameters(SECOND)),
            constraint(
                ConstraintKind.FIXED_DAY, FixedDayParameters(MONDAY), identifier=101
            ),
            constraint(
                ConstraintKind.FIXED_DAY, FixedDayParameters(TUESDAY),
                source=SECOND, identifier=102,
            ),
        ),
    )
    result = solve(source)

    assert result.status is SolverStatus.INFEASIBLE
    assert set(result.diagnostics[0].workload_ids) == {FIRST, SECOND}
    assert set(result.diagnostics[0].constraint_ids) == {
        UUID(int=100), UUID(int=101), UUID(int=102)
    }


def test_consecutive_with_compatible_fixed_days_can_be_solved() -> None:
    source = problem(
        workloads=(workload(FIRST), workload(SECOND)),
        constraints=(
            constraint(ConstraintKind.CONSECUTIVE, RelatedWorkloadParameters(SECOND)),
            constraint(
                ConstraintKind.FIXED_DAY, FixedDayParameters(MONDAY), identifier=101
            ),
            constraint(
                ConstraintKind.FIXED_DAY, FixedDayParameters(MONDAY),
                source=SECOND, identifier=102,
            ),
        ),
    )
    result = solve(source)

    assert result.status is SolverStatus.SOLVED
    assert {item.weekday for item in result.variants[0].entries} == {MONDAY}


def test_consecutive_with_disjoint_time_windows_reports_identified_constraints() -> None:
    source = problem(
        workloads=(workload(FIRST), workload(SECOND)),
        constraints=(
            constraint(ConstraintKind.CONSECUTIVE, RelatedWorkloadParameters(SECOND)),
            constraint(
                ConstraintKind.TIME_RANGE,
                TimeRangeParameters((WeeklyWindow("ANY", MONDAY, time(8), time(9)),)),
                identifier=101,
            ),
            constraint(
                ConstraintKind.TIME_RANGE,
                TimeRangeParameters((WeeklyWindow("ANY", MONDAY, time(11), time(12)),)),
                source=SECOND, identifier=102,
            ),
        ),
    )
    result = solve(source)

    assert result.status is SolverStatus.INFEASIBLE
    assert set(result.diagnostics[0].constraint_ids) == {
        UUID(int=100), UUID(int=101), UUID(int=102)
    }
