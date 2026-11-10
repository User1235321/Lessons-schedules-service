from typing import Protocol

from app.domain.scheduling.job import Job, JobMessage, JobProgress, ResultOptions
from app.domain.scheduling.schedule import Schedule
from app.domain.scheduling.solver import SolverControl, SolverResult
from app.domain.shared.ids import JobId, ProjectId, ScheduleId


class JobRepository(Protocol):
    def add(self, job: Job) -> None: ...

    def get(self, project_id: ProjectId, job_id: JobId) -> Job | None: ...

    def get_for_update(self, project_id: ProjectId, job_id: JobId) -> Job | None: ...

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
