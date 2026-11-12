from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.domain.scheduling.job import Job
from app.domain.shared.errors import NotFound
from app.domain.shared.ids import JobId, ProjectId, UserId
from app.infrastructure.persistence.mappers.jobs import (
    job_to_domain,
    job_to_row,
    job_update_values,
)
from app.infrastructure.persistence.models import ProjectRow
from app.infrastructure.persistence.models.jobs import JobRow


class SqlJobRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, job: Job) -> None:
        self._session.add(job_to_row(job))
        self._session.flush()

    def get(self, project_id: ProjectId, job_id: JobId) -> Job | None:
        row = self._session.scalar(
            select(JobRow).where(JobRow.id == job_id, JobRow.project_id == project_id)
        )
        return job_to_domain(row) if row else None

    def get_for_update(self, project_id: ProjectId, job_id: JobId) -> Job | None:
        row = self._session.scalar(
            select(JobRow)
            .where(JobRow.id == job_id, JobRow.project_id == project_id)
            .with_for_update()
        )
        return job_to_domain(row) if row else None

    def get_owned(self, job_id: JobId, owner_id: UserId) -> Job | None:
        return self._get_owned(job_id, owner_id, for_update=False)

    def get_owned_for_update(self, job_id: JobId, owner_id: UserId) -> Job | None:
        return self._get_owned(job_id, owner_id, for_update=True)

    def _get_owned(self, job_id: JobId, owner_id: UserId, *, for_update: bool) -> Job | None:
        query = (
            select(JobRow)
            .join(ProjectRow, JobRow.project_id == ProjectRow.id)
            .where(JobRow.id == job_id, ProjectRow.owner_id == owner_id)
        )
        if for_update:
            query = query.with_for_update(of=JobRow)
        row = self._session.scalar(query)
        return job_to_domain(row) if row else None

    def save(self, job: Job) -> None:
        updated = self._session.scalar(
            update(JobRow)
            .where(JobRow.id == job.id, JobRow.project_id == job.project_id)
            .values(job_update_values(job))
            .returning(JobRow.id)
        )
        if updated is None:
            raise NotFound("Задание не найдено", job_id=str(job.id))
