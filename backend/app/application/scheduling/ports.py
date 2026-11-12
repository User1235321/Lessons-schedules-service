from contextlib import AbstractContextManager
from datetime import datetime
from typing import Protocol

from app.domain.scheduling.job import Job, JobMessage, JobProgress, ResultOptions
from app.domain.scheduling.problem import ScheduleProblem
from app.domain.scheduling.schedule import Schedule
from app.domain.scheduling.solver import SolverControl, SolverResult
from app.domain.shared.ids import JobId, ProjectId, ScheduleId, UserId


class JobRepository(Protocol):
    def add(self, job: Job) -> None: ...

    def get(self, project_id: ProjectId, job_id: JobId) -> Job | None: ...

    def get_for_update(self, project_id: ProjectId, job_id: JobId) -> Job | None: ...

    def get_owned(self, job_id: JobId, owner_id: UserId) -> Job | None: ...

    def get_owned_for_update(self, job_id: JobId, owner_id: UserId) -> Job | None: ...

    def save(self, job: Job) -> None: ...


class ScheduleRepository(Protocol):
    def add(self, schedule: Schedule) -> None: ...

    def get(self, project_id: ProjectId, schedule_id: ScheduleId) -> Schedule | None: ...

    def get_for_update(self, project_id: ProjectId, schedule_id: ScheduleId) -> Schedule | None: ...

    def list_for_job(self, project_id: ProjectId, job_id: JobId) -> list[Schedule]: ...

    def list_in_project(self, project_id: ProjectId) -> list[Schedule]: ...

    def save(self, schedule: Schedule) -> None: ...


class JobPublishError(Exception):
    pass


class JobStateStoreError(Exception):
    pass


class JobPublisher(Protocol):
    def publish(self, message: JobMessage) -> None: ...


class JobOutbox(Protocol):
    def add(self, job_id: JobId, created_at: datetime) -> None: ...

    def get_pending_for_update(self) -> JobMessage | None: ...

    def mark_published(self, job_id: JobId, published_at: datetime) -> None: ...


class JobExecutionLock(Protocol):
    def acquire(self, job_id: JobId) -> AbstractContextManager[bool]: ...


class JobProblemSource(Protocol):
    def load(self, job: Job) -> ScheduleProblem: ...


class JobStateStore(Protocol):
    def get_progress(self, job_id: JobId) -> JobProgress | None: ...

    def set_progress(self, job_id: JobId, progress: JobProgress) -> None: ...

    def request_cancel(self, job_id: JobId) -> None: ...

    def is_cancel_requested(self, job_id: JobId) -> bool: ...

    def clear(self, job_id: JobId) -> None: ...


class ScheduleSolver[InputT](Protocol):
    def solve(
        self, problem: InputT, options: ResultOptions, control: SolverControl
    ) -> SolverResult: ...


type ScheduleProblemSolver = ScheduleSolver[ScheduleProblem]
