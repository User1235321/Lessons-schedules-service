from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import Connection, event

from app.domain.auth.session import UserSession
from app.domain.auth.user import Email, User
from app.domain.shared.ids import SessionId, UserId
from app.infrastructure.persistence.uow import SqlUnitOfWork

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)


def test_session_found_for_update_is_locked(uow: SqlUnitOfWork, db_connection: Connection) -> None:
    user = User(id=UserId(uuid4()), email=Email("ivan@mail.ru"), password_hash="h", created_at=NOW)
    session = UserSession.open(
        session_id=SessionId(uuid4()),
        user_id=user.id,
        refresh_token_hash="abc",
        now=NOW,
        ttl=timedelta(days=30),
    )
    with uow:
        uow.users.add(user)
        uow.user_sessions.add(session)
        uow.commit()
    statements: list[str] = []
    event.listen(db_connection, "before_cursor_execute", lambda *args: statements.append(args[2]))

    with uow:
        assert uow.user_sessions.get_by_token_hash_for_update("abc") == session
        assert uow.user_sessions.get_by_token_hash_for_update("other") is None

    # Без блокировки два refresh с одним токеном оба выдали бы новые пары
    selects = [statement for statement in statements if statement.startswith("SELECT")]
    assert len(selects) == 2
    assert all(select.endswith("FOR UPDATE") for select in selects)
