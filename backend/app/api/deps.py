from typing import Annotated, Protocol

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.cookies import RefreshCookie
from app.application.auth.use_cases import (
    Authenticate,
    GetCurrentUser,
    Login,
    Logout,
    Refresh,
    Register,
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
