import hashlib
import secrets
from datetime import datetime, timedelta

import argon2
import jwt
from argon2.exceptions import VerifyMismatchError

from app.domain.shared.ids import UserId


class Argon2PasswordHasher:
    """Реализует PasswordHasher: Argon2id с параметрами argon2-cffi по умолчанию (RFC 9106)."""

    def __init__(self) -> None:
        self._hasher = argon2.PasswordHasher()

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
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

    def new_refresh_token(self) -> str:
        return secrets.token_urlsafe(32)

    def hash_refresh_token(self, refresh_token: str) -> str:
        # Медленный хеш, как у пароля, не нужен: 256 случайных бит не подобрать перебором
        return hashlib.sha256(refresh_token.encode()).hexdigest()
