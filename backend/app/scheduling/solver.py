from collections import defaultdict
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid5

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
    Placement,
    SearchCancelled,
    check_cancelled,
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


class FeasibleScheduleSolver:
    def solve(
        self, problem: ScheduleProblem, options: ResultOptions, control: SolverControl
    ) -> SolverResult:
        if control.is_cancel_requested():
            return SolverResult(SolverStatus.CANCELLED)
        if problem.constraints:
            raise NotImplementedError("Дополнительные ограничения реализуются в задаче #67")
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

        variants: list[ScheduleVariant] = []
        try:
            for placements in find_placements(requirements, problem.settings, control):
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
