from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.domain.scheduling.job import JobMessage, JobType
from app.domain.shared.ids import JobId, ProjectId
from app.infrastructure.persistence.models.jobs import JobOutboxRow, JobRow


class SqlJobOutbox:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, job_id: JobId, created_at: datetime) -> None:
        self._session.add(JobOutboxRow(job_id=job_id, created_at=created_at))

    def get_pending_for_update(self) -> JobMessage | None:
        row = self._session.execute(
            select(JobRow.id, JobRow.project_id, JobRow.job_type)
            .join(JobOutboxRow, JobOutboxRow.job_id == JobRow.id)
            .where(JobOutboxRow.published_at.is_(None))
            .order_by(JobOutboxRow.created_at, JobOutboxRow.job_id)
            .limit(1)
            .with_for_update(of=JobOutboxRow, skip_locked=True)
        ).one_or_none()
        if row is None:
            return None
        return JobMessage(JobId(row.id), ProjectId(row.project_id), JobType(row.job_type))

    def mark_published(self, job_id: JobId, published_at: datetime) -> None:
        self._session.execute(
            update(JobOutboxRow)
            .where(JobOutboxRow.job_id == job_id, JobOutboxRow.published_at.is_(None))
            .values(published_at=published_at)
        )
