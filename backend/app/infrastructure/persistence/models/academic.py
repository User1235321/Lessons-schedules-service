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
from app.domain.academic.room import RoomType
from app.domain.academic.workload import LessonFormat
from app.domain.shared.week import Week, Weekday
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.checks import one_of

LESSON_TYPE_LENGTH = 16
ROOM_TYPE_LENGTH = 32
FORMAT_LENGTH = 16
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
    """Колонки WeeklyInterval. Вместе с владельцем — первичный ключ: точный повтор не пройдёт."""

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


class _TeacherIntervalColumns(_WeeklyIntervalColumns):
    teacher_id: Mapped[UUID] = mapped_column(
        ForeignKey("teachers.id", ondelete="CASCADE"), primary_key=True, sort_order=-1
    )


class TeacherAvailabilityRow(_TeacherIntervalColumns, Base):
    """Когда преподаватель может вести занятия (HLD 9.4)."""

    __tablename__ = "teacher_availability"
    __table_args__ = _interval_checks()


class TeacherPreferenceRow(_TeacherIntervalColumns, Base):
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


def _in_project(columns: list[str], table: str, name: str) -> ForeignKeyConstraint:
    """Ссылка на данные того же проекта. Занятое удалить нельзя, а вместе с проектом можно:
    DEFERRABLE позволяет удалению проекта отложить проверку до commit (см. SqlProjectRepository).
    """
    return ForeignKeyConstraint(
        ["project_id", *columns],
        [f"{table}.project_id", f"{table}.id"],
        name=name,
        deferrable=True,
        initially="IMMEDIATE",
    )


class RoomRow(Base):
    __tablename__ = "rooms"
    __table_args__ = (
        UniqueConstraint("project_id", "id", name="uq_rooms_project_id_id"),
        CheckConstraint("btrim(name) <> ''", name="name_not_blank"),
        CheckConstraint("capacity > 0", name="capacity_positive"),
        CheckConstraint(one_of("type", RoomType), name="type_known"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(MAX_NAME_LENGTH))
    capacity: Mapped[int]
    type: Mapped[str] = mapped_column(String(ROOM_TYPE_LENGTH))

    availability: Mapped[list["RoomAvailabilityRow"]] = relationship(viewonly=True, lazy="raise")
    capabilities: Mapped[list["RoomCapabilityRow"]] = relationship(viewonly=True, lazy="raise")


class RoomAvailabilityRow(_WeeklyIntervalColumns, Base):
    """Когда аудитория свободна для занятий (HLD 9.5)."""

    __tablename__ = "room_availability"
    __table_args__ = _interval_checks()

    room_id: Mapped[UUID] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), primary_key=True, sort_order=-1
    )


class RoomCapabilityRow(Base):
    """Для чего годится специализированная или лабораторная аудитория (F_Data_9)."""

    __tablename__ = "room_capabilities"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "room_id"],
            ["rooms.project_id", "rooms.id"],
            name="fk_room_capabilities_room",
            ondelete="CASCADE",
        ),
        _in_project(["subject_id"], "subjects", "fk_room_capabilities_subject"),
        CheckConstraint(one_of("lesson_type", LessonType), name="lesson_type_known"),
        Index("ix_room_capabilities_project_id_subject_id", "project_id", "subject_id"),
    )

    project_id: Mapped[UUID]
    room_id: Mapped[UUID] = mapped_column(primary_key=True)
    subject_id: Mapped[UUID] = mapped_column(primary_key=True)
    lesson_type: Mapped[str] = mapped_column(String(LESSON_TYPE_LENGTH), primary_key=True)


class StreamRow(Base):
    __tablename__ = "student_streams"
    __table_args__ = (
        UniqueConstraint("project_id", "id", name="uq_student_streams_project_id_id"),
        CheckConstraint("btrim(name) <> ''", name="name_not_blank"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(MAX_NAME_LENGTH))

    groups: Mapped[list["StreamGroupRow"]] = relationship(viewonly=True, lazy="raise")


class StreamGroupRow(Base):
    """Группа в составе потока (HLD 9.7)."""

    __tablename__ = "stream_groups"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "stream_id"],
            ["student_streams.project_id", "student_streams.id"],
            name="fk_stream_groups_stream",
            ondelete="CASCADE",
        ),
        _in_project(["group_id"], "student_groups", "fk_stream_groups_group"),
        Index("ix_stream_groups_project_id_group_id", "project_id", "group_id"),
    )

    project_id: Mapped[UUID]
    stream_id: Mapped[UUID] = mapped_column(primary_key=True)
    group_id: Mapped[UUID] = mapped_column(primary_key=True)


class WorkloadRow(Base):
    """Элемент учебной нагрузки (HLD 9.8). Цель — ровно одна из group_id, subgroup_id, stream_id."""

    __tablename__ = "workloads"
    __table_args__ = (
        UniqueConstraint("project_id", "id", name="uq_workloads_project_id_id"),
        _in_project(["subject_id"], "subjects", "fk_workloads_subject"),
        _in_project(["group_id"], "student_groups", "fk_workloads_group"),
        _in_project(["subgroup_id"], "subgroups", "fk_workloads_subgroup"),
        _in_project(["stream_id"], "student_streams", "fk_workloads_stream"),
        CheckConstraint("num_nonnulls(group_id, subgroup_id, stream_id) = 1", name="one_target"),
        CheckConstraint(one_of("lesson_type", LessonType), name="lesson_type_known"),
        CheckConstraint(one_of("format", LessonFormat), name="format_known"),
        CheckConstraint("occurrences_per_cycle > 0", name="occurrences_positive"),
        CheckConstraint("duration_minutes > 0", name="duration_positive"),
        CheckConstraint("required_teacher_count >= 1", name="teacher_count_positive"),
        CheckConstraint(
            "lesson_type = 'LAB' OR required_teacher_count = 1",
            name="single_teacher_unless_lab",
        ),
        Index("ix_workloads_project_id_subject_id", "project_id", "subject_id"),
        Index("ix_workloads_project_id_group_id", "project_id", "group_id"),
        Index("ix_workloads_project_id_subgroup_id", "project_id", "subgroup_id"),
        Index("ix_workloads_project_id_stream_id", "project_id", "stream_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    subject_id: Mapped[UUID]
    lesson_type: Mapped[str] = mapped_column(String(LESSON_TYPE_LENGTH))
    format: Mapped[str] = mapped_column(String(FORMAT_LENGTH))
    occurrences_per_cycle: Mapped[int]
    duration_minutes: Mapped[int | None]
    required_teacher_count: Mapped[int]
    group_id: Mapped[UUID | None]
    subgroup_id: Mapped[UUID | None]
    stream_id: Mapped[UUID | None]


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
Index("uq_rooms_project_id_name", RoomRow.project_id, func.lower(RoomRow.name), unique=True)
Index(
    "uq_student_streams_project_id_name",
    StreamRow.project_id,
    func.lower(StreamRow.name),
    unique=True,
)
