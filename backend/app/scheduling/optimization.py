from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import time
from fractions import Fraction
from heapq import nsmallest
from itertools import islice
from operator import itemgetter
from uuid import UUID

from app.domain.scheduling.problem import CriterionType, ScheduleProblem
from app.domain.scheduling.schedule import CriterionScore
from app.domain.scheduling.solver import SolverControl
from app.domain.shared.week import Weekday
from app.scheduling.candidates import LessonRequirements, Placement, check_cancelled


@dataclass(frozen=True)
class _Cohort:
    """Студенты одной подгруппы либо остаток группы с общим расписанием."""

    group_id: UUID
    subgroup_id: UUID | None
    size: int


def _student_cohorts(
    problem: ScheduleProblem, requirements: tuple[LessonRequirements, ...]
) -> dict[UUID, tuple[_Cohort, ...]]:
    by_group: dict[UUID, list[_Cohort]] = defaultdict(list)
    for subgroup in problem.subgroups:
        by_group[subgroup.group_id].append(
            _Cohort(subgroup.group_id, subgroup.id, subgroup.student_count)
        )
    for group in problem.groups:
        remaining = group.student_count - sum(cohort.size for cohort in by_group[group.id])
        if remaining:
            by_group[group.id].append(_Cohort(group.id, None, remaining))

    result = {}
    for requirement in requirements:
        participants = requirement.participants
        if participants.subgroup_id is not None:
            cohorts = (
                _Cohort(
                    participants.group_ids[0], participants.subgroup_id, participants.student_count
                ),
            )
        else:
            cohorts = tuple(
                cohort for group in participants.group_ids for cohort in by_group[group]
            )
        result[requirement.workload.id] = cohorts
    return result


@dataclass
class _DayLoad:
    first: int = 24 * 60
    last: int = 0
    taught: int = 0

    def add(self, start: int, end: int) -> None:
        self.first = min(self.first, start)
        self.last = max(self.last, end)
        self.taught += end - start

    @property
    def gaps(self) -> int:
        # Поиск уже исключил пересечения для каждого участника в этот день.
        return self.last - self.first - self.taught


StudentDays = dict[tuple[_Cohort, str], dict[Weekday, _DayLoad]]


def _load_imbalance(student_days: StudentDays, problem: ScheduleProblem) -> float:
    cycle = problem.settings.cycle
    week_lengths = {"ODD": len(cycle.odd_week_days), "EVEN": len(cycle.even_week_days)}
    numerators: dict[str, int] = defaultdict(int)
    for (cohort, week), days in student_days.items():
        length = week_lengths[week]
        total = sum(day.taught for day in days.values())
        # У пустого учебного дня отклонение от среднего равно total / length.
        deviation = sum(abs(day.taught * length - total) for day in days.values())
        deviation += (length - len(days)) * total
        numerators[week] += cohort.size * deviation
    # Один перевод в float сохраняет равенство оценок при разном числе дней в неделях.
    return float(sum(Fraction(value, week_lengths[week]) for week, value in numerators.items()))


def _preference_matches(placement: Placement) -> int:
    return sum(
        any(
            window.week in ("ANY", placement.week)
            and window.day == placement.weekday
            and window.start <= placement.start_time
            and placement.end_time <= window.end
            for window in teacher.preferences
        )
        for teacher in placement.teachers
    )


def _scores(
    placements: tuple[Placement, ...],
    criteria: tuple[CriterionType, ...],
    cohorts: dict[UUID, tuple[_Cohort, ...]],
    problem: ScheduleProblem,
    control: SolverControl,
) -> tuple[CriterionScore, ...]:
    student_days: StudentDays = defaultdict(lambda: defaultdict(_DayLoad))
    teacher_days: dict[tuple[UUID, str, Weekday], _DayLoad] = defaultdict(_DayLoad)
    early_late = 0
    preferences = 0
    for placement in placements:
        check_cancelled(control)
        start = placement.start_time.hour * 60 + placement.start_time.minute
        end = placement.end_time.hour * 60 + placement.end_time.minute
        if cohorts:
            for cohort in cohorts[placement.requirements.workload.id]:
                student_days[cohort, placement.week][placement.weekday].add(start, end)
        if CriterionType.TEACHER_GAPS in criteria:
            for teacher in placement.teachers:
                teacher_days[teacher.id, placement.week, placement.weekday].add(start, end)
        if CriterionType.TEACHER_PREFERENCES in criteria:
            preferences += _preference_matches(placement)
        if CriterionType.EARLY_LATE_CLASSES in criteria:
            early_late += placement.start_time < time(9) or placement.end_time > time(18)

    values: dict[CriterionType, float] = {
        CriterionType.TEACHER_PREFERENCES: preferences,
        CriterionType.EARLY_LATE_CLASSES: early_late,
        CriterionType.TEACHER_GAPS: sum(day.gaps for day in teacher_days.values()),
    }
    if CriterionType.STUDENT_GAPS in criteria:
        values[CriterionType.STUDENT_GAPS] = sum(
            cohort.size * day.gaps
            for (cohort, _), days in student_days.items()
            for day in days.values()
        )
    if CriterionType.BALANCED_STUDENT_LOAD in criteria:
        values[CriterionType.BALANCED_STUDENT_LOAD] = _load_imbalance(student_days, problem)
    return tuple(CriterionScore(kind.value, values[kind]) for kind in criteria)


def select_placements(
    candidates: Iterable[tuple[Placement, ...]],
    problem: ScheduleProblem,
    requirements: tuple[LessonRequirements, ...],
    limit: int,
    control: SolverControl,
) -> Iterator[tuple[tuple[Placement, ...], tuple[CriterionScore, ...]]]:
    criteria = tuple(
        CriterionType(criterion.criterion_type)
        for criterion in sorted(problem.optimization_criteria, key=lambda c: c.priority)
        if criterion.is_active
    )
    if not criteria:
        for candidate in islice(candidates, limit):
            yield candidate, ()
        return

    cohorts = (
        _student_cohorts(problem, requirements)
        if CriterionType.STUDENT_GAPS in criteria or CriterionType.BALANCED_STUDENT_LOAD in criteria
        else {}
    )
    # Даже при полной доступности совпадений не может быть больше числа назначений
    # преподавателей с предпочтениями. Остальные критерии ограничены снизу нулём.
    max_preferences = (
        sum(
            item.workload.occurrences_per_cycle
            * min(
                item.workload.required_teacher_count,
                sum(bool(teacher.preferences) for teacher in item.teachers),
            )
            for item in requirements
        )
        if CriterionType.TEACHER_PREFERENCES in criteria
        else 0
    )
    best_possible = tuple(
        -max_preferences if kind is CriterionType.TEACHER_PREFERENCES else 0 for kind in criteria
    )

    def scored_candidates():
        optimal_count = 0
        for candidate in candidates:
            scores = _scores(candidate, criteria, cohorts, problem, control)
            rank = tuple(
                -score.value if kind is CriterionType.TEACHER_PREFERENCES else score.value
                for kind, score in zip(criteria, scores, strict=True)
            )
            yield rank, candidate, scores
            if rank == best_possible:
                optimal_count += 1
                if optimal_count == limit:
                    return

    # nsmallest хранит до limit вариантов и сохраняет порядок получения при равенстве.
    for _, candidate, scores in nsmallest(limit, scored_candidates(), key=itemgetter(0)):
        yield candidate, scores
