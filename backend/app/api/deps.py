from typing import Annotated, Protocol

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.cookies import RefreshCookie
from app.application.academic.groups import (
    CreateGroup,
    CreateSubgroup,
    DeleteGroup,
    DeleteSubgroup,
    GetGroup,
    GetSubgroup,
    ListGroups,
    ListSubgroups,
    UpdateGroup,
    UpdateSubgroup,
)
from app.application.academic.rooms import (
    CreateRoom,
    DeleteRoom,
    GetRoom,
    ListRooms,
    UpdateRoom,
)
from app.application.academic.streams import (
    CreateStream,
    DeleteStream,
    GetStream,
    ListStreams,
    UpdateStream,
)
from app.application.academic.subjects import (
    CreateSubject,
    DeleteSubject,
    GetSubject,
    ListSubjects,
    UpdateSubject,
)
from app.application.academic.teachers import (
    CreateTeacher,
    DeleteTeacher,
    GetTeacher,
    ListTeachers,
    UpdateTeacher,
)
from app.application.academic.workloads import (
    CreateWorkload,
    DeleteWorkload,
    GetWorkload,
    ListWorkloads,
    UpdateWorkload,
)
from app.application.auth.password_reset import ConfirmPasswordReset, RequestPasswordReset
from app.application.auth.use_cases import (
    Authenticate,
    GetCurrentUser,
    Login,
    Logout,
    Refresh,
    Register,
)
from app.application.import_export.schedules import ImportSchedule
from app.application.projects.use_cases import (
    CreateProject,
    DeleteProject,
    GetProject,
    ListProjects,
    UpdateProject,
)
from app.application.scheduling.schedules import (
    GetSchedule,
    QueueScheduleProcessing,
    UpdateScheduleEntry,
    ValidateSchedule,
)
from app.application.scheduling.use_cases import (
    CancelGenerationJob,
    CreateGenerationJob,
    GetGenerationJob,
    GetGenerationSchedules,
)
from app.domain.shared.errors import NotAuthenticated
from app.domain.shared.ids import UserId


class UseCases(Protocol):
    """Фабрики сценариев. Реализует bootstrap.Container: api не импортирует bootstrap."""

    def register(self) -> Register: ...

    def login(self) -> Login: ...

    def refresh(self) -> Refresh: ...

    def request_password_reset(self) -> RequestPasswordReset: ...

    def confirm_password_reset(self) -> ConfirmPasswordReset: ...

    def logout(self) -> Logout: ...

    def authenticate(self) -> Authenticate: ...

    def get_current_user(self) -> GetCurrentUser: ...

    def create_project(self) -> CreateProject: ...
    def create_generation_job(self) -> CreateGenerationJob: ...

    def list_projects(self) -> ListProjects: ...

    def get_project(self) -> GetProject: ...

    def update_project(self) -> UpdateProject: ...

    def delete_project(self) -> DeleteProject: ...

    def create_subject(self) -> CreateSubject: ...

    def list_subjects(self) -> ListSubjects: ...

    def get_subject(self) -> GetSubject: ...

    def update_subject(self) -> UpdateSubject: ...

    def delete_subject(self) -> DeleteSubject: ...

    def create_teacher(self) -> CreateTeacher: ...

    def list_teachers(self) -> ListTeachers: ...

    def get_teacher(self) -> GetTeacher: ...

    def update_teacher(self) -> UpdateTeacher: ...

    def delete_teacher(self) -> DeleteTeacher: ...

    def create_group(self) -> CreateGroup: ...

    def list_groups(self) -> ListGroups: ...

    def get_group(self) -> GetGroup: ...

    def update_group(self) -> UpdateGroup: ...

    def delete_group(self) -> DeleteGroup: ...

    def create_subgroup(self) -> CreateSubgroup: ...

    def list_subgroups(self) -> ListSubgroups: ...

    def get_subgroup(self) -> GetSubgroup: ...

    def update_subgroup(self) -> UpdateSubgroup: ...

    def delete_subgroup(self) -> DeleteSubgroup: ...


    def create_room(self) -> CreateRoom: ...

    def list_rooms(self) -> ListRooms: ...

    def get_room(self) -> GetRoom: ...

    def update_room(self) -> UpdateRoom: ...

    def delete_room(self) -> DeleteRoom: ...

    def create_stream(self) -> CreateStream: ...

    def list_streams(self) -> ListStreams: ...

    def get_stream(self) -> GetStream: ...

    def update_stream(self) -> UpdateStream: ...

    def delete_stream(self) -> DeleteStream: ...

    def create_workload(self) -> CreateWorkload: ...

    def list_workloads(self) -> ListWorkloads: ...

    def get_workload(self) -> GetWorkload: ...

    def update_workload(self) -> UpdateWorkload: ...

    def delete_workload(self) -> DeleteWorkload: ...

    def get_generation_job(self) -> GetGenerationJob: ...

    def get_generation_schedules(self) -> GetGenerationSchedules: ...

    def get_schedule(self) -> GetSchedule: ...

    def import_schedule(self) -> ImportSchedule: ...

    def queue_schedule_processing(self) -> QueueScheduleProcessing: ...

    def update_schedule_entry(self) -> UpdateScheduleEntry: ...

    def validate_schedule(self) -> ValidateSchedule: ...

    def cancel_generation_job(self) -> CancelGenerationJob: ...


def get_use_cases(request: Request) -> UseCases:
    return request.app.state.container


UseCasesDep = Annotated[UseCases, Depends(get_use_cases)]


def get_refresh_cookie(request: Request) -> RefreshCookie:
    return request.app.state.refresh_cookie


RefreshCookieDep = Annotated[RefreshCookie, Depends(get_refresh_cookie)]

# Без auto_error: свой ответ FastAPI не в формате ошибок из HLD 10
_bearer = HTTPBearer(auto_error=False)


def get_current_user_id(
    use_cases: UseCasesDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> UserId:
    """Пользователь из заголовка ``Authorization: Bearer <access-токен>`` (NF_Security_1)."""
    if credentials is None:
        raise NotAuthenticated("Требуется вход в систему")
    return use_cases.authenticate().execute(credentials.credentials)


CurrentUserDep = Annotated[UserId, Depends(get_current_user_id)]
