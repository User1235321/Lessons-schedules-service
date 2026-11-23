from collections import Counter
from collections.abc import Iterator
from dataclasses import replace
from uuid import UUID

from app.domain.scheduling.job import ExistingScheduleInput, JobProgress, JobType
from app.domain.scheduling.problem import ScheduleProblem
from app.domain.scheduling.schedule import LessonFormat, Schedule, ScheduleEntry, ScheduleSource
from app.domain.scheduling.solver import ScheduleVariant, SolverControl, SolverDiagnostic
from app.domain.scheduling.solver import SolverResult, SolverStatus
from app.domain.scheduling.validation import validate_schedule
from app.domain.shared.ids import JobId
from app.scheduling.candidates import (
    LessonRequirements,
    Placement,
    SearchCancelled,
    check_cancelled,
    iter_placements,
    prepare_requirements,
)
from app.scheduling.optimization import PlacementScorer


def _label(value: str | None) -> str:
    return " ".join(value.casefold().split()) if value else ""


def _resource_equal(left_id, left_name, right_id, right_name) -> bool:
    if left_id is not None and right_id is not None:
        return left_id == right_id
    return _label(left_name) == _label(right_name)


def _teachers_equal(original: ScheduleEntry, candidate: ScheduleEntry) -> bool:
    remaining = list(candidate.teachers)
    for teacher in original.teachers:
        match = next(
            (
                item
                for item in remaining
                if _resource_equal(
                    teacher.teacher_id, teacher.display_name, item.teacher_id, item.display_name
                )
            ),
            None,
        )
        if match is None:
            return False
        remaining.remove(match)
    return not remaining


def _distance(original: ScheduleEntry, candidate: ScheduleEntry) -> int:
    return sum(
        (
            (original.week, original.weekday) != (candidate.week, candidate.weekday),
            (original.start_time, original.end_time) != (candidate.start_time, candidate.end_time),
            original.lesson_format != candidate.lesson_format,
            not _resource_equal(
                original.room_id, original.room_name, candidate.room_id, candidate.room_name
            ),
            not _teachers_equal(original, candidate),
        )
    )


def _match_workload(
    entry: ScheduleEntry, requirements: dict[UUID, LessonRequirements]
) -> UUID | None:
    if entry.workload_id is not None:
        return entry.workload_id if entry.workload_id in requirements else None
    if not (entry.subject_name and entry.participant_label and entry.lesson_type):
        return None
    matches = [
        workload_id
        for workload_id, requirement in requirements.items()
        if _label(entry.subject_name) == _label(requirement.subject_name)
        and _label(entry.participant_label) == _label(requirement.participants.label)
        and entry.lesson_type == requirement.workload.lesson_type
    ]
    return matches[0] if len(matches) == 1 else None


def _requirements_by_format(
    problem: ScheduleProblem, control: SolverControl
) -> dict[tuple[UUID, LessonFormat], LessonRequirements]:
    result = {}
    for lesson_format in LessonFormat:
        formatted = replace(
            problem,
            workloads=tuple(
                replace(workload, lesson_format=lesson_format) for workload in problem.workloads
            ),
        )
        requirements, _ = prepare_requirements(formatted, control)
        result.update(((item.workload.id, lesson_format), item) for item in requirements)
    return result


def _fixed_placement(original: ScheduleEntry, candidate: ScheduleEntry) -> bool:
    return (
        (original.week, original.weekday, original.start_time, original.end_time)
        == (candidate.week, candidate.weekday, candidate.start_time, candidate.end_time)
        and (original.lesson_format is None or original.lesson_format == candidate.lesson_format)
        and (
            not (original.room_id or original.room_name)
            or _resource_equal(
                original.room_id, original.room_name, candidate.room_id, candidate.room_name
            )
        )
        and (not original.teachers or _teachers_equal(original, candidate))
    )


def _options(
    original: ScheduleEntry,
    workload_id: UUID,
    default_format: LessonFormat,
    requirements: dict[tuple[UUID, LessonFormat], LessonRequirements],
    problem: ScheduleProblem,
    fixed: bool,
    preserve: bool,
    control: SolverControl,
) -> list[tuple[int, Placement, ScheduleEntry]]:
    result = []
    formats = tuple(dict.fromkeys((original.lesson_format or default_format, default_format)))
    for lesson_format in formats:
        requirement = requirements.get((workload_id, lesson_format))
        if requirement is None:
            continue
        for placement in iter_placements(requirement, problem.settings, control):
            entry = placement.to_entry(original.id)
            if not fixed or _fixed_placement(original, entry):
                result.append((_distance(original, entry) if preserve else 0, placement, entry))
    return sorted(result, key=lambda item: item[0])


def _infeasible(message: str, workload_ids: tuple[UUID, ...] = ()) -> SolverResult:
    return SolverResult(
        SolverStatus.INFEASIBLE, diagnostics=(SolverDiagnostic(message, workload_ids),)
    )


class ExistingScheduleSolver:
    def solve(
        self,
        source: ExistingScheduleInput,
        job_type: JobType,
        problem: ScheduleProblem,
        control: SolverControl,
    ) -> SolverResult:
        try:
            return self._solve(source, job_type, problem, control)
        except SearchCancelled:
            return SolverResult(SolverStatus.CANCELLED)

    def _solve(
        self,
        source: ExistingScheduleInput,
        job_type: JobType,
        problem: ScheduleProblem,
        control: SolverControl,
    ) -> SolverResult:
        check_cancelled(control)
        requirements = _requirements_by_format(problem, control)
        by_workload = {item.workload.id: item for item in requirements.values()}
        workloads = {item.id: item for item in problem.workloads}
        linked = []
        for entry in source.schedule.entries:
            check_cancelled(control)
            workload_id = _match_workload(entry, by_workload)
            if workload_id is None:
                return _infeasible(
                    "Для занятия не найдена однозначная учебная нагрузка с данными для расчёта"
                )
            linked.append(workload_id)
        counts = Counter(linked)
        mismatched = tuple(
            workload.id
            for workload in problem.workloads
            if counts[workload.id] != workload.occurrences_per_cycle
        )
        if mismatched:
            return _infeasible("Количество занятий не соответствует учебной нагрузке", mismatched)
        preserve = job_type is not JobType.REOPTIMIZE_FULL
        fixed = set(source.fixed_entry_ids)
        choices = []
        for entry, workload_id in zip(source.schedule.entries, linked, strict=True):
            options = _options(
                entry, workload_id, workloads[workload_id].lesson_format, requirements, problem,
                entry.id in fixed, preserve, control,
            )
            if not options:
                return _infeasible("Для занятия отсутствуют допустимые размещения", (workload_id,))
            choices.append(options)
        template = replace(
            source.schedule,
            source=ScheduleSource.GENERATED,
            job_id=JobId(UUID(int=0)),
            result_index=1,
            criterion_scores=(),
            entries=(),
        )
        scorer = PlacementScorer(problem, tuple(by_workload.values()))
        return self._search(template, choices, scorer, problem, control)

    def _search(
        self,
        schedule: Schedule,
        choices: list[list[tuple[int, Placement, ScheduleEntry]]],
        scorer: PlacementScorer,
        problem: ScheduleProblem,
        control: SolverControl,
    ) -> SolverResult:
        if not choices:
            return _infeasible("В расписании отсутствуют занятия")
        order = sorted(range(len(choices)), key=lambda i: len(choices[i]))
        selected: list[tuple[Placement, ScheduleEntry]] = []
        stack: list[Iterator[tuple[int, Placement, ScheduleEntry]]] = [iter(choices[order[0]])]
        costs = [0]
        best_rank = None
        best = None
        deepest = 0
        while stack:
            check_cancelled(control)
            option = next(stack[-1], None)
            if option is None:
                stack.pop()
                if selected:
                    selected.pop()
                    costs.pop()
                continue
            delta, placement, candidate = option
            cost = costs[-1] + delta
            if best_rank is not None and cost > best_rank[0]:
                continue
            assignments = (*selected, (placement, candidate))
            entries = tuple(entry for _, entry in assignments)
            complete = len(entries) == len(order)
            if validate_schedule(
                replace(schedule, entries=entries), problem, partial_assignment=not complete
            ):
                continue
            if len(entries) > deepest:
                deepest = len(entries)
                control.report_progress(JobProgress(min(99, 100 * deepest / len(order))))
            if complete:
                original_order = tuple(
                    item for _, item in sorted(zip(order, assignments, strict=True))
                )
                scores = scorer.score(tuple(item[0] for item in original_order), control)
                rank = (cost, *scorer.rank(scores))
                if best_rank is None or rank < best_rank:
                    best_rank = rank
                    best = ScheduleVariant(tuple(item[1] for item in original_order), scores)
                    if rank == (0, *scorer.best_possible):
                        break
            else:
                selected.append((placement, candidate))
                costs.append(cost)
                stack.append(iter(choices[order[len(entries)]]))
        if best is None:
            return _infeasible("Полное допустимое расписание не найдено")
        return SolverResult(SolverStatus.SOLVED, (best,))
