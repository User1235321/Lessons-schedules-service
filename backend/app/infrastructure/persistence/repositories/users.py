from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.auth.errors import EmailAlreadyRegistered
from app.domain.auth.password_reset import PasswordResetToken
from app.domain.auth.session import UserSession
from app.domain.auth.user import Email, User
from app.domain.shared.errors import NotFound
from app.domain.shared.ids import UserId
from app.infrastructure.persistence.errors import violated_constraint
from app.infrastructure.persistence.mappers.users import (
    session_to_domain,
    session_to_row,
    session_update_values,
    user_to_domain,
    user_to_row,
)
from app.infrastructure.persistence.models import PasswordResetTokenRow, UserRow, UserSessionRow


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

    def update_password_hash(self, user_id: UserId, password_hash: str) -> None:
        updated = self._session.scalar(
            update(UserRow)
            .where(UserRow.id == user_id)
            .values(password_hash=password_hash)
            .returning(UserRow.id)
        )
        if updated is None:
            raise NotFound("Учётная запись не найдена", user_id=str(user_id))


class SqlPasswordResetRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def replace(self, token: PasswordResetToken) -> None:
        values = {"token_hash": token.token_hash, "expires_at": token.expires_at}
        self._session.execute(
            insert(PasswordResetTokenRow)
            .values(user_id=token.user_id, **values)
            .on_conflict_do_update(index_elements=[PasswordResetTokenRow.user_id], set_=values)
        )

    def get_for_update(self, token_hash: str) -> PasswordResetToken | None:
        row = self._session.scalar(
            select(PasswordResetTokenRow)
            .where(PasswordResetTokenRow.token_hash == token_hash)
            .with_for_update()
        )
        if row is None:
            return None
        return PasswordResetToken(UserId(row.user_id), row.token_hash, row.expires_at)

    def remove(self, user_id: UserId) -> None:
        self._session.execute(
            delete(PasswordResetTokenRow).where(PasswordResetTokenRow.user_id == user_id)
        )


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

    def get_by_token_hash_for_update(self, refresh_token_hash: str) -> UserSession | None:
        row = self._session.scalar(
            select(UserSessionRow)
            .where(UserSessionRow.refresh_token_hash == refresh_token_hash)
            .with_for_update()
        )
        return session_to_domain(row) if row else None

    def save(self, session: UserSession) -> None:
        updated = self._session.scalar(
            update(UserSessionRow)
            .where(UserSessionRow.id == session.id)
            .values(session_update_values(session))
            .returning(UserSessionRow.id)
        )
        if updated is None:
            raise NotFound("Сессия не найдена", session_id=str(session.id))
