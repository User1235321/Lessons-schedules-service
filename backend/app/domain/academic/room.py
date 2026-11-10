from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from app.domain.academic.capability import Capability, ordered_capabilities
from app.domain.academic.names import clean_name
from app.domain.shared.errors import InvalidValue
from app.domain.shared.ids import ProjectId, RoomId
from app.domain.shared.week import WeeklyInterval, ordered_intervals

_MISSING_NAME = "Укажите номер или название аудитории"


class RoomType(StrEnum):
    """Тип аудитории (F_Data_8, HLD 9.5)."""

    LECTURE = "LECTURE"
    PRACTICE_UNIVERSAL = "PRACTICE_UNIVERSAL"
    PRACTICE_SPECIALIZED = "PRACTICE_SPECIALIZED"
    LABORATORY = "LABORATORY"

    @property
    def has_capabilities(self) -> bool:
        """Допустимые дисциплины задаются только специализированным и лабораторным (F_Data_9)."""
        return self in (RoomType.PRACTICE_SPECIALIZED, RoomType.LABORATORY)


@dataclass(kw_only=True)
class Room:
    """Аудитория проекта (F_Data_7).

    Обязательны название, вместимость и хотя бы один промежуток доступности. Пустой
    набор пар у специализированной или лабораторной аудитории допустим: что он значит,
    решает расчёт.
    """

    id: RoomId
    project_id: ProjectId
    name: str
    capacity: int
    type: RoomType
    availability: tuple[WeeklyInterval, ...]
    capabilities: tuple[Capability, ...] = ()

    def __post_init__(self) -> None:
        self.rename(self.name)
        self.change_capacity(self.capacity)
        self.change_availability(self.availability)
        self.change_type(self.type, self.capabilities)

    def rename(self, name: str) -> None:
        self.name = clean_name(name, field="name", missing=_MISSING_NAME)

    def change_capacity(self, capacity: int) -> None:
        if capacity <= 0:  # F_Valid_1
            raise InvalidValue("Нужна положительная вместимость", field="capacity")
        self.capacity = capacity

    def change_availability(self, availability: Iterable[WeeklyInterval]) -> None:
        ordered = ordered_intervals(availability)
        if not ordered:
            raise InvalidValue("Укажите хотя бы один промежуток доступности", field="availability")
        self.availability = ordered

    def change_type(self, room_type: RoomType, capabilities: Iterable[Capability]) -> None:
        """Тип и пары меняются вместе: пары допустимы не у каждого типа."""
        ordered = ordered_capabilities(capabilities)
        if ordered and not room_type.has_capabilities:
            raise InvalidValue(
                "Дисциплины задаются только специализированным и лабораторным аудиториям",
                field="capabilities",
            )
        self.type = room_type
        self.capabilities = ordered

    def change_capabilities(self, capabilities: Iterable[Capability]) -> None:
        self.change_type(self.type, capabilities)
