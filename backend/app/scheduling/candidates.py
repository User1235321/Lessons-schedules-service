from collections.abc import Iterator
from dataclasses import dataclass
from datetime import time
from itertools import combinations
from typing import Literal
from uuid import UUID

from app.domain.projects.settings import DurationModeKind, ProjectSettings, TimeModeKind
from app.domain.scheduling.constraint_validation import covered_by
from app.domain.scheduling.problem import ScheduleProblem, WorkloadSnapshot, WorkloadTargetKind
from app.domain.scheduling.resources import (
    GroupSnapshot,
    RoomSnapshot,
    RoomType,
    SubgroupSnapshot,
    TeacherSnapshot,
    WeeklyWindow,
)
from app.domain.scheduling.schedule import LessonFormat, ScheduleEntry, TeacherAssignment
from app.domain.scheduling.solver import SolverControl, SolverDiagnostic
from app.domain.shared.ids import ScheduleEntryId
from app.domain.shared.week import Weekday

_ROOM_TYPES = {
    "LECTURE": (RoomType.LECTURE,),
    "PRACTICE": (RoomType.PRACTICE_UNIVERSAL, RoomType.PRACTICE_SPECIALIZED),
    "LAB": (RoomType.LABORATORY,),
}
_WEEK_ORDER = {"ODD": 0, "EVEN": 1}
_DAY_ORDER = {day: index for index, day in enumerate(Weekday)}
_PROBE_ID = ScheduleEntryId(UUID(int=0))


class SearchCancelled(Exception):
    pass


def check_cancelled(control: SolverControl) -> None:
    if control.is_cancel_requested():
        raise SearchCancelled


@dataclass(frozen=True)
class Participants:
    group_ids: tuple[UUID, ...]
    subgroup_id: UUID | None
    student_count: int
    label: str
    availability: tuple[tuple[WeeklyWindow, ...], ...]


@dataclass(frozen=True)
class LessonRequirements:
    workload: WorkloadSnapshot
    subject_name: str
    participants: Participants
    teachers: tuple[TeacherSnapshot, ...]
    rooms: tuple[RoomSnapshot, ...]
    duration_minutes: int


@dataclass(frozen=True)
class Placement:
    requirements: LessonRequirements
    week: Literal["ODD", "EVEN"]
    weekday: Weekday
    start_time: time
    end_time: time
    teachers: tuple[TeacherSnapshot, ...]
    room: RoomSnapshot | None

    @property
    def order_key(self) -> tuple[object, ...]:
        return (
            _WEEK_ORDER[self.week],
            _DAY_ORDER[self.weekday],
            self.start_time,
            tuple(teacher.id for teacher in self.teachers),
            self.room.id if self.room else UUID(int=0),
        )

    def to_entry(self, entry_id: ScheduleEntryId) -> ScheduleEntry:
        workload = self.requirements.workload
        return ScheduleEntry(
            id=entry_id,
            week=self.week,
            weekday=self.weekday,
            start_time=self.start_time,
            end_time=self.end_time,
            workload_id=workload.id,
            subject_name=self.requirements.subject_name,
            participant_label=self.requirements.participants.label,
            lesson_type=workload.lesson_type,
            lesson_format=workload.lesson_format,
            room_id=self.room.id if self.room else None,
            room_name=self.room.name if self.room else None,
            teachers=tuple(
                TeacherAssignment(teacher.full_name, teacher.id) for teacher in self.teachers
            ),
        )


def _participants(
    workload: WorkloadSnapshot,
    groups: dict[UUID, GroupSnapshot],
    subgroups: dict[UUID, SubgroupSnapshot],
    streams: dict[UUID, tuple[str, tuple[UUID, ...]]],
) -> Participants | None:
    target = workload.target.resource_id
    if workload.target.kind is WorkloadTargetKind.GROUP:
        group = groups.get(target)
        if group is None:
            return None
        return Participants(
            (group.id,), None, group.student_count, group.name, (group.availability,)
        )
    if workload.target.kind is WorkloadTargetKind.SUBGROUP:
        subgroup = subgroups.get(target)
        if subgroup is None or subgroup.group_id not in groups:
            return None
        group = groups[subgroup.group_id]
        return Participants(
            (group.id,),
            subgroup.id,
            subgroup.student_count,
            f"{group.name} / {subgroup.name}",
            (group.availability, subgroup.availability),
        )
    stream = streams.get(target)
    if stream is None:
        return None
    label, members = stream
    group_ids = tuple(dict.fromkeys(members))
    if not group_ids or any(group_id not in groups for group_id in group_ids):
        return None
    return Participants(
        group_ids,
        None,
        sum(groups[group_id].student_count for group_id in group_ids),
        label,
        tuple(groups[group_id].availability for group_id in group_ids),
    )


def _qualified_teachers(
    problem: ScheduleProblem, workload: WorkloadSnapshot
) -> tuple[TeacherSnapshot, ...]:
    return tuple(
        sorted(
            (
                teacher
                for teacher in problem.teachers
                if any(
                    capability.subject_id == workload.subject_id
                    and capability.lesson_type == workload.lesson_type
                    for capability in teacher.capabilities
                )
            ),
            key=lambda teacher: teacher.id,
        )
    )


def _suitable_rooms(
    problem: ScheduleProblem, workload: WorkloadSnapshot, students: int
) -> tuple[RoomSnapshot, ...]:
    if workload.lesson_format is LessonFormat.REMOTE:
        return ()
    return tuple(
        sorted(
            (
                room
                for room in problem.rooms
                if room.room_type in _ROOM_TYPES[workload.lesson_type]
                and room.capacity >= students
                and (
                    not room.capabilities
                    or any(
                        capability.subject_id == workload.subject_id
                        and capability.lesson_type == workload.lesson_type
                        for capability in room.capabilities
                    )
                )
            ),
            key=lambda room: room.id,
        )
    )


def prepare_requirements(
    problem: ScheduleProblem, control: SolverControl
) -> tuple[tuple[LessonRequirements, ...], tuple[SolverDiagnostic, ...]]:
    subjects = {subject.id: subject.name for subject in problem.subjects}
    groups = {group.id: group for group in problem.groups}
    subgroups = {subgroup.id: subgroup for subgroup in problem.subgroups}
    streams = {stream.id: (stream.name, stream.group_ids) for stream in problem.streams}
    requirements: list[LessonRequirements] = []
    diagnostics: list[SolverDiagnostic] = []

    for workload in sorted(problem.workloads, key=lambda item: item.id):
        check_cancelled(control)
        participants = _participants(workload, groups, subgroups, streams)
        teachers = _qualified_teachers(problem, workload)
        duration = (
            problem.settings.duration_mode.duration_minutes
            if problem.settings.duration_mode.kind is DurationModeKind.UNIFORM
            else workload.duration_minutes
        )
        if workload.subject_id not in subjects:
            reason = "Для учебной нагрузки не найдена дисциплина"
        elif participants is None:
            reason = "Для учебной нагрузки не найдены участники"
        elif duration is None or duration <= 0 or duration >= 1440:
            reason = "Для учебной нагрузки не задана допустимая длительность"
        elif len(teachers) < workload.required_teacher_count:
            reason = "Недостаточно квалифицированных преподавателей"
        else:
            rooms = _suitable_rooms(problem, workload, participants.student_count)
            reason = (
                "Нет подходящих аудиторий для очного занятия"
                if workload.lesson_format is LessonFormat.ONSITE and not rooms
                else None
            )
        if reason is not None:
            diagnostics.append(SolverDiagnostic(reason, (workload.id,)))
            continue
        requirements.append(
            LessonRequirements(
                workload,
                subjects[workload.subject_id],
                participants,
                teachers,
                rooms,
                duration,
            )
        )
    return tuple(requirements), tuple(diagnostics)


def _time_slots(
    settings: ProjectSettings, duration: int
) -> Iterator[tuple[Literal["ODD", "EVEN"], Weekday, time, time]]:
    step = (
        60
        if settings.time_mode.kind is TimeModeKind.HOUR_START
        else settings.time_mode.step_minutes
    )
    for week, days in (
        ("ODD", settings.cycle.odd_week_days),
        ("EVEN", settings.cycle.even_week_days),
    ):
        for day in days:
            for minutes in range(0, 1440 - duration, step):
                end = minutes + duration
                yield (
                    week,
                    day,
                    time(minutes // 60, minutes % 60),
                    time(end // 60, end % 60),
                )


def iter_placements(
    requirements: LessonRequirements, settings: ProjectSettings, control: SolverControl
) -> Iterator[Placement]:
    for week, day, start, end in _time_slots(settings, requirements.duration_minutes):
        check_cancelled(control)
        probe = ScheduleEntry(
            id=_PROBE_ID,
            week=week,
            weekday=day,
            start_time=start,
            end_time=end,
        )
        if any(
            windows and not covered_by(windows, probe)
            for windows in requirements.participants.availability
        ):
            continue
        teachers = tuple(
            teacher
            for teacher in requirements.teachers
            if covered_by(teacher.availability, probe)
        )
        if len(teachers) < requirements.workload.required_teacher_count:
            continue
        rooms: tuple[RoomSnapshot | None, ...] = (
            tuple(
                room
                for room in requirements.rooms
                if covered_by(room.availability, probe)
            )
            if requirements.workload.lesson_format is LessonFormat.ONSITE
            else (None,)
        )
        for assigned_teachers in combinations(
            teachers, requirements.workload.required_teacher_count
        ):
            for room in rooms:
                check_cancelled(control)
                yield Placement(
                    requirements, week, day, start, end, assigned_teachers, room
                )
