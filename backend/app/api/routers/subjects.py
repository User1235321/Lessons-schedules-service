from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentUserDep, UseCasesDep
from app.api.schemas.academic import SubjectRequest, SubjectResponse, SubjectUpdateRequest
from app.domain.shared.ids import ProjectId, SubjectId

router = APIRouter(prefix="/projects/{project_id}/subjects", tags=["subjects"])


@router.get("")
def list_subjects(
    project_id: UUID, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> list[SubjectResponse]:
    subjects = use_cases.list_subjects().execute(user_id, ProjectId(project_id))
    return [SubjectResponse.of(subject) for subject in subjects]


@router.post("", status_code=201)
def create_subject(
    project_id: UUID, body: SubjectRequest, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> SubjectResponse:
    subject = use_cases.create_subject().execute(user_id, ProjectId(project_id), body.name)
    return SubjectResponse.of(subject)


@router.get("/{subject_id}")
def get_subject(
    project_id: UUID, subject_id: UUID, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> SubjectResponse:
    subject = use_cases.get_subject().execute(user_id, ProjectId(project_id), SubjectId(subject_id))
    return SubjectResponse.of(subject)


@router.patch("/{subject_id}")
def update_subject(
    project_id: UUID,
    subject_id: UUID,
    body: SubjectUpdateRequest,
    user_id: CurrentUserDep,
    use_cases: UseCasesDep,
) -> SubjectResponse:
    subject = use_cases.update_subject().execute(
        user_id, ProjectId(project_id), SubjectId(subject_id), body.name
    )
    return SubjectResponse.of(subject)


@router.delete("/{subject_id}", status_code=204)
def delete_subject(
    project_id: UUID, subject_id: UUID, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> None:
    use_cases.delete_subject().execute(user_id, ProjectId(project_id), SubjectId(subject_id))
