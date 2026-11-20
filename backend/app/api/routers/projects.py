from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentUserDep, UseCasesDep
from app.api.schemas.projects import CreateProjectRequest, ProjectResponse, UpdateProjectRequest
from app.domain.shared.ids import ProjectId

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
def list_projects(user_id: CurrentUserDep, use_cases: UseCasesDep) -> list[ProjectResponse]:
    return [ProjectResponse.of(project) for project in use_cases.list_projects().execute(user_id)]


@router.post("", status_code=201)
def create_project(
    body: CreateProjectRequest, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> ProjectResponse:
    project = use_cases.create_project().execute(user_id, body.name, body.settings_changes())
    return ProjectResponse.of(project)


@router.get("/{project_id}")
def get_project(
    project_id: UUID, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> ProjectResponse:
    return ProjectResponse.of(use_cases.get_project().execute(user_id, ProjectId(project_id)))


@router.patch("/{project_id}")
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
