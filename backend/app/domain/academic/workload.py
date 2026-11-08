from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from app.domain.academic.lesson_type import LessonType
from app.domain.shared.errors import InvalidValue
from app.domain.shared.ids import ProjectId, SubjectId, WorkloadId


class TargetType(StrEnum):
    """Для кого нагрузка (F_Data_16). Значения совпадают с форматом test-data."""

    GROUP = "GROUP"
    SUBGROUP = "SUBGROUP"
    STREAM = "STREAM"


@dataclass(frozen=True)
class WorkloadTarget:
    """Ровно одна цель нагрузки: группа, подгруппа или поток (HLD 9.8)."""

    type: TargetType
    id: UUID


class LessonFormat(StrEnum):
    """Формат занятия (F_Data_17). Дистанционному аудитория не назначается."""

    ONSITE = "ONSITE"
    REMOTE = "REMOTE"


@dataclass(frozen=True, kw_only=True)
class Workload:
    """Элемент учебной нагрузки (F_Data_16).

    Меняется заменой: dataclasses.replace проверяет новое значение заново.
    Длительность необязательна: что она есть в режиме INDIVIDUAL, проверяется перед
    расчётом (F_Valid_3), иначе смена режима проекта ломала бы сохранённую нагрузку.
    """

    id: WorkloadId
    project_id: ProjectId
    target: WorkloadTarget
    subject_id: SubjectId
    lesson_type: LessonType
    format: LessonFormat
    occurrences_per_cycle: int
    duration_minutes: int | None = None
    required_teacher_count: int = 1

    def __post_init__(self) -> None:
        if self.occurrences_per_cycle <= 0:  # F_Valid_1
            raise InvalidValue(
                "Нужно положительное число занятий за цикл", field="occurrences_per_cycle"
            )
        if self.duration_minutes is not None and self.duration_minutes <= 0:
            raise InvalidValue("Нужна положительная длительность", field="duration_minutes")
        if self.required_teacher_count < 1:
            raise InvalidValue("Нужен хотя бы один преподаватель", field="required_teacher_count")
        # HLD 9.8: несколько преподавателей бывает только на лабораторной
        if self.lesson_type is not LessonType.LAB and self.required_teacher_count != 1:
            raise InvalidValue(
                "На лекции и практике ровно один преподаватель", field="required_teacher_count"
            )
