from typing import NewType, Protocol

from app.domain.files import StoredFile, StoredFileCategory
from app.domain.shared.ids import ProjectId, StoredFileId, UserId

ObjectKey = NewType("ObjectKey", str)


class ObjectStorageError(Exception):
    pass


class ObjectStorage(Protocol):
    def put(self, key: ObjectKey, content: bytes, *, content_type: str) -> None: ...

    def get(self, key: ObjectKey) -> bytes | None: ...

    def delete(self, key: ObjectKey) -> None: ...


class StoredFileRepository(Protocol):
    def add(self, file: StoredFile) -> None: ...

    def get(self, project_id: ProjectId, file_id: StoredFileId) -> StoredFile | None: ...

    def get_owned(
        self, file_id: StoredFileId, user_id: UserId, *, for_update: bool = False
    ) -> StoredFile | None: ...

    def list_in_project(
        self, project_id: ProjectId, *, category: StoredFileCategory | None = None
    ) -> list[StoredFile]: ...

    def delete(self, project_id: ProjectId, file_id: StoredFileId) -> None: ...
