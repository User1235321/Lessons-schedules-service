from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Response

from app.api.deps import CurrentUserDep, UseCasesDep
from app.api.schemas.files import ExportRequest, StoredFileResponse
from app.api.schemas.project_archive import encode_project
from app.api.schemas.schedule_export import encode_schedule
from app.application.import_export.files import CONTENT_TYPES
from app.domain.files import StoredFileCategory, UnsupportedFileFormat
from app.domain.shared.errors import InvalidValue
from app.domain.shared.ids import ProjectId, ScheduleId, StoredFileId

router = APIRouter(tags=["files"])


@router.get("/projects/{project_id}/files")
def list_files(
    project_id: UUID,
    user_id: CurrentUserDep,
    use_cases: UseCasesDep,
    category: StoredFileCategory | None = None,
) -> list[StoredFileResponse]:
    files = use_cases.list_files().execute(user_id, ProjectId(project_id), category)
    return [StoredFileResponse.model_validate(file) for file in files]


@router.post("/projects/{project_id}/exports", status_code=201)
def export_file(
    project_id: UUID, body: ExportRequest, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> StoredFileResponse:
    extension = body.file_format.lower()
    if body.scope == "PROJECT":
        if body.schedule_id is not None:
            raise InvalidValue("Для полного проекта расписание не задаётся", field="schedule_id")
        if extension != "json":
            raise UnsupportedFileFormat("Для переноса проекта нужен JSON")
        file = use_cases.export_project().execute(user_id, ProjectId(project_id), encode_project)
    else:
        if body.schedule_id is None:
            raise InvalidValue("Укажите расписание", field="schedule_id")
        file = use_cases.export_schedule().execute(
            user_id, ProjectId(project_id), ScheduleId(body.schedule_id), extension, encode_schedule
        )
    return StoredFileResponse.model_validate(file)


@router.get("/files/{file_id}", response_class=Response)
def download_file(file_id: UUID, user_id: CurrentUserDep, use_cases: UseCasesDep) -> Response:
    file, content = use_cases.download_file().execute(user_id, StoredFileId(file_id))
    return Response(
        content,
        media_type=CONTENT_TYPES.get(file.file_format, "application/octet-stream"),
        headers={
            "Content-Disposition": "attachment; filename*=UTF-8''"
            + quote(file.original_name, safe="")
        },
    )


@router.delete("/files/{file_id}", status_code=204)
def delete_file(file_id: UUID, user_id: CurrentUserDep, use_cases: UseCasesDep) -> None:
    use_cases.delete_file().execute(user_id, StoredFileId(file_id))
