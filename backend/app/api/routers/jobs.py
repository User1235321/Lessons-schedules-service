from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentUserDep, UseCasesDep
from app.api.schemas.jobs import (
    GenerationJobRequest,
    JobResponse,
    QueuedJobResponse,
    ScheduleResponse,
)
from app.domain.shared.ids import JobId, ProjectId

router = APIRouter(tags=["generation-jobs"])


@router.post("/projects/{project_id}/generation-jobs", status_code=202)
def create_generation_job(
    project_id: UUID,
    body: GenerationJobRequest,
    user_id: CurrentUserDep,
    use_cases: UseCasesDep,
) -> QueuedJobResponse:
    job = use_cases.create_generation_job().execute(
        user_id, ProjectId(project_id), body.to_options()
    )
    return QueuedJobResponse.of(job)


@router.get("/generation-jobs/{job_id}")
def get_generation_job(
    job_id: UUID, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> JobResponse:
    return JobResponse.of(use_cases.get_generation_job().execute(user_id, JobId(job_id)))


@router.get("/generation-jobs/{job_id}/schedules")
def get_generation_schedules(
    job_id: UUID, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> list[ScheduleResponse]:
    schedules = use_cases.get_generation_schedules().execute(user_id, JobId(job_id))
    return [ScheduleResponse.of(schedule) for schedule in schedules]


@router.post("/generation-jobs/{job_id}/cancel", status_code=202)
def cancel_generation_job(
    job_id: UUID, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> JobResponse:
    return JobResponse.of(use_cases.cancel_generation_job().execute(user_id, JobId(job_id)))
