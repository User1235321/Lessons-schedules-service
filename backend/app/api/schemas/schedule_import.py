import json
from typing import Literal, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ValidationError

from app.api.schemas.academic import HourMinute
from app.api.schemas.files import StoredFileResponse
from app.api.schemas.schedules import ScheduleValidationResponse, TeacherAssignmentRequest
from app.api.schemas.table_rows import import_rows
from app.api.schemas.transfer_values import check_storage_values
from app.application.import_export.schedules import ImportIssue, ImportResult
from app.domain.scheduling.resources import LessonType
from app.domain.scheduling.schedule import LessonFormat, ScheduleEntry, TeacherAssignment
from app.domain.shared.errors import InvalidValue
from app.domain.shared.ids import ScheduleEntryId
from app.domain.shared.week import Weekday


class ImportedEntry(BaseModel):
    week: Literal["ODD", "EVEN"]
    weekday: Weekday
    start_time: HourMinute
    end_time: HourMinute
    workload_id: UUID | None = None
    subject_name: str | None = None
    participant_label: str | None = None
    lesson_type: LessonType | None = None
    lesson_format: LessonFormat | None = None
    room_id: UUID | None = None
    room_name: str | None = None
    teachers: list[TeacherAssignmentRequest] = Field(default_factory=list)

    def to_entry(self, entry_id: ScheduleEntryId | None = None) -> ScheduleEntry:
        return ScheduleEntry(
            id=entry_id if entry_id is not None else ScheduleEntryId(uuid4()),
            week=self.week,
            weekday=self.weekday,
            start_time=self.start_time,
            end_time=self.end_time,
            workload_id=self.workload_id,
            subject_name=self.subject_name,
            participant_label=self.participant_label,
            lesson_type=self.lesson_type,
            lesson_format=self.lesson_format,
            room_id=self.room_id,
            room_name=self.room_name,
            teachers=tuple(TeacherAssignment(t.display_name, t.teacher_id) for t in self.teachers),
        )


def parse_schedule(
    content: bytes, extension: str, mapping: dict[str, str]
) -> tuple[list[ScheduleEntry], list[ImportIssue]]:
    entries = []
    issues = []
    for index, raw in import_rows(content, extension):
        if isinstance(raw, ImportIssue):
            issues.append(raw)
            continue
        if not isinstance(raw, dict):
            issues.append(ImportIssue(index, None, "Ожидается строка с полями занятия"))
            continue
        values = {mapping.get(k, k): v for k, v in raw.items() if v not in ("", None)}
        try:
            if isinstance(values.get("teachers"), str):
                values["teachers"] = json.loads(values["teachers"])
            entry = ImportedEntry.model_validate(values)
            check_storage_values(entry.model_dump())
            entries.append(entry.to_entry())
        except ValidationError as error:
            issues.extend(
                ImportIssue(index, ".".join(map(str, item["loc"])), item["msg"])
                for item in error.errors()
            )
        except InvalidValue as error:
            issues.append(ImportIssue(index, error.field, error.message))
        except json.JSONDecodeError:
            issues.append(ImportIssue(index, "teachers", "Ожидается JSON-массив преподавателей"))
    if not entries and not issues:
        issues.append(ImportIssue(None, "entries", "В файле нет занятий"))
    return entries, issues


class UploadedFileResponse(StoredFileResponse):
    category: Literal["UPLOAD"]


class ScheduleImportResponse(BaseModel):
    file: UploadedFileResponse
    imported_count: int
    schedule_ids: list[UUID]
    errors: list[ImportIssue]
    validation: ScheduleValidationResponse | None = None

    @classmethod
    def of(cls, result: ImportResult) -> Self:
        return cls(
            file=UploadedFileResponse.model_validate(result.file),
            imported_count=result.imported_count,
            errors=result.errors,
            schedule_ids=[result.file.schedule_id] if result.file.schedule_id else [],
            validation=ScheduleValidationResponse.of(result.conflicts)
            if result.file.schedule_id
            else None,
        )
