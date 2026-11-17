import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "72ac1f6f9c11"
down_revision = "e5820ab67f31"
branch_labels = None
depends_on = None

CONSTRAINT_TYPES = (
    "MIN_START_TIME", "MAX_END_TIME", "ALLOWED_DAYS", "EVERY_WEEK", "CONSECUTIVE",
    "NOT_CONSECUTIVE", "MIN_GAP", "BEFORE", "FIXED_DAY", "TIME_RANGE",
)
CRITERION_TYPES = (
    "STUDENT_GAPS", "TEACHER_GAPS", "TEACHER_PREFERENCES",
    "BALANCED_STUDENT_LOAD", "EARLY_LATE_CLASSES",
)


def _allowed_types(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def upgrade() -> None:
    op.create_table(
        "extra_constraints",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("constraint_type", sa.String(32), nullable=False),
        sa.Column("scope", JSONB(), nullable=False),
        sa.Column("parameters", JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_extra_constraints")),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"],
            name=op.f("fk_extra_constraints_project_id_projects"), ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            _allowed_types("constraint_type", CONSTRAINT_TYPES),
            name=op.f("ck_extra_constraints_constraint_type_known"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(scope) = 'object'", name=op.f("ck_extra_constraints_scope_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(parameters) = 'object'",
            name=op.f("ck_extra_constraints_parameters_object"),
        ),
    )
    op.create_index("ix_extra_constraints_project_id", "extra_constraints", ["project_id"])
    op.create_table(
        "optimization_criteria",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("criterion_type", sa.String(48), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint(
            "project_id", "criterion_type", name=op.f("pk_optimization_criteria")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"],
            name=op.f("fk_optimization_criteria_project_id_projects"), ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            _allowed_types("criterion_type", CRITERION_TYPES),
            name=op.f("ck_optimization_criteria_criterion_type_known"),
        ),
        sa.CheckConstraint(
            "priority > 0", name=op.f("ck_optimization_criteria_priority_positive"),
        ),
    )
    op.create_index(
        "uq_optimization_criteria_active_priority",
        "optimization_criteria", ["project_id", "priority"],
        unique=True, postgresql_where=sa.text("is_active"),
    )


def downgrade() -> None:
    op.drop_index("uq_optimization_criteria_active_priority", table_name="optimization_criteria")
    op.drop_table("optimization_criteria")
    op.drop_index("ix_extra_constraints_project_id", table_name="extra_constraints")
    op.drop_table("extra_constraints")
