"""Все ORM-модели. Alembic импортирует этот пакет, чтобы видеть полную схему.

Каждый новый модуль моделей нужно импортировать здесь, иначе автогенерация
миграций его не заметит.
"""

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.academic import (
    RoomAvailabilityRow,
    RoomCapabilityRow,
    RoomRow,
    StreamGroupRow,
    StreamRow,
    StudentGroupRow,
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
from app.infrastructure.persistence.models.jobs import JobOutboxRow, JobRow
from app.infrastructure.persistence.models.projects import ProjectRow
from app.infrastructure.persistence.models.schedules import (
    ScheduleEntryRow,
    ScheduleEntryTeacherRow,
    ScheduleRow,
)
from app.infrastructure.persistence.models.users import UserRow, UserSessionRow

__all__ = [
    "Base",
    "ExtraConstraintRow",
    "JobOutboxRow",
    "JobRow",
    "OptimizationCriterionRow",
    "ProjectRow",
    "RoomAvailabilityRow",
    "RoomCapabilityRow",
    "RoomRow",
    "ScheduleEntryRow",
    "ScheduleEntryTeacherRow",
    "ScheduleRow",
    "StreamGroupRow",
    "StreamRow",
    "StudentGroupRow",
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
