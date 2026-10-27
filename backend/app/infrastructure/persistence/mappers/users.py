from typing import Any

from app.domain.auth.session import UserSession
from app.domain.auth.user import Email, User
from app.domain.shared.ids import SessionId, UserId
from app.infrastructure.persistence.models import UserRow, UserSessionRow


def user_to_row(user: User) -> UserRow:
    return UserRow(
        id=user.id,
        email=user.email.value,
        password_hash=user.password_hash,
        created_at=user.created_at,
    )


def user_to_domain(row: UserRow) -> User:
    return User(
        id=UserId(row.id),
        email=Email(row.email),
        password_hash=row.password_hash,
        created_at=row.created_at,
    )


def session_columns(session: UserSession) -> dict[str, Any]:
    """Значения всех колонок сессии, кроме id."""
    return {
        "user_id": session.user_id,
        "refresh_token_hash": session.refresh_token_hash,
        "created_at": session.created_at,
        "expires_at": session.expires_at,
        "revoked_at": session.revoked_at,
    }


def session_to_row(session: UserSession) -> UserSessionRow:
    return UserSessionRow(id=session.id, **session_columns(session))


def session_to_domain(row: UserSessionRow) -> UserSession:
    return UserSession(
        id=SessionId(row.id),
        user_id=UserId(row.user_id),
        refresh_token_hash=row.refresh_token_hash,
        created_at=row.created_at,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
    )
