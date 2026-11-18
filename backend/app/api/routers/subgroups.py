from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentUserDep, UseCasesDep
from app.api.schemas.academic import SubgroupRequest, SubgroupResponse, SubgroupUpdateRequest
from app.domain.shared.ids import GroupId, ProjectId, SubgroupId

# Подгруппы видны и внутри ответа группы. Здесь их меняют по одной (HLD 10)
router = APIRouter(prefix="/projects/{project_id}/subgroups", tags=["subgroups"])


@router.get("")
def list_subgroups(
    project_id: UUID,
    user_id: CurrentUserDep,
    use_cases: UseCasesDep,
    group_id: UUID | None = None,
) -> list[SubgroupResponse]:
    subgroups = use_cases.list_subgroups().execute(
        user_id, ProjectId(project_id), None if group_id is None else GroupId(group_id)
    )
    return [SubgroupResponse.of(subgroup) for subgroup in subgroups]


@router.post("", status_code=201)
def create_subgroup(
    project_id: UUID, body: SubgroupRequest, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> SubgroupResponse:
    subgroup = use_cases.create_subgroup().execute(
        user_id, ProjectId(project_id), GroupId(body.group_id), body.name, body.student_count
    )
    return SubgroupResponse.of(subgroup)


@router.get("/{subgroup_id}")
def get_subgroup(
    project_id: UUID, subgroup_id: UUID, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> SubgroupResponse:
    subgroup = use_cases.get_subgroup().execute(
        user_id, ProjectId(project_id), SubgroupId(subgroup_id)
    )
    return SubgroupResponse.of(subgroup)


@router.patch("/{subgroup_id}")
def update_subgroup(
    project_id: UUID,
    subgroup_id: UUID,
    body: SubgroupUpdateRequest,
    user_id: CurrentUserDep,
    use_cases: UseCasesDep,
) -> SubgroupResponse:
    subgroup = use_cases.update_subgroup().execute(
        user_id, ProjectId(project_id), SubgroupId(subgroup_id), body.name, body.student_count
    )
    return SubgroupResponse.of(subgroup)


@router.delete("/{subgroup_id}", status_code=204)
def delete_subgroup(
    project_id: UUID, subgroup_id: UUID, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> None:
    use_cases.delete_subgroup().execute(user_id, ProjectId(project_id), SubgroupId(subgroup_id))
