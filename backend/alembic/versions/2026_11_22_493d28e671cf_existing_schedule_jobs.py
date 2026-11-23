import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "493d28e671cf"
down_revision = "26b8d99174ad"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("schedule_jobs", sa.Column("existing_input", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("schedule_jobs", "existing_input")
