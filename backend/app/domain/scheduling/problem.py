from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from app.domain.projects.settings import ProjectSettings
from app.domain.scheduling.constraints import ExtraConstraintSnapshot
from app.domain.scheduling.resources import (
    GroupSnapshot,
    LessonType,
    RoomSnapshot,
    StreamSnapshot,
    SubgroupSnapshot,
    SubjectSnapshot,
    TeacherSnapshot,
)
from app.domain.scheduling.schedule import LessonFormat
from app.domain.shared.errors import InvalidValue


class WorkloadTargetKind(StrEnum):
    GROUP = "GROUP"
    SUBGROUP = "SUBGROUP"
    STREAM = "STREAM"


@dataclass(frozen=True)
class WorkloadTarget:
    kind: WorkloadTargetKind
    resource_id: UUID


@dataclass(frozen=True)
class WorkloadSnapshot:
    id: UUID
    target: WorkloadTarget
    subject_id: UUID
    lesson_type: LessonType
    lesson_format: LessonFormat
    occurrences_per_cycle: int
    required_teacher_count: int
    duration_minutes: int | None = None

    def __post_init__(self) -> None:
        if self.occurrences_per_cycle <= 0:
            raise InvalidValue(
                "Количество занятий должно быть положительным", field="occurrences_per_cycle"
            )
        if self.required_teacher_count <= 0:
            raise InvalidValue(
                "Количество преподавателей должно быть положительным",
                field="required_teacher_count",
            )
        if self.lesson_type in ("LECTURE", "PRACTICE") and self.required_teacher_count != 1:
            raise InvalidValue(
                "Лекцию или практику ведёт один преподаватель",
                field="required_teacher_count",
            )
        if self.duration_minutes is not None and self.duration_minutes <= 0:
            raise InvalidValue("Длительность должна быть положительной", field="duration_minutes")


@dataclass(frozen=True)
class OptimizationCriterionSnapshot:
    criterion_type: str
    priority: int
    is_active: bool = True

    def __post_init__(self) -> None:
        if not self.criterion_type.strip():
            raise InvalidValue("Укажите критерий оптимизации", field="criterion_type")
        if self.priority <= 0:
            raise InvalidValue("Приоритет должен быть положительным", field="priority")


@dataclass(frozen=True)
class ScheduleProblem:
    settings: ProjectSettings
    subjects: tuple[SubjectSnapshot, ...] = ()
    teachers: tuple[TeacherSnapshot, ...] = ()
    rooms: tuple[RoomSnapshot, ...] = ()
    groups: tuple[GroupSnapshot, ...] = ()
    subgroups: tuple[SubgroupSnapshot, ...] = ()
    streams: tuple[StreamSnapshot, ...] = ()
    workloads: tuple[WorkloadSnapshot, ...] = ()
    constraints: tuple[ExtraConstraintSnapshot, ...] = ()
    optimization_criteria: tuple[OptimizationCriterionSnapshot, ...] = ()

    def __post_init__(self) -> None:
        for collection in (
            self.subjects,
            self.teachers,
            self.rooms,
            self.groups,
            self.subgroups,
            self.streams,
            self.workloads,
            self.constraints,
        ):
            ids = [item.id for item in collection]
            if len(ids) != len(set(ids)):
                raise InvalidValue("Идентификаторы элементов не должны повторяться", field="id")

        active = [criterion for criterion in self.optimization_criteria if criterion.is_active]
        priorities = [criterion.priority for criterion in active]
        if len(priorities) != len(set(priorities)):
            raise InvalidValue("Приоритеты активных критериев должны отличаться", field="priority")
        types = [criterion.criterion_type for criterion in self.optimization_criteria]
        if len(types) != len(set(types)):
            raise InvalidValue("Критерий оптимизации задан повторно", field="criterion_type")

        for group in self.groups:
            students = sum(
                subgroup.student_count
                for subgroup in self.subgroups
                if subgroup.group_id == group.id
            )
            if students > group.student_count:
                raise InvalidValue(
                    "Число студентов в подгруппах превышает численность группы",
                    field="student_count",
                )
