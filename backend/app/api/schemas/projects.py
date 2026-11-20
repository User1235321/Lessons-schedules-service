from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StrictInt, field_validator

from app.application.projects.use_cases import SettingsChanges
from app.domain.projects.project import Project
from app.domain.projects.settings import DurationModeKind, TimeModeKind
from app.domain.shared.week import Weekday


class ProjectSettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    odd_week_days: list[Weekday] | None = None
    even_week_days: list[Weekday] | None = None
    time_mode: TimeModeKind | None = None
    time_step_minutes: StrictInt | None = None
    duration_mode: DurationModeKind | None = None
    duration_minutes: StrictInt | None = None

    @field_validator("odd_week_days", "even_week_days", "time_mode", "duration_mode")
    @classmethod
    def reject_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("Поле не может быть null")
        return value

    def settings_changes(self) -> SettingsChanges:
        supplied = self.model_fields_set
        return SettingsChanges(
            odd_week_days=(
                tuple(self.odd_week_days) if "odd_week_days" in supplied else None
            ),
            even_week_days=(
                tuple(self.even_week_days) if "even_week_days" in supplied else None
            ),
            time_mode=self.time_mode,
            time_step_minutes=self.time_step_minutes,
            has_time_step_minutes="time_step_minutes" in supplied,
            duration_mode=self.duration_mode,
            duration_minutes=self.duration_minutes,
            has_duration_minutes="duration_minutes" in supplied,
        )


class CreateProjectRequest(ProjectSettingsRequest):
    name: str


class UpdateProjectRequest(ProjectSettingsRequest):
    name: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def reject_null_name(cls, value: object) -> object:
        if value is None:
            raise ValueError("Имя проекта не может быть null")
        return value


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    odd_week_days: list[Weekday]
    even_week_days: list[Weekday]
    time_mode: TimeModeKind
    time_step_minutes: int | None
    duration_mode: DurationModeKind
    duration_minutes: int | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, project: Project) -> "ProjectResponse":
        return cls(
            id=project.id,
            name=project.name,
            odd_week_days=list(project.settings.cycle.odd_week_days),
            even_week_days=list(project.settings.cycle.even_week_days),
            time_mode=project.settings.time_mode.kind,
            time_step_minutes=project.settings.time_mode.step_minutes,
            duration_mode=project.settings.duration_mode.kind,
            duration_minutes=project.settings.duration_mode.duration_minutes,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )
