import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "e5820ab67f31"
down_revision = "c3ab950ec614"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_schedule_jobs_project_id", "schedule_jobs", ["project_id", "id"]
    )
    op.create_table(
        "schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("result_index", sa.Integer(), nullable=True),
        sa.Column("criterion_scores", JSONB(none_as_null=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_schedules")),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_schedules_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "job_id"],
            ["schedule_jobs.project_id", "schedule_jobs.id"],
            name=op.f("fk_schedules_project_id_schedule_jobs"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("job_id", "result_index", name=op.f("uq_schedules_job_id")),
        sa.CheckConstraint(
            "source IN ('GENERATED', 'IMPORTED')", name=op.f("ck_schedules_source_known")
        ),
        sa.CheckConstraint(
            "source <> 'GENERATED' OR "
            "(job_id IS NOT NULL AND result_index IS NOT NULL AND criterion_scores IS NOT NULL)",
            name=op.f("ck_schedules_generated_has_provenance"),
        ),
        sa.CheckConstraint(
            "source <> 'IMPORTED' OR job_id IS NULL", name=op.f("ck_schedules_imported_has_no_job")
        ),
        sa.CheckConstraint("result_index > 0", name=op.f("ck_schedules_result_index_positive")),
    )
    op.create_index("ix_schedules_project_id", "schedules", ["project_id"])
    op.create_table(
        "schedule_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("schedule_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("workload_id", sa.Uuid(), nullable=True),
        sa.Column("subject_name", sa.String(), nullable=True),
        sa.Column("participant_label", sa.String(), nullable=True),
        sa.Column("lesson_type", sa.String(16), nullable=True),
        sa.Column("lesson_format", sa.String(8), nullable=True),
        sa.Column("week", sa.String(4), nullable=False),
        sa.Column("weekday", sa.String(9), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("room_id", sa.Uuid(), nullable=True),
        sa.Column("room_name", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_schedule_entries")),
        sa.ForeignKeyConstraint(
            ["schedule_id"],
            ["schedules.id"],
            name=op.f("fk_schedule_entries_schedule_id_schedules"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "schedule_id", "position", name=op.f("uq_schedule_entries_schedule_id")
        ),
        sa.CheckConstraint("week IN ('ODD', 'EVEN')", name=op.f("ck_schedule_entries_week_known")),
        sa.CheckConstraint(
            "weekday IN ('MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY')",
            name=op.f("ck_schedule_entries_weekday_known"),
        ),
        sa.CheckConstraint(
            "end_time > start_time", name=op.f("ck_schedule_entries_interval_positive")
        ),
        sa.CheckConstraint(
            "lesson_format IN ('ONSITE', 'REMOTE')",
            name=op.f("ck_schedule_entries_lesson_format_known"),
        ),
        sa.CheckConstraint(
            "lesson_type IN ('LECTURE', 'PRACTICE', 'LAB')",
            name=op.f("ck_schedule_entries_lesson_type_known"),
        ),
        sa.CheckConstraint(
            "lesson_format <> 'REMOTE' OR (room_id IS NULL AND room_name IS NULL)",
            name=op.f("ck_schedule_entries_remote_has_no_room"),
        ),
    )
    op.create_index("ix_schedule_entries_schedule_id", "schedule_entries", ["schedule_id"])
    op.create_table(
        "schedule_entry_teachers",
        sa.Column("entry_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("teacher_id", sa.Uuid(), nullable=True),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("entry_id", "position", name=op.f("pk_schedule_entry_teachers")),
        sa.ForeignKeyConstraint(
            ["entry_id"],
            ["schedule_entries.id"],
            name=op.f("fk_schedule_entry_teachers_entry_id_schedule_entries"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "entry_id", "teacher_id", name=op.f("uq_schedule_entry_teachers_entry_id")
        ),
    )


def downgrade() -> None:
    op.drop_table("schedule_entry_teachers")
    op.drop_index("ix_schedule_entries_schedule_id", table_name="schedule_entries")
    op.drop_table("schedule_entries")
    op.drop_index("ix_schedules_project_id", table_name="schedules")
    op.drop_table("schedules")
    op.drop_constraint("uq_schedule_jobs_project_id", "schedule_jobs", type_="unique")
