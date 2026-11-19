from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.files import StoredFileCategory
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.checks import one_of


class StoredFileRow(Base):
    __tablename__ = "stored_files"
    __table_args__ = (
        CheckConstraint(one_of("category", StoredFileCategory), name="category_known"),
        CheckConstraint("btrim(original_name) <> ''", name="original_name_not_blank"),
        CheckConstraint("btrim(file_format) <> ''", name="file_format_not_blank"),
        CheckConstraint("btrim(object_key) <> ''", name="object_key_not_blank"),
        CheckConstraint("size_bytes >= 0", name="size_nonnegative"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(String(8))
    original_name: Mapped[str] = mapped_column(String(255))
    file_format: Mapped[str] = mapped_column(String(16))
    object_key: Mapped[str] = mapped_column(Text, unique=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime]
    schedule_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("schedules.id", ondelete="SET NULL"), index=True
    )
    job_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("schedule_jobs.id", ondelete="SET NULL"), index=True
    )
