"""add rooms, streams and workloads

Revision ID: 723cc89301de
Revises: 82939baba47b
Create Date: 2026-11-08 21:30:10.863698

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '723cc89301de'
down_revision: str | Sequence[str] | None = '82939baba47b'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Значения записаны прямо в миграции: она не должна меняться вместе с кодом приложения.
ROOM_TYPES = "('LECTURE', 'PRACTICE_UNIVERSAL', 'PRACTICE_SPECIALIZED', 'LABORATORY')"
LESSON_TYPES = "('LECTURE', 'PRACTICE', 'LAB')"
FORMATS = "('ONSITE', 'REMOTE')"
WEEKS = "('ODD', 'EVEN', 'ANY')"
WEEKDAYS = "('MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY')"


def in_project(columns: list[str], table: str, name: str) -> sa.ForeignKeyConstraint:
    """Ссылка на данные того же проекта. DEFERRABLE — чтобы удаление проекта могло
    отложить проверку до commit, когда каскад уберёт и ссылки."""
    return sa.ForeignKeyConstraint(
        ['project_id', *columns], [f'{table}.project_id', f'{table}.id'],
        name=name, deferrable=True, initially='IMMEDIATE',
    )


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'rooms',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('project_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('capacity', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_rooms')),
        sa.ForeignKeyConstraint(
            ['project_id'], ['projects.id'],
            name=op.f('fk_rooms_project_id_projects'), ondelete='CASCADE',
        ),
        sa.UniqueConstraint('project_id', 'id', name='uq_rooms_project_id_id'),
        sa.CheckConstraint("btrim(name) <> ''", name=op.f('ck_rooms_name_not_blank')),
        sa.CheckConstraint('capacity > 0', name=op.f('ck_rooms_capacity_positive')),
        sa.CheckConstraint(f"type IN {ROOM_TYPES}", name=op.f('ck_rooms_type_known')),
    )
    op.create_index(
        'uq_rooms_project_id_name', 'rooms',
        ['project_id', sa.literal_column('lower(name)')], unique=True,
    )

    op.create_table(
        'room_availability',
        sa.Column('room_id', sa.Uuid(), nullable=False),
        sa.Column('week', sa.String(length=4), nullable=False),
        sa.Column('day', sa.String(length=9), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.PrimaryKeyConstraint(
            'room_id', 'week', 'day', 'start_time', 'end_time', name=op.f('pk_room_availability')
        ),
        sa.ForeignKeyConstraint(
            ['room_id'], ['rooms.id'],
            name=op.f('fk_room_availability_room_id_rooms'), ondelete='CASCADE',
        ),
        sa.CheckConstraint(f"week IN {WEEKS}", name=op.f('ck_room_availability_week_known')),
        sa.CheckConstraint(f"day IN {WEEKDAYS}", name=op.f('ck_room_availability_day_known')),
        sa.CheckConstraint(
            'end_time > start_time', name=op.f('ck_room_availability_ends_after_start')
        ),
    )

    op.create_table(
        'room_capabilities',
        sa.Column('project_id', sa.Uuid(), nullable=False),
        sa.Column('room_id', sa.Uuid(), nullable=False),
        sa.Column('subject_id', sa.Uuid(), nullable=False),
        sa.Column('lesson_type', sa.String(length=16), nullable=False),
        sa.PrimaryKeyConstraint(
            'room_id', 'subject_id', 'lesson_type', name=op.f('pk_room_capabilities')
        ),
        sa.ForeignKeyConstraint(
            ['project_id', 'room_id'], ['rooms.project_id', 'rooms.id'],
            name='fk_room_capabilities_room', ondelete='CASCADE',
        ),
        in_project(['subject_id'], 'subjects', 'fk_room_capabilities_subject'),
        sa.CheckConstraint(
            f"lesson_type IN {LESSON_TYPES}", name=op.f('ck_room_capabilities_lesson_type_known')
        ),
    )
    op.create_index(
        'ix_room_capabilities_project_id_subject_id', 'room_capabilities',
        ['project_id', 'subject_id'],
    )

    op.create_table(
        'student_streams',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('project_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_student_streams')),
        sa.ForeignKeyConstraint(
            ['project_id'], ['projects.id'],
            name=op.f('fk_student_streams_project_id_projects'), ondelete='CASCADE',
        ),
        sa.UniqueConstraint('project_id', 'id', name='uq_student_streams_project_id_id'),
        sa.CheckConstraint("btrim(name) <> ''", name=op.f('ck_student_streams_name_not_blank')),
    )
    op.create_index(
        'uq_student_streams_project_id_name', 'student_streams',
        ['project_id', sa.literal_column('lower(name)')], unique=True,
    )

    op.create_table(
        'stream_groups',
        sa.Column('project_id', sa.Uuid(), nullable=False),
        sa.Column('stream_id', sa.Uuid(), nullable=False),
        sa.Column('group_id', sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint('stream_id', 'group_id', name=op.f('pk_stream_groups')),
        sa.ForeignKeyConstraint(
            ['project_id', 'stream_id'], ['student_streams.project_id', 'student_streams.id'],
            name='fk_stream_groups_stream', ondelete='CASCADE',
        ),
        in_project(['group_id'], 'student_groups', 'fk_stream_groups_group'),
    )
    op.create_index(
        'ix_stream_groups_project_id_group_id', 'stream_groups', ['project_id', 'group_id']
    )

    op.create_table(
        'workloads',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('project_id', sa.Uuid(), nullable=False),
        sa.Column('subject_id', sa.Uuid(), nullable=False),
        sa.Column('lesson_type', sa.String(length=16), nullable=False),
        sa.Column('format', sa.String(length=16), nullable=False),
        sa.Column('occurrences_per_cycle', sa.Integer(), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=True),
        sa.Column('required_teacher_count', sa.Integer(), nullable=False),
        sa.Column('group_id', sa.Uuid(), nullable=True),
        sa.Column('subgroup_id', sa.Uuid(), nullable=True),
        sa.Column('stream_id', sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_workloads')),
        sa.ForeignKeyConstraint(
            ['project_id'], ['projects.id'],
            name=op.f('fk_workloads_project_id_projects'), ondelete='CASCADE',
        ),
        sa.UniqueConstraint('project_id', 'id', name='uq_workloads_project_id_id'),
        in_project(['subject_id'], 'subjects', 'fk_workloads_subject'),
        in_project(['group_id'], 'student_groups', 'fk_workloads_group'),
        in_project(['subgroup_id'], 'subgroups', 'fk_workloads_subgroup'),
        in_project(['stream_id'], 'student_streams', 'fk_workloads_stream'),
        sa.CheckConstraint(
            'num_nonnulls(group_id, subgroup_id, stream_id) = 1',
            name=op.f('ck_workloads_one_target'),
        ),
        sa.CheckConstraint(
            f"lesson_type IN {LESSON_TYPES}", name=op.f('ck_workloads_lesson_type_known')
        ),
        sa.CheckConstraint(f"format IN {FORMATS}", name=op.f('ck_workloads_format_known')),
        sa.CheckConstraint(
            'occurrences_per_cycle > 0', name=op.f('ck_workloads_occurrences_positive')
        ),
        sa.CheckConstraint('duration_minutes > 0', name=op.f('ck_workloads_duration_positive')),
        sa.CheckConstraint(
            'required_teacher_count >= 1', name=op.f('ck_workloads_teacher_count_positive')
        ),
        sa.CheckConstraint(
            "lesson_type = 'LAB' OR required_teacher_count = 1",
            name=op.f('ck_workloads_single_teacher_unless_lab'),
        ),
    )
    for column in ('subject_id', 'group_id', 'subgroup_id', 'stream_id'):
        op.create_index(
            f'ix_workloads_project_id_{column}', 'workloads', ['project_id', column]
        )


def downgrade() -> None:
    """Downgrade schema."""
    for column in ('stream_id', 'subgroup_id', 'group_id', 'subject_id'):
        op.drop_index(f'ix_workloads_project_id_{column}', table_name='workloads')
    op.drop_table('workloads')
    op.drop_index('ix_stream_groups_project_id_group_id', table_name='stream_groups')
    op.drop_table('stream_groups')
    op.drop_index('uq_student_streams_project_id_name', table_name='student_streams')
    op.drop_table('student_streams')
    op.drop_index('ix_room_capabilities_project_id_subject_id', table_name='room_capabilities')
    op.drop_table('room_capabilities')
    op.drop_table('room_availability')
    op.drop_index('uq_rooms_project_id_name', table_name='rooms')
    op.drop_table('rooms')
