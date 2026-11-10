from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentUserDep, UseCasesDep
from app.api.schemas.projects import CreateProjectRequest, ProjectResponse, UpdateProjectRequest
from app.domain.shared.ids import ProjectId

# Пустые параметры режимов в ответ не попадают, как в test-data: {"type": "HOUR_START"}
router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model_exclude_none=True)
def list_projects(user_id: CurrentUserDep, use_cases: UseCasesDep) -> list[ProjectResponse]:
    return [ProjectResponse.of(project) for project in use_cases.list_projects().execute(user_id)]


@router.post("", status_code=201, response_model_exclude_none=True)
def create_project(
    body: CreateProjectRequest, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> ProjectResponse:
    project = use_cases.create_project().execute(user_id, body.name, body.settings_changes())
    return ProjectResponse.of(project)


@router.get("/{project_id}", response_model_exclude_none=True)
def get_project(
    project_id: UUID, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> ProjectResponse:
    return ProjectResponse.of(use_cases.get_project().execute(user_id, ProjectId(project_id)))


@router.patch("/{project_id}", response_model_exclude_none=True)
def update_project(
    project_id: UUID, body: UpdateProjectRequest, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> ProjectResponse:
    project = use_cases.update_project().execute(
        user_id, ProjectId(project_id), body.name, body.settings_changes()
    )
    return ProjectResponse.of(project)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: UUID, user_id: CurrentUserDep, use_cases: UseCasesDep) -> None:
    use_cases.delete_project().execute(user_id, ProjectId(project_id))
