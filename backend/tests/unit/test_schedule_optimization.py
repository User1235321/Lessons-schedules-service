from dataclasses import replace
from datetime import time
from uuid import UUID

import pytest

from app.domain.projects.settings import DurationMode, TimeMode
from app.domain.scheduling.constraints import (
    ConstraintKind,
    ConstraintScope,
    ConstraintScopeKind,
    ExtraConstraintSnapshot,
    TimeRangeParameters,
)
from app.domain.scheduling.job import ResultMode, ResultOptions
from app.domain.scheduling.problem import (
    CriterionType,
    OptimizationCriterionSnapshot,
    WorkloadTargetKind,
)
from app.domain.scheduling.resources import (
    GroupSnapshot,
    StreamSnapshot,
    SubgroupSnapshot,
    WeeklyWindow,
)
from app.domain.scheduling.schedule import CriterionScore
from app.domain.scheduling.solver import SolverStatus
from app.domain.shared.week import Weekday
from app.scheduling import solver
from tests.unit.test_feasible_solver import (
    GROUP,
    LEFT,
    MONDAY,
    RIGHT,
    SECOND_GROUP,
    SECOND_TEACHER,
    STREAM,
    WORKLOAD,
    RecordingControl,
    problem,
    settings,
    solve,
    teacher,
    window,
    workload,
)

TUESDAY = Weekday.TUESDAY
PREFERENCES = CriterionType.TEACHER_PREFERENCES
EARLY_LATE = CriterionType.EARLY_LATE_CLASSES


def criteria(*kinds: CriterionType) -> tuple[OptimizationCriterionSnapshot, ...]:
    return tuple(
        OptimizationCriterionSnapshot(kind, priority) for priority, kind in enumerate(kinds, 1)
    )


def scheduled_at(workload_id: UUID, interval: WeeklyWindow) -> ExtraConstraintSnapshot:
    return ExtraConstraintSnapshot(
        workload_id,
        ConstraintKind.TIME_RANGE,
        ConstraintScope(ConstraintScopeKind.WORKLOAD, workload_id),
        TimeRangeParameters((interval,)),
    )


def test_later_best_wins_and_equal_variants_keep_discovery_order_at_cutoff() -> None:
    assigned = replace(
        teacher(availability=(window(time(9), time(14)),)),
        preferences=(window(time(12), time(14)),),
    )
    source = replace(problem(teachers=(assigned,)), optimization_criteria=criteria(PREFERENCES))

    for options, hours in [
        (ResultOptions(), [12]),
        (ResultOptions(ResultMode.TOP_N, 1), [12]),
        (ResultOptions(ResultMode.TOP_N, 3), [12, 13, 9]),
        (ResultOptions(ResultMode.TOP_N, 100), [12, 13, 9, 10, 11]),
    ]:
        result = solve(source, options)
        assert result.status is SolverStatus.SOLVED
        assert [v.entries[0].start_time.hour for v in result.variants] == hours
        assert [v.criterion_scores[0].value for v in result.variants] == [
            int(h >= 12) for h in hours
        ]


def test_priority_and_inactive_criteria_determine_single_best() -> None:
    assigned = replace(
        teacher(availability=(window(time(8), time(11)),)), preferences=(window(time(8), time(9)),)
    )
    source = problem(teachers=(assigned,))
    for order, hour, values in [
        ((EARLY_LATE, PREFERENCES), 9, (0, 0)),
        ((PREFERENCES, EARLY_LATE), 8, (1, 1)),
    ]:
        # Входной порядок специально обратен порядку приоритетов.
        (variant,) = solve(replace(source, optimization_criteria=criteria(*order)[::-1])).variants
        assert variant.entries[0].start_time == time(hour)
        assert variant.criterion_scores == tuple(
            CriterionScore(k, v) for k, v in zip(order, values, strict=True)
        )
    inactive = (OptimizationCriterionSnapshot(EARLY_LATE, 1, is_active=False),)
    assert solve(replace(source, optimization_criteria=inactive)).variants == solve(source).variants


def test_lab_scores_each_teacher_once_and_requires_one_covering_preference() -> None:
    first = replace(teacher(lesson_type="LAB"), preferences=(window(), window(time(8), time(11))))
    second = replace(
        teacher(SECOND_TEACHER, "LAB"),
        preferences=(
            window(time(9), time(9, 30), "ODD"),
            window(time(9, 30), time(10), "ODD"),
            window(day=TUESDAY),
            window(week="EVEN"),
        ),
    )
    source = problem(
        teachers=(first, second),
        workloads=(workload(lesson_type="LAB", teacher_count=2),),
        project_settings=settings(even=(MONDAY,)),
    )
    result = solve(
        replace(source, optimization_criteria=criteria(PREFERENCES)),
        ResultOptions(ResultMode.TOP_N, 5),
    )
    assert [(v.entries[0].week, v.criterion_scores[0].value) for v in result.variants] == [
        ("EVEN", 2),
        ("ODD", 1),
    ]


@pytest.mark.parametrize(
    ("start", "end", "penalty"), [(9, 18, 0), (8, 18, 1), (9, 19, 1), (8, 19, 1)]
)
def test_early_late_thresholds_count_each_lesson_once(start, end, penalty) -> None:
    source = problem(
        teachers=(teacher(availability=(window(time(start), time(end)),)),),
        project_settings=replace(
            settings(), duration_mode=DurationMode.uniform((end - start) * 60)
        ),
    )
    (variant,) = solve(replace(source, optimization_criteria=criteria(EARLY_LATE))).variants
    assert variant.criterion_scores == (CriterionScore(EARLY_LATE, penalty),)


def test_stream_group_subgroups_and_unassigned_students_share_only_their_own_lessons() -> None:
    # 9 — поток, 10 — правая подгруппа, 11 — левая, 12 — вторая группа, 13 — первая группа.
    targets = [
        (STREAM, WorkloadTargetKind.STREAM),
        (RIGHT, WorkloadTargetKind.SUBGROUP),
        (LEFT, WorkloadTargetKind.SUBGROUP),
        (SECOND_GROUP, WorkloadTargetKind.GROUP),
        (GROUP, WorkloadTargetKind.GROUP),
    ]
    loads = tuple(
        workload(UUID(int=i + 100), target, kind) for i, (target, kind) in enumerate(targets)
    )
    source = problem(
        groups=(GroupSnapshot(GROUP, "Первая", 10), GroupSnapshot(SECOND_GROUP, "Вторая", 4)),
        subgroups=(
            SubgroupSnapshot(LEFT, GROUP, "Левая", 3),
            SubgroupSnapshot(RIGHT, GROUP, "Правая", 5),
        ),
        streams=(StreamSnapshot(STREAM, "Поток", (GROUP, SECOND_GROUP)),),
        workloads=loads,
        teachers=(teacher(availability=(window(time(9), time(14)),)),),
        project_settings=settings((MONDAY, TUESDAY)),
    )
    source = replace(
        source,
        constraints=tuple(
            scheduled_at(load.id, window(time(hour), time(hour + 1)))
            for hour, load in enumerate(loads, 9)
        ),
        optimization_criteria=criteria(
            CriterionType.STUDENT_GAPS,
            CriterionType.BALANCED_STUDENT_LOAD,
            CriterionType.TEACHER_GAPS,
        ),
    )
    (variant,) = solve(source).variants
    assert variant.criterion_scores == (
        CriterionScore("STUDENT_GAPS", 3 * 120 + 5 * 120 + 2 * 180 + 4 * 120),
        CriterionScore("BALANCED_STUDENT_LOAD", 3 * 180 + 5 * 180 + 2 * 120 + 4 * 120),
        CriterionScore("TEACHER_GAPS", 0),
    )


def test_each_week_has_its_own_study_days_and_overnight_gaps_are_excluded() -> None:
    intervals = (
        window(week="ODD"),
        window(time(11), time(12), "ODD"),
        window(time(17), time(18), "ODD", TUESDAY),
        window(time(15), time(16), "EVEN"),
    )
    loads = tuple(workload(UUID(int=100 + i)) for i in range(len(intervals)))
    source = problem(
        workloads=loads,
        teachers=(teacher(availability=intervals),),
        project_settings=settings((MONDAY, TUESDAY), (MONDAY, Weekday.WEDNESDAY, Weekday.FRIDAY)),
    )
    source = replace(
        source,
        constraints=tuple(
            scheduled_at(load.id, interval) for load, interval in zip(loads, intervals, strict=True)
        ),
        optimization_criteria=criteria(
            CriterionType.TEACHER_GAPS,
            CriterionType.STUDENT_GAPS,
            CriterionType.BALANCED_STUDENT_LOAD,
        ),
    )
    (variant,) = solve(source).variants
    assert variant.criterion_scores == (
        CriterionScore("TEACHER_GAPS", 60),
        CriterionScore("STUDENT_GAPS", 60 * 20),
        CriterionScore("BALANCED_STUDENT_LOAD", (60 + 80) * 20),
    )


def test_only_feasible_candidates_are_ranked_and_infeasibility_is_preserved() -> None:
    assigned = replace(teacher(availability=(window(time(9), time(12)),)), preferences=(window(),))
    source = replace(problem(teachers=(assigned,)), optimization_criteria=criteria(PREFERENCES))
    constrained = replace(source, constraints=(scheduled_at(WORKLOAD, window(time(10), time(12))),))
    result = solve(constrained, ResultOptions(ResultMode.TOP_N, 5))
    assert [v.entries[0].start_time for v in result.variants] == [time(10), time(11)]
    assert all(v.criterion_scores == (CriterionScore(PREFERENCES, 0),) for v in result.variants)
    impossible = replace(source, constraints=(scheduled_at(WORKLOAD, window(time(15), time(16))),))
    result = solve(impossible)
    assert result.status is SolverStatus.INFEASIBLE
    assert result.variants == ()
    assert result.diagnostics


def test_empty_workload_has_one_variant_with_zero_active_scores() -> None:
    kinds = tuple(CriterionType)
    source = replace(problem(workloads=()), optimization_criteria=criteria(*kinds))
    (variant,) = solve(source, ResultOptions(ResultMode.TOP_N, 3)).variants
    assert variant.entries == ()
    assert variant.criterion_scores == tuple(CriterionScore(kind, 0) for kind in kinds)


def test_individual_durations_and_subhour_gaps_use_minutes() -> None:
    intervals = (window(time(9, 15), time(10)), window(time(10, 25), time(10, 55)))
    loads = (workload(duration=45), workload(UUID(int=100), duration=30))
    source = problem(
        teachers=(teacher(availability=intervals),),
        workloads=loads,
        project_settings=replace(
            settings((MONDAY, TUESDAY)),
            time_mode=TimeMode.step(5),
            duration_mode=DurationMode.individual(),
        ),
    )
    source = replace(
        source,
        constraints=tuple(
            scheduled_at(load.id, interval) for load, interval in zip(loads, intervals, strict=True)
        ),
        optimization_criteria=criteria(
            CriterionType.STUDENT_GAPS,
            CriterionType.TEACHER_GAPS,
            CriterionType.BALANCED_STUDENT_LOAD,
        ),
    )
    (variant,) = solve(source).variants
    assert variant.criterion_scores == (
        CriterionScore("STUDENT_GAPS", 25 * 20),
        CriterionScore("TEACHER_GAPS", 25),
        CriterionScore("BALANCED_STUDENT_LOAD", (45 + 30) * 20),
    )


def test_top_n_matches_independent_stable_sort_of_all_feasible_schedules() -> None:
    days = (MONDAY, TUESDAY)
    availability = tuple(window(time(8), time(11), day=day) for day in days)
    first = replace(teacher(availability=availability), preferences=(window(time(8), time(9)),))
    second = teacher(SECOND_TEACHER, availability=availability)
    source = problem(
        teachers=(first, second),
        workloads=(workload(occurrences=2),),
        project_settings=settings(days),
    )
    # 6 слотов, 2 разных проведения и по 2 возможных преподавателя: C(6,2) * 4.
    candidates = solve(source, ResultOptions(ResultMode.TOP_N, 100)).variants
    assert len(candidates) == 60

    def expected_scores(variant):
        left, right = variant.entries
        same_day = left.weekday == right.weekday
        gap = (right.start_time.hour - left.end_time.hour) * 60 if same_day else 0
        return {
            CriterionType.STUDENT_GAPS: 20 * gap,
            CriterionType.TEACHER_GAPS: gap if left.teachers == right.teachers else 0,
            CriterionType.BALANCED_STUDENT_LOAD: 20 * 120 if same_day else 0,
            EARLY_LATE: sum(e.start_time.hour < 9 for e in variant.entries),
            PREFERENCES: sum(
                e.teachers[0].teacher_id == first.id
                and e.weekday == MONDAY
                and e.start_time == time(8)
                for e in variant.entries
            ),
        }

    for order in (tuple(CriterionType), tuple(reversed(CriterionType))):
        scored = [(candidate, expected_scores(candidate)) for candidate in candidates]
        expected = sorted(
            scored,
            key=lambda pair: tuple(-pair[1][k] if k == PREFERENCES else pair[1][k] for k in order),
        )
        for limit in (1, 7, 70):
            result = solve(
                replace(source, optimization_criteria=criteria(*order)),
                ResultOptions(ResultMode.TOP_N, limit),
            )
            assert result.variants == tuple(
                replace(
                    candidate, criterion_scores=tuple(CriterionScore(k, values[k]) for k in order)
                )
                for candidate, values in expected[:limit]
            )


def test_cancellation_after_first_feasible_candidate_discards_partial_ranking(monkeypatch) -> None:
    assigned = replace(
        teacher(availability=(window(time(9), time(12)),)),
        preferences=(window(time(11), time(12)),),
    )
    source = replace(problem(teachers=(assigned,)), optimization_criteria=criteria(PREFERENCES))
    original_search = solver.find_placements
    control = RecordingControl()

    def cancel_after_first_candidate(*args, **kwargs):
        for candidate in original_search(*args, **kwargs):
            yield candidate
            control.cancel_after = 0

    monkeypatch.setattr(solver, "find_placements", cancel_after_first_candidate)
    result = solve(source, control=control)
    assert result.status is SolverStatus.CANCELLED
    assert result.variants == ()
    assert result.diagnostics == ()
