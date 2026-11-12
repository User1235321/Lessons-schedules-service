from app.domain.scheduling.job import Job, ResultOptions
from app.domain.scheduling.problem import ScheduleProblem
from app.domain.scheduling.solver import SolverControl, SolverResult


class UnavailableJobProblemSource:
    def load(self, job: Job) -> ScheduleProblem:
        raise RuntimeError("Загрузка снимка учебных данных ещё не реализована")


class UnavailableScheduleSolver:
    def solve(
        self, problem: ScheduleProblem, options: ResultOptions, control: SolverControl
    ) -> SolverResult:
        raise RuntimeError("Вычислительное ядро расписания ещё не реализовано")
