from collections.abc import Callable
from dataclasses import dataclass

from app.application.auth.access import owned_project
from app.application.import_export.files import CONTENT_TYPES, store_and_commit
from app.application.import_export.ports import ObjectStorage
from app.application.shared.ports import Clock, IdGenerator
from app.application.shared.uow import UnitOfWork
from app.domain.files import StoredFile, StoredFileCategory, UnsupportedFileFormat
from app.domain.scheduling.schedule import Schedule
from app.domain.shared.errors import NotFound
from app.domain.shared.ids import ProjectId, ScheduleId, StoredFileId, UserId


@dataclass
class ExportSchedule:
    uow: UnitOfWork
    storage: ObjectStorage
    ids: IdGenerator
    clock: Clock

    def execute(
        self,
        user_id: UserId,
        project_id: ProjectId,
        schedule_id: ScheduleId,
        extension: str,
        encode: Callable[[Schedule, str], bytes],
    ) -> StoredFile:
        with self.uow:
            owned_project(self.uow, project_id, user_id)
            if extension not in CONTENT_TYPES:
                raise UnsupportedFileFormat("Поддерживаются JSON, CSV, XLSX и ODS")
            schedule = self.uow.schedules.get(project_id, schedule_id)
            if schedule is None:
                raise NotFound("Расписание не найдено", schedule_id=str(schedule_id))
            content = encode(schedule, extension)
            file_id = StoredFileId(self.ids.new_id())
            file = StoredFile(
                id=file_id,
                project_id=project_id,
                user_id=user_id,
                category=StoredFileCategory.EXPORT,
                original_name=f"Расписание-{schedule_id}.{extension}",
                file_format=extension,
                object_key=f"projects/{project_id}/exports/{file_id}.{extension}",
                size_bytes=len(content),
                created_at=self.clock.now(),
                schedule_id=schedule_id,
                job_id=schedule.job_id,
            )
            store_and_commit(self.uow, self.storage, file, content, CONTENT_TYPES[extension])
            return file
