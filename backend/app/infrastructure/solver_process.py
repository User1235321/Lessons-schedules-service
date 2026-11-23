"""Изолированный CPU-процесс. Только родитель владеет SQL, Kafka и Redis."""

import logging
import multiprocessing
from concurrent.futures import Future, ThreadPoolExecutor, wait
from multiprocessing.connection import Connection
from time import monotonic

from app.domain.scheduling.job import JobProgress
from app.domain.scheduling.solver import SolverControl, SolverResult, SolverStatus

POLL_SECONDS = 0.25
HEARTBEAT_SECONDS = 1.0


class _ChildControl:
    def __init__(self, progress, stop) -> None:
        self.progress = progress
        self.stop = stop

    def report_progress(self, progress: JobProgress) -> None:
        self.progress.value = progress.percent

    def is_cancel_requested(self) -> bool:
        return self.stop.is_set()


def _run(solver, inputs, progress, stop, output: Connection) -> None:
    with output:
        try:
            result = solver.solve(*inputs, _ChildControl(progress, stop))
        except Exception as error:
            logging.getLogger(__name__).exception("Ошибка ядра планировщика")
            output.send((None, f"{type(error).__name__}: {error}"))
        else:
            output.send((result, None))


class SupervisedSolver:
    def __init__(self, solver) -> None:
        self.solver = solver

    def solve(self, *args) -> SolverResult:
        *inputs, control = args
        if control.is_cancel_requested():
            return SolverResult(SolverStatus.CANCELLED)
        context = multiprocessing.get_context("spawn")
        progress = context.Value("d", 0)
        stop = context.Event()
        reader, writer = context.Pipe(duplex=False)
        process = context.Process(target=_run, args=(self.solver, inputs, progress, stop, writer))
        with reader, writer, ThreadPoolExecutor(max_workers=1) as executor:
            process.start()
            writer.close()
            try:
                result = executor.submit(self._receive, reader)
                return self._wait(result, progress, control)
            finally:
                stop.set()
                process.join(POLL_SECONDS)
                if process.is_alive():
                    process.terminate()
                    process.join(POLL_SECONDS)
                if process.is_alive():
                    process.kill()
                    process.join()
                process.close()

    @staticmethod
    def _receive(output: Connection) -> SolverResult:
        try:
            result, error = output.recv()
        except EOFError as exc:
            raise RuntimeError("Процесс планировщика завершился без результата") from exc
        if error is not None:
            raise RuntimeError(error)
        return result

    @staticmethod
    def _wait(result: Future[SolverResult], progress, control: SolverControl) -> SolverResult:
        next_heartbeat = monotonic()
        while True:
            if control.is_cancel_requested():
                return SolverResult(SolverStatus.CANCELLED)
            if result.done():
                return result.result()
            now = monotonic()
            if now >= next_heartbeat:
                control.report_progress(JobProgress(progress.value))
                next_heartbeat = now + HEARTBEAT_SECONDS
            wait((result,), timeout=POLL_SECONDS)
