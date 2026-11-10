from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.api.schemas.paths import inside
from app.application.projects.use_cases import SettingsChanges
from app.domain.projects.project import Project
from app.domain.projects.settings import (
    DurationMode,
    DurationModeKind,
    StudyCycle,
    TimeMode,
    TimeModeKind,
)
from app.domain.shared.week import Weekday

# Форма проекта совпадает с test-data/minimal-project.json


class CycleSchema(BaseModel):
    odd_week_days: list[Weekday]
    even_week_days: list[Weekday]

    def to_domain(self) -> StudyCycle:
        return StudyCycle(tuple(self.odd_week_days), tuple(self.even_week_days))

    @classmethod
    def of(cls, cycle: StudyCycle) -> "CycleSchema":
        return cls(
            odd_week_days=list(cycle.odd_week_days), even_week_days=list(cycle.even_week_days)
        )


class TimeModeSchema(BaseModel):
    type: TimeModeKind
    step_minutes: int | None = None

    def to_domain(self) -> TimeMode:
        with inside("time_mode"):
            return TimeMode(self.type, self.step_minutes)

    @classmethod
    def of(cls, mode: TimeMode) -> "TimeModeSchema":
        return cls(type=mode.kind, step_minutes=mode.step_minutes)


class DurationModeSchema(BaseModel):
    type: DurationModeKind
    duration_minutes: int | None = None

    def to_domain(self) -> DurationMode:
        with inside("duration_mode"):
            return DurationMode(self.type, self.duration_minutes)

    @classmethod
    def of(cls, mode: DurationMode) -> "DurationModeSchema":
        return cls(type=mode.kind, duration_minutes=mode.duration_minutes)


class _SettingsBlocks(BaseModel):
    cycle: CycleSchema | None = None
    time_mode: TimeModeSchema | None = None
    duration_mode: DurationModeSchema | None = None

    def settings_changes(self) -> SettingsChanges:
        return SettingsChanges(
            cycle=self.cycle.to_domain() if self.cycle else None,
            time_mode=self.time_mode.to_domain() if self.time_mode else None,
            duration_mode=self.duration_mode.to_domain() if self.duration_mode else None,
        )


class CreateProjectRequest(_SettingsBlocks):
    """Обязательно только имя. Остальные блоки — по умолчанию (F_Project_5)."""

    name: str


class UpdateProjectRequest(_SettingsBlocks):
    """Присланный блок заменяется целиком. Отсутствующий или null — не меняется."""

    name: str | None = None


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    cycle: CycleSchema
    time_mode: TimeModeSchema
    duration_mode: DurationModeSchema
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, project: Project) -> "ProjectResponse":
        return cls(
            id=project.id,
            name=project.name,
            cycle=CycleSchema.of(project.settings.cycle),
            time_mode=TimeModeSchema.of(project.settings.time_mode),
            duration_mode=DurationModeSchema.of(project.settings.duration_mode),
            created_at=project.created_at,
            updated_at=project.updated_at,
        )
