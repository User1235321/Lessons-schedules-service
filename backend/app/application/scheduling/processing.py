import logging
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field, replace
from datetime import timedelta
from threading import Event, Lock
from time import monotonic

from app.application.scheduling.ports import (
    JobExecutionLock,
    JobProblemSource,
    JobStateStore,
    JobStateStoreError,
    ScheduleProblemSolver,
)
from app.application.shared.ports import Clock, IdGenerator
from app.application.shared.uow import UnitOfWork
from app.domain.scheduling.job import Job, JobMessage, JobProgress, JobStatus
from app.domain.scheduling.schedule import Schedule, ScheduleSource
from app.domain.scheduling.solver import SolverDiagnostic, SolverResult, SolverStatus
from app.domain.shared.ids import JobId, ScheduleEntryId, ScheduleId

logger = logging.getLogger(__name__)
FINAL_PROGRESS_RETENTION = timedelta(hours=24)
POLL_SECONDS = 0.25
HEARTBEAT_SECONDS = 1.0


@dataclass
class JobSolverControl:
    job_id: JobId
    _progress: JobProgress = field(default_factory=lambda: JobProgress(0), init=False)
    _stopped: Event = field(default_factory=Event, init=False)
    _guard: Lock = field(default_factory=Lock, init=False)

    def report_progress(self, progress: JobProgress) -> None:
        with self._guard:
            self._progress = JobProgress(min(99, progress.percent))

    def get_progress(self) -> JobProgress:
        with self._guard:
            return self._progress

    def stop(self) -> None:
        self._stopped.set()

    def is_cancel_requested(self) -> bool:
        return self._stopped.is_set()


@dataclass
class ProcessJob:
    uow: UnitOfWork
    lock: JobExecutionLock
    state: JobStateStore
    problems: JobProblemSource
    solver: ScheduleProblemSolver
    clock: Clock
    ids: IdGenerator

    def execute(self, message: JobMessage) -> bool:
        with self.lock.acquire(message.job_id) as acquired:
            if not acquired:
                return False
            job = self._start(message)
            if job is not None:
                self._calculate(job)
            return True

    def _start(self, message: JobMessage) -> Job | None:
        with self.uow:
            job = self.uow.jobs.get_for_update(message.project_id, message.job_id)
            if job is None or job.job_type is not message.job_type:
                logger.warning("Получено неизвестное задание: %s", message.job_id)
                return None
            if job.is_terminal:
                self._finalize_state(job)
                return None
            if job.status is JobStatus.RUNNING:
                failed = job.finish(
                    JobStatus.FAILED, self.clock.now(), "Выполнение прервано аварией Worker"
                )
                self.uow.jobs.save(failed)
                self.uow.commit()
                self._finalize_state(failed)
                return None
            running = job.start(self.clock.now())
            self.uow.jobs.save(running)
            self.uow.commit()
        return running

    def _calculate(self, job: Job) -> None:
        control = JobSolverControl(job.id)
        try:
            if self.state.is_cancel_requested(job.id):
                result = SolverResult(SolverStatus.CANCELLED)
            else:
                self.state.set_progress(job.id, JobProgress(0))
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(self._solve, job, control)
                    try:
                        result = self._await_result(future, control)
                    finally:
                        control.stop()
            if len(result.variants) > job.result_options.limit:
                raise ValueError("Ядро вернуло слишком много вариантов")
        except Exception as error:
            logger.exception("Ошибка выполнения задания %s", job.id)
            self._finish(job, JobStatus.FAILED, error_message=str(error))
            return
        status = (
            JobStatus.CANCELLED if result.status is SolverStatus.CANCELLED else JobStatus.COMPLETED
        )
        self._finish(job, status, result=result)

    def _solve(self, job: Job, control: JobSolverControl) -> SolverResult:
        if control.is_cancel_requested():
            return SolverResult(SolverStatus.CANCELLED)
        problem = self.problems.load(job)
        if control.is_cancel_requested():
            return SolverResult(SolverStatus.CANCELLED)
        problem.check_size_limits()
        if control.is_cancel_requested():
            return SolverResult(SolverStatus.CANCELLED)
        return self.solver.solve(problem, job.result_options, control)

    def _await_result(
        self, future: Future[SolverResult], control: JobSolverControl
    ) -> SolverResult:
        next_heartbeat = monotonic() + HEARTBEAT_SECONDS
        while True:
            if self.state.is_cancel_requested(control.job_id):
                control.stop()
                return SolverResult(SolverStatus.CANCELLED)
            if future.done():
                return future.result()
            now = monotonic()
            if now >= next_heartbeat:
                self.state.set_progress(control.job_id, control.get_progress())
                next_heartbeat = now + HEARTBEAT_SECONDS
            wait((future,), timeout=POLL_SECONDS)

    def _finish(
        self,
        job: Job,
        status: JobStatus,
        *,
        result: SolverResult | None = None,
        error_message: str | None = None,
    ) -> None:
        with self.uow:
            current = self.uow.jobs.get_for_update(job.project_id, job.id)
            if current is None or current.status is not JobStatus.RUNNING:
                return
            if status is JobStatus.COMPLETED:
                try:
                    if self.state.is_cancel_requested(job.id):
                        status = JobStatus.CANCELLED
                        result = None
                except JobStateStoreError:
                    status = JobStatus.FAILED
                    result = None
                    error_message = "Не удалось проверить отмену перед сохранением результата"
            finished = current.finish(status, self.clock.now(), error_message)
            if result is not None:
                if result.status is SolverStatus.INFEASIBLE:
                    diagnostics = result.diagnostics or (
                        SolverDiagnostic("Допустимое размещение занятий не найдено"),
                    )
                    finished = replace(finished, diagnostics=diagnostics)
                self._save_variants(finished, result)
            self.uow.jobs.save(finished)
            self.uow.commit()
        self._finalize_state(finished)

    def _save_variants(self, job: Job, result: SolverResult) -> None:
        for index, variant in enumerate(result.variants, start=1):
            self.uow.schedules.add(
                Schedule(
                    id=ScheduleId(self.ids.new_id()),
                    project_id=job.project_id,
                    source=ScheduleSource.GENERATED,
                    job_id=job.id,
                    result_index=index,
                    entries=tuple(
                        replace(entry, id=ScheduleEntryId(self.ids.new_id()))
                        for entry in variant.entries
                    ),
                    criterion_scores=variant.criterion_scores,
                    created_at=job.finished_at,
                )
            )

    def _finalize_state(self, job: Job) -> None:
        try:
            if job.status is JobStatus.COMPLETED:
                self.state.complete(job.id, job.finished_at + FINAL_PROGRESS_RETENTION)
            else:
                self.state.clear(job.id)
        except JobStateStoreError:
            logger.warning(
                "Не удалось завершить состояние Redis для задания %s", job.id, exc_info=True
            )
