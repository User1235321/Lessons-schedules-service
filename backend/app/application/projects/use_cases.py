from dataclasses import dataclass

from app.application.auth.access import owned_project
from app.application.shared.ports import Clock, IdGenerator
from app.application.shared.uow import UnitOfWork
from app.domain.projects.project import Project
from app.domain.projects.settings import (
    DurationMode,
    DurationModeKind,
    ProjectSettings,
    StudyCycle,
    TimeMode,
    TimeModeKind,
)
from app.domain.shared.errors import InvalidValue
from app.domain.shared.ids import ProjectId, UserId
from app.domain.shared.week import Weekday


@dataclass(frozen=True)
class SettingsChanges:
    odd_week_days: tuple[Weekday, ...] | None = None
    even_week_days: tuple[Weekday, ...] | None = None
    time_mode: TimeModeKind | None = None
    time_step_minutes: int | None = None
    has_time_step_minutes: bool = False
    duration_mode: DurationModeKind | None = None
    duration_minutes: int | None = None
    has_duration_minutes: bool = False

    def is_empty(self) -> bool:
        return (
            self.odd_week_days is None
            and self.even_week_days is None
            and self.time_mode is None
            and not self.has_time_step_minutes
            and self.duration_mode is None
            and not self.has_duration_minutes
        )

    def applied_to(self, settings: ProjectSettings) -> ProjectSettings:
        cycle = settings.cycle
        if self.odd_week_days is not None or self.even_week_days is not None:
            cycle = StudyCycle(
                self.odd_week_days
                if self.odd_week_days is not None
                else cycle.odd_week_days,
                self.even_week_days
                if self.even_week_days is not None
                else cycle.even_week_days,
            )

        time_mode = settings.time_mode
        if self.time_mode is not None or self.has_time_step_minutes:
            try:
                time_mode = TimeMode(
                    self.time_mode if self.time_mode is not None else time_mode.kind,
                    self.time_step_minutes
                    if self.has_time_step_minutes
                    else time_mode.step_minutes,
                )
            except InvalidValue as error:
                raise InvalidValue(error.message, field="time_step_minutes") from error

        duration_mode = settings.duration_mode
        if self.duration_mode is not None or self.has_duration_minutes:
            duration_mode = DurationMode(
                self.duration_mode if self.duration_mode is not None else duration_mode.kind,
                self.duration_minutes
                if self.has_duration_minutes
                else duration_mode.duration_minutes,
            )

        return ProjectSettings(cycle, time_mode, duration_mode)


@dataclass(frozen=True)
class CreateProject:
    uow: UnitOfWork
    clock: Clock
    ids: IdGenerator

    def execute(self, owner_id: UserId, name: str, settings: SettingsChanges) -> Project:
        project = Project.create(
            project_id=ProjectId(self.ids.new_id()),
            owner_id=owner_id,
            name=name,
            now=self.clock.now(),
            settings=settings.applied_to(ProjectSettings.default()),
        )
        with self.uow:
            self.uow.projects.add(project)
            self.uow.commit()
        return project


@dataclass(frozen=True)
class ListProjects:
    uow: UnitOfWork

    def execute(self, owner_id: UserId) -> list[Project]:
        with self.uow:
            return self.uow.projects.list_owned(owner_id)


@dataclass(frozen=True)
class GetProject:
    uow: UnitOfWork

    def execute(self, owner_id: UserId, project_id: ProjectId) -> Project:
        with self.uow:
            return owned_project(self.uow, project_id, owner_id)


@dataclass(frozen=True)
class UpdateProject:
    uow: UnitOfWork
    clock: Clock

    def execute(
        self, owner_id: UserId, project_id: ProjectId, name: str | None, settings: SettingsChanges
    ) -> Project:
        with self.uow:
            project = owned_project(self.uow, project_id, owner_id)
            if name is None and settings.is_empty():
                return project
            now = self.clock.now()
            if name is not None:
                project.rename(name, now)
            if not settings.is_empty():
                project.change_settings(settings.applied_to(project.settings), now)
            self.uow.projects.save(project)
            self.uow.commit()
        return project


@dataclass(frozen=True)
class DeleteProject:
    uow: UnitOfWork

    def execute(self, owner_id: UserId, project_id: ProjectId) -> None:
        with self.uow:
            owned_project(self.uow, project_id, owner_id)
            self.uow.projects.delete(project_id, owner_id)
            self.uow.commit()
