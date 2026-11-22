from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep

from app.domain.scheduling.job import JobProgress
from app.domain.scheduling.solver import SolverStatus
from app.infrastructure.solver_process import SupervisedSolver


class SleepingSolver:
    def solve(self, control):
        control.report_progress(JobProgress(37))
        # Имитирует блокирующий участок ядра без проверок отмены.
        sleep(30)


def test_worker_refreshes_progress_and_stops_blocked_core_within_two_seconds():
    class Control:
        def __init__(self):
            self.heartbeats = []
            self.ready = Event()
            self.cancel = Event()

        def report_progress(self, value):
            if value.percent == 37:
                self.heartbeats.append(monotonic())
                if len(self.heartbeats) >= 2:
                    self.ready.set()

        def is_cancel_requested(self):
            return self.cancel.is_set()

    control = Control()
    with ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(SupervisedSolver(SleepingSolver()).solve, control)
        try:
            assert control.ready.wait(10)
            assert control.heartbeats[1] - control.heartbeats[0] <= 2
        finally:
            control.cancel.set()
        assert result.result(timeout=2).status is SolverStatus.CANCELLED
