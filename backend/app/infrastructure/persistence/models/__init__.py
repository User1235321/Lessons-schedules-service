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
from app.infrastructure.persistence.models.projects import ProjectRow
from app.infrastructure.persistence.models.users import UserRow, UserSessionRow

__all__ = [
    "Base",
    "ProjectRow",
    "RoomAvailabilityRow",
    "RoomCapabilityRow",
    "RoomRow",
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
