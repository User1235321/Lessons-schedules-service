from uuid import UUID

from app.domain.scheduling.constraint_validation import constraint_conflicts
from app.domain.scheduling.constraints import ConstraintKind, ExtraConstraintSnapshot
from app.domain.scheduling.problem import ScheduleProblem
from app.domain.scheduling.schedule import ScheduleEntry
from app.domain.scheduling.solver import SolverControl, SolverDiagnostic
from app.domain.shared.ids import ScheduleEntryId
from app.domain.shared.week import Weekday
from app.scheduling.candidates import LessonRequirements, check_cancelled, iter_placements


def _candidate_entries(
    requirement: LessonRequirements,
    problem: ScheduleProblem,
    control: SolverControl,
) -> tuple[ScheduleEntry, ...]:
    entries: dict[tuple[str, Weekday, object, object], ScheduleEntry] = {}
    for placement in iter_placements(requirement, problem.settings, control):
        position = (
            placement.week,
            placement.weekday,
            placement.start_time,
            placement.end_time,
        )
        if position not in entries:
            entries[position] = placement.to_entry(ScheduleEntryId(requirement.workload.id))
    return tuple(entries.values())


def _has_adjacent_pair(
    constraint: ExtraConstraintSnapshot,
    source: tuple[ScheduleEntry, ...],
    related: tuple[ScheduleEntry, ...],
) -> bool:
    starts = {(entry.week, entry.weekday, entry.start_time): entry for entry in related}
    ends = {(entry.week, entry.weekday, entry.end_time): entry for entry in related}
    for entry in source:
        for other in (
            starts.get((entry.week, entry.weekday, entry.end_time)),
            ends.get((entry.week, entry.weekday, entry.start_time)),
        ):
            if other is not None and not any(
                constraint_conflicts(constraint, [entry], [other], True)
            ):
                return True
    return False


def _has_ordered_pair(
    constraint: ExtraConstraintSnapshot,
    source: tuple[ScheduleEntry, ...],
    related: tuple[ScheduleEntry, ...],
) -> bool:
    weekdays = {day: index for index, day in enumerate(Weekday)}

    def position(entry: ScheduleEntry, end: bool) -> tuple[int, int, object]:
        return (
            int(entry.week == "EVEN"),
            weekdays[entry.weekday],
            entry.end_time if end else entry.start_time,
        )

    earliest_finish = min(source, key=lambda entry: position(entry, True))
    latest_start = max(related, key=lambda entry: position(entry, False))
    return not any(
        constraint_conflicts(constraint, [earliest_finish], [latest_start], True)
    )


def diagnose_incompatible_pairs(
    problem: ScheduleProblem,
    requirements: tuple[LessonRequirements, ...],
    control: SolverControl,
) -> tuple[SolverDiagnostic, ...]:
    by_workload = {item.workload.id: item for item in requirements}
    candidates: dict[UUID, tuple[ScheduleEntry, ...]] = {}
    diagnostics: list[SolverDiagnostic] = []

    for constraint in problem.constraints:
        check_cancelled(control)
        if constraint.kind not in (ConstraintKind.CONSECUTIVE, ConstraintKind.BEFORE):
            continue
        source_id = constraint.scope.resource_id
        target_id = constraint.parameters.workload_id
        if source_id == target_id or source_id not in by_workload or target_id not in by_workload:
            continue

        for workload_id in (source_id, target_id):
            if workload_id not in candidates:
                candidates[workload_id] = _candidate_entries(
                    by_workload[workload_id], problem, control
                )

        source = candidates[source_id]
        related = candidates[target_id]
        if not source or not related:
            continue

        compatible = (
            _has_adjacent_pair(constraint, source, related)
            if constraint.kind is ConstraintKind.CONSECUTIVE
            else _has_ordered_pair(constraint, source, related)
        )
        if compatible:
            continue

        scope_constraints = (
            item.id
            for workload_id in (source_id, target_id)
            for item in by_workload[workload_id].constraints
        )
        diagnostics.append(
            SolverDiagnostic(
                "Для связанных нагрузок нет совместимых размещений",
                (source_id, target_id),
                tuple(dict.fromkeys((constraint.id, *scope_constraints))),
            )
        )
    return tuple(diagnostics)
