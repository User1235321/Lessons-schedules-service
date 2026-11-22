from pathlib import PurePath
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Form, UploadFile
from pydantic import TypeAdapter, ValidationError

from app.api.deps import CurrentUserDep, UseCasesDep
from app.api.schemas.schedule_import import ScheduleImportResponse, parse_schedule
from app.domain.files import FileTooLarge, UnsupportedFileFormat
from app.domain.shared.errors import InvalidValue
from app.domain.shared.ids import ProjectId

router = APIRouter(tags=["imports"])
MAX_UPLOAD_BYTES = 16 * 1024 * 1024


@router.post("/projects/{project_id}/imports")
def import_schedule(
    project_id: UUID,
    file: UploadFile,
    import_mode: Annotated[Literal["SCHEDULE"], Form()],
    user_id: CurrentUserDep,
    use_cases: UseCasesDep,
    mapping: Annotated[str | None, Form()] = None,
) -> ScheduleImportResponse:
    name = file.filename or ""
    extension = PurePath(name).suffix.lower().lstrip(".")
    if extension not in {"json", "csv", "xlsx", "ods"}:
        raise UnsupportedFileFormat("Поддерживаются JSON, CSV, XLSX и ODS")
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise FileTooLarge("Размер файла превышает 16 МиБ")
    try:
        columns = TypeAdapter(dict[str, str]).validate_json(mapping) if mapping is not None else {}
    except ValidationError as error:
        raise InvalidValue(
            "Ожидается JSON-объект сопоставления столбцов", field="mapping"
        ) from error
    result = use_cases.import_schedule().execute(
        user_id,
        ProjectId(project_id),
        name,
        extension,
        content,
        file.content_type or "application/octet-stream",
        lambda: parse_schedule(content, extension, columns),
    )
    return ScheduleImportResponse.of(result)
