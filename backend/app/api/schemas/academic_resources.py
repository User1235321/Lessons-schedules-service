from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.academic import HourMinute
from app.application.academic.rooms import RoomChanges, RoomDraft
from app.application.academic.streams import StreamChanges, StreamDraft
from app.application.academic.workloads import WorkloadDraft
from app.domain.academic.capability import Capability
from app.domain.academic.lesson_type import LessonType
from app.domain.academic.room import Room, RoomType
from app.domain.academic.stream import Stream
from app.domain.academic.workload import LessonFormat, TargetType, Workload, WorkloadTarget
from app.domain.shared.errors import InvalidValue
from app.domain.shared.ids import GroupId, SubjectId
from app.domain.shared.week import Week, Weekday, WeeklyInterval


class ResourceSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AvailabilityInterval(ResourceSchema):
    week: Week
    weekday: Weekday
    start_time: HourMinute
    end_time: HourMinute

    def to_domain(self, index: int) -> WeeklyInterval:
        if self.end_time <= self.start_time:
            raise InvalidValue(
                "Окончание должно быть позже начала",
                field=f"availability.{index}.end_time",
            )
        return WeeklyInterval(self.week, self.weekday, self.start_time, self.end_time)

    @classmethod
    def of(cls, interval: WeeklyInterval) -> "AvailabilityInterval":
        return cls(
            week=interval.week,
            weekday=interval.day,
            start_time=interval.start,
            end_time=interval.end,
        )


class RoomCapability(ResourceSchema):
    subject_id: UUID
    lesson_type: LessonType

    def to_domain(self) -> Capability:
        return Capability(SubjectId(self.subject_id), self.lesson_type)

    @classmethod
    def of(cls, capability: Capability) -> "RoomCapability":
        return cls(subject_id=capability.subject_id, lesson_type=capability.lesson_type)


def _availability(items: list[AvailabilityInterval]) -> tuple[WeeklyInterval, ...]:
    return tuple(item.to_domain(index) for index, item in enumerate(items))


def _capabilities(items: list[RoomCapability]) -> tuple[Capability, ...]:
    return tuple(item.to_domain() for item in items)


class RoomRequest(ResourceSchema):
    name: str
    capacity: int
    room_type: RoomType
    availability: list[AvailabilityInterval]
    capabilities: list[RoomCapability] = Field(default_factory=list)

    def to_draft(self) -> RoomDraft:
        return RoomDraft(
            name=self.name,
            capacity=self.capacity,
            room_type=self.room_type,
            availability=_availability(self.availability),
            capabilities=_capabilities(self.capabilities),
        )


class RoomUpdateRequest(ResourceSchema):
    name: str | None = None
    capacity: int | None = None
    room_type: RoomType | None = None
    availability: list[AvailabilityInterval] | None = None
    capabilities: list[RoomCapability] | None = None

    def to_changes(self) -> RoomChanges:
        return RoomChanges(
            name=self.name,
            capacity=self.capacity,
            room_type=self.room_type,
            availability=None if self.availability is None else _availability(self.availability),
            capabilities=None if self.capabilities is None else _capabilities(self.capabilities),
        )


class RoomResponse(ResourceSchema):
    id: UUID
    name: str
    capacity: int
    room_type: RoomType
    availability: list[AvailabilityInterval]
    capabilities: list[RoomCapability]

    @classmethod
    def of(cls, room: Room) -> "RoomResponse":
        return cls(
            id=room.id,
            name=room.name,
            capacity=room.capacity,
            room_type=room.type,
            availability=[AvailabilityInterval.of(item) for item in room.availability],
            capabilities=[RoomCapability.of(item) for item in room.capabilities],
        )


class StreamRequest(ResourceSchema):
    name: str
    group_ids: list[UUID]

    def to_draft(self) -> StreamDraft:
        return StreamDraft(self.name, tuple(GroupId(group_id) for group_id in self.group_ids))


class StreamUpdateRequest(ResourceSchema):
    name: str | None = None
    group_ids: list[UUID] | None = None

    def to_changes(self) -> StreamChanges:
        return StreamChanges(
            name=self.name,
            group_ids=None
            if self.group_ids is None
            else tuple(GroupId(group_id) for group_id in self.group_ids),
        )


class StreamResponse(ResourceSchema):
    id: UUID
    name: str
    group_ids: list[UUID]

    @classmethod
    def of(cls, stream: Stream) -> "StreamResponse":
        return cls(id=stream.id, name=stream.name, group_ids=list(stream.group_ids))


_TARGETS = {
    "group_id": TargetType.GROUP,
    "subgroup_id": TargetType.SUBGROUP,
    "stream_id": TargetType.STREAM,
}


def _target(values: dict[str, UUID | None]) -> WorkloadTarget:
    chosen = [(name, value) for name, value in values.items() if value is not None]
    if len(chosen) != 1:
        raise InvalidValue(
            "Укажите ровно одну группу, подгруппу или поток",
            field="group_id",
        )
    name, value = chosen[0]
    return WorkloadTarget(type=_TARGETS[name], id=value)


class WorkloadRequest(ResourceSchema):
    subject_id: UUID
    lesson_type: LessonType
    lesson_format: LessonFormat
    occurrences_per_cycle: int
    duration_minutes: int | None = None
    required_teacher_count: int
    group_id: UUID | None = None
    subgroup_id: UUID | None = None
    stream_id: UUID | None = None

    def to_draft(self) -> WorkloadDraft:
        return WorkloadDraft(
            target=_target(
                {
                    "group_id": self.group_id,
                    "subgroup_id": self.subgroup_id,
                    "stream_id": self.stream_id,
                }
            ),
            subject_id=SubjectId(self.subject_id),
            lesson_type=self.lesson_type,
            lesson_format=self.lesson_format,
            occurrences_per_cycle=self.occurrences_per_cycle,
            duration_minutes=self.duration_minutes,
            required_teacher_count=self.required_teacher_count,
        )


class WorkloadUpdateRequest(ResourceSchema):
    subject_id: UUID | None = None
    lesson_type: LessonType | None = None
    lesson_format: LessonFormat | None = None
    occurrences_per_cycle: int | None = None
    duration_minutes: int | None = None
    required_teacher_count: int | None = None
    group_id: UUID | None = None
    subgroup_id: UUID | None = None
    stream_id: UUID | None = None

    def to_changes(self) -> dict[str, Any]:
        values = self.model_dump(exclude_unset=True)
        target_values = {name: values.pop(name) for name in _TARGETS if name in values}
        if target_values:
            values["target"] = _target(target_values)
        for name, value in values.items():
            if value is None and name != "duration_minutes":
                raise InvalidValue("Поле не может быть пустым", field=name)
        if "subject_id" in values:
            values["subject_id"] = SubjectId(values["subject_id"])
        if "lesson_format" in values:
            values["format"] = values.pop("lesson_format")
        return values


class WorkloadResponse(ResourceSchema):
    id: UUID
    subject_id: UUID
    lesson_type: LessonType
    lesson_format: LessonFormat
    occurrences_per_cycle: int
    duration_minutes: int | None
    required_teacher_count: int
    group_id: UUID | None
    subgroup_id: UUID | None
    stream_id: UUID | None

    @classmethod
    def of(cls, workload: Workload) -> "WorkloadResponse":
        target = workload.target
        return cls(
            id=workload.id,
            subject_id=workload.subject_id,
            lesson_type=workload.lesson_type,
            lesson_format=workload.format,
            occurrences_per_cycle=workload.occurrences_per_cycle,
            duration_minutes=workload.duration_minutes,
            required_teacher_count=workload.required_teacher_count,
            group_id=target.id if target.type is TargetType.GROUP else None,
            subgroup_id=target.id if target.type is TargetType.SUBGROUP else None,
            stream_id=target.id if target.type is TargetType.STREAM else None,
        )
