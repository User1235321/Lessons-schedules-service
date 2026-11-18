from dataclasses import dataclass

from app.application.auth.access import owned_project
from app.application.shared.ports import Clock, IdGenerator
from app.application.shared.uow import UnitOfWork
from app.domain.projects.project import Project
from app.domain.projects.settings import DurationMode, ProjectSettings, StudyCycle, TimeMode
from app.domain.shared.ids import ProjectId, UserId


@dataclass(frozen=True)
class SettingsChanges:
    """Блоки настроек, которые прислал клиент. None — блок не прислан и не меняется."""

    cycle: StudyCycle | None = None
    time_mode: TimeMode | None = None
    duration_mode: DurationMode | None = None

    def is_empty(self) -> bool:
        return self.cycle is None and self.time_mode is None and self.duration_mode is None

    def applied_to(self, settings: ProjectSettings) -> ProjectSettings:
        # Блок заменяется целиком: режим и его параметр не разойдутся
        return ProjectSettings(
            cycle=self.cycle if self.cycle is not None else settings.cycle,
            time_mode=self.time_mode if self.time_mode is not None else settings.time_mode,
            duration_mode=(
                self.duration_mode if self.duration_mode is not None else settings.duration_mode
            ),
        )


@dataclass(frozen=True)
class CreateProject:
    """Новый проект (F_Project_1). Чего клиент не прислал, берётся по умолчанию (F_Project_5)."""

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
    """Проекты пользователя, сначала недавно изменённые (F_Project_3)."""

    uow: UnitOfWork

    def execute(self, owner_id: UserId) -> list[Project]:
        with self.uow:
            return self.uow.projects.list_owned(owner_id)


@dataclass(frozen=True)
class GetProject:
    """Открытие проекта (F_Project_2, F_Project_4)."""

    uow: UnitOfWork

    def execute(self, owner_id: UserId, project_id: ProjectId) -> Project:
        with self.uow:
            return owned_project(self.uow, project_id, owner_id)


@dataclass(frozen=True)
class UpdateProject:
    """Переименование и смена настроек (F_Project_2, F_Data_1–3)."""

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
    """Удаление проекта вместе со всеми его данными (F_Project_2)."""

    uow: UnitOfWork

    def execute(self, owner_id: UserId, project_id: ProjectId) -> None:
        with self.uow:
            owned_project(self.uow, project_id, owner_id)
            self.uow.projects.delete(project_id, owner_id)
            self.uow.commit()
