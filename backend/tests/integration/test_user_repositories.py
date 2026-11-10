from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import Connection

from app.domain.auth.errors import EmailAlreadyRegistered
from app.domain.auth.session import UserSession
from app.domain.auth.user import Email, User
from app.domain.shared.errors import NotFound
from app.domain.shared.ids import SessionId, UserId
from app.infrastructure.persistence.uow import SqlUnitOfWork
from tests.database import recorded_statements

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


def a_user(email: str = "ivan@mail.ru") -> User:
    return User(id=UserId(uuid4()), email=Email(email), password_hash="hash", created_at=NOW)


def a_session(user: User, token_hash: str = "token-hash") -> UserSession:
    return UserSession.open(
        session_id=SessionId(uuid4()),
        user_id=user.id,
        refresh_token_hash=token_hash,
        now=NOW,
        ttl=timedelta(days=30),
    )


def test_user_is_found_by_id_and_email(uow: SqlUnitOfWork) -> None:
    user = a_user("ivan@mail.ru")
    with uow:
        uow.users.add(user)
        uow.commit()

    with uow:
        assert uow.users.get(user.id) == user
        assert uow.users.get_by_email(Email("Ivan@Mail.ru")) == user


def test_unknown_user_is_not_found(uow: SqlUnitOfWork) -> None:
    with uow:
        assert uow.users.get(UserId(uuid4())) is None
        assert uow.users.get_by_email(Email("nobody@mail.ru")) is None


def test_taken_email_is_reported_as_domain_error(uow: SqlUnitOfWork) -> None:
    with uow:
        uow.users.add(a_user("ivan@mail.ru"))
        uow.commit()

    with uow, pytest.raises(EmailAlreadyRegistered) as error:
        uow.users.add(a_user("IVAN@mail.ru"))

    assert error.value.details == {"field": "email"}


def test_changes_without_commit_are_discarded(uow: SqlUnitOfWork) -> None:
    user = a_user()
    with uow:
        uow.users.add(user)

    with uow:
        assert uow.users.get(user.id) is None


def test_session_is_found_by_token_hash(uow: SqlUnitOfWork) -> None:
    user = a_user()
    session = a_session(user, token_hash="abc")
    with uow:
        uow.users.add(user)
        uow.user_sessions.add(session)
        uow.commit()

    with uow:
        assert uow.user_sessions.get_by_token_hash("abc") == session
        assert uow.user_sessions.get_by_token_hash("other") is None


def test_revoked_session_is_saved(uow: SqlUnitOfWork) -> None:
    user = a_user()
    session = a_session(user)
    with uow:
        uow.users.add(user)
        uow.user_sessions.add(session)
        uow.commit()

    with uow:
        stored = uow.user_sessions.get_by_token_hash(session.refresh_token_hash)
        assert stored is not None
        stored.revoke(NOW + timedelta(hours=1))
        uow.user_sessions.save(stored)
        uow.commit()

    with uow:
        reloaded = uow.user_sessions.get_by_token_hash(session.refresh_token_hash)
        assert reloaded is not None
        assert reloaded.revoked_at == NOW + timedelta(hours=1)


def test_session_saving_is_a_single_update(uow: SqlUnitOfWork, db_connection: Connection) -> None:
    user = a_user()
    session = a_session(user)
    with uow:
        uow.users.add(user)
        uow.user_sessions.add(session)
        uow.commit()

    with uow:
        stored = uow.user_sessions.get_by_token_hash(session.refresh_token_hash)
        assert stored is not None
        stored.revoke(NOW + timedelta(hours=1))
        with recorded_statements(db_connection) as statements:
            uow.user_sessions.save(stored)

    assert statements == ["UPDATE"]


def test_saving_missing_session_fails(uow: SqlUnitOfWork) -> None:
    user = a_user()
    with uow:
        uow.users.add(user)

        with pytest.raises(NotFound):
            uow.user_sessions.save(a_session(user))


def test_session_save_writes_only_token_hash_and_revocation(uow: SqlUnitOfWork) -> None:
    user, other = a_user("ivan@mail.ru"), a_user("petr@mail.ru")
    session = a_session(user, token_hash="old")
    with uow:
        uow.users.add(user)
        uow.users.add(other)
        uow.user_sessions.add(session)
        uow.commit()
    later = NOW + timedelta(hours=1)

    with uow:
        stored = uow.user_sessions.get_by_token_hash("old")
        assert stored is not None
        stored.rotate("new")
        stored.revoke(later)
        stored.user_id = other.id
        stored.created_at = later
        stored.expires_at = later
        uow.user_sessions.save(stored)
        uow.commit()

    with uow:
        reloaded = uow.user_sessions.get_by_token_hash("new")
    assert reloaded is not None
    assert reloaded.revoked_at == later
    assert (reloaded.user_id, reloaded.created_at, reloaded.expires_at) == (
        session.user_id,
        session.created_at,
        session.expires_at,
    )
