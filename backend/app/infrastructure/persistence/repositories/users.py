from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.auth.errors import EmailAlreadyRegistered
from app.domain.auth.session import UserSession
from app.domain.auth.user import Email, User
from app.domain.shared.errors import NotFound
from app.domain.shared.ids import UserId
from app.infrastructure.persistence.errors import violated_constraint
from app.infrastructure.persistence.mappers.users import (
    session_columns,
    session_to_domain,
    session_to_row,
    user_to_domain,
    user_to_row,
)
from app.infrastructure.persistence.models import UserRow, UserSessionRow


class SqlUserRepository:
    """Реализует UserRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, user: User) -> None:
        self._session.add(user_to_row(user))
        try:
            # Сразу, а не при commit: две одновременные регистрации ловит только UNIQUE
            self._session.flush()
        except IntegrityError as error:
            if violated_constraint(error) == "uq_users_email":
                raise EmailAlreadyRegistered(
                    "Этот адрес уже зарегистрирован", field="email"
                ) from error
            raise

    def get(self, user_id: UserId) -> User | None:
        row = self._session.get(UserRow, user_id)
        return user_to_domain(row) if row else None

    def get_by_email(self, email: Email) -> User | None:
        row = self._session.scalar(select(UserRow).where(UserRow.email == email.value))
        return user_to_domain(row) if row else None


class SqlUserSessionRepository:
    """Реализует UserSessionRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, session: UserSession) -> None:
        self._session.add(session_to_row(session))

    def get_by_token_hash(self, refresh_token_hash: str) -> UserSession | None:
        row = self._session.scalar(
            select(UserSessionRow).where(UserSessionRow.refresh_token_hash == refresh_token_hash)
        )
        return session_to_domain(row) if row else None

    def save(self, session: UserSession) -> None:
        updated = self._session.scalar(
            update(UserSessionRow)
            .where(UserSessionRow.id == session.id)
            .values(session_columns(session))
            .returning(UserSessionRow.id)
        )
        if updated is None:
            raise NotFound("Сессия не найдена", session_id=str(session.id))
