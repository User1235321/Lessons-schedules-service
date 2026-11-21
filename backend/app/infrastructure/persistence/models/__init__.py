"""Все ORM-модели. Alembic импортирует этот пакет, чтобы видеть полную схему.

Каждый новый модуль моделей нужно импортировать здесь, иначе автогенерация
миграций его не заметит.
"""

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.academic import (
    GroupAvailabilityRow,
    RoomAvailabilityRow,
    RoomCapabilityRow,
    RoomRow,
    StreamGroupRow,
    StreamRow,
    StudentGroupRow,
    SubgroupAvailabilityRow,
    SubgroupRow,
    SubjectRow,
    TeacherAvailabilityRow,
    TeacherCapabilityRow,
    TeacherPreferenceRow,
    TeacherRow,
    WorkloadRow,
)
from app.infrastructure.persistence.models.constraints import (
    ExtraConstraintRow,
    OptimizationCriterionRow,
)
from app.infrastructure.persistence.models.files import StoredFileRow
from app.infrastructure.persistence.models.jobs import JobOutboxRow, JobRow
from app.infrastructure.persistence.models.projects import ProjectRow
from app.infrastructure.persistence.models.schedules import (
    ScheduleEntryRow,
    ScheduleEntryTeacherRow,
    ScheduleRow,
)
from app.infrastructure.persistence.models.users import (
    PasswordResetTokenRow,
    UserRow,
    UserSessionRow,
)

__all__ = [
    "Base",
    "ExtraConstraintRow",
    "GroupAvailabilityRow",
    "JobOutboxRow",
    "JobRow",
    "OptimizationCriterionRow",
    "PasswordResetTokenRow",
    "ProjectRow",
    "RoomAvailabilityRow",
    "RoomCapabilityRow",
    "RoomRow",
    "ScheduleEntryRow",
    "ScheduleEntryTeacherRow",
    "ScheduleRow",
    "StoredFileRow",
    "StreamGroupRow",
    "StreamRow",
    "StudentGroupRow",
    "SubgroupAvailabilityRow",
    "SubgroupRow",
    "SubjectRow",
    "TeacherAvailabilityRow",
    "TeacherCapabilityRow",
    "TeacherPreferenceRow",
    "TeacherRow",
    "UserRow",
    "UserSessionRow",
    "WorkloadRow",
]
