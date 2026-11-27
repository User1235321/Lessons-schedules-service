from typing import Self

from sqlalchemy import Engine
from sqlalchemy.orm import Session, SessionTransaction, sessionmaker

from app.infrastructure.persistence.repositories.academic import (
    SqlGroupRepository,
    SqlRoomRepository,
    SqlStreamRepository,
    SqlSubjectRepository,
    SqlTeacherRepository,
    SqlWorkloadRepository,
)
from app.infrastructure.persistence.repositories.constraints import (
    SqlConstraintRepository,
    SqlCriterionRepository,
)
from app.infrastructure.persistence.repositories.files import SqlStoredFileRepository
from app.infrastructure.persistence.repositories.job_outbox import SqlJobOutbox
from app.infrastructure.persistence.repositories.jobs import SqlJobRepository
from app.infrastructure.persistence.repositories.projects import SqlProjectRepository
from app.infrastructure.persistence.repositories.schedules import SqlScheduleRepository
from app.infrastructure.persistence.repositories.users import (
    SqlPasswordResetRepository,
    SqlUserRepository,
    SqlUserSessionRepository,
)


class SqlUnitOfWork:
    """Реализует UnitOfWork поверх одной сессии SQLAlchemy."""

    users: SqlUserRepository
    user_sessions: SqlUserSessionRepository
    password_resets: SqlPasswordResetRepository
    projects: SqlProjectRepository
    subjects: SqlSubjectRepository
    teachers: SqlTeacherRepository
    groups: SqlGroupRepository
    rooms: SqlRoomRepository
    streams: SqlStreamRepository
    workloads: SqlWorkloadRepository
    jobs: SqlJobRepository
    job_outbox: SqlJobOutbox
    schedules: SqlScheduleRepository
    constraints: SqlConstraintRepository
    criteria: SqlCriterionRepository
    files: SqlStoredFileRepository

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        parent: Session | None = None,
        *,
        snapshot: bool = False,
    ) -> None:
        self._session_factory = session_factory
        self._snapshot = snapshot
        self._parent = parent
        self._savepoint: SessionTransaction | None = None

    def __enter__(self) -> Self:
        self._session = self._parent if self._parent is not None else self._session_factory()
        if self._snapshot and isinstance(self._session.get_bind(), Engine):
            self._session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        if self._parent is not None:
            self._savepoint = self._session.begin_nested()
        self.users = SqlUserRepository(self._session)
        self.user_sessions = SqlUserSessionRepository(self._session)
        self.password_resets = SqlPasswordResetRepository(self._session)
        self.projects = SqlProjectRepository(self._session)
        self.subjects = SqlSubjectRepository(self._session)
        self.teachers = SqlTeacherRepository(self._session)
        self.groups = SqlGroupRepository(self._session)
        self.rooms = SqlRoomRepository(self._session)
        self.streams = SqlStreamRepository(self._session)
        self.workloads = SqlWorkloadRepository(self._session)
        self.jobs = SqlJobRepository(self._session)
        self.job_outbox = SqlJobOutbox(self._session)
        self.schedules = SqlScheduleRepository(self._session)
        self.constraints = SqlConstraintRepository(self._session)
        self.criteria = SqlCriterionRepository(self._session)
        self.files = SqlStoredFileRepository(self._session)
        return self

    def __exit__(self, *exc: object) -> None:
        if self._savepoint is not None:
            self._savepoint.close()
            return
        self._session.rollback()  # после commit() откатывать уже нечего
        self._session.close()

    def nested(self) -> Self:
        return type(self)(self._session_factory, self._session)

    def commit(self) -> None:
        if self._savepoint is None:
            self._session.commit()
        else:
            self._savepoint.commit()
