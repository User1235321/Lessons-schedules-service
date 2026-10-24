from dataclasses import dataclass
from datetime import UTC
from typing import Annotated, ClassVar

from fastapi import Cookie, Response

from app.application.auth.use_cases import AuthTokens

REFRESH_COOKIE_NAME = "refresh_token"

# Значение cookie, если браузер его прислал
RefreshTokenCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)]


@dataclass(frozen=True)
class RefreshCookie:
    """Refresh-токен хранится только в httpOnly-cookie.

    Скрипт на странице, даже внедрённый через XSS, не может его прочитать.
    С SameSite=Strict браузер не приложит cookie к запросу с чужого сайта,
    а с Path=/auth — к остальным запросам к API.
    """

    secure: bool
    path: ClassVar[str] = "/auth"

    def set(self, response: Response, tokens: AuthTokens) -> None:
        response.set_cookie(
            REFRESH_COOKIE_NAME,
            tokens.refresh_token,
            # Cookie живёт столько же, сколько сессия. Starlette требует время именно в UTC
            expires=tokens.refresh_expires_at.astimezone(UTC),
            path=self.path,
            secure=self.secure,
            httponly=True,
            samesite="strict",
        )

    def clear(self, response: Response) -> None:
        response.delete_cookie(
            REFRESH_COOKIE_NAME,
            path=self.path,
            secure=self.secure,
            httponly=True,
            samesite="strict",
        )
