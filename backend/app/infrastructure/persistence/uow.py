from typing import Self

from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.persistence.repositories.job_outbox import SqlJobOutbox
from app.infrastructure.persistence.repositories.jobs import SqlJobRepository
from app.infrastructure.persistence.repositories.projects import SqlProjectRepository
from app.infrastructure.persistence.repositories.schedules import SqlScheduleRepository
from app.infrastructure.persistence.repositories.users import (
    SqlUserRepository,
    SqlUserSessionRepository,
)


class SqlUnitOfWork:
    """Реализует UnitOfWork поверх одной сессии SQLAlchemy."""

    users: SqlUserRepository
    user_sessions: SqlUserSessionRepository
    projects: SqlProjectRepository
    jobs: SqlJobRepository
    job_outbox: SqlJobOutbox
    schedules: SqlScheduleRepository

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def __enter__(self) -> Self:
        self._session = self._session_factory()
        self.users = SqlUserRepository(self._session)
        self.user_sessions = SqlUserSessionRepository(self._session)
        self.projects = SqlProjectRepository(self._session)
        self.jobs = SqlJobRepository(self._session)
        self.job_outbox = SqlJobOutbox(self._session)
        self.schedules = SqlScheduleRepository(self._session)
        return self

    def __exit__(self, *exc: object) -> None:
        self._session.rollback()  # после commit() откатывать уже нечего
        self._session.close()

    def commit(self) -> None:
        self._session.commit()
