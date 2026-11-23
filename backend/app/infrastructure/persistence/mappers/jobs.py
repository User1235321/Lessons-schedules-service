from typing import Any

from pydantic import TypeAdapter

from app.domain.scheduling.job import (
    ExistingScheduleInput,
    Job,
    JobStatus,
    JobType,
    ResultMode,
    ResultOptions,
    SolverDiagnostic,
)
from app.domain.scheduling.problem import ScheduleProblem
from app.domain.shared.ids import JobId, ProjectId
from app.infrastructure.persistence.models.jobs import JobRow

_INPUT = TypeAdapter(ExistingScheduleInput)
problem_codec = TypeAdapter(ScheduleProblem)
_DIAGNOSTICS = TypeAdapter(tuple[SolverDiagnostic, ...])


def job_to_row(job: Job) -> JobRow:
    return JobRow(
        id=job.id,
        project_id=job.project_id,
        job_type=job.job_type.value,
        result_mode=job.result_options.mode.value,
        top_n=job.result_options.top_n,
        existing_input=_INPUT.dump_python(job.existing, mode="json") if job.existing else None,
        created_at=job.created_at,
        **job_update_values(job),
    )


def job_update_values(job: Job) -> dict[str, Any]:
    return {
        "status": job.status.value,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "error_message": job.error_message,
        "diagnostics": _DIAGNOSTICS.dump_python(job.diagnostics, mode="json"),
    }


def job_to_domain(row: JobRow, *, include_input: bool = True) -> Job:
    return Job(
        id=JobId(row.id),
        project_id=ProjectId(row.project_id),
        job_type=JobType(row.job_type),
        status=JobStatus(row.status),
        result_options=ResultOptions(ResultMode(row.result_mode), row.top_n),
        created_at=row.created_at,
        existing=_INPUT.validate_python(row.existing_input)
        if include_input and row.existing_input
        else None,
        started_at=row.started_at,
        finished_at=row.finished_at,
        error_message=row.error_message,
        diagnostics=_DIAGNOSTICS.validate_python(row.diagnostics),
    )
