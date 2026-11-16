from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentUserDep, UseCasesDep
from app.api.schemas.academic_resources import (
    WorkloadRequest,
    WorkloadResponse,
    WorkloadUpdateRequest,
)
from app.domain.shared.ids import ProjectId, WorkloadId

router = APIRouter(prefix="/projects/{project_id}/workloads", tags=["workloads"])


@router.get("")
def list_workloads(
    project_id: UUID, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> list[WorkloadResponse]:
    workloads = use_cases.list_workloads().execute(user_id, ProjectId(project_id))
    return [WorkloadResponse.of(workload) for workload in workloads]


@router.post("", status_code=201)
def create_workload(
    project_id: UUID, body: WorkloadRequest, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> WorkloadResponse:
    workload = use_cases.create_workload().execute(
        user_id, ProjectId(project_id), body.to_draft()
    )
    return WorkloadResponse.of(workload)


@router.get("/{workload_id}")
def get_workload(
    project_id: UUID, workload_id: UUID, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> WorkloadResponse:
    workload = use_cases.get_workload().execute(
        user_id, ProjectId(project_id), WorkloadId(workload_id)
    )
    return WorkloadResponse.of(workload)


@router.patch("/{workload_id}")
def update_workload(
    project_id: UUID,
    workload_id: UUID,
    body: WorkloadUpdateRequest,
    user_id: CurrentUserDep,
    use_cases: UseCasesDep,
) -> WorkloadResponse:
    workload = use_cases.update_workload().execute(
        user_id, ProjectId(project_id), WorkloadId(workload_id), body.to_changes()
    )
    return WorkloadResponse.of(workload)


@router.delete("/{workload_id}", status_code=204)
def delete_workload(
    project_id: UUID, workload_id: UUID, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> None:
    use_cases.delete_workload().execute(
        user_id, ProjectId(project_id), WorkloadId(workload_id)
    )
