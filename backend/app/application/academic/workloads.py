from dataclasses import dataclass, replace
from typing import Any

from app.application.academic.changes import project_data_changed
from app.application.auth.access import owned_project
from app.application.constraints.references import ensure_not_referenced
from app.application.shared.ports import Clock, IdGenerator
from app.application.shared.uow import UnitOfWork
from app.domain.academic.lesson_type import LessonType
from app.domain.academic.workload import LessonFormat, TargetType, Workload, WorkloadTarget
from app.domain.shared.errors import InvalidValue, NotFound
from app.domain.shared.ids import (
    GroupId,
    ProjectId,
    StreamId,
    SubgroupId,
    SubjectId,
    UserId,
    WorkloadId,
)


@dataclass(frozen=True)
class WorkloadDraft:
    target: WorkloadTarget
    subject_id: SubjectId
    lesson_type: LessonType
    lesson_format: LessonFormat
    occurrences_per_cycle: int
    duration_minutes: int | None
    required_teacher_count: int


def _check_references(uow: UnitOfWork, project_id: ProjectId, workload: Workload) -> None:
    if uow.subjects.get(project_id, workload.subject_id) is None:
        raise InvalidValue("Такой дисциплины нет в проекте", field="subject_id")

    target = workload.target
    match target.type:
        case TargetType.GROUP:
            found = uow.groups.get(project_id, GroupId(target.id))
        case TargetType.SUBGROUP:
            found = uow.groups.get_by_subgroup(project_id, SubgroupId(target.id))
        case TargetType.STREAM:
            found = uow.streams.get(project_id, StreamId(target.id))
        case _:
            raise InvalidValue("Неизвестный тип цели", field="target.type")
    if found is None:
        raise InvalidValue("Такой группы, подгруппы или потока нет в проекте", field=f"{target.type.lower()}_id")


def _not_found(workload_id: WorkloadId) -> NotFound:
    return NotFound("Учебная нагрузка не найдена", workload_id=str(workload_id))


@dataclass(frozen=True)
class CreateWorkload:
    uow: UnitOfWork
    clock: Clock
    ids: IdGenerator

    def execute(self, user_id: UserId, project_id: ProjectId, draft: WorkloadDraft) -> Workload:
        with self.uow:
            project = owned_project(self.uow, project_id, user_id)
            workload = Workload(
                id=WorkloadId(self.ids.new_id()),
                project_id=project.id,
                target=draft.target,
                subject_id=draft.subject_id,
                lesson_type=draft.lesson_type,
                format=draft.lesson_format,
                occurrences_per_cycle=draft.occurrences_per_cycle,
                duration_minutes=draft.duration_minutes,
                required_teacher_count=draft.required_teacher_count,
            )
            _check_references(self.uow, project_id, workload)
            self.uow.workloads.add(workload)
            project_data_changed(self.uow, project, self.clock.now())
            self.uow.commit()
        return workload


@dataclass(frozen=True)
class ListWorkloads:
    uow: UnitOfWork

    def execute(self, user_id: UserId, project_id: ProjectId) -> list[Workload]:
        with self.uow:
            owned_project(self.uow, project_id, user_id)
            return self.uow.workloads.list_in_project(project_id)


@dataclass(frozen=True)
class GetWorkload:
    uow: UnitOfWork

    def execute(
        self, user_id: UserId, project_id: ProjectId, workload_id: WorkloadId
    ) -> Workload:
        with self.uow:
            owned_project(self.uow, project_id, user_id)
            workload = self.uow.workloads.get(project_id, workload_id)
        if workload is None:
            raise _not_found(workload_id)
        return workload


@dataclass(frozen=True)
class UpdateWorkload:
    uow: UnitOfWork
    clock: Clock

    def execute(
        self,
        user_id: UserId,
        project_id: ProjectId,
        workload_id: WorkloadId,
        changes: dict[str, Any],
    ) -> Workload:
        with self.uow:
            project = owned_project(self.uow, project_id, user_id)
            workload = self.uow.workloads.get_for_update(project_id, workload_id)
            if workload is None:
                raise _not_found(workload_id)
            if not changes:
                return workload
            updated = replace(workload, **changes)
            _check_references(self.uow, project_id, updated)
            self.uow.workloads.save(updated)
            project_data_changed(self.uow, project, self.clock.now())
            self.uow.commit()
        return updated


@dataclass(frozen=True)
class DeleteWorkload:
    uow: UnitOfWork
    clock: Clock

    def execute(
        self, user_id: UserId, project_id: ProjectId, workload_id: WorkloadId
    ) -> None:
        with self.uow:
            project = owned_project(self.uow, project_id, user_id)
            self.uow.constraints.lock_project(project_id)
            if self.uow.workloads.get_for_update(project_id, workload_id) is None:
                raise _not_found(workload_id)
            ensure_not_referenced(self.uow, project_id, "WORKLOAD", {workload_id})
            self.uow.workloads.delete(project_id, workload_id)
            project_data_changed(self.uow, project, self.clock.now())
            self.uow.commit()
