from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.scheduling.job import JobStatus, JobType, ResultMode
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.checks import one_of


class JobRow(Base):
    __tablename__ = "schedule_jobs"
    __table_args__ = (
        UniqueConstraint("project_id", "id"),
        CheckConstraint(one_of("job_type", JobType), name="job_type_known"),
        CheckConstraint(one_of("status", JobStatus), name="status_known"),
        CheckConstraint(one_of("result_mode", ResultMode), name="result_mode_known"),
        CheckConstraint("(result_mode = 'TOP_N') = (top_n IS NOT NULL)", name="top_n_matches_mode"),
        CheckConstraint("top_n > 0", name="top_n_positive"),
        CheckConstraint(
            "status <> 'QUEUED' OR (started_at IS NULL AND finished_at IS NULL)",
            name="queued_not_started",
        ),
        CheckConstraint(
            "status NOT IN ('RUNNING', 'COMPLETED') OR started_at IS NOT NULL",
            name="started_at_required",
        ),
        CheckConstraint(
            "(status IN ('COMPLETED', 'FAILED', 'CANCELLED')) = (finished_at IS NOT NULL)",
            name="finished_at_matches_status",
        ),
        CheckConstraint("started_at >= created_at", name="started_after_creation"),
        CheckConstraint(
            "finished_at >= coalesce(started_at, created_at)", name="finished_after_start"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    job_type: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(16))
    result_mode: Mapped[str] = mapped_column(String(8))
    top_n: Mapped[int | None]
    created_at: Mapped[datetime]
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    error_message: Mapped[str | None] = mapped_column(Text)


class JobOutboxRow(Base):
    __tablename__ = "job_outbox"
    __table_args__ = (
        Index(
            "ix_job_outbox_pending",
            "created_at",
            "job_id",
            postgresql_where=text("published_at IS NULL"),
        ),
        CheckConstraint("published_at >= created_at", name="published_after_creation"),
    )

    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("schedule_jobs.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime]
    published_at: Mapped[datetime | None]
