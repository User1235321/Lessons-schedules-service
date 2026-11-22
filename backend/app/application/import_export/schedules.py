import logging
from collections.abc import Callable
from dataclasses import dataclass

from app.application.auth.access import owned_project
from app.application.import_export.ports import ObjectKey, ObjectStorage, ObjectStorageError
from app.application.scheduling.validation_data import load_validation_data
from app.application.shared.ports import Clock, IdGenerator
from app.application.shared.uow import UnitOfWork
from app.domain.files import StoredFile, StoredFileCategory
from app.domain.scheduling.schedule import Schedule, ScheduleConflict, ScheduleEntry, ScheduleSource
from app.domain.scheduling.validation import validate_schedule
from app.domain.shared.ids import ProjectId, ScheduleId, StoredFileId, UserId

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ImportIssue:
    row: int | None
    field: str | None
    message: str


@dataclass(frozen=True)
class ImportResult:
    file: StoredFile
    imported_count: int
    errors: list[ImportIssue]
    conflicts: list[ScheduleConflict]


@dataclass
class ImportSchedule:
    uow: UnitOfWork
    storage: ObjectStorage
    ids: IdGenerator
    clock: Clock

    def execute(
        self,
        user_id: UserId,
        project_id: ProjectId,
        filename: str,
        extension: str,
        content: bytes,
        content_type: str,
        parse: Callable[[], tuple[list[ScheduleEntry], list[ImportIssue]]],
    ) -> ImportResult:
        with self.uow:
            project = owned_project(self.uow, project_id, user_id)
            entries, errors = parse()
            now = self.clock.now()
            file_id = StoredFileId(self.ids.new_id())
            key = ObjectKey(f"projects/{project_id}/uploads/{file_id}.{extension}")
            schedule_id = None
            conflicts = []
            if entries:
                schedule_id = ScheduleId(self.ids.new_id())
                schedule = Schedule(
                    id=schedule_id,
                    project_id=project_id,
                    source=ScheduleSource.IMPORTED,
                    created_at=now,
                    entries=tuple(entries),
                )
                conflicts = validate_schedule(schedule, load_validation_data(self.uow, project))
                self.uow.schedules.add(schedule)
            file = StoredFile(
                id=file_id,
                project_id=project_id,
                user_id=user_id,
                category=StoredFileCategory.UPLOAD,
                original_name=filename,
                file_format=extension,
                size_bytes=len(content),
                created_at=now,
                object_key=key,
                schedule_id=schedule_id,
            )
            self.uow.files.add(file)
            self.storage.put(key, content, content_type=content_type)
            try:
                self.uow.commit()
            except Exception:
                try:
                    self.storage.delete(key)
                except ObjectStorageError:
                    logger.exception("Не удалось удалить файл после ошибки импорта: %s", key)
                raise
        return ImportResult(file, len(entries), errors, conflicts)
