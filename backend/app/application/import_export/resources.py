from collections.abc import Callable, Iterable
from dataclasses import dataclass
from uuid import UUID

from app.application.academic.groups import CreateGroup, CreateSubgroup, UpdateGroup, UpdateSubgroup
from app.application.academic.rooms import CreateRoom, UpdateRoom
from app.application.academic.streams import CreateStream, UpdateStream
from app.application.academic.subjects import CreateSubject, UpdateSubject
from app.application.academic.teachers import CreateTeacher, UpdateTeacher
from app.application.academic.workloads import CreateWorkload, UpdateWorkload
from app.application.auth.access import owned_project
from app.application.constraints.use_cases import CreateConstraint, UpdateConstraint
from app.application.import_export.files import store_and_commit
from app.application.import_export.ports import ObjectStorage
from app.application.import_export.schedules import ImportIssue
from app.application.shared.ports import Clock, IdGenerator
from app.application.shared.uow import UnitOfWork
from app.domain.files import StoredFile, StoredFileCategory
from app.domain.shared.errors import DomainError, InvalidValue, NotFound
from app.domain.shared.ids import ProjectId, ScheduleId, StoredFileId, UserId

OPERATIONS = {
    "subjects": (CreateSubject, UpdateSubject),
    "groups": (CreateGroup, UpdateGroup),
    "subgroups": (CreateSubgroup, UpdateSubgroup),
    "teachers": (CreateTeacher, UpdateTeacher),
    "rooms": (CreateRoom, UpdateRoom),
    "streams": (CreateStream, UpdateStream),
    "workloads": (CreateWorkload, UpdateWorkload),
    "constraints": (CreateConstraint, UpdateConstraint),
}


@dataclass(frozen=True)
class ResourceChange:
    resource: str
    existing_id: UUID | None
    arguments: tuple[object, ...]

    def apply(
        self, uow: UnitOfWork, clock: Clock, ids: IdGenerator, user: UserId, project: ProjectId
    ) -> None:
        create, update = OPERATIONS[self.resource]
        if self.existing_id is None:
            create(uow.nested(), clock, ids).execute(user, project, *self.arguments)
        else:
            update(uow.nested(), clock).execute(user, project, self.existing_id, *self.arguments)


@dataclass(frozen=True)
class Upload:
    name: str
    extension: str
    content: bytes
    content_type: str

    def metadata(
        self, ids: IdGenerator, clock: Clock, user: UserId, project: ProjectId
    ) -> StoredFile:
        file_id = StoredFileId(ids.new_id())
        return StoredFile(
            id=file_id,
            project_id=project,
            user_id=user,
            category=StoredFileCategory.UPLOAD,
            original_name=self.name,
            file_format=self.extension,
            size_bytes=len(self.content),
            created_at=clock.now(),
            object_key=f"projects/{project}/uploads/{file_id}.{self.extension}",
        )


@dataclass(frozen=True)
class DataImportResult:
    file: StoredFile
    imported_count: int
    schedule_ids: list[ScheduleId]
    errors: list[ImportIssue]


@dataclass
class ImportResources:
    uow: UnitOfWork
    storage: ObjectStorage
    ids: IdGenerator
    clock: Clock

    def execute(
        self,
        user: UserId,
        project: ProjectId,
        upload: Upload,
        resource: str,
        rows: Callable[[], Iterable[tuple[int | None, ResourceChange | ImportIssue]]],
    ) -> DataImportResult:
        with self.uow:
            owned_project(self.uow, project, user)
            if resource not in OPERATIONS:
                raise InvalidValue("Неизвестный тип ресурса", field="resource")
            errors = []
            count = 0
            for number, row in rows():
                if isinstance(row, ImportIssue):
                    errors.append(row)
                    continue
                try:
                    row.apply(self.uow, self.clock, self.ids, user, project)
                except DomainError as error:
                    field = error.details.get(
                        "field", "id" if isinstance(error, NotFound) else None
                    )
                    errors.append(ImportIssue(number, field, error.message))
                else:
                    count += 1
            if not count and not errors:
                errors.append(ImportIssue(None, "file", "В файле нет строк"))
            file = upload.metadata(self.ids, self.clock, user, project)
            store_and_commit(self.uow, self.storage, file, upload.content, upload.content_type)
            return DataImportResult(file, count, [], errors)
