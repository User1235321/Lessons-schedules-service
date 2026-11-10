from typing import NewType, Protocol

ObjectKey = NewType("ObjectKey", str)


class ObjectStorageError(Exception):
    pass


class ObjectStorage(Protocol):
    def put(self, key: ObjectKey, content: bytes, *, content_type: str) -> None: ...

    def get(self, key: ObjectKey) -> bytes | None: ...

    def delete(self, key: ObjectKey) -> None: ...
