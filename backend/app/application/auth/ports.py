from datetime import datetime
from typing import Protocol

from app.domain.auth.session import UserSession
from app.domain.auth.user import Email, User
from app.domain.shared.ids import UserId


class UserRepository(Protocol):
    def add(self, user: User) -> None:
        """Сохраняет новую учётную запись. Если адрес занят — EmailAlreadyRegistered."""
        ...

    def get(self, user_id: UserId) -> User | None: ...

    def get_by_email(self, email: Email) -> User | None: ...


class UserSessionRepository(Protocol):
    def add(self, session: UserSession) -> None: ...

    def get_by_token_hash(self, refresh_token_hash: str) -> UserSession | None: ...

    def save(self, session: UserSession) -> None: ...


class PasswordHasher(Protocol):
    """Адаптивное хеширование паролей (HLD 8)."""

    def hash(self, password: str) -> str: ...

    def verify(self, password: str, password_hash: str) -> bool: ...


class TokenService(Protocol):
    """Access-токены и refresh-токены (HLD 8)."""

    def issue_access_token(self, user_id: UserId, now: datetime) -> str: ...

    def new_refresh_token(self) -> str: ...

    def hash_refresh_token(self, refresh_token: str) -> str:
        """Одинаковый токен всегда даёт одинаковый хеш: по нему ищется сессия."""
        ...
