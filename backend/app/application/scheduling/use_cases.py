from dataclasses import dataclass

from app.application.auth.access import owned_project
from app.application.scheduling.ports import JobStateStore
from app.application.shared.ports import Clock, IdGenerator
from app.application.shared.uow import UnitOfWork
from app.domain.scheduling.errors import JobNotCancellable
from app.domain.scheduling.job import Job, JobProgress, JobStatus, JobType, ResultOptions
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
            owned_project(self.uow, project_id, user_id)
            job = Job(
                id=JobId(self.ids.new_id()),
                project_id=project_id,
                job_type=JobType.GENERATE,
                status=JobStatus.QUEUED,
                result_options=options,
                created_at=self.clock.now(),
            )
            self.uow.jobs.add(job)
            self.uow.job_outbox.add(job.id, job.created_at)
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
        return JobView(job, self.state.get_progress(job_id))


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
