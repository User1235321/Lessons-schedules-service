from dataclasses import dataclass
from datetime import time
from enum import StrEnum
from typing import Literal
from uuid import UUID

from app.domain.shared.errors import InvalidValue
from app.domain.shared.week import Weekday

CycleWeek = Literal["ODD", "EVEN", "ANY"]
LessonType = Literal["LECTURE", "PRACTICE", "LAB"]


@dataclass(frozen=True)
class WeeklyWindow:
    week: CycleWeek
    day: Weekday
    start: time
    end: time

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise InvalidValue("Окончание должно быть позже начала", field="end")


@dataclass(frozen=True)
class SubjectSnapshot:
    id: UUID
    name: str


@dataclass(frozen=True)
class TeachingCapability:
    subject_id: UUID
    lesson_type: LessonType


@dataclass(frozen=True)
class TeacherSnapshot:
    id: UUID
    full_name: str
    capabilities: tuple[TeachingCapability, ...]
    availability: tuple[WeeklyWindow, ...]
    preferences: tuple[WeeklyWindow, ...] = ()

    def __post_init__(self) -> None:
        if not self.capabilities:
            raise InvalidValue("Укажите возможности преподавателя", field="capabilities")
        if not self.availability:
            raise InvalidValue("Укажите доступность преподавателя", field="availability")


class RoomType(StrEnum):
    LECTURE = "LECTURE"
    PRACTICE_UNIVERSAL = "PRACTICE_UNIVERSAL"
    PRACTICE_SPECIALIZED = "PRACTICE_SPECIALIZED"
    LABORATORY = "LABORATORY"


@dataclass(frozen=True)
class RoomSnapshot:
    id: UUID
    name: str
    capacity: int
    room_type: RoomType
    availability: tuple[WeeklyWindow, ...]
    capabilities: tuple[TeachingCapability, ...] = ()

    def __post_init__(self) -> None:
        if self.capacity <= 0:
            raise InvalidValue("Вместимость должна быть положительной", field="capacity")


@dataclass(frozen=True)
class GroupSnapshot:
    id: UUID
    name: str
    student_count: int
    availability: tuple[WeeklyWindow, ...] = ()

    def __post_init__(self) -> None:
        if self.student_count <= 0:
            raise InvalidValue("Число студентов должно быть положительным", field="student_count")


@dataclass(frozen=True)
class SubgroupSnapshot:
    id: UUID
    group_id: UUID
    name: str
    student_count: int
    availability: tuple[WeeklyWindow, ...] = ()

    def __post_init__(self) -> None:
        if self.student_count <= 0:
            raise InvalidValue("Число студентов должно быть положительным", field="student_count")


@dataclass(frozen=True)
class StreamSnapshot:
    id: UUID
    name: str
    group_ids: tuple[UUID, ...]
