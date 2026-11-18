from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentUserDep, UseCasesDep
from app.api.schemas.constraints import CriterionSchema, ReplaceCriteriaRequest
from app.domain.shared.ids import ProjectId

router = APIRouter(
    prefix="/projects/{project_id}/optimization-criteria", tags=["optimization-criteria"]
)


@router.get("")
def list_criteria(
    project_id: UUID, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> list[CriterionSchema]:
    criteria = use_cases.list_criteria().execute(user_id, ProjectId(project_id))
    return [CriterionSchema.of(criterion) for criterion in criteria]


@router.put("")
def replace_criteria(
    project_id: UUID,
    body: ReplaceCriteriaRequest,
    user_id: CurrentUserDep,
    use_cases: UseCasesDep,
) -> list[CriterionSchema]:
    criteria = use_cases.replace_criteria().execute(
        user_id, ProjectId(project_id), tuple(item.to_domain() for item in body.criteria)
    )
    return [CriterionSchema.of(criterion) for criterion in criteria]
