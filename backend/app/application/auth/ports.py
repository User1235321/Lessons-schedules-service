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
