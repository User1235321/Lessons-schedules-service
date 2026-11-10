from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentUserDep, UseCasesDep
from app.api.schemas.academic import TeacherRequest, TeacherResponse, TeacherUpdateRequest
from app.domain.shared.ids import ProjectId, TeacherId

router = APIRouter(prefix="/projects/{project_id}/teachers", tags=["teachers"])


@router.get("")
def list_teachers(
    project_id: UUID, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> list[TeacherResponse]:
    teachers = use_cases.list_teachers().execute(user_id, ProjectId(project_id))
    return [TeacherResponse.of(teacher) for teacher in teachers]


@router.post("", status_code=201)
def create_teacher(
    project_id: UUID, body: TeacherRequest, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> TeacherResponse:
    teacher = use_cases.create_teacher().execute(user_id, ProjectId(project_id), body.to_draft())
    return TeacherResponse.of(teacher)


@router.get("/{teacher_id}")
def get_teacher(
    project_id: UUID, teacher_id: UUID, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> TeacherResponse:
    teacher = use_cases.get_teacher().execute(user_id, ProjectId(project_id), TeacherId(teacher_id))
    return TeacherResponse.of(teacher)


@router.patch("/{teacher_id}")
def update_teacher(
    project_id: UUID,
    teacher_id: UUID,
    body: TeacherUpdateRequest,
    user_id: CurrentUserDep,
    use_cases: UseCasesDep,
) -> TeacherResponse:
    teacher = use_cases.update_teacher().execute(
        user_id, ProjectId(project_id), TeacherId(teacher_id), body.to_changes()
    )
    return TeacherResponse.of(teacher)


@router.delete("/{teacher_id}", status_code=204)
def delete_teacher(
    project_id: UUID, teacher_id: UUID, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> None:
    use_cases.delete_teacher().execute(user_id, ProjectId(project_id), TeacherId(teacher_id))
