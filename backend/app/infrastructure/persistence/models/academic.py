from datetime import time
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.academic.lesson_type import LessonType
from app.domain.academic.names import MAX_NAME_LENGTH
from app.domain.shared.week import Week, Weekday
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.checks import one_of

LESSON_TYPE_LENGTH = 16
WEEK_LENGTH = 4
WEEKDAY_LENGTH = 9  # WEDNESDAY

# Ссылки на данные проекта составные: (project_id, id). Так база не даст связать
# преподавателя с дисциплиной или подгруппу с группой из другого проекта.


class SubjectRow(Base):
    __tablename__ = "subjects"
    __table_args__ = (
        UniqueConstraint("project_id", "id", name="uq_subjects_project_id_id"),
        CheckConstraint("btrim(name) <> ''", name="name_not_blank"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(MAX_NAME_LENGTH))


class TeacherRow(Base):
    __tablename__ = "teachers"
    __table_args__ = (
        UniqueConstraint("project_id", "id", name="uq_teachers_project_id_id"),
        CheckConstraint("btrim(full_name) <> ''", name="full_name_not_blank"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    full_name: Mapped[str] = mapped_column(String(MAX_NAME_LENGTH))

    # Только для чтения вместе с преподавателем: пишет их репозиторий явными запросами
    capabilities: Mapped[list["TeacherCapabilityRow"]] = relationship(viewonly=True, lazy="raise")
    availability: Mapped[list["TeacherAvailabilityRow"]] = relationship(viewonly=True, lazy="raise")
    preferences: Mapped[list["TeacherPreferenceRow"]] = relationship(viewonly=True, lazy="raise")


class TeacherCapabilityRow(Base):
    __tablename__ = "teacher_capabilities"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "teacher_id"],
            ["teachers.project_id", "teachers.id"],
            name="fk_teacher_capabilities_teacher",
            ondelete="CASCADE",
        ),
        # Занятую дисциплину удалить нельзя. DEFERRABLE — для удаления проекта: оно откладывает
        # проверку до commit, иначе исход зависел бы от порядка каскадов (см. SqlProjectRepository)
        ForeignKeyConstraint(
            ["project_id", "subject_id"],
            ["subjects.project_id", "subjects.id"],
            name="fk_teacher_capabilities_subject",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        CheckConstraint(one_of("lesson_type", LessonType), name="lesson_type_known"),
        Index("ix_teacher_capabilities_project_id_subject_id", "project_id", "subject_id"),
    )

    project_id: Mapped[UUID]
    teacher_id: Mapped[UUID] = mapped_column(primary_key=True)
    subject_id: Mapped[UUID] = mapped_column(primary_key=True)
    lesson_type: Mapped[str] = mapped_column(String(LESSON_TYPE_LENGTH), primary_key=True)


class _WeeklyIntervalColumns:
    """Колонки WeeklyInterval. Точный повтор промежутка не пройдёт первичный ключ."""

    teacher_id: Mapped[UUID] = mapped_column(
        ForeignKey("teachers.id", ondelete="CASCADE"), primary_key=True
    )
    week: Mapped[str] = mapped_column(String(WEEK_LENGTH), primary_key=True)
    day: Mapped[str] = mapped_column(String(WEEKDAY_LENGTH), primary_key=True)
    start_time: Mapped[time] = mapped_column(primary_key=True)
    end_time: Mapped[time] = mapped_column(primary_key=True)


def _interval_checks() -> tuple[CheckConstraint, ...]:
    return (
        CheckConstraint(one_of("week", Week), name="week_known"),
        CheckConstraint(one_of("day", Weekday), name="day_known"),
        CheckConstraint("end_time > start_time", name="ends_after_start"),
    )


class TeacherAvailabilityRow(_WeeklyIntervalColumns, Base):
    """Когда преподаватель может вести занятия (HLD 9.4)."""

    __tablename__ = "teacher_availability"
    __table_args__ = _interval_checks()


class TeacherPreferenceRow(_WeeklyIntervalColumns, Base):
    """Когда преподавателю удобнее. Влияет только на оптимизацию (HLD 9.4)."""

    __tablename__ = "teacher_preferences"
    __table_args__ = _interval_checks()


class StudentGroupRow(Base):
    __tablename__ = "student_groups"
    __table_args__ = (
        UniqueConstraint("project_id", "id", name="uq_student_groups_project_id_id"),
        CheckConstraint("btrim(name) <> ''", name="name_not_blank"),
        CheckConstraint("student_count > 0", name="student_count_positive"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(MAX_NAME_LENGTH))
    student_count: Mapped[int]

    subgroups: Mapped[list["SubgroupRow"]] = relationship(viewonly=True, lazy="raise")


class SubgroupRow(Base):
    """Подгруппа. project_id нужен, чтобы нагрузка ссылалась на подгруппу своего проекта."""

    __tablename__ = "subgroups"
    __table_args__ = (
        UniqueConstraint("project_id", "id", name="uq_subgroups_project_id_id"),
        ForeignKeyConstraint(
            ["project_id", "group_id"],
            ["student_groups.project_id", "student_groups.id"],
            name="fk_subgroups_group",
            ondelete="CASCADE",
        ),
        CheckConstraint("btrim(name) <> ''", name="name_not_blank"),
        CheckConstraint("student_count > 0", name="student_count_positive"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID]
    group_id: Mapped[UUID]
    name: Mapped[str] = mapped_column(String(MAX_NAME_LENGTH))
    student_count: Mapped[int]


# Названия уникальны без учёта регистра (их сравнивает и домен, см. name_key)
Index(
    "uq_subjects_project_id_name", SubjectRow.project_id, func.lower(SubjectRow.name), unique=True
)
Index(
    "uq_student_groups_project_id_name",
    StudentGroupRow.project_id,
    func.lower(StudentGroupRow.name),
    unique=True,
)
Index("uq_subgroups_group_id_name", SubgroupRow.group_id, func.lower(SubgroupRow.name), unique=True)
