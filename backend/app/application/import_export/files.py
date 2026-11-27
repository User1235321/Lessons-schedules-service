import logging
from dataclasses import dataclass

from app.application.auth.access import owned_project
from app.application.import_export.ports import ObjectKey, ObjectStorage, ObjectStorageError
from app.application.shared.uow import UnitOfWork
from app.domain.files import StoredFile, StoredFileCategory
from app.domain.shared.errors import NotFound
from app.domain.shared.ids import ProjectId, StoredFileId, UserId

logger = logging.getLogger(__name__)

CONTENT_TYPES = {
    "json": "application/json",
    "csv": "text/csv; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "ods": "application/vnd.oasis.opendocument.spreadsheet",
}


def store_and_commit(
    uow: UnitOfWork, storage: ObjectStorage, file: StoredFile, content: bytes, content_type: str
) -> None:
    key = ObjectKey(file.object_key)
    uow.files.add(file)
    storage.put(key, content, content_type=content_type)
    try:
        uow.commit()
    except Exception:
        try:
            storage.delete(key)
        except ObjectStorageError:
            logger.exception("Не удалось удалить объект после ошибки фиксации: %s", file.id)
        raise


@dataclass
class ListFiles:
    uow: UnitOfWork

    def execute(
        self, user_id: UserId, project_id: ProjectId, category: StoredFileCategory | None
    ) -> list[StoredFile]:
        with self.uow:
            owned_project(self.uow, project_id, user_id)
            return self.uow.files.list_in_project(project_id, category=category)


@dataclass
class DownloadFile:
    uow: UnitOfWork
    storage: ObjectStorage

    def execute(self, user_id: UserId, file_id: StoredFileId) -> tuple[StoredFile, bytes]:
        with self.uow:
            file = self.uow.files.get_owned(file_id, user_id)
            if file is None:
                raise NotFound("Файл не найден", file_id=str(file_id))
            content = self.storage.get(ObjectKey(file.object_key))
            if content is None:
                raise NotFound("Файл не найден", file_id=str(file_id))
            return file, content


@dataclass
class DeleteFile:
    uow: UnitOfWork
    storage: ObjectStorage

    def execute(self, user_id: UserId, file_id: StoredFileId) -> None:
        with self.uow:
            file = self.uow.files.get_owned(file_id, user_id, for_update=True)
            if file is None:
                raise NotFound("Файл не найден", file_id=str(file_id))
            key = ObjectKey(file.object_key)
            content = self.storage.get(key)
            self.uow.files.delete(file.project_id, file.id)
            self.storage.delete(key)
            try:
                self.uow.commit()
            except Exception:
                if content is not None:
                    try:
                        self.storage.put(
                            key,
                            content,
                            content_type=CONTENT_TYPES.get(
                                file.file_format, "application/octet-stream"
                            ),
                        )
                    except ObjectStorageError:
                        logger.exception(
                            "Не удалось восстановить объект после ошибки удаления: %s", file.id
                        )
                raise
