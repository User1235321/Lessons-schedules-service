from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.application.scheduling.use_cases import JobView
from app.domain.scheduling.job import Job, JobStatus, JobType, ResultMode, ResultOptions


class GenerationJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_mode: ResultMode = ResultMode.SINGLE
    top_n: int | None = Field(default=None, strict=True, gt=0)

    def to_options(self) -> ResultOptions:
        return ResultOptions(self.result_mode, self.top_n)


class QueuedJobResponse(BaseModel):
    job_id: UUID
    status: Literal[JobStatus.QUEUED] = JobStatus.QUEUED

    @classmethod
    def of(cls, job: Job) -> Self:
        return cls(job_id=job.id)


class JobResponse(BaseModel):
    id: UUID
    project_id: UUID
    job_type: JobType
    status: JobStatus
    progress: float | None
    error_message: str | None

    @classmethod
    def of(cls, view: JobView) -> Self:
        return cls(
            id=view.job.id,
            project_id=view.job.project_id,
            job_type=view.job.job_type,
            status=view.job.status,
            progress=view.progress.percent if view.progress else None,
            error_message=view.job.error_message,
        )
