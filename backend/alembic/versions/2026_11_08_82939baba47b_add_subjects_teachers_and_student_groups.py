"""add subjects, teachers and student groups

Revision ID: 82939baba47b
Revises: fa66cf515842
Create Date: 2026-11-08 19:48:57.527241

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '82939baba47b'
down_revision: str | Sequence[str] | None = 'fa66cf515842'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Значения записаны прямо в миграции: она не должна меняться вместе с кодом приложения.
LESSON_TYPES = "('LECTURE', 'PRACTICE', 'LAB')"
WEEKS = "('ODD', 'EVEN', 'ANY')"
WEEKDAYS = "('MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY')"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'subjects',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('project_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_subjects')),
        sa.ForeignKeyConstraint(
            ['project_id'], ['projects.id'],
            name=op.f('fk_subjects_project_id_projects'), ondelete='CASCADE',
        ),
        sa.UniqueConstraint('project_id', 'id', name='uq_subjects_project_id_id'),
        sa.CheckConstraint("btrim(name) <> ''", name=op.f('ck_subjects_name_not_blank')),
    )
    op.create_index(
        'uq_subjects_project_id_name', 'subjects',
        ['project_id', sa.literal_column('lower(name)')], unique=True,
    )

    op.create_table(
        'teachers',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('project_id', sa.Uuid(), nullable=False),
        sa.Column('full_name', sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_teachers')),
        sa.ForeignKeyConstraint(
            ['project_id'], ['projects.id'],
            name=op.f('fk_teachers_project_id_projects'), ondelete='CASCADE',
        ),
        sa.UniqueConstraint('project_id', 'id', name='uq_teachers_project_id_id'),
        sa.CheckConstraint(
            "btrim(full_name) <> ''", name=op.f('ck_teachers_full_name_not_blank')
        ),
    )

    op.create_table(
        'teacher_capabilities',
        sa.Column('project_id', sa.Uuid(), nullable=False),
        sa.Column('teacher_id', sa.Uuid(), nullable=False),
        sa.Column('subject_id', sa.Uuid(), nullable=False),
        sa.Column('lesson_type', sa.String(length=16), nullable=False),
        sa.PrimaryKeyConstraint(
            'teacher_id', 'subject_id', 'lesson_type', name=op.f('pk_teacher_capabilities')
        ),
        sa.ForeignKeyConstraint(
            ['project_id', 'teacher_id'], ['teachers.project_id', 'teachers.id'],
            name='fk_teacher_capabilities_teacher', ondelete='CASCADE',
        ),
        # Занятую дисциплину удалить нельзя. DEFERRABLE — чтобы удаление проекта
        # могло отложить проверку до commit, когда каскад уберёт и ссылки
        sa.ForeignKeyConstraint(
            ['project_id', 'subject_id'], ['subjects.project_id', 'subjects.id'],
            name='fk_teacher_capabilities_subject', deferrable=True, initially='IMMEDIATE',
        ),
        sa.CheckConstraint(
            f"lesson_type IN {LESSON_TYPES}", name=op.f('ck_teacher_capabilities_lesson_type_known')
        ),
    )
    op.create_index(
        'ix_teacher_capabilities_project_id_subject_id', 'teacher_capabilities',
        ['project_id', 'subject_id'],
    )

    for table in ('teacher_availability', 'teacher_preferences'):
        op.create_table(
            table,
            sa.Column('teacher_id', sa.Uuid(), nullable=False),
            sa.Column('week', sa.String(length=4), nullable=False),
            sa.Column('day', sa.String(length=9), nullable=False),
            sa.Column('start_time', sa.Time(), nullable=False),
            sa.Column('end_time', sa.Time(), nullable=False),
            sa.PrimaryKeyConstraint(
                'teacher_id', 'week', 'day', 'start_time', 'end_time', name=op.f(f'pk_{table}')
            ),
            sa.ForeignKeyConstraint(
                ['teacher_id'], ['teachers.id'],
                name=op.f(f'fk_{table}_teacher_id_teachers'), ondelete='CASCADE',
            ),
            sa.CheckConstraint(f"week IN {WEEKS}", name=op.f(f'ck_{table}_week_known')),
            sa.CheckConstraint(f"day IN {WEEKDAYS}", name=op.f(f'ck_{table}_day_known')),
            sa.CheckConstraint('end_time > start_time', name=op.f(f'ck_{table}_ends_after_start')),
        )

    op.create_table(
        'student_groups',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('project_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('student_count', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_student_groups')),
        sa.ForeignKeyConstraint(
            ['project_id'], ['projects.id'],
            name=op.f('fk_student_groups_project_id_projects'), ondelete='CASCADE',
        ),
        sa.UniqueConstraint('project_id', 'id', name='uq_student_groups_project_id_id'),
        sa.CheckConstraint("btrim(name) <> ''", name=op.f('ck_student_groups_name_not_blank')),
        sa.CheckConstraint(
            'student_count > 0', name=op.f('ck_student_groups_student_count_positive')
        ),
    )
    op.create_index(
        'uq_student_groups_project_id_name', 'student_groups',
        ['project_id', sa.literal_column('lower(name)')], unique=True,
    )

    op.create_table(
        'subgroups',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('project_id', sa.Uuid(), nullable=False),
        sa.Column('group_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('student_count', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_subgroups')),
        sa.ForeignKeyConstraint(
            ['project_id', 'group_id'], ['student_groups.project_id', 'student_groups.id'],
            name='fk_subgroups_group', ondelete='CASCADE',
        ),
        sa.UniqueConstraint('project_id', 'id', name='uq_subgroups_project_id_id'),
        sa.CheckConstraint("btrim(name) <> ''", name=op.f('ck_subgroups_name_not_blank')),
        sa.CheckConstraint('student_count > 0', name=op.f('ck_subgroups_student_count_positive')),
    )
    op.create_index(
        'uq_subgroups_group_id_name', 'subgroups',
        ['group_id', sa.literal_column('lower(name)')], unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('uq_subgroups_group_id_name', table_name='subgroups')
    op.drop_table('subgroups')
    op.drop_index('uq_student_groups_project_id_name', table_name='student_groups')
    op.drop_table('student_groups')
    op.drop_table('teacher_preferences')
    op.drop_table('teacher_availability')
    op.drop_index('ix_teacher_capabilities_project_id_subject_id', table_name='teacher_capabilities')
    op.drop_table('teacher_capabilities')
    op.drop_table('teachers')
    op.drop_index('uq_subjects_project_id_name', table_name='subjects')
    op.drop_table('subjects')
