from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from app.application.auth.access import owned_project
from app.application.constraints.use_cases import ReplaceCriteria
from app.application.import_export.files import store_and_commit
from app.application.import_export.ports import ObjectStorage
from app.application.import_export.resources import DataImportResult, ResourceChange, Upload
from app.application.import_export.schedules import ImportIssue
from app.application.projects.use_cases import SettingsChanges, UpdateProject
from app.application.shared.ports import Clock, IdGenerator
from app.application.shared.uow import UnitOfWork
from app.domain.academic.group import StudentGroup
from app.domain.academic.room import Room
from app.domain.academic.stream import Stream
from app.domain.academic.subject import Subject
from app.domain.academic.teacher import Teacher
from app.domain.academic.workload import Workload
from app.domain.files import StoredFile, StoredFileCategory
from app.domain.projects.project import Project
from app.domain.scheduling.constraints import ExtraConstraintSnapshot
from app.domain.scheduling.problem import OptimizationCriterionSnapshot
from app.domain.scheduling.schedule import Schedule
from app.domain.shared.errors import DomainError, InvalidValue
from app.domain.shared.ids import ProjectId, StoredFileId, UserId


@dataclass
class ProjectContents:
    project: Project
    subjects: list[Subject]
    groups: list[StudentGroup]
    teachers: list[Teacher]
    rooms: list[Room]
    streams: list[Stream]
    workloads: list[Workload]
    constraints: list[ExtraConstraintSnapshot]
    criteria: list[OptimizationCriterionSnapshot]
    schedules: list[Schedule]

    @classmethod
    def read(cls, uow: UnitOfWork, project: Project):
        key = project.id
        return cls(
            project,
            uow.subjects.list_in_project(key),
            uow.groups.list_in_project(key),
            uow.teachers.list_in_project(key),
            uow.rooms.list_in_project(key),
            uow.streams.list_in_project(key),
            uow.workloads.list_in_project(key),
            uow.constraints.list_in_project(key),
            uow.criteria.list_in_project(key),
            uow.schedules.list_in_project(key),
        )

    def has_data(self) -> bool:
        return any(
            (
                self.subjects,
                self.groups,
                self.teachers,
                self.rooms,
                self.streams,
                self.workloads,
                self.constraints,
                self.criteria,
                self.schedules,
            )
        )


@dataclass(frozen=True)
class RestoreId:
    """ID уже выделен для восстановления ссылок между записями архива."""

    value: UUID

    def new_id(self) -> UUID:
        return self.value


@dataclass
class ArchivedResource:
    id: UUID
    row: int
    change: ResourceChange


@dataclass
class ProjectRestore:
    name: str
    settings: SettingsChanges
    resources: list[ArchivedResource]
    criteria: tuple[OptimizationCriterionSnapshot, ...]
    schedules: list[Schedule]


@dataclass
class ExportProject:
    uow: UnitOfWork
    storage: ObjectStorage
    ids: IdGenerator
    clock: Clock

    def execute(
        self, user: UserId, project_id: ProjectId, encode: Callable[[ProjectContents], bytes]
    ) -> StoredFile:
        with self.uow:
            project = owned_project(self.uow, project_id, user)
            content = encode(ProjectContents.read(self.uow, project))
            file_id = StoredFileId(self.ids.new_id())
            file = StoredFile(
                id=file_id,
                project_id=project_id,
                user_id=user,
                category=StoredFileCategory.EXPORT,
                original_name=f"Проект-{project_id}.json",
                file_format="json",
                object_key=f"projects/{project_id}/exports/{file_id}.json",
                size_bytes=len(content),
                created_at=self.clock.now(),
            )
            store_and_commit(self.uow, self.storage, file, content, "application/json")
            return file


@dataclass
class ImportProject:
    uow: UnitOfWork
    storage: ObjectStorage
    ids: IdGenerator
    clock: Clock

    def execute(
        self,
        user: UserId,
        project_id: ProjectId,
        upload: Upload,
        prepare: Callable[[IdGenerator, ProjectId], ProjectRestore],
    ) -> DataImportResult:
        with self.uow:
            project = owned_project(self.uow, project_id, user, for_update=True)
            errors = []
            count = 0
            schedule_ids = []
            try:
                if (
                    self.uow.jobs.has_in_project(project_id)
                    or ProjectContents.read(self.uow, project).has_data()
                ):
                    raise InvalidValue("Для восстановления нужен пустой проект", field="project")
                plan = prepare(self.ids, project_id)
                with self.uow.nested() as tx:
                    UpdateProject(tx.nested(), self.clock).execute(
                        user, project_id, plan.name, plan.settings
                    )
                    for record in plan.resources:
                        try:
                            record.change.apply(
                                tx, self.clock, RestoreId(record.id), user, project_id
                            )
                        except DomainError as error:
                            field = error.details.get("field")
                            location = record.change.resource + ("." + field if field else "")
                            raise InvalidValue(
                                error.message, field=location, row=record.row
                            ) from error
                    ReplaceCriteria(tx.nested(), self.clock).execute(
                        user, project_id, plan.criteria
                    )
                    for schedule in plan.schedules:
                        tx.schedules.add(schedule)
                    tx.commit()
                schedule_ids = [schedule.id for schedule in plan.schedules]
                count = 1 + len(plan.resources) + len(plan.criteria) + len(schedule_ids)
            except DomainError as error:
                errors.append(
                    ImportIssue(
                        error.details.get("row"),
                        error.details.get("field", "project"),
                        error.message,
                    )
                )
            file = upload.metadata(self.ids, self.clock, user, project_id)
            store_and_commit(self.uow, self.storage, file, upload.content, upload.content_type)
            return DataImportResult(file, count, schedule_ids, errors)
