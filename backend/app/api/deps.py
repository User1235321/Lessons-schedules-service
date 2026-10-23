from typing import Annotated, Protocol

from fastapi import Depends, Request

from app.application.auth.use_cases import Login, Register


class UseCases(Protocol):
    """Фабрики сценариев. Реализует bootstrap.Container: api не импортирует bootstrap."""

    def register(self) -> Register: ...

    def login(self) -> Login: ...


def get_use_cases(request: Request) -> UseCases:
    return request.app.state.container


UseCasesDep = Annotated[UseCases, Depends(get_use_cases)]
