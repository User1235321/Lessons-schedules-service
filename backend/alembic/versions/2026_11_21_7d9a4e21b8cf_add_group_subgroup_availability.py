from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7d9a4e21b8cf"
down_revision: str | Sequence[str] | None = "a43de8f70912"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WEEKS = "('ODD', 'EVEN', 'ANY')"
WEEKDAYS = "('MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY')"


def upgrade() -> None:
    for name, owner_column, owner_table in (
        ("group_availability", "group_id", "student_groups"),
        ("subgroup_availability", "subgroup_id", "subgroups"),
    ):
        op.create_table(
            name,
            sa.Column(owner_column, sa.Uuid(), nullable=False),
            sa.Column("week", sa.String(length=4), nullable=False),
            sa.Column("day", sa.String(length=9), nullable=False),
            sa.Column("start_time", sa.Time(), nullable=False),
            sa.Column("end_time", sa.Time(), nullable=False),
            sa.PrimaryKeyConstraint(
                owner_column, "week", "day", "start_time", "end_time",
                name=op.f(f"pk_{name}"),
            ),
            sa.ForeignKeyConstraint(
                [owner_column], [f"{owner_table}.id"],
                name=op.f(f"fk_{name}_{owner_column}_{owner_table}"),
                ondelete="CASCADE",
            ),
            sa.CheckConstraint(f"week IN {WEEKS}", name=op.f(f"ck_{name}_week_known")),
            sa.CheckConstraint(f"day IN {WEEKDAYS}", name=op.f(f"ck_{name}_day_known")),
            sa.CheckConstraint("end_time > start_time", name=op.f(f"ck_{name}_ends_after_start")),
        )


def downgrade() -> None:
    op.drop_table("subgroup_availability")
    op.drop_table("group_availability")
