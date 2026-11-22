from collections import defaultdict
from dataclasses import replace
from datetime import UTC, datetime
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from app.domain.scheduling.constraint_validation import seconds
from app.domain.scheduling.constraints import (
    ConstraintKind,
    ConstraintScopeKind,
    ExtraConstraintSnapshot,
    FixedDayParameters,
    MinimumGapParameters,
    RelatedWorkloadParameters,
)
from app.domain.scheduling.job import JobProgress, ResultOptions
from app.domain.scheduling.problem import ScheduleProblem
from app.domain.scheduling.schedule import Schedule, ScheduleSource
from app.domain.scheduling.solver import (
    ScheduleVariant,
    SolverControl,
    SolverDiagnostic,
    SolverResult,
    SolverStatus,
)
from app.domain.scheduling.validation import validate_schedule
from app.domain.shared.ids import JobId, ProjectId, ScheduleEntryId, ScheduleId
from app.scheduling.candidates import (
    LessonRequirements,
    Placement,
    SearchCancelled,
    check_cancelled,
    iter_placements,
    prepare_requirements,
)
from app.scheduling.search import find_placements

_VALIDATION_ID = UUID(int=0)
_VALIDATION_DATE = datetime(2000, 1, 1, tzinfo=UTC)


def _validated_variant(
    problem: ScheduleProblem, placements: tuple[Placement, ...]
) -> ScheduleVariant:
    counts: dict[UUID, int] = defaultdict(int)
    entries = []
    for placement in sorted(placements, key=lambda item: item.order_key):
        workload_id = placement.requirements.workload.id
        counts[workload_id] += 1
        entry_id = ScheduleEntryId(
            uuid5(NAMESPACE_URL, f"lessons-schedules/{workload_id}/{counts[workload_id]}")
        )
        entries.append(placement.to_entry(entry_id))

    schedule = Schedule(
        id=ScheduleId(_VALIDATION_ID),
        project_id=ProjectId(_VALIDATION_ID),
        source=ScheduleSource.GENERATED,
        job_id=JobId(_VALIDATION_ID),
        result_index=1,
        criterion_scores=(),
        created_at=_VALIDATION_DATE,
        entries=tuple(entries),
    )
    conflicts = validate_schedule(schedule, problem)
    if conflicts:
        codes = ", ".join(sorted({conflict.code for conflict in conflicts}))
        raise ValueError(f"Планировщик сформировал недопустимое расписание: {codes}")
    return ScheduleVariant(schedule.entries, ())


_WORKLOAD_ONLY = {
    ConstraintKind.EVERY_WEEK,
    ConstraintKind.CONSECUTIVE,
    ConstraintKind.NOT_CONSECUTIVE,
    ConstraintKind.MIN_GAP,
    ConstraintKind.BEFORE,
    ConstraintKind.FIXED_DAY,
}


def _reference_diagnostics(
    problem: ScheduleProblem, control: SolverControl
) -> tuple[SolverDiagnostic, ...]:
    resources = {
        ConstraintScopeKind.GROUP: {item.id for item in problem.groups},
        ConstraintScopeKind.SUBGROUP: {item.id for item in problem.subgroups},
        ConstraintScopeKind.STREAM: {item.id for item in problem.streams},
        ConstraintScopeKind.WORKLOAD: {item.id for item in problem.workloads},
    }
    errors: list[SolverDiagnostic] = []
    for constraint in problem.constraints:
        check_cancelled(control)
        scope = constraint.scope
        if constraint.kind in _WORKLOAD_ONLY and scope.kind is not ConstraintScopeKind.WORKLOAD:
            errors.append(SolverDiagnostic(
                "Для ограничения требуется область WORKLOAD",
                constraint_ids=(constraint.id,),
            ))
        if (
            scope.kind is not ConstraintScopeKind.PROJECT
            and scope.resource_id not in resources[scope.kind]
        ):
            errors.append(SolverDiagnostic(
                "Область ограничения ссылается на отсутствующий ресурс",
                constraint_ids=(constraint.id,),
            ))
        parameters = constraint.parameters
        if isinstance(parameters, (RelatedWorkloadParameters, MinimumGapParameters)):
            if parameters.workload_id not in resources[ConstraintScopeKind.WORKLOAD]:
                errors.append(SolverDiagnostic(
                    "Связанная учебная нагрузка отсутствует",
                    constraint_ids=(constraint.id,),
                ))
            if (
                constraint.kind is ConstraintKind.BEFORE
                and scope.resource_id == parameters.workload_id
            ):
                errors.append(SolverDiagnostic(
                    "Занятие не может предшествовать самому себе",
                    workload_ids=(parameters.workload_id,),
                    constraint_ids=(constraint.id,),
                ))
    return tuple(errors)


def _combination_diagnostics(
    problem: ScheduleProblem,
    requirements: tuple[LessonRequirements, ...],
    control: SolverControl,
) -> tuple[SolverDiagnostic, ...]:
    errors: list[SolverDiagnostic] = []
    for requirement in requirements:
        check_cancelled(control)
        workload = requirement.workload
        weekly = [
            constraint
            for constraint in problem.constraints
            if constraint.kind is ConstraintKind.EVERY_WEEK
            and constraint.scope.resource_id == workload.id
        ]
        if weekly:
            if workload.occurrences_per_cycle < 2:
                errors.append(SolverDiagnostic(
                    "Для проведения в обе недели необходимо минимум два занятия",
                    (workload.id,),
                    tuple(constraint.id for constraint in weekly),
                ))
            for fixed in requirement.constraints:
                if (
                    fixed.kind is ConstraintKind.FIXED_DAY
                    and isinstance(fixed.parameters, FixedDayParameters)
                    and fixed.parameters.week != "ANY"
                ):
                    errors.append(SolverDiagnostic(
                        "Фиксация на одной неделе несовместима с проведением каждую неделю",
                        (workload.id,),
                        tuple(constraint.id for constraint in weekly) + (fixed.id,),
                    ))
        lower = [
            constraint for constraint in requirement.constraints
            if constraint.kind is ConstraintKind.MIN_START_TIME
        ]
        upper = [
            constraint for constraint in requirement.constraints
            if constraint.kind is ConstraintKind.MAX_END_TIME
        ]
        if lower and upper:
            earliest = max(lower, key=lambda item: item.parameters.value)
            latest = min(upper, key=lambda item: item.parameters.value)
            if (
                seconds(earliest.parameters.value) + requirement.duration_minutes * 60
                > seconds(latest.parameters.value)
            ):
                errors.append(SolverDiagnostic(
                    "Длительность занятия несовместима с границами времени",
                    (workload.id,),
                    (earliest.id, latest.id),
                ))

    pairs: dict[tuple[UUID, UUID], dict[ConstraintKind, list[ExtraConstraintSnapshot]]] = {}
    before: dict[tuple[UUID, UUID], ExtraConstraintSnapshot] = {}
    for constraint in problem.constraints:
        check_cancelled(control)
        if not isinstance(constraint.parameters, (RelatedWorkloadParameters, MinimumGapParameters)):
            continue
        source = constraint.scope.resource_id
        target = constraint.parameters.workload_id
        pair = tuple(sorted((source, target)))
        pairs.setdefault(pair, {}).setdefault(constraint.kind, []).append(constraint)
        if constraint.kind is ConstraintKind.BEFORE:
            before[(source, target)] = constraint
    for (source, target), kinds in pairs.items():
        check_cancelled(control)
        required = kinds.get(ConstraintKind.CONSECUTIVE, ())
        forbidden = (
            *kinds.get(ConstraintKind.NOT_CONSECUTIVE, ()),
            *kinds.get(ConstraintKind.MIN_GAP, ()),
        )
        if required and forbidden:
            errors.append(SolverDiagnostic(
                "Обязательная последовательность противоречит запрету или интервалу",
                tuple(dict.fromkeys((source, target))),
                (required[0].id, forbidden[0].id),
            ))
    for (source, target), constraint in before.items():
        check_cancelled(control)
        if source < target and (target, source) in before:
            errors.append(SolverDiagnostic(
                "Взаимно противоположные требования порядка занятий",
                (source, target),
                (constraint.id, before[(target, source)].id),
            ))
    return tuple(errors)


def _candidate_diagnostics(
    problem: ScheduleProblem,
    requirements: tuple[LessonRequirements, ...],
    control: SolverControl,
) -> tuple[SolverDiagnostic, ...]:
    errors: list[SolverDiagnostic] = []
    weekly_ids = {
        constraint.scope.resource_id: constraint.id
        for constraint in problem.constraints
        if constraint.kind is ConstraintKind.EVERY_WEEK
    }

    def restricting_ids(
        requirement: LessonRequirements,
        week: Literal["ODD", "EVEN"] | None = None,
    ) -> tuple[UUID, ...]:
        if not requirement.constraints:
            return ()
        without_constraints = replace(requirement, constraints=())
        if next(
            iter_placements(without_constraints, problem.settings, control, week), None
        ) is None:
            return ()
        return tuple(item.id for item in requirement.constraints)

    for requirement in requirements:
        check_cancelled(control)
        workload_id = requirement.workload.id
        week_constraint = weekly_ids.get(workload_id)
        if week_constraint is not None:
            for week in ("ODD", "EVEN"):
                if next(
                    iter_placements(requirement, problem.settings, control, week),
                    None,
                ) is None:
                    errors.append(SolverDiagnostic(
                        f"Для обязательного проведения отсутствует размещение на неделе {week}",
                        (workload_id,),
                        (week_constraint,) + restricting_ids(requirement, week),
                    ))
        elif next(iter_placements(requirement, problem.settings, control), None) is None:
            errors.append(SolverDiagnostic(
                "Для учебной нагрузки отсутствуют допустимые размещения",
                (workload_id,),
                restricting_ids(requirement),
            ))
    return tuple(errors)


class FeasibleScheduleSolver:
    def solve(
        self, problem: ScheduleProblem, options: ResultOptions, control: SolverControl
    ) -> SolverResult:
        if control.is_cancel_requested():
            return SolverResult(SolverStatus.CANCELLED)
        if any(criterion.is_active for criterion in problem.optimization_criteria):
            raise NotImplementedError("Оптимизация расписания реализуется в задаче #68")

        try:
            requirements, diagnostics = prepare_requirements(problem, control)
        except SearchCancelled:
            return SolverResult(SolverStatus.CANCELLED)
        if diagnostics:
            if control.is_cancel_requested():
                return SolverResult(SolverStatus.CANCELLED)
            control.report_progress(JobProgress(100))
            return SolverResult(SolverStatus.INFEASIBLE, diagnostics=diagnostics)

        try:
            rule_diagnostics = (
                _reference_diagnostics(problem, control)
                or _combination_diagnostics(problem, requirements, control)
                or _candidate_diagnostics(problem, requirements, control)
                if problem.constraints
                else ()
            )
        except SearchCancelled:
            return SolverResult(SolverStatus.CANCELLED)
        if rule_diagnostics:
            if control.is_cancel_requested():
                return SolverResult(SolverStatus.CANCELLED)
            control.report_progress(JobProgress(100))
            return SolverResult(SolverStatus.INFEASIBLE, diagnostics=rule_diagnostics)

        variants: list[ScheduleVariant] = []
        try:
            for placements in find_placements(
                requirements, problem.settings, control, problem.constraints
            ):
                check_cancelled(control)
                variants.append(_validated_variant(problem, placements))
                if len(variants) >= options.limit:
                    break
            check_cancelled(control)
        except SearchCancelled:
            return SolverResult(SolverStatus.CANCELLED)

        control.report_progress(JobProgress(100))
        if variants:
            return SolverResult(SolverStatus.SOLVED, variants=tuple(variants))
        return SolverResult(
            SolverStatus.INFEASIBLE,
            diagnostics=(SolverDiagnostic("Полное допустимое расписание не найдено"),),
        )
