from app.domain.scheduling.job import JobProgress, ResultOptions
from app.domain.scheduling.problem import ScheduleProblem
from app.domain.scheduling.solver import (
    ScheduleVariant,
    SolverControl,
    SolverResult,
    SolverStatus,
)


class PreviewScheduleSolver:
    def solve(
        self, problem: ScheduleProblem, options: ResultOptions, control: SolverControl
    ) -> SolverResult:
        if control.is_cancel_requested():
            return SolverResult(SolverStatus.CANCELLED)
        if problem.workloads:
            raise NotImplementedError("Расчёт расписания по учебной нагрузке ещё не реализован")
        control.report_progress(JobProgress(50))
        if control.is_cancel_requested():
            return SolverResult(SolverStatus.CANCELLED)
        return SolverResult(SolverStatus.SOLVED, (ScheduleVariant((), ()),))
