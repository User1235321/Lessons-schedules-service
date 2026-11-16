from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentUserDep, UseCasesDep
from app.api.schemas.academic import GroupRequest, GroupResponse, GroupUpdateRequest
from app.domain.shared.ids import GroupId, ProjectId

router = APIRouter(prefix="/projects/{project_id}/groups", tags=["groups"])


@router.get("")
def list_groups(
    project_id: UUID, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> list[GroupResponse]:
    groups = use_cases.list_groups().execute(user_id, ProjectId(project_id))
    return [GroupResponse.of(group) for group in groups]


@router.post("", status_code=201)
def create_group(
    project_id: UUID, body: GroupRequest, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> GroupResponse:
    group = use_cases.create_group().execute(
        user_id, ProjectId(project_id), body.name, body.student_count
    )
    return GroupResponse.of(group)


@router.get("/{group_id}")
def get_group(
    project_id: UUID, group_id: UUID, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> GroupResponse:
    group = use_cases.get_group().execute(user_id, ProjectId(project_id), GroupId(group_id))
    return GroupResponse.of(group)


@router.patch("/{group_id}")
def update_group(
    project_id: UUID,
    group_id: UUID,
    body: GroupUpdateRequest,
    user_id: CurrentUserDep,
    use_cases: UseCasesDep,
) -> GroupResponse:
    group = use_cases.update_group().execute(
        user_id, ProjectId(project_id), GroupId(group_id), body.name, body.student_count
    )
    return GroupResponse.of(group)


@router.delete("/{group_id}", status_code=204)
def delete_group(
    project_id: UUID, group_id: UUID, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> None:
    use_cases.delete_group().execute(user_id, ProjectId(project_id), GroupId(group_id))
