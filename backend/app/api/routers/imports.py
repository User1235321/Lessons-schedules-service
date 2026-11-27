from pathlib import PurePath
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Form, UploadFile
from pydantic import TypeAdapter, ValidationError

from app.api.deps import CurrentUserDep, UseCasesDep
from app.api.schemas.project_archive import prepare_project
from app.api.schemas.resource_import import resource_rows
from app.api.schemas.schedule_import import ScheduleImportResponse, parse_schedule
from app.application.import_export.files import CONTENT_TYPES
from app.application.import_export.resources import Upload
from app.domain.files import MAX_UPLOAD_BYTES, FileTooLarge, UnsupportedFileFormat
from app.domain.shared.errors import InvalidValue
from app.domain.shared.ids import ProjectId

router = APIRouter(tags=["imports"])


@router.post("/projects/{project_id}/imports")
def import_schedule(
    project_id: UUID,
    file: UploadFile,
    import_mode: Annotated[Literal["SCHEDULE", "RESOURCE", "PROJECT"], Form()],
    user_id: CurrentUserDep,
    use_cases: UseCasesDep,
    mapping: Annotated[str | None, Form()] = None,
    resource: Annotated[str | None, Form()] = None,
) -> ScheduleImportResponse:
    project = ProjectId(project_id)
    name = file.filename or ""
    extension = PurePath(name).suffix.lower().lstrip(".")
    if extension not in CONTENT_TYPES:
        raise UnsupportedFileFormat("Поддерживаются JSON, CSV, XLSX и ODS")
    if import_mode == "PROJECT" and extension != "json":
        raise UnsupportedFileFormat("Для переноса проекта нужен JSON")
    if (import_mode == "RESOURCE") != (resource is not None):
        raise InvalidValue("Тип ресурса задаётся только при RESOURCE", field="resource")
    if import_mode == "PROJECT" and mapping is not None:
        raise InvalidValue("Архив проекта использует фиксированную схему", field="mapping")
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise FileTooLarge("Размер файла превышает 16 МиБ")
    try:
        columns = TypeAdapter(dict[str, str]).validate_json(mapping) if mapping is not None else {}
    except ValidationError as error:
        raise InvalidValue(
            "Ожидается JSON-объект сопоставления столбцов", field="mapping"
        ) from error
    mime = file.content_type or "application/octet-stream"
    upload = Upload(name, extension, content, mime)
    if import_mode == "PROJECT":
        result = use_cases.import_project().execute(
            user_id,
            project,
            upload,
            lambda ids, destination: prepare_project(content, ids, destination),
        )
    elif resource is not None:
        if len(set(columns.values())) != len(columns):
            raise InvalidValue("Два столбца сопоставлены одному полю", field="mapping")
        result = use_cases.import_resources().execute(
            user_id,
            project,
            upload,
            resource,
            lambda: resource_rows(content, extension, resource, columns),
        )
    else:
        schedule = use_cases.import_schedule().execute(
            user_id,
            project,
            name,
            extension,
            content,
            mime,
            lambda: parse_schedule(content, extension, columns),
        )
        return ScheduleImportResponse.of(schedule)
    return ScheduleImportResponse.model_validate(result, from_attributes=True)
