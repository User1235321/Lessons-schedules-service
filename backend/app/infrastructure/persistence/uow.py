from typing import Self

from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.persistence.repositories.academic import (
    SqlGroupRepository,
    SqlRoomRepository,
    SqlStreamRepository,
    SqlSubjectRepository,
    SqlTeacherRepository,
    SqlWorkloadRepository,
)
from app.infrastructure.persistence.repositories.projects import SqlProjectRepository
from app.infrastructure.persistence.repositories.users import (
    SqlUserRepository,
    SqlUserSessionRepository,
)


class SqlUnitOfWork:
    """Реализует UnitOfWork поверх одной сессии SQLAlchemy."""

    users: SqlUserRepository
    user_sessions: SqlUserSessionRepository
    projects: SqlProjectRepository
    subjects: SqlSubjectRepository
    teachers: SqlTeacherRepository
    groups: SqlGroupRepository
    rooms: SqlRoomRepository
    streams: SqlStreamRepository
    workloads: SqlWorkloadRepository

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def __enter__(self) -> Self:
        self._session = self._session_factory()
        self.users = SqlUserRepository(self._session)
        self.user_sessions = SqlUserSessionRepository(self._session)
        self.projects = SqlProjectRepository(self._session)
        self.subjects = SqlSubjectRepository(self._session)
        self.teachers = SqlTeacherRepository(self._session)
        self.groups = SqlGroupRepository(self._session)
        self.rooms = SqlRoomRepository(self._session)
        self.streams = SqlStreamRepository(self._session)
        self.workloads = SqlWorkloadRepository(self._session)
        return self

    def __exit__(self, *exc: object) -> None:
        self._session.rollback()  # после commit() откатывать уже нечего
        self._session.close()

    def commit(self) -> None:
        self._session.commit()
