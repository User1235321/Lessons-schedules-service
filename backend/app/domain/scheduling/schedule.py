from dataclasses import dataclass
from datetime import datetime, time
from enum import StrEnum
from typing import Literal
from uuid import UUID

from app.domain.shared.errors import InvalidValue
from app.domain.shared.ids import JobId, ProjectId, ScheduleEntryId, ScheduleId
from app.domain.shared.week import Weekday


class ScheduleSource(StrEnum):
    GENERATED = "GENERATED"
    IMPORTED = "IMPORTED"


class LessonFormat(StrEnum):
    ONSITE = "ONSITE"
    REMOTE = "REMOTE"


@dataclass(frozen=True)
class TeacherAssignment:
    display_name: str
    teacher_id: UUID | None = None


@dataclass(frozen=True, kw_only=True)
class ScheduleEntry:
    id: ScheduleEntryId
    week: Literal["ODD", "EVEN"]
    weekday: Weekday
    start_time: time
    end_time: time
    workload_id: UUID | None = None
    subject_name: str | None = None
    participant_label: str | None = None
    lesson_type: Literal["LECTURE", "PRACTICE", "LAB"] | None = None
    lesson_format: LessonFormat | None = None
    room_id: UUID | None = None
    room_name: str | None = None
    teachers: tuple[TeacherAssignment, ...] = ()

    def __post_init__(self) -> None:
        if self.end_time <= self.start_time:
            raise InvalidValue("Окончание должно быть позже начала", field="end_time")
        if self.lesson_format is LessonFormat.REMOTE and (
            self.room_id is not None or self.room_name is not None
        ):
            raise InvalidValue("Для дистанционного занятия аудитория не задаётся", field="room_id")
        teacher_ids = [teacher.teacher_id for teacher in self.teachers if teacher.teacher_id]
        if len(teacher_ids) != len(set(teacher_ids)):
            raise InvalidValue("Преподаватель назначен на занятие повторно", field="teachers")


@dataclass(frozen=True)
class CriterionScore:
    criterion: str
    value: float


@dataclass(frozen=True, kw_only=True)
class Schedule:
    id: ScheduleId
    project_id: ProjectId
    source: ScheduleSource
    entries: tuple[ScheduleEntry, ...]
    created_at: datetime
    job_id: JobId | None = None
    result_index: int | None = None
    criterion_scores: tuple[CriterionScore, ...] | None = None

    def __post_init__(self) -> None:
        if self.source is ScheduleSource.GENERATED:
            if self.job_id is None:
                raise InvalidValue("Сгенерированному расписанию нужно задание", field="job_id")
            if self.result_index is None or self.result_index < 1:
                raise InvalidValue("Номер варианта должен быть положительным", field="result_index")
            if self.criterion_scores is None:
                raise InvalidValue("Нужны оценки критериев", field="criterion_scores")
            if any(entry.workload_id is None for entry in self.entries):
                raise InvalidValue("Занятия должны ссылаться на нагрузку", field="entries")
        elif self.job_id is not None:
            raise InvalidValue("Импортированное расписание не связано с заданием", field="job_id")
