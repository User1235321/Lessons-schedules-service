import sqlalchemy as sa
from alembic import op

revision = "c3ab950ec614"
down_revision = "fa66cf515842"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "schedule_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("job_type", sa.String(24), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("result_mode", sa.String(8), nullable=False),
        sa.Column("top_n", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_schedule_jobs")),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_schedule_jobs_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "job_type IN ('GENERATE', 'REOPTIMIZE_FULL', 'REOPTIMIZE_MIN_CHANGES', 'AUTO_REPAIR')",
            name=op.f("ck_schedule_jobs_job_type_known"),
        ),
        sa.CheckConstraint(
            "status IN ('QUEUED', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED')",
            name=op.f("ck_schedule_jobs_status_known"),
        ),
        sa.CheckConstraint(
            "result_mode IN ('SINGLE', 'TOP_N')",
            name=op.f("ck_schedule_jobs_result_mode_known"),
        ),
        sa.CheckConstraint(
            "(result_mode = 'TOP_N') = (top_n IS NOT NULL)",
            name=op.f("ck_schedule_jobs_top_n_matches_mode"),
        ),
        sa.CheckConstraint("top_n > 0", name=op.f("ck_schedule_jobs_top_n_positive")),
        sa.CheckConstraint(
            "status <> 'QUEUED' OR (started_at IS NULL AND finished_at IS NULL)",
            name=op.f("ck_schedule_jobs_queued_not_started"),
        ),
        sa.CheckConstraint(
            "status NOT IN ('RUNNING', 'COMPLETED') OR started_at IS NOT NULL",
            name=op.f("ck_schedule_jobs_started_at_required"),
        ),
        sa.CheckConstraint(
            "(status IN ('COMPLETED', 'FAILED', 'CANCELLED')) = (finished_at IS NOT NULL)",
            name=op.f("ck_schedule_jobs_finished_at_matches_status"),
        ),
        sa.CheckConstraint(
            "started_at >= created_at", name=op.f("ck_schedule_jobs_started_after_creation")
        ),
        sa.CheckConstraint(
            "finished_at >= coalesce(started_at, created_at)",
            name=op.f("ck_schedule_jobs_finished_after_start"),
        ),
    )
    op.create_index("ix_schedule_jobs_project_id", "schedule_jobs", ["project_id"])
    op.create_table(
        "job_outbox",
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("job_id", name=op.f("pk_job_outbox")),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["schedule_jobs.id"],
            name=op.f("fk_job_outbox_job_id_schedule_jobs"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "published_at >= created_at", name=op.f("ck_job_outbox_published_after_creation")
        ),
    )
    op.create_index(
        "ix_job_outbox_pending",
        "job_outbox",
        ["created_at", "job_id"],
        postgresql_where=sa.text("published_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_job_outbox_pending", table_name="job_outbox")
    op.drop_table("job_outbox")
    op.drop_index("ix_schedule_jobs_project_id", table_name="schedule_jobs")
    op.drop_table("schedule_jobs")
