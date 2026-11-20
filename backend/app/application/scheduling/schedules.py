from dataclasses import dataclass, replace
from datetime import time
from typing import Literal, TypedDict
from uuid import UUID

from app.application.auth.access import owned_project
from app.application.scheduling.validation_data import load_validation_data
from app.application.shared.uow import UnitOfWork
from app.domain.scheduling.problem import ScheduleProblem
from app.domain.scheduling.resources import LessonType
from app.domain.scheduling.schedule import (
    LessonFormat,
    Schedule,
    ScheduleConflict,
    ScheduleEntry,
    TeacherAssignment,
)
from app.domain.scheduling.validation import validate_schedule
from app.domain.shared.errors import InvalidValue, NotFound
from app.domain.shared.ids import ScheduleEntryId, ScheduleId, UserId
from app.domain.shared.week import Weekday


class EntryChanges(TypedDict, total=False):
    week: Literal["ODD", "EVEN"]
    weekday: Weekday
    start_time: time
    end_time: time
    subject_name: str | None
    participant_label: str | None
    lesson_type: LessonType | None
    lesson_format: LessonFormat | None
    room_id: UUID | None
    room_name: str | None
    teachers: tuple[TeacherAssignment, ...]


def _owned_schedule(
    uow: UnitOfWork, schedule_id: ScheduleId, user_id: UserId, *, for_update: bool = False
) -> Schedule:
    schedule = uow.schedules.get_owned(schedule_id, user_id, for_update=for_update)
    if schedule is None:
        raise NotFound("Расписание не найдено", schedule_id=str(schedule_id))
    return schedule


def _updated_entry(
    entry: ScheduleEntry, changes: EntryChanges, problem: ScheduleProblem
) -> ScheduleEntry:
    changes = changes.copy()
    room_id = changes.get("room_id")
    if room_id is not None:
        room = next((room for room in problem.rooms if room.id == room_id), None)
        if room is None:
            raise InvalidValue("Аудитория не найдена в проекте", field="room_id")
        changes.setdefault("room_name", room.name)
    if changes.get("lesson_format") is LessonFormat.REMOTE:
        # Старое назначение очищается, а явно переданные поля проходят проверку домена.
        changes.setdefault("room_id", None)
        changes.setdefault("room_name", None)
    if "teachers" in changes:
        names = {teacher.id: teacher.full_name for teacher in problem.teachers}
        assignments: list[TeacherAssignment] = []
        for index, assignment in enumerate(changes["teachers"]):
            if assignment.teacher_id is None:
                if not assignment.display_name.strip():
                    raise InvalidValue(
                        "Укажите имя преподавателя", field=f"teachers.{index}.display_name"
                    )
                assignments.append(assignment)
                continue
            if assignment.teacher_id not in names:
                raise InvalidValue(
                    "Преподаватель не найден в проекте", field=f"teachers.{index}.teacher_id"
                )
            assignments.append(
                TeacherAssignment(names[assignment.teacher_id], assignment.teacher_id)
            )
        changes["teachers"] = tuple(assignments)
    return replace(entry, **changes)


@dataclass(frozen=True)
class GetSchedule:
    uow: UnitOfWork

    def execute(self, user_id: UserId, schedule_id: ScheduleId) -> Schedule:
        with self.uow:
            return _owned_schedule(self.uow, schedule_id, user_id)


@dataclass(frozen=True)
class UpdateScheduleEntry:
    uow: UnitOfWork

    def execute(
        self,
        user_id: UserId,
        schedule_id: ScheduleId,
        entry_id: ScheduleEntryId,
        changes: EntryChanges,
    ) -> tuple[ScheduleEntry, list[ScheduleConflict]]:
        with self.uow:
            schedule = _owned_schedule(self.uow, schedule_id, user_id, for_update=True)
            entry = next((entry for entry in schedule.entries if entry.id == entry_id), None)
            if entry is None:
                raise NotFound("Занятие не найдено", entry_id=str(entry_id))
            project = owned_project(self.uow, schedule.project_id, user_id)
            problem = load_validation_data(self.uow, project)
            edited = _updated_entry(entry, changes, problem)
            updated = replace(
                schedule,
                entries=tuple(edited if item.id == entry.id else item for item in schedule.entries),
            )
            conflicts = validate_schedule(updated, problem)
            if edited != entry:
                self.uow.schedules.save(updated)
                self.uow.commit()
            return edited, conflicts


@dataclass(frozen=True)
class ValidateSchedule:
    uow: UnitOfWork

    def execute(self, user_id: UserId, schedule_id: ScheduleId) -> list[ScheduleConflict]:
        with self.uow:
            schedule = _owned_schedule(self.uow, schedule_id, user_id)
            project = owned_project(self.uow, schedule.project_id, user_id)
            problem = load_validation_data(self.uow, project)
        return validate_schedule(schedule, problem)
