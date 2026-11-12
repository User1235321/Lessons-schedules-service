"""Все ORM-модели. Alembic импортирует этот пакет, чтобы видеть полную схему.

Каждый новый модуль моделей нужно импортировать здесь, иначе автогенерация
миграций его не заметит.
"""

from app.infrastructure.persistence.base import Base
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
    "JobOutboxRow",
    "JobRow",
    "ProjectRow",
    "ScheduleEntryRow",
    "ScheduleEntryTeacherRow",
    "ScheduleRow",
    "UserRow",
    "UserSessionRow",
]
