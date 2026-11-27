from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.files import StoredFile, StoredFileCategory
from app.domain.shared.errors import AlreadyExists, InvalidValue, NotFound
from app.domain.shared.ids import ProjectId, StoredFileId, UserId
from app.infrastructure.persistence.errors import violated_constraint
from app.infrastructure.persistence.models.files import StoredFileRow
from app.infrastructure.persistence.models.jobs import JobRow
from app.infrastructure.persistence.models.projects import ProjectRow
from app.infrastructure.persistence.models.schedules import ScheduleRow


def _to_domain(row: StoredFileRow) -> StoredFile:
    return StoredFile(
        id=StoredFileId(row.id),
        project_id=ProjectId(row.project_id),
        user_id=row.user_id,
        category=StoredFileCategory(row.category),
        original_name=row.original_name,
        file_format=row.file_format,
        object_key=row.object_key,
        size_bytes=row.size_bytes,
        created_at=row.created_at,
        schedule_id=row.schedule_id,
        job_id=row.job_id,
    )


class SqlStoredFileRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, file: StoredFile) -> None:
        self._validate_references(file)
        self._session.add(
            StoredFileRow(
                id=file.id,
                project_id=file.project_id,
                user_id=file.user_id,
                category=file.category.value,
                original_name=file.original_name,
                file_format=file.file_format,
                object_key=file.object_key,
                size_bytes=file.size_bytes,
                created_at=file.created_at,
                schedule_id=file.schedule_id,
                job_id=file.job_id,
            )
        )
        try:
            self._session.flush()
        except IntegrityError as error:
            if violated_constraint(error) in ("pk_stored_files", "uq_stored_files_object_key"):
                raise AlreadyExists("Файл уже зарегистрирован", file_id=str(file.id)) from error
            raise

    def get(self, project_id: ProjectId, file_id: StoredFileId) -> StoredFile | None:
        row = self._session.scalar(
            select(StoredFileRow).where(
                StoredFileRow.project_id == project_id, StoredFileRow.id == file_id
            )
        )
        return _to_domain(row) if row else None

    def get_owned(
        self, file_id: StoredFileId, user_id: UserId, *, for_update: bool = False
    ) -> StoredFile | None:
        query = (
            select(StoredFileRow)
            .join(ProjectRow, ProjectRow.id == StoredFileRow.project_id)
            .where(StoredFileRow.id == file_id, ProjectRow.owner_id == user_id)
        )
        if for_update:
            query = query.with_for_update(of=StoredFileRow)
        row = self._session.scalar(query)
        return _to_domain(row) if row else None

    def list_in_project(
        self, project_id: ProjectId, *, category: StoredFileCategory | None = None
    ) -> list[StoredFile]:
        query = select(StoredFileRow).where(StoredFileRow.project_id == project_id)
        if category is not None:
            query = query.where(StoredFileRow.category == category.value)
        rows = self._session.scalars(
            query.order_by(StoredFileRow.created_at.desc(), StoredFileRow.id)
        )
        return [_to_domain(row) for row in rows]

    def delete(self, project_id: ProjectId, file_id: StoredFileId) -> None:
        deleted = self._session.scalar(
            delete(StoredFileRow)
            .where(StoredFileRow.project_id == project_id, StoredFileRow.id == file_id)
            .returning(StoredFileRow.id)
        )
        if deleted is None:
            raise NotFound("Файл не найден", file_id=str(file_id))

    def _validate_references(self, file: StoredFile) -> None:
        owner_id = self._session.scalar(
            select(ProjectRow.owner_id).where(ProjectRow.id == file.project_id)
        )
        if owner_id is None or owner_id != file.user_id:
            raise NotFound("Проект не найден", project_id=str(file.project_id))
        if file.schedule_id is not None:
            schedule_id = self._session.scalar(
                select(ScheduleRow.id).where(
                    ScheduleRow.id == file.schedule_id,
                    ScheduleRow.project_id == file.project_id,
                )
            )
            if schedule_id is None:
                raise InvalidValue("Расписание не принадлежит проекту", field="schedule_id")
        if file.job_id is not None:
            job_id = self._session.scalar(
                select(JobRow.id).where(
                    JobRow.id == file.job_id,
                    JobRow.project_id == file.project_id,
                )
            )
            if job_id is None:
                raise InvalidValue("Задание не принадлежит проекту", field="job_id")
