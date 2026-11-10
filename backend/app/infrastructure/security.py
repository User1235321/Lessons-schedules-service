import hashlib
import secrets
from datetime import datetime, timedelta
from functools import cache
from uuid import UUID

import argon2
import jwt
from argon2.exceptions import VerifyMismatchError

from app.domain.auth.errors import InvalidAccessToken
from app.domain.shared.ids import UserId

# Параметры argon2-cffi по умолчанию (RFC 9106). Одни и те же для настоящих и фиктивного хеша
_ARGON2 = argon2.PasswordHasher()


@cache
def _dummy_hash() -> str:
    # Один раз на процесс: Argon2 намеренно медленный
    return _ARGON2.hash(secrets.token_urlsafe(32))


class Argon2PasswordHasher:
    """Реализует PasswordHasher: Argon2id."""

    def __init__(self) -> None:
        self.dummy_hash = _dummy_hash()

    def hash(self, password: str) -> str:
        return _ARGON2.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        try:
            return _ARGON2.verify(password_hash, password)
        except VerifyMismatchError:
            return False


class JwtTokenService:
    """Реализует TokenService. Access-токен — JWT (HS256), refresh-токен — случайная строка."""

    algorithm = "HS256"

    def __init__(self, secret: str, access_ttl: timedelta) -> None:
        self._secret = secret
        self._access_ttl = access_ttl

    def issue_access_token(self, user_id: UserId, now: datetime) -> str:
        claims = {"sub": str(user_id), "iat": now, "exp": now + self._access_ttl}
        return jwt.encode(claims, self._secret, algorithm=self.algorithm)

    def read_access_token(self, access_token: str, now: datetime) -> UserId:
        try:
            claims = jwt.decode(
                access_token,
                self._secret,
                algorithms=[self.algorithm],
                # Срок сверяем с Clock, а не с часами PyJWT, чтобы проверять его в тестах (HLD 15.3)
                options={"verify_exp": False, "verify_iat": False, "require": ["sub", "exp"]},
            )
            user_id = UserId(UUID(claims["sub"]))
            expired = now.timestamp() >= claims["exp"]
        except (jwt.InvalidTokenError, ValueError, TypeError) as error:
            raise InvalidAccessToken("Недействительный токен доступа") from error
        if expired:
            raise InvalidAccessToken("Срок действия токена доступа истёк")
        return user_id

    def new_refresh_token(self) -> str:
        return secrets.token_urlsafe(32)

    def hash_refresh_token(self, refresh_token: str) -> str:
        # Медленный хеш, как у пароля, не нужен: 256 случайных бит не подобрать перебором
        return hashlib.sha256(refresh_token.encode()).hexdigest()
