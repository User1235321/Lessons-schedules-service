from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domain.files import StoredFileCategory


class StoredFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    category: StoredFileCategory
    original_name: str
    file_format: str
    size_bytes: int
    created_at: datetime
    schedule_id: UUID | None
    job_id: UUID | None


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Literal["SCHEDULE", "PROJECT"]
    schedule_id: UUID | None = None
    file_format: str
