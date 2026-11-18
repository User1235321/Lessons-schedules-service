from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.scheduling.constraints import ConstraintKind
from app.domain.scheduling.problem import CriterionType
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.checks import one_of


class ExtraConstraintRow(Base):
    __tablename__ = "extra_constraints"
    __table_args__ = (
        CheckConstraint(one_of("constraint_type", ConstraintKind), name="constraint_type_known"),
        CheckConstraint("jsonb_typeof(scope) = 'object'", name="scope_object"),
        CheckConstraint("jsonb_typeof(parameters) = 'object'", name="parameters_object"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    constraint_type: Mapped[str] = mapped_column(String(32))
    scope: Mapped[dict[str, object]] = mapped_column(JSONB)
    parameters: Mapped[dict[str, object]] = mapped_column(JSONB)


class OptimizationCriterionRow(Base):
    __tablename__ = "optimization_criteria"
    __table_args__ = (
        CheckConstraint(one_of("criterion_type", CriterionType), name="criterion_type_known"),
        CheckConstraint("priority > 0", name="priority_positive"),
        Index(
            "uq_optimization_criteria_active_priority",
            "project_id",
            "priority",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    criterion_type: Mapped[str] = mapped_column(String(48), primary_key=True)
    priority: Mapped[int]
    is_active: Mapped[bool]
