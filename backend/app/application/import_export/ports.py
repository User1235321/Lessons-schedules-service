from typing import NewType, Protocol

from app.domain.files import StoredFile
from app.domain.shared.ids import ProjectId, StoredFileId

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

    def list_in_project(self, project_id: ProjectId) -> list[StoredFile]: ...

    def delete(self, project_id: ProjectId, file_id: StoredFileId) -> None: ...
