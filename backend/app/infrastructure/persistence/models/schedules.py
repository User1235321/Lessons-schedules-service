from datetime import datetime, time
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.base import Base


class ScheduleRow(Base):
    __tablename__ = "schedules"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "job_id"],
            ["schedule_jobs.project_id", "schedule_jobs.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("job_id", "result_index"),
        CheckConstraint("source IN ('GENERATED', 'IMPORTED')", name="source_known"),
        CheckConstraint(
            "source <> 'GENERATED' OR "
            "(job_id IS NOT NULL AND result_index IS NOT NULL AND criterion_scores IS NOT NULL)",
            name="generated_has_provenance",
        ),
        CheckConstraint("source <> 'IMPORTED' OR job_id IS NULL", name="imported_has_no_job"),
        CheckConstraint("result_index > 0", name="result_index_positive"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[str] = mapped_column(String(16))
    job_id: Mapped[UUID | None]
    result_index: Mapped[int | None]
    criterion_scores: Mapped[list[dict[str, str | float]] | None] = mapped_column(
        JSONB(none_as_null=True)
    )
    created_at: Mapped[datetime]


class ScheduleEntryRow(Base):
    __tablename__ = "schedule_entries"
    __table_args__ = (
        CheckConstraint("week IN ('ODD', 'EVEN')", name="week_known"),
        CheckConstraint(
            "weekday IN ('MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY')",
            name="weekday_known",
        ),
        CheckConstraint("end_time > start_time", name="interval_positive"),
        CheckConstraint("lesson_format IN ('ONSITE', 'REMOTE')", name="lesson_format_known"),
        CheckConstraint("lesson_type IN ('LECTURE', 'PRACTICE', 'LAB')", name="lesson_type_known"),
        CheckConstraint(
            "lesson_format <> 'REMOTE' OR (room_id IS NULL AND room_name IS NULL)",
            name="remote_has_no_room",
        ),
        UniqueConstraint("schedule_id", "position"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    schedule_id: Mapped[UUID] = mapped_column(
        ForeignKey("schedules.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int]
    workload_id: Mapped[UUID | None]
    subject_name: Mapped[str | None]
    participant_label: Mapped[str | None]
    lesson_type: Mapped[str | None] = mapped_column(String(16))
    lesson_format: Mapped[str | None] = mapped_column(String(8))
    week: Mapped[str] = mapped_column(String(4))
    weekday: Mapped[str] = mapped_column(String(9))
    start_time: Mapped[time]
    end_time: Mapped[time]
    room_id: Mapped[UUID | None]
    room_name: Mapped[str | None]


class ScheduleEntryTeacherRow(Base):
    __tablename__ = "schedule_entry_teachers"
    __table_args__ = (UniqueConstraint("entry_id", "teacher_id"),)

    entry_id: Mapped[UUID] = mapped_column(
        ForeignKey("schedule_entries.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[UUID | None]
    display_name: Mapped[str]
