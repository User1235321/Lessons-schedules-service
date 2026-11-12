import logging
from dataclasses import dataclass, replace

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
from app.domain.scheduling.solver import SolverResult, SolverStatus
from app.domain.shared.ids import JobId, ScheduleEntryId, ScheduleId

logger = logging.getLogger(__name__)


@dataclass
class JobSolverControl:
    job_id: JobId
    state: JobStateStore

    def report_progress(self, progress: JobProgress) -> None:
        self.state.set_progress(self.job_id, progress)

    def is_cancel_requested(self) -> bool:
        return self.state.is_cancel_requested(self.job_id)


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
                self._clear_state(job.id)
                return None
            if job.status is JobStatus.RUNNING:
                self.uow.jobs.save(
                    job.finish(
                        JobStatus.FAILED, self.clock.now(), "Выполнение прервано аварией Worker"
                    )
                )
                self.uow.commit()
                self._clear_state(job.id)
                return None
            running = job.start(self.clock.now())
            self.uow.jobs.save(running)
            self.uow.commit()
        return running

    def _calculate(self, job: Job) -> None:
        control = JobSolverControl(job.id, self.state)
        try:
            if control.is_cancel_requested():
                result = SolverResult(SolverStatus.CANCELLED)
            else:
                control.report_progress(JobProgress(0))
                problem = self.problems.load(job)
                result = self.solver.solve(problem, job.result_options, control)
                if control.is_cancel_requested():
                    result = SolverResult(SolverStatus.CANCELLED)
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
                self._save_variants(finished, result)
            self.uow.jobs.save(finished)
            self.uow.commit()
        self._clear_state(job.id)

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

    def _clear_state(self, job_id: JobId) -> None:
        try:
            self.state.clear(job_id)
        except JobStateStoreError:
            logger.warning("Не удалось очистить Redis для задания %s", job_id, exc_info=True)
