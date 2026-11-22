import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "26b8d99174ad"
down_revision = "7d9a4e21b8cf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "schedule_job_inputs",
        sa.Column(
            "job_id",
            sa.Uuid(),
            sa.ForeignKey("schedule_jobs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("problem", JSONB(), nullable=False),
    )
    op.add_column(
        "schedule_jobs",
        sa.Column("diagnostics", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("schedule_jobs", "diagnostics")
    op.drop_table("schedule_job_inputs")
