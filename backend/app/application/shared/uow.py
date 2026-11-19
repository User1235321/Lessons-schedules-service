from typing import Protocol, Self

from app.application.academic.ports import (
    GroupRepository,
    RoomRepository,
    StreamRepository,
    SubjectRepository,
    TeacherRepository,
    WorkloadRepository,
)
from app.application.auth.ports import (
    PasswordResetRepository,
    UserRepository,
    UserSessionRepository,
)
from app.application.constraints.ports import ConstraintRepository, CriterionRepository
from app.application.import_export.ports import StoredFileRepository
from app.application.projects.ports import ProjectRepository
from app.application.scheduling.ports import JobOutbox, JobRepository, ScheduleRepository


class UnitOfWork(Protocol):
    """Одна транзакция. Без commit() изменения отбрасываются при выходе из with."""

    users: UserRepository
    user_sessions: UserSessionRepository
    password_resets: PasswordResetRepository
    projects: ProjectRepository
    subjects: SubjectRepository
    teachers: TeacherRepository
    groups: GroupRepository
    rooms: RoomRepository
    streams: StreamRepository
    workloads: WorkloadRepository
    jobs: JobRepository
    job_outbox: JobOutbox
    schedules: ScheduleRepository
    constraints: ConstraintRepository
    criteria: CriterionRepository
    files: StoredFileRepository

    def __enter__(self) -> Self: ...

    def __exit__(self, *exc: object) -> None: ...

    def commit(self) -> None: ...
