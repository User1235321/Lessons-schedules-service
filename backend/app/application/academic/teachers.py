from collections.abc import Sequence
from dataclasses import dataclass

from app.application.academic.changes import project_data_changed
from app.application.auth.access import owned_project
from app.application.shared.ports import Clock, IdGenerator
from app.application.shared.uow import UnitOfWork
from app.domain.academic.capability import Capability
from app.domain.academic.teacher import Teacher
from app.domain.shared.errors import InvalidValue, NotFound
from app.domain.shared.ids import ProjectId, TeacherId, UserId
from app.domain.shared.week import WeeklyInterval


@dataclass(frozen=True)
class TeacherDraft:
    """Новый преподаватель. Наборы — в порядке клиента: по нему строится путь поля в ошибке."""

    full_name: str
    capabilities: tuple[Capability, ...]
    availability: tuple[WeeklyInterval, ...]
    preferences: tuple[WeeklyInterval, ...] = ()


@dataclass(frozen=True)
class TeacherChanges:
    """Присланные части. None — часть не прислана, набор заменяется целиком."""

    full_name: str | None = None
    capabilities: tuple[Capability, ...] | None = None
    availability: tuple[WeeklyInterval, ...] | None = None
    preferences: tuple[WeeklyInterval, ...] | None = None


def _not_found(teacher_id: TeacherId) -> NotFound:
    return NotFound("Преподаватель не найден", teacher_id=str(teacher_id))


def _check_subjects(
    uow: UnitOfWork, project_id: ProjectId, capabilities: Sequence[Capability]
) -> None:
    """Дисциплины пар есть в проекте. Ошибка называет элемент: capabilities.1.subject_id."""
    known = {subject.id for subject in uow.subjects.list_in_project(project_id)}
    for index, capability in enumerate(capabilities):
        if capability.subject_id not in known:
            raise InvalidValue(
                "Такой дисциплины нет в проекте", field=f"capabilities.{index}.subject_id"
            )


@dataclass(frozen=True)
class CreateTeacher:
    uow: UnitOfWork
    clock: Clock
    ids: IdGenerator

    def execute(self, user_id: UserId, project_id: ProjectId, draft: TeacherDraft) -> Teacher:
        with self.uow:
            project = owned_project(self.uow, project_id, user_id)
            _check_subjects(self.uow, project_id, draft.capabilities)
            teacher = Teacher(
                id=TeacherId(self.ids.new_id()),
                project_id=project.id,
                full_name=draft.full_name,
                capabilities=draft.capabilities,
                availability=draft.availability,
                preferences=draft.preferences,
            )
            self.uow.teachers.add(teacher)
            project_data_changed(self.uow, project, self.clock.now())
            self.uow.commit()
        return teacher


@dataclass(frozen=True)
class ListTeachers:
    uow: UnitOfWork

    def execute(self, user_id: UserId, project_id: ProjectId) -> list[Teacher]:
        with self.uow:
            owned_project(self.uow, project_id, user_id)
            return self.uow.teachers.list_in_project(project_id)


@dataclass(frozen=True)
class GetTeacher:
    uow: UnitOfWork

    def execute(self, user_id: UserId, project_id: ProjectId, teacher_id: TeacherId) -> Teacher:
        with self.uow:
            owned_project(self.uow, project_id, user_id)
            teacher = self.uow.teachers.get(project_id, teacher_id)
        if teacher is None:
            raise _not_found(teacher_id)
        return teacher


@dataclass(frozen=True)
class UpdateTeacher:
    uow: UnitOfWork
    clock: Clock

    def execute(
        self,
        user_id: UserId,
        project_id: ProjectId,
        teacher_id: TeacherId,
        changes: TeacherChanges,
    ) -> Teacher:
        with self.uow:
            project = owned_project(self.uow, project_id, user_id)
            teacher = self.uow.teachers.get_for_update(project_id, teacher_id)
            if teacher is None:
                raise _not_found(teacher_id)
            if changes == TeacherChanges():
                return teacher
            if changes.full_name is not None:
                teacher.rename(changes.full_name)
            if changes.capabilities is not None:
                _check_subjects(self.uow, project_id, changes.capabilities)
                teacher.change_capabilities(changes.capabilities)
            if changes.availability is not None:
                teacher.change_availability(changes.availability)
            if changes.preferences is not None:
                teacher.change_preferences(changes.preferences)
            self.uow.teachers.save(teacher)
            project_data_changed(self.uow, project, self.clock.now())
            self.uow.commit()
        return teacher


@dataclass(frozen=True)
class DeleteTeacher:
    uow: UnitOfWork
    clock: Clock

    def execute(self, user_id: UserId, project_id: ProjectId, teacher_id: TeacherId) -> None:
        with self.uow:
            project = owned_project(self.uow, project_id, user_id)
            self.uow.teachers.delete(project_id, teacher_id)
            project_data_changed(self.uow, project, self.clock.now())
            self.uow.commit()
