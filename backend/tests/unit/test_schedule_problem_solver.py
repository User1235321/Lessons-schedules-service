from app.application.scheduling.ports import ScheduleProblemSolver
from app.domain.projects.settings import ProjectSettings
from app.domain.scheduling.job import JobProgress, ResultOptions
from app.domain.scheduling.problem import ScheduleProblem
from app.domain.scheduling.solver import (
    ScheduleVariant,
    SolverControl,
    SolverDiagnostic,
    SolverResult,
    SolverStatus,
)


class RecordingControl:
    def __init__(self, cancelled: bool = False) -> None:
        self.cancelled = cancelled
        self.progress: list[JobProgress] = []

    def report_progress(self, progress: JobProgress) -> None:
        self.progress.append(progress)

    def is_cancel_requested(self) -> bool:
        return self.cancelled


class ContractSolver:
    def solve(
        self, problem: ScheduleProblem, options: ResultOptions, control: SolverControl
    ) -> SolverResult:
        if control.is_cancel_requested():
            return SolverResult(SolverStatus.CANCELLED)

        control.report_progress(JobProgress(100))
        if not problem.workloads:
            return SolverResult(
                SolverStatus.INFEASIBLE,
                diagnostics=(SolverDiagnostic("Отсутствует учебная нагрузка"),),
            )
        return SolverResult(
            SolverStatus.SOLVED,
            variants=(ScheduleVariant((), ()),)[: options.limit],
        )


def test_concrete_solver_contract_reports_infeasibility_and_progress() -> None:
    solver: ScheduleProblemSolver = ContractSolver()
    control = RecordingControl()
    result = solver.solve(ScheduleProblem(ProjectSettings.default()), ResultOptions(), control)

    assert result.status is SolverStatus.INFEASIBLE
    assert result.diagnostics[0].message == "Отсутствует учебная нагрузка"
    assert control.progress == [JobProgress(100)]


def test_concrete_solver_contract_supports_cancellation() -> None:
    solver: ScheduleProblemSolver = ContractSolver()
    control = RecordingControl(cancelled=True)
    result = solver.solve(ScheduleProblem(ProjectSettings.default()), ResultOptions(), control)

    assert result.status is SolverStatus.CANCELLED
    assert control.progress == []
