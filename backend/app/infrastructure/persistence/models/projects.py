from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.projects.project import MAX_NAME_LENGTH
from app.domain.projects.settings import DurationModeKind, TimeModeKind
from app.domain.shared.week import Weekday
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.checks import all_of, one_of

MODE_LENGTH = 16
WEEKDAY_LENGTH = 9  # WEDNESDAY


class ProjectRow(Base):
    """Проект и его настройки времени (HLD 9.3). Настройки — объекты-значения, поэтому колонки."""

    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("btrim(name) <> ''", name="name_not_blank"),
        CheckConstraint(all_of("odd_week_days", Weekday), name="odd_week_days_known"),
        CheckConstraint(all_of("even_week_days", Weekday), name="even_week_days_known"),
        CheckConstraint(one_of("time_mode", TimeModeKind), name="time_mode_known"),
        CheckConstraint(
            "(time_mode = 'STEP') = (time_step_minutes IS NOT NULL)", name="time_step_matches_mode"
        ),
        CheckConstraint("time_step_minutes > 0", name="time_step_positive"),
        CheckConstraint(one_of("duration_mode", DurationModeKind), name="duration_mode_known"),
        CheckConstraint(
            "(duration_mode = 'UNIFORM') = (duration_minutes IS NOT NULL)",
            name="duration_matches_mode",
        ),
        CheckConstraint("duration_minutes > 0", name="duration_positive"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(MAX_NAME_LENGTH))
    odd_week_days: Mapped[list[str]] = mapped_column(ARRAY(String(WEEKDAY_LENGTH)))
    even_week_days: Mapped[list[str]] = mapped_column(ARRAY(String(WEEKDAY_LENGTH)))
    time_mode: Mapped[str] = mapped_column(String(MODE_LENGTH))
    time_step_minutes: Mapped[int | None]
    duration_mode: Mapped[str] = mapped_column(String(MODE_LENGTH))
    duration_minutes: Mapped[int | None]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
