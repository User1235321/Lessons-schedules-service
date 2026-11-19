import sqlalchemy as sa
from alembic import op

revision = "b9e6f231a4f0"
down_revision = "72ac1f6f9c11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stored_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(8), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("file_format", sa.String(16), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schedule_id", sa.Uuid(), nullable=True),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stored_files")),
        sa.UniqueConstraint("object_key", name=op.f("uq_stored_files_object_key")),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"],
            name=op.f("fk_stored_files_project_id_projects"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name=op.f("fk_stored_files_user_id_users"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["schedule_id"], ["schedules.id"],
            name=op.f("fk_stored_files_schedule_id_schedules"), ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["schedule_jobs.id"],
            name=op.f("fk_stored_files_job_id_schedule_jobs"), ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "category IN ('UPLOAD', 'EXPORT')",
            name=op.f("ck_stored_files_category_known"),
        ),
        sa.CheckConstraint(
            "btrim(original_name) <> ''",
            name=op.f("ck_stored_files_original_name_not_blank"),
        ),
        sa.CheckConstraint(
            "btrim(file_format) <> ''",
            name=op.f("ck_stored_files_file_format_not_blank"),
        ),
        sa.CheckConstraint(
            "btrim(object_key) <> ''",
            name=op.f("ck_stored_files_object_key_not_blank"),
        ),
        sa.CheckConstraint("size_bytes >= 0", name=op.f("ck_stored_files_size_nonnegative")),
    )
    op.create_index("ix_stored_files_project_id", "stored_files", ["project_id"])
    op.create_index("ix_stored_files_schedule_id", "stored_files", ["schedule_id"])
    op.create_index("ix_stored_files_job_id", "stored_files", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_stored_files_job_id", table_name="stored_files")
    op.drop_index("ix_stored_files_schedule_id", table_name="stored_files")
    op.drop_index("ix_stored_files_project_id", table_name="stored_files")
    op.drop_table("stored_files")
