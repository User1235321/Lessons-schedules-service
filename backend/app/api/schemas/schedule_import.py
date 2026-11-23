import csv
import json
from datetime import datetime
from io import BytesIO, StringIO
from typing import Literal, Self
from uuid import UUID, uuid4
from zipfile import BadZipFile, ZipFile

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from python_calamine import CalamineError, load_workbook

from app.api.schemas.academic import HourMinute
from app.api.schemas.schedules import ScheduleValidationResponse, TeacherAssignmentRequest
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

    def to_entry(self) -> ScheduleEntry:
        return ScheduleEntry(
            id=ScheduleEntryId(uuid4()),
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


class _CsvRowError(ValueError):
    def __init__(self, row: int, message: str) -> None:
        super().__init__(message)
        self.row = row


def _rows(content: bytes, extension: str):
    if extension == "json":
        data = json.loads(content.decode("utf-8-sig"))
        rows = data.get("entries") if isinstance(data, dict) else data
        if not isinstance(rows, list):
            raise ValueError("Ожидается список занятий или объект с полем entries")
        yield from enumerate(rows, 1)
        return
    if extension == "csv":
        data = content.decode("utf-8-sig")
        header = data.partition("\n")[0]
        reader = csv.reader(
            StringIO(data, newline=""), delimiter=";" if ";" in header else ",", strict=True
        )
        index = 1
        try:
            headers = next(reader, [])
            while True:
                index = reader.line_num + 1
                row = next(reader, None)
                if row is None:
                    break
                if len(row) > len(headers):
                    yield index, ImportIssue(index, None, "Лишние значения в строке")
                elif row:
                    yield index, dict(zip(headers, row))
        except csv.Error as error:
            raise _CsvRowError(index, str(error)) from error
        return
    with ZipFile(BytesIO(content)) as archive:
        if sum(item.file_size for item in archive.infolist()) > 128 * 1024 * 1024:
            raise ValueError("Распакованная таблица слишком велика")
    with load_workbook(BytesIO(content)) as workbook:
        if not workbook.sheet_names:
            raise ValueError("В файле отсутствует лист с занятиями")
        sheet = workbook.get_sheet_by_index(0)
        if sheet.height * sheet.width > 1_000_000:
            raise ValueError("Слишком большая область данных таблицы")
        rows = iter(sheet.iter_rows())
        headers = next(rows, [])
        for index, row in enumerate(rows, 2):
            if any(value not in (None, "") for value in row):
                yield index, dict(zip(headers, row))


def parse_schedule(
    content: bytes, extension: str, mapping: dict[str, str]
) -> tuple[list[ScheduleEntry], list[ImportIssue]]:
    entries = []
    issues = []
    try:
        for index, raw in _rows(content, extension):
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
                entries.append(ImportedEntry.model_validate(values).to_entry())
            except ValidationError as error:
                issues.extend(
                    ImportIssue(index, ".".join(map(str, item["loc"])), item["msg"])
                    for item in error.errors()
                )
            except InvalidValue as error:
                issues.append(ImportIssue(index, error.field, error.message))
            except json.JSONDecodeError:
                issues.append(
                    ImportIssue(index, "teachers", "Ожидается JSON-массив преподавателей")
                )
    except _CsvRowError as error:
        issues.append(ImportIssue(error.row, "file", str(error)))
    except (ValueError, CalamineError, BadZipFile, RecursionError) as error:
        issues.append(ImportIssue(None, "file", str(error)))
    if not entries and not issues:
        issues.append(ImportIssue(None, "entries", "В файле нет занятий"))
    return entries, issues


class UploadedFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    category: Literal["UPLOAD"]
    original_name: str
    file_format: str
    size_bytes: int
    created_at: datetime
    schedule_id: UUID | None
    job_id: UUID | None


class ScheduleImportResponse(BaseModel):
    file: UploadedFileResponse
    imported_count: int
    schedule_ids: list[UUID]
    errors: list[ImportIssue]
    validation: ScheduleValidationResponse | None

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
