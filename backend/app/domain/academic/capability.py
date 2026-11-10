from collections.abc import Iterable
from dataclasses import dataclass

from app.domain.academic.lesson_type import LessonType
from app.domain.shared.ids import SubjectId

_LESSON_TYPE_ORDER = {lesson_type: index for index, lesson_type in enumerate(LessonType)}


@dataclass(frozen=True)
class Capability:
    """Дисциплина и тип занятия: что ведёт преподаватель или для чего годится аудитория."""

    subject_id: SubjectId
    lesson_type: LessonType


def ordered_capabilities(capabilities: Iterable[Capability]) -> tuple[Capability, ...]:
    """Пары без повторов. Порядок не важен, но постоянен: по дисциплине, затем по типу."""
    return tuple(
        sorted(
            set(capabilities),
            key=lambda pair: (str(pair.subject_id), _LESSON_TYPE_ORDER[pair.lesson_type]),
        )
    )
