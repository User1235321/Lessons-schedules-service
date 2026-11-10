import re
from datetime import time
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, Field, PlainSerializer, WithJsonSchema

from app.api.schemas.paths import inside
from app.application.academic.groups import SubgroupInGroup
from app.application.academic.teachers import TeacherChanges, TeacherDraft
from app.domain.academic.group import StudentGroup
from app.domain.academic.lesson_type import LessonType
from app.domain.academic.subject import Subject
from app.domain.academic.teacher import Capability, Teacher
from app.domain.shared.ids import SubjectId
from app.domain.shared.week import Week, Weekday, WeeklyInterval

# Форма данных совпадает с test-data/minimal-project.json

_HOUR_MINUTE = re.compile(r"([01]\d|2[0-3]):[0-5]\d")


def _parse_hour_minute(value: object) -> object:
    if isinstance(value, time):  # ответ собирает сам сервер; из JSON приходят только строки
        return value
    if isinstance(value, str) and _HOUR_MINUTE.fullmatch(value):
        return time.fromisoformat(value)
    raise ValueError("Время в формате ЧЧ:ММ, например 09:00")


HourMinute = Annotated[
    time,
    BeforeValidator(_parse_hour_minute),
    PlainSerializer(lambda value: value.strftime("%H:%M"), return_type=str),
    WithJsonSchema(
        {"type": "string", "pattern": "^([01]\\d|2[0-3]):[0-5]\\d$", "example": "09:00"}
    ),
]
# Больше в колонку integer не поместится. Это предел хранения, а не правило предметной области
StudentCount = Annotated[int, Field(le=2**31 - 1)]


class SubjectRequest(BaseModel):
    name: str


class SubjectUpdateRequest(BaseModel):
    name: str | None = None


class SubjectResponse(BaseModel):
    id: UUID
    name: str

    @classmethod
    def of(cls, subject: Subject) -> "SubjectResponse":
        return cls(id=subject.id, name=subject.name)


class CapabilitySchema(BaseModel):
    subject_id: UUID
    lesson_type: LessonType

    def to_domain(self) -> Capability:
        return Capability(SubjectId(self.subject_id), self.lesson_type)

    @classmethod
    def of(cls, capability: Capability) -> "CapabilitySchema":
        return cls(subject_id=capability.subject_id, lesson_type=capability.lesson_type)


class IntervalSchema(BaseModel):
    week: Week
    day: Weekday
    start: HourMinute
    end: HourMinute

    @classmethod
    def of(cls, interval: WeeklyInterval) -> "IntervalSchema":
        return cls(week=interval.week, day=interval.day, start=interval.start, end=interval.end)


def _intervals(block: str, items: list[IntervalSchema]) -> tuple[WeeklyInterval, ...]:
    intervals = []
    for index, item in enumerate(items):
        with inside(f"{block}.{index}"):
            intervals.append(WeeklyInterval(item.week, item.day, item.start, item.end))
    return tuple(intervals)


def _capabilities(items: list[CapabilitySchema]) -> tuple[Capability, ...]:
    return tuple(item.to_domain() for item in items)


class TeacherRequest(BaseModel):
    """Обязательны ФИО, хотя бы одна пара и хотя бы один промежуток доступности (F_Data_4)."""

    full_name: str
    capabilities: list[CapabilitySchema]
    availability: list[IntervalSchema]
    preferences: list[IntervalSchema] = []

    def to_draft(self) -> TeacherDraft:
        return TeacherDraft(
            full_name=self.full_name,
            capabilities=_capabilities(self.capabilities),
            availability=_intervals("availability", self.availability),
            preferences=_intervals("preferences", self.preferences),
        )


class TeacherUpdateRequest(BaseModel):
    """Присланный набор заменяется целиком. Отсутствующий или null — не меняется."""

    full_name: str | None = None
    capabilities: list[CapabilitySchema] | None = None
    availability: list[IntervalSchema] | None = None
    preferences: list[IntervalSchema] | None = None

    def to_changes(self) -> TeacherChanges:
        return TeacherChanges(
            full_name=self.full_name,
            capabilities=None if self.capabilities is None else _capabilities(self.capabilities),
            availability=(
                None if self.availability is None else _intervals("availability", self.availability)
            ),
            preferences=(
                None if self.preferences is None else _intervals("preferences", self.preferences)
            ),
        )


class TeacherResponse(BaseModel):
    id: UUID
    full_name: str
    capabilities: list[CapabilitySchema]
    availability: list[IntervalSchema]
    preferences: list[IntervalSchema]

    @classmethod
    def of(cls, teacher: Teacher) -> "TeacherResponse":
        return cls(
            id=teacher.id,
            full_name=teacher.full_name,
            capabilities=[CapabilitySchema.of(item) for item in teacher.capabilities],
            availability=[IntervalSchema.of(item) for item in teacher.availability],
            preferences=[IntervalSchema.of(item) for item in teacher.preferences],
        )


class GroupRequest(BaseModel):
    """Группа создаётся без подгрупп: они добавляются через /subgroups."""

    name: str
    student_count: StudentCount


class GroupUpdateRequest(BaseModel):
    name: str | None = None
    student_count: StudentCount | None = None


class SubgroupItem(BaseModel):
    """Подгруппа внутри ответа группы, как в test-data."""

    id: UUID
    name: str
    student_count: int


class GroupResponse(BaseModel):
    id: UUID
    name: str
    student_count: int
    subgroups: list[SubgroupItem]

    @classmethod
    def of(cls, group: StudentGroup) -> "GroupResponse":
        return cls(
            id=group.id,
            name=group.name,
            student_count=group.student_count,
            subgroups=[
                SubgroupItem(id=sub.id, name=sub.name, student_count=sub.student_count)
                for sub in group.subgroups
            ],
        )


class SubgroupRequest(BaseModel):
    group_id: UUID
    name: str
    student_count: StudentCount


class SubgroupUpdateRequest(BaseModel):
    """Перенести подгруппу в другую группу нельзя: group_id здесь нет."""

    name: str | None = None
    student_count: StudentCount | None = None


class SubgroupResponse(BaseModel):
    id: UUID
    group_id: UUID
    name: str
    student_count: int

    @classmethod
    def of(cls, placed: SubgroupInGroup) -> "SubgroupResponse":
        return cls(
            id=placed.subgroup.id,
            group_id=placed.group_id,
            name=placed.subgroup.name,
            student_count=placed.subgroup.student_count,
        )
