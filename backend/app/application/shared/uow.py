from typing import Protocol, Self

from app.application.auth.ports import UserRepository, UserSessionRepository
from app.application.projects.ports import ProjectRepository
from app.application.scheduling.ports import JobOutbox, JobRepository, ScheduleRepository


class UnitOfWork(Protocol):
    """Одна транзакция. Без commit() изменения отбрасываются при выходе из with."""

    users: UserRepository
    user_sessions: UserSessionRepository
    projects: ProjectRepository
    jobs: JobRepository
    job_outbox: JobOutbox
    schedules: ScheduleRepository

    def __enter__(self) -> Self: ...

    def __exit__(self, *exc: object) -> None: ...

    def commit(self) -> None: ...
