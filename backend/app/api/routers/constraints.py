from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentUserDep, UseCasesDep
from app.api.schemas.constraints import (
    ConstraintResponse,
    CreateConstraintRequest,
    UpdateConstraintRequest,
)
from app.domain.shared.ids import ProjectId

router = APIRouter(prefix="/projects/{project_id}/constraints", tags=["constraints"])


@router.get("")
def list_constraints(
    project_id: UUID, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> list[ConstraintResponse]:
    constraints = use_cases.list_constraints().execute(user_id, ProjectId(project_id))
    return [ConstraintResponse.of(project_id, constraint) for constraint in constraints]


@router.post("", status_code=201)
def create_constraint(
    project_id: UUID,
    body: CreateConstraintRequest,
    user_id: CurrentUserDep,
    use_cases: UseCasesDep,
) -> ConstraintResponse:
    constraint = use_cases.create_constraint().execute(
        user_id, ProjectId(project_id), body.to_draft()
    )
    return ConstraintResponse.of(project_id, constraint)


@router.patch("/{constraint_id}")
def update_constraint(
    project_id: UUID,
    constraint_id: UUID,
    body: UpdateConstraintRequest,
    user_id: CurrentUserDep,
    use_cases: UseCasesDep,
) -> ConstraintResponse:
    constraint = use_cases.update_constraint().execute(
        user_id, ProjectId(project_id), constraint_id, body.to_changes()
    )
    return ConstraintResponse.of(project_id, constraint)


@router.delete("/{constraint_id}", status_code=204)
def delete_constraint(
    project_id: UUID,
    constraint_id: UUID,
    user_id: CurrentUserDep,
    use_cases: UseCasesDep,
) -> None:
    use_cases.delete_constraint().execute(user_id, ProjectId(project_id), constraint_id)
