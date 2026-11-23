from dataclasses import dataclass

from app.application.auth.access import owned_project
from app.application.scheduling.ports import JobStateStore, JobStateStoreError
from app.application.scheduling.validation_data import enqueue_with_snapshot
from app.application.shared.ports import Clock, IdGenerator
from app.application.shared.uow import UnitOfWork
from app.domain.scheduling.errors import JobNotCancellable, JobResultsUnavailable
from app.domain.scheduling.job import Job, JobProgress, JobStatus, JobType, ResultOptions
from app.domain.scheduling.schedule import Schedule
from app.domain.shared.errors import NotFound
from app.domain.shared.ids import JobId, ProjectId, UserId


@dataclass(frozen=True)
class JobView:
    job: Job
    progress: JobProgress | None


@dataclass
class CreateGenerationJob:
    uow: UnitOfWork
    clock: Clock
    ids: IdGenerator

    def execute(self, user_id: UserId, project_id: ProjectId, options: ResultOptions) -> Job:
        with self.uow:
            project = owned_project(self.uow, project_id, user_id, for_update=True)
            job = Job(
                id=JobId(self.ids.new_id()),
                project_id=project_id,
                job_type=JobType.GENERATE,
                status=JobStatus.QUEUED,
                result_options=options,
                created_at=self.clock.now(),
            )
            enqueue_with_snapshot(self.uow, job, project)
            self.uow.commit()
        return job


@dataclass
class GetGenerationJob:
    uow: UnitOfWork
    state: JobStateStore

    def execute(self, user_id: UserId, job_id: JobId) -> JobView:
        with self.uow:
            job = self.uow.jobs.get_owned(job_id, user_id)
            if job is None:
                raise NotFound("Задание не найдено", job_id=str(job_id))
        try:
            progress = self.state.get_progress(job_id)
        except JobStateStoreError:
            progress = None
        return JobView(job, progress)


@dataclass
class GetGenerationSchedules:
    uow: UnitOfWork

    def execute(self, user_id: UserId, job_id: JobId) -> list[Schedule]:
        with self.uow:
            job = self.uow.jobs.get_owned(job_id, user_id)
            if job is None:
                raise NotFound("Задание не найдено", job_id=str(job_id))
            if job.status is not JobStatus.COMPLETED:
                raise JobResultsUnavailable("Результаты задания ещё недоступны", job_id=str(job_id))
            return self.uow.schedules.list_for_job(job.project_id, job_id)


@dataclass
class CancelGenerationJob:
    uow: UnitOfWork
    state: JobStateStore

    def execute(self, user_id: UserId, job_id: JobId) -> JobView:
        with self.uow:
            job = self.uow.jobs.get_owned_for_update(job_id, user_id)
            if job is None:
                raise NotFound("Задание не найдено", job_id=str(job_id))
            if job.is_terminal:
                raise JobNotCancellable("Задание уже завершено", job_id=str(job_id))
            self.state.request_cancel(job_id)
            progress = self.state.get_progress(job_id)
        return JobView(job, progress)
