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
from app.application.auth.use_cases import (
    Authenticate,
    GetCurrentUser,
    Login,
    Logout,
    Refresh,
    Register,
)
from app.application.projects.use_cases import (
    CreateProject,
    DeleteProject,
    GetProject,
    ListProjects,
    UpdateProject,
)
from app.domain.shared.errors import NotAuthenticated
from app.domain.shared.ids import UserId


class UseCases(Protocol):
    """Фабрики сценариев. Реализует bootstrap.Container: api не импортирует bootstrap."""

    def register(self) -> Register: ...

    def login(self) -> Login: ...

    def refresh(self) -> Refresh: ...

    def logout(self) -> Logout: ...

    def authenticate(self) -> Authenticate: ...

    def get_current_user(self) -> GetCurrentUser: ...

    def create_project(self) -> CreateProject: ...

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
