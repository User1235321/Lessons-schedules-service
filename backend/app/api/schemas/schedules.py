from typing import Literal, Self, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.api.schemas.academic import HourMinute
from app.api.schemas.jobs import ScheduleEntryResponse, TeacherAssignmentResponse
from app.application.scheduling.schedules import EntryChanges
from app.domain.scheduling.resources import LessonType
from app.domain.scheduling.schedule import (
    LessonFormat,
    ScheduleConflict,
    ScheduleEntry,
    TeacherAssignment,
)
from app.domain.shared.week import Weekday


class TeacherAssignmentRequest(TeacherAssignmentResponse):
    model_config = ConfigDict(extra="forbid")

    teacher_id: UUID | None = None


class ScheduleEntryPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    week: Literal["ODD", "EVEN"] | None = None
    weekday: Weekday | None = None
    start_time: HourMinute | None = None
    end_time: HourMinute | None = None
    subject_name: str | None = None
    participant_label: str | None = None
    lesson_type: LessonType | None = None
    lesson_format: LessonFormat | None = None
    room_id: UUID | None = None
    room_name: str | None = None
    teachers: list[TeacherAssignmentRequest] | None = None

    @field_validator("week", "weekday", "start_time", "end_time", "teachers")
    @classmethod
    def _reject_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("Поле не может быть null")
        return value

    def to_changes(self) -> EntryChanges:
        # Сериализатор HourMinute предназначен для JSON, а команде нужны объекты time.
        values = {field: getattr(self, field) for field in self.model_fields_set}
        if self.teachers is not None:
            values["teachers"] = tuple(
                TeacherAssignment(item.display_name, item.teacher_id) for item in self.teachers
            )
        return cast(EntryChanges, values)


class ScheduleConflictResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    message: str
    entry_ids: list[UUID]
    details: dict[str, object]


class ScheduleEntryUpdateResponse(BaseModel):
    entry: ScheduleEntryResponse
    conflicts: list[ScheduleConflictResponse]

    @classmethod
    def of(cls, entry: ScheduleEntry, conflicts: list[ScheduleConflict]) -> Self:
        return cls(
            entry=ScheduleEntryResponse.model_validate(entry),
            conflicts=[ScheduleConflictResponse.model_validate(conflict) for conflict in conflicts],
        )


class ScheduleValidationResponse(BaseModel):
    status: Literal["valid", "invalid"]
    conflicts: list[ScheduleConflictResponse]

    @classmethod
    def of(cls, conflicts: list[ScheduleConflict]) -> Self:
        return cls(
            status="invalid" if conflicts else "valid",
            conflicts=[ScheduleConflictResponse.model_validate(conflict) for conflict in conflicts],
        )
