from dataclasses import dataclass

from app.application.academic.changes import project_data_changed
from app.application.auth.access import owned_project
from app.application.shared.ports import Clock, IdGenerator
from app.application.shared.uow import UnitOfWork
from app.domain.academic.subject import Subject
from app.domain.shared.errors import NotFound
from app.domain.shared.ids import ProjectId, SubjectId, UserId


def _not_found(subject_id: SubjectId) -> NotFound:
    return NotFound("Дисциплина не найдена", subject_id=str(subject_id))


@dataclass(frozen=True)
class CreateSubject:
    uow: UnitOfWork
    clock: Clock
    ids: IdGenerator

    def execute(self, user_id: UserId, project_id: ProjectId, name: str) -> Subject:
        with self.uow:
            project = owned_project(self.uow, project_id, user_id)
            subject = Subject(id=SubjectId(self.ids.new_id()), project_id=project.id, name=name)
            self.uow.subjects.add(subject)
            project_data_changed(self.uow, project, self.clock.now())
            self.uow.commit()
        return subject


@dataclass(frozen=True)
class ListSubjects:
    uow: UnitOfWork

    def execute(self, user_id: UserId, project_id: ProjectId) -> list[Subject]:
        with self.uow:
            owned_project(self.uow, project_id, user_id)
            return self.uow.subjects.list_in_project(project_id)


@dataclass(frozen=True)
class GetSubject:
    uow: UnitOfWork

    def execute(self, user_id: UserId, project_id: ProjectId, subject_id: SubjectId) -> Subject:
        with self.uow:
            owned_project(self.uow, project_id, user_id)
            subject = self.uow.subjects.get(project_id, subject_id)
        if subject is None:
            raise _not_found(subject_id)
        return subject


@dataclass(frozen=True)
class UpdateSubject:
    uow: UnitOfWork
    clock: Clock

    def execute(
        self, user_id: UserId, project_id: ProjectId, subject_id: SubjectId, name: str | None
    ) -> Subject:
        with self.uow:
            project = owned_project(self.uow, project_id, user_id)
            subject = self.uow.subjects.get(project_id, subject_id)
            if subject is None:
                raise _not_found(subject_id)
            if name is None:
                return subject
            subject.rename(name)
            self.uow.subjects.save(subject)
            project_data_changed(self.uow, project, self.clock.now())
            self.uow.commit()
        return subject


@dataclass(frozen=True)
class DeleteSubject:
    """Занятую дисциплину удалить нельзя: SubjectInUse со списком преподавателей."""

    uow: UnitOfWork
    clock: Clock

    def execute(self, user_id: UserId, project_id: ProjectId, subject_id: SubjectId) -> None:
        with self.uow:
            project = owned_project(self.uow, project_id, user_id)
            self.uow.subjects.delete(project_id, subject_id)
            project_data_changed(self.uow, project, self.clock.now())
            self.uow.commit()
