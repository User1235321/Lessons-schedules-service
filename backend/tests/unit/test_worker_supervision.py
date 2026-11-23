from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep

from app.domain.scheduling.job import JobProgress
from app.domain.scheduling.solver import SolverResult, SolverStatus
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


class ImmediateSolver:
    def solve(self, control):
        return SolverResult(SolverStatus.INFEASIBLE)


def test_worker_monitors_cancel_while_receiving_result(monkeypatch):
    receiving, release, cancel, observed = Event(), Event(), Event(), Event()
    receive = SupervisedSolver._receive

    def blocked_receive(output):
        receiving.set()
        assert release.wait(10)
        return receive(output)

    class Control:
        def report_progress(self, value):
            pass

        def is_cancel_requested(self):
            if cancel.is_set():
                observed.set()
                return True
            return False

    monkeypatch.setattr(SupervisedSolver, "_receive", staticmethod(blocked_receive))
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(SupervisedSolver(ImmediateSolver()).solve, Control())
        try:
            assert receiving.wait(10)
            cancel.set()
            assert observed.wait(2)
        finally:
            release.set()
        assert future.result(timeout=10).status is SolverStatus.CANCELLED
