from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.domain.shared.errors import DomainError, InvalidValue
from app.domain.shared.ids import JobId, ProjectId, ScheduleId, StoredFileId, UserId


class StoredFileCategory(StrEnum):
    UPLOAD = "UPLOAD"
    EXPORT = "EXPORT"


class FileTooLarge(DomainError):
    code = "FILE_TOO_LARGE"


class UnsupportedFileFormat(DomainError):
    code = "UNSUPPORTED_FILE_FORMAT"


@dataclass(frozen=True, kw_only=True)
class StoredFile:
    id: StoredFileId
    project_id: ProjectId
    user_id: UserId
    category: StoredFileCategory
    original_name: str
    file_format: str
    object_key: str
    size_bytes: int
    created_at: datetime
    schedule_id: ScheduleId | None = None
    job_id: JobId | None = None

    def __post_init__(self) -> None:
        if not self.original_name.strip() or len(self.original_name) > 255:
            raise InvalidValue("Недопустимое имя файла", field="original_name")
        if not self.file_format.strip() or len(self.file_format) > 16:
            raise InvalidValue("Недопустимый формат файла", field="file_format")
        if not self.object_key.strip():
            raise InvalidValue("Не указан ключ объекта", field="object_key")
        if self.size_bytes < 0:
            raise InvalidValue("Размер файла не может быть отрицательным", field="size_bytes")
