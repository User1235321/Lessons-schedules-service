from typing import Any

from app.domain.scheduling.job import Job, JobStatus, JobType, ResultMode, ResultOptions
from app.domain.shared.ids import JobId, ProjectId
from app.infrastructure.persistence.models.jobs import JobRow


def job_to_row(job: Job) -> JobRow:
    return JobRow(
        id=job.id,
        project_id=job.project_id,
        job_type=job.job_type.value,
        result_mode=job.result_options.mode.value,
        top_n=job.result_options.top_n,
        created_at=job.created_at,
        **job_update_values(job),
    )


def job_update_values(job: Job) -> dict[str, Any]:
    return {
        "status": job.status.value,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "error_message": job.error_message,
    }


def job_to_domain(row: JobRow) -> Job:
    return Job(
        id=JobId(row.id),
        project_id=ProjectId(row.project_id),
        job_type=JobType(row.job_type),
        status=JobStatus(row.status),
        result_options=ResultOptions(ResultMode(row.result_mode), row.top_n),
        created_at=row.created_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
        error_message=row.error_message,
    )
