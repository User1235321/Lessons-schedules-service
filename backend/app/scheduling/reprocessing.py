from collections.abc import Iterator
from dataclasses import replace
from datetime import time

from app.domain.scheduling.job import ExistingScheduleInput, JobProgress, JobType
from app.domain.scheduling.problem import ScheduleProblem
from app.domain.scheduling.schedule import ScheduleEntry
from app.domain.scheduling.solver import ScheduleVariant, SolverControl, SolverResult, SolverStatus
from app.domain.scheduling.validation import validate_schedule
from app.scheduling.candidates import (
    LessonRequirements,
    SearchCancelled,
    check_cancelled,
    iter_placements,
    prepare_requirements,
    time_slots,
)
from app.scheduling.quality import criterion_scores


def _distance(original: ScheduleEntry, candidate: ScheduleEntry) -> int:
    def teachers(entry):
        return frozenset(t.teacher_id or t.display_name for t in entry.teachers)

    return sum(
        (
            (original.week, original.weekday) != (candidate.week, candidate.weekday),
            (original.start_time, original.end_time) != (candidate.start_time, candidate.end_time),
            original.lesson_format != candidate.lesson_format,
            (original.room_id or original.room_name) != (candidate.room_id or candidate.room_name),
            teachers(original) != teachers(candidate),
        )
    )


def _minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def _candidates(
    original: ScheduleEntry,
    problem: ScheduleProblem,
    requirement: LessonRequirements | None,
    duration: int,
    fixed: bool,
    control: SolverControl,
) -> Iterator[ScheduleEntry]:
    yield original
    if fixed:
        return
    # Даже без справочников у занятия есть длительность и сетка времени проекта.
    for week, day, start, end in time_slots(problem.settings, duration):
        check_cancelled(control)
        yield replace(original, week=week, weekday=day, start_time=start, end_time=end)
    if requirement is not None:
        for placement in iter_placements(requirement, problem.settings, control):
            candidate = placement.to_entry(original.id)
            yield replace(
                candidate,
                subject_name=original.subject_name,
                participant_label=original.participant_label,
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
            return self._search(source, job_type, problem, control)
        except SearchCancelled:
            return SolverResult(SolverStatus.CANCELLED)

    def _search(
        self,
        source: ExistingScheduleInput,
        job_type: JobType,
        problem: ScheduleProblem,
        control: SolverControl,
    ) -> SolverResult:
        schedule = source.schedule
        preserve = job_type is not JobType.REOPTIMIZE_FULL
        check_cancelled(control)
        if not validate_schedule(schedule, problem):
            scores = criterion_scores(schedule.entries, problem)
            if all(score.value == 0 for score in scores) or preserve:
                # В режиме минимальных изменений только исходное размещение имеет цену ноль.
                return SolverResult(
                    SolverStatus.SOLVED, (ScheduleVariant(schedule.entries, scores),)
                )

        requirements, _ = prepare_requirements(problem, control)
        by_workload = {req.workload.id: req for req in requirements}
        durations = {w.id: w.duration_minutes for w in problem.workloads}
        fixed = set(source.fixed_entry_ids)
        choices = []
        for original in schedule.entries:
            duration = (
                problem.settings.duration_mode.duration_minutes
                or durations.get(original.workload_id)
                or _minutes(original.end_time) - _minutes(original.start_time)
            )
            candidates = _candidates(
                original,
                problem,
                by_workload.get(original.workload_id),
                duration,
                original.id in fixed,
                control,
            )
            options = []
            for entry in dict.fromkeys(candidates):
                check_cancelled(control)
                if not validate_schedule(
                    replace(schedule, entries=(entry,)), problem, partial_assignment=True
                ):
                    cost = _distance(original, entry) if preserve else 0
                    options.append((cost, entry))
            if not options:
                return SolverResult(SolverStatus.INFEASIBLE)
            choices.append(sorted(options, key=lambda item: item[0]))

        # Явный стек поиска не ограничивает размер расписания глубиной стека Python.
        order = sorted(range(len(choices)), key=lambda i: len(choices[i]))
        selected: list[ScheduleEntry] = []
        stack = [iter(choices[order[0]])] if choices else []
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
            delta, candidate = option
            cost = costs[-1] + delta
            if best_rank is not None and cost > best_rank[0]:
                continue
            entries = (*selected, candidate)
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
                    e for _, e in sorted(zip(order, entries), key=lambda pair: pair[0])
                )
                scores = criterion_scores(original_order, problem)
                rank = (cost, *(score.value for score in scores))
                if best_rank is None or rank < best_rank:
                    best_rank = rank
                    best = ScheduleVariant(original_order, scores)
                    if not any(rank):
                        break
            else:
                selected.append(candidate)
                costs.append(cost)
                stack.append(iter(choices[order[len(entries)]]))
        if best is None:
            return SolverResult(SolverStatus.INFEASIBLE)
        return SolverResult(SolverStatus.SOLVED, (best,))
