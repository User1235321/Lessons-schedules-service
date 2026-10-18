"""add users, user sessions and projects

Revision ID: fa66cf515842
Revises:
Create Date: 2026-10-18 07:33:56.194707

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'fa66cf515842'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Значения записаны прямо в миграции: она не должна меняться вместе с кодом приложения.
WEEKDAYS = "ARRAY['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY']"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'users',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('email', sa.String(length=254), nullable=False),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
        sa.UniqueConstraint('email', name=op.f('uq_users_email')),
        sa.CheckConstraint('email = lower(email)', name=op.f('ck_users_email_lowercase')),
    )

    op.create_table(
        'user_sessions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('refresh_token_hash', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_user_sessions')),
        sa.ForeignKeyConstraint(
            ['user_id'], ['users.id'],
            name=op.f('fk_user_sessions_user_id_users'), ondelete='CASCADE',
        ),
        sa.UniqueConstraint(
            'refresh_token_hash', name=op.f('uq_user_sessions_refresh_token_hash')
        ),
    )
    op.create_index(op.f('ix_user_sessions_user_id'), 'user_sessions', ['user_id'])

    op.create_table(
        'projects',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('owner_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('odd_week_days', postgresql.ARRAY(sa.String(length=9)), nullable=False),
        sa.Column('even_week_days', postgresql.ARRAY(sa.String(length=9)), nullable=False),
        sa.Column('time_mode', sa.String(length=16), nullable=False),
        sa.Column('time_step_minutes', sa.Integer(), nullable=True),
        sa.Column('duration_mode', sa.String(length=16), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_projects')),
        sa.ForeignKeyConstraint(
            ['owner_id'], ['users.id'],
            name=op.f('fk_projects_owner_id_users'), ondelete='CASCADE',
        ),
        sa.CheckConstraint("btrim(name) <> ''", name=op.f('ck_projects_name_not_blank')),
        sa.CheckConstraint(
            f"odd_week_days <@ {WEEKDAYS}::varchar[]",
            name=op.f('ck_projects_odd_week_days_known'),
        ),
        sa.CheckConstraint(
            f"even_week_days <@ {WEEKDAYS}::varchar[]",
            name=op.f('ck_projects_even_week_days_known'),
        ),
        sa.CheckConstraint(
            "time_mode IN ('HOUR_START', 'STEP')", name=op.f('ck_projects_time_mode_known')
        ),
        sa.CheckConstraint(
            "(time_mode = 'STEP') = (time_step_minutes IS NOT NULL)",
            name=op.f('ck_projects_time_step_matches_mode'),
        ),
        sa.CheckConstraint('time_step_minutes > 0', name=op.f('ck_projects_time_step_positive')),
        sa.CheckConstraint(
            "duration_mode IN ('UNIFORM', 'INDIVIDUAL')",
            name=op.f('ck_projects_duration_mode_known'),
        ),
        sa.CheckConstraint(
            "(duration_mode = 'UNIFORM') = (duration_minutes IS NOT NULL)",
            name=op.f('ck_projects_duration_matches_mode'),
        ),
        sa.CheckConstraint('duration_minutes > 0', name=op.f('ck_projects_duration_positive')),
    )
    op.create_index(op.f('ix_projects_owner_id'), 'projects', ['owner_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_projects_owner_id'), table_name='projects')
    op.drop_table('projects')
    op.drop_index(op.f('ix_user_sessions_user_id'), table_name='user_sessions')
    op.drop_table('user_sessions')
    op.drop_table('users')
