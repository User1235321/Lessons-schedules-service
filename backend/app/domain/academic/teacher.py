from collections.abc import Iterable
from dataclasses import dataclass

from app.domain.academic.lesson_type import LessonType
from app.domain.academic.names import clean_name
from app.domain.shared.errors import InvalidValue
from app.domain.shared.ids import ProjectId, SubjectId, TeacherId
from app.domain.shared.week import WeeklyInterval, ordered_intervals

_MISSING_NAME = "Укажите ФИО преподавателя"
_LESSON_TYPE_ORDER = {lesson_type: index for index, lesson_type in enumerate(LessonType)}


@dataclass(frozen=True)
class Capability:
    """Дисциплина и тип занятия, которые преподаватель может вести (HLD 9.4)."""

    subject_id: SubjectId
    lesson_type: LessonType


@dataclass(kw_only=True)
class Teacher:
    """Преподаватель проекта (F_Data_4).

    Обязательны ФИО, хотя бы одна пара «дисциплина и тип занятия» и хотя бы один
    промежуток доступности. Предпочтения необязательны и влияют только на оптимизацию.
    Повторы в наборах убираются, порядок в них не важен.
    """

    id: TeacherId
    project_id: ProjectId
    full_name: str
    capabilities: tuple[Capability, ...]
    availability: tuple[WeeklyInterval, ...]
    preferences: tuple[WeeklyInterval, ...] = ()

    def __post_init__(self) -> None:
        self.rename(self.full_name)
        self.change_capabilities(self.capabilities)
        self.change_availability(self.availability)
        self.change_preferences(self.preferences)

    def rename(self, full_name: str) -> None:
        self.full_name = clean_name(full_name, field="full_name", missing=_MISSING_NAME)

    def change_capabilities(self, capabilities: Iterable[Capability]) -> None:
        unique = sorted(
            set(capabilities),
            key=lambda pair: (str(pair.subject_id), _LESSON_TYPE_ORDER[pair.lesson_type]),
        )
        if not unique:
            raise InvalidValue(
                "Укажите хотя бы одну дисциплину с типом занятия", field="capabilities"
            )
        self.capabilities = tuple(unique)

    def change_availability(self, availability: Iterable[WeeklyInterval]) -> None:
        ordered = ordered_intervals(availability)
        if not ordered:
            raise InvalidValue("Укажите хотя бы один промежуток доступности", field="availability")
        self.availability = ordered

    def change_preferences(self, preferences: Iterable[WeeklyInterval]) -> None:
        self.preferences = ordered_intervals(preferences)
