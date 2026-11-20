from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from uuid import UUID

from app.domain.projects.settings import DurationModeKind, ProjectSettings, TimeModeKind
from app.domain.scheduling.constraint_validation import constraint_conflicts, covered_by, seconds
from app.domain.scheduling.constraints import (
    ConstraintScope,
    ConstraintScopeKind,
    MinimumGapParameters,
    RelatedWorkloadParameters,
)
from app.domain.scheduling.problem import ScheduleProblem, WorkloadSnapshot, WorkloadTargetKind
from app.domain.scheduling.resources import (
    GroupSnapshot,
    RoomSnapshot,
    RoomType,
    SubgroupSnapshot,
    TeacherSnapshot,
)
from app.domain.scheduling.schedule import (
    LessonFormat,
    Schedule,
    ScheduleConflict,
    ScheduleEntry,
    ScheduleSource,
)
from app.domain.shared.week import Weekday

_ROOM_TYPES = {
    "LECTURE": (RoomType.LECTURE,),
    "PRACTICE": (RoomType.PRACTICE_UNIVERSAL, RoomType.PRACTICE_SPECIALIZED),
    "LAB": (RoomType.LABORATORY,),
}


@dataclass(frozen=True)
class _Placement:
    entry: ScheduleEntry
    workload: WorkloadSnapshot | None
    groups: tuple[UUID, ...]
    subgroup: UUID | None
    students: int | None

    @property
    def lesson_type(self) -> str | None:
        return self.entry.lesson_type or (self.workload.lesson_type if self.workload else None)

    @property
    def lesson_format(self) -> LessonFormat | None:
        return self.entry.lesson_format or (self.workload.lesson_format if self.workload else None)

    def matches(self, scope: ConstraintScope, subgroups: dict[UUID, SubgroupSnapshot]) -> bool:
        if scope.kind is ConstraintScopeKind.PROJECT:
            return True
        if scope.kind is ConstraintScopeKind.WORKLOAD:
            return scope.resource_id == self.entry.workload_id
        if scope.kind is ConstraintScopeKind.GROUP:
            return scope.resource_id in self.groups
        if scope.kind is ConstraintScopeKind.SUBGROUP:
            subgroup = subgroups.get(scope.resource_id)
            return scope.resource_id == self.subgroup or (
                self.subgroup is None and subgroup is not None and subgroup.group_id in self.groups
            )
        return bool(
            self.workload
            and self.workload.target.kind is WorkloadTargetKind.STREAM
            and self.workload.target.resource_id == scope.resource_id
        )


def _conflict(
    code: str, message: str, *entries: ScheduleEntry, **details: object
) -> ScheduleConflict:
    return ScheduleConflict(code, message, tuple(sorted({entry.id for entry in entries})), details)


def _placements(schedule: Schedule, problem: ScheduleProblem) -> Iterator[_Placement]:
    workloads = {workload.id: workload for workload in problem.workloads}
    groups = {group.id: group for group in problem.groups}
    subgroups = {subgroup.id: subgroup for subgroup in problem.subgroups}
    streams = {stream.id: stream for stream in problem.streams}
    for entry in schedule.entries:
        workload = workloads.get(entry.workload_id)
        if workload is None:
            yield _Placement(entry, None, (), None, None)
            continue
        kind, target = workload.target.kind, workload.target.resource_id
        if kind is WorkloadTargetKind.SUBGROUP:
            subgroup = subgroups.get(target)
            yield _Placement(
                entry,
                workload,
                (subgroup.group_id,) if subgroup else (),
                target,
                subgroup.student_count if subgroup else None,
            )
            continue
        group_ids = (
            (target,)
            if kind is WorkloadTargetKind.GROUP
            else (tuple(dict.fromkeys(streams[target].group_ids)) if target in streams else ())
        )
        students = (
            sum(groups[group_id].student_count for group_id in group_ids)
            if group_ids and all(group_id in groups for group_id in group_ids)
            else None
        )
        yield _Placement(entry, workload, group_ids, None, students)


def _time_conflicts(placement: _Placement, settings: ProjectSettings) -> Iterator[ScheduleConflict]:
    entry = placement.entry
    days = settings.cycle.odd_week_days if entry.week == "ODD" else settings.cycle.even_week_days
    if entry.weekday not in days:
        yield _conflict("NON_STUDY_DAY", "Занятие назначено на неучебный день", entry)
    step = (
        60
        if settings.time_mode.kind is TimeModeKind.HOUR_START
        else settings.time_mode.step_minutes
    )
    if step is not None and seconds(entry.start_time) % (step * 60):
        yield _conflict("START_TIME_STEP", "Начало занятия не соответствует шагу проекта", entry)
    if settings.duration_mode.kind is DurationModeKind.UNIFORM:
        duration = settings.duration_mode.duration_minutes
    else:
        duration = placement.workload.duration_minutes if placement.workload else None
    if (
        duration is not None
        and seconds(entry.end_time) - seconds(entry.start_time) != duration * 60
    ):
        yield _conflict(
            "LESSON_DURATION",
            "Длительность занятия не соответствует заданной",
            entry,
            expected_minutes=duration,
        )


def _teacher_conflicts(
    placement: _Placement,
    teachers: dict[UUID, TeacherSnapshot],
    generated: bool,
) -> Iterator[ScheduleConflict]:
    entry = placement.entry
    required = (
        1
        if placement.lesson_type in ("LECTURE", "PRACTICE")
        else (
            placement.workload.required_teacher_count
            if placement.lesson_type == "LAB" and placement.workload
            else None
        )
    )
    if required is not None and (generated or entry.teachers) and len(entry.teachers) != required:
        yield _conflict(
            "TEACHER_COUNT",
            "Количество преподавателей не соответствует типу занятия или нагрузке",
            entry,
            expected=required,
            actual=len(entry.teachers),
        )
    for assignment in entry.teachers:
        teacher = teachers.get(assignment.teacher_id)
        if teacher is None:
            if generated:
                yield _conflict(
                    "TEACHER_NOT_FOUND",
                    "Преподаватель занятия отсутствует в справочнике проекта",
                    entry,
                    teacher_id=str(assignment.teacher_id) if assignment.teacher_id else None,
                )
            continue
        if not covered_by(teacher.availability, entry):
            yield _conflict(
                "TEACHER_UNAVAILABLE",
                "Преподаватель недоступен в это время",
                entry,
                teacher_id=str(teacher.id),
            )
        if (
            placement.workload
            and placement.lesson_type
            and not any(
                capability.subject_id == placement.workload.subject_id
                and capability.lesson_type == placement.lesson_type
                for capability in teacher.capabilities
            )
        ):
            yield _conflict(
                "TEACHER_NOT_QUALIFIED",
                "Преподаватель не ведёт эту дисциплину и тип занятия",
                entry,
                teacher_id=str(teacher.id),
                subject_id=str(placement.workload.subject_id),
            )


def _room_conflicts(
    placement: _Placement,
    rooms: dict[UUID, RoomSnapshot],
    generated: bool,
) -> Iterator[ScheduleConflict]:
    entry = placement.entry
    if placement.lesson_format is LessonFormat.REMOTE:
        if entry.room_id is not None or entry.room_name is not None:
            yield _conflict("REMOTE_ROOM", "Дистанционное занятие не занимает аудиторию", entry)
        return
    room = rooms.get(entry.room_id)
    if room is None:
        if generated and placement.lesson_format is LessonFormat.ONSITE:
            yield _conflict("ROOM_REQUIRED", "Очному занятию нужна аудитория из справочника", entry)
        return
    if not covered_by(room.availability, entry):
        yield _conflict(
            "ROOM_UNAVAILABLE", "Аудитория недоступна в это время", entry, room_id=str(room.id)
        )
    if placement.lesson_type and room.room_type not in _ROOM_TYPES[placement.lesson_type]:
        yield _conflict(
            "ROOM_TYPE", "Тип аудитории не подходит для занятия", entry, room_id=str(room.id)
        )
    if (
        room.capabilities
        and placement.workload
        and placement.lesson_type
        and not any(
            capability.subject_id == placement.workload.subject_id
            and capability.lesson_type == placement.lesson_type
            for capability in room.capabilities
        )
    ):
        yield _conflict(
            "ROOM_SPECIALIZATION",
            "Аудитория не предназначена для этой дисциплины и типа занятия",
            entry,
            room_id=str(room.id),
            subject_id=str(placement.workload.subject_id),
        )
    if placement.students is not None and room.capacity < placement.students:
        yield _conflict(
            "ROOM_CAPACITY_CONFLICT",
            "В аудитории недостаточно мест",
            entry,
            room_id=str(room.id),
            capacity=room.capacity,
            students=placement.students,
        )


def _group_conflicts(
    placement: _Placement,
    groups: dict[UUID, GroupSnapshot],
    subgroup: SubgroupSnapshot | None,
) -> Iterator[ScheduleConflict]:
    entry = placement.entry
    participants: list[GroupSnapshot | SubgroupSnapshot] = [
        groups[group_id] for group_id in placement.groups if group_id in groups
    ]
    if subgroup is not None:
        participants.append(subgroup)
    for participant in participants:
        if participant.availability and not covered_by(participant.availability, entry):
            yield _conflict(
                "GROUP_UNAVAILABLE",
                "Группа или подгруппа недоступна в это время",
                entry,
                participant_id=str(participant.id),
            )


_OVERLAP_REASONS = {
    "GROUP_OVERLAP": "Занятия групп или подгрупп пересекаются",
    "TEACHER_OVERLAP": "У преподавателя одновременно проходят два занятия",
    "ROOM_OVERLAP": "В аудитории одновременно проходят два занятия",
}


def _overlap_conflicts(placements: list[_Placement]) -> Iterator[ScheduleConflict]:
    by_resource: dict[tuple[str, UUID, str, Weekday], list[_Placement]] = defaultdict(list)
    for placement in placements:
        entry = placement.entry
        resources = [("GROUP_OVERLAP", group_id) for group_id in placement.groups]
        resources.extend(
            ("TEACHER_OVERLAP", teacher.teacher_id)
            for teacher in entry.teachers
            if teacher.teacher_id is not None
        )
        if entry.room_id is not None and placement.lesson_format is not LessonFormat.REMOTE:
            resources.append(("ROOM_OVERLAP", entry.room_id))
        for code, resource_id in resources:
            by_resource[code, resource_id, entry.week, entry.weekday].append(placement)
    for (code, resource_id, _, _), items in by_resource.items():
        # При разных подгруппах общий родитель сам по себе не создаёт конфликт.
        items.sort(key=lambda item: item.entry.start_time)
        for index, left in enumerate(items):
            for other in range(index + 1, len(items)):
                right = items[other]
                if right.entry.start_time >= left.entry.end_time:
                    break
                if (
                    code == "GROUP_OVERLAP"
                    and left.subgroup is not None
                    and right.subgroup is not None
                    and left.subgroup != right.subgroup
                ):
                    continue
                yield _conflict(
                    code,
                    _OVERLAP_REASONS[code],
                    left.entry,
                    right.entry,
                    resource_id=str(resource_id),
                )


def _extra_conflicts(
    problem: ScheduleProblem,
    placements: list[_Placement],
    by_workload: dict[UUID, list[ScheduleEntry]],
    complete: bool,
) -> Iterator[ScheduleConflict]:
    subgroups = {subgroup.id: subgroup for subgroup in problem.subgroups}
    for constraint in problem.constraints:
        scope = constraint.scope
        if scope.kind is ConstraintScopeKind.WORKLOAD:
            selected = by_workload.get(scope.resource_id, [])
        else:
            selected = [item.entry for item in placements if item.matches(scope, subgroups)]
        params = constraint.parameters
        related = (
            by_workload.get(params.workload_id, [])
            if isinstance(params, (RelatedWorkloadParameters, MinimumGapParameters))
            else []
        )
        yield from constraint_conflicts(constraint, selected, related, complete)


def validate_schedule(schedule: Schedule, problem: ScheduleProblem) -> list[ScheduleConflict]:
    placements = list(_placements(schedule, problem))
    generated = schedule.source is ScheduleSource.GENERATED
    complete = generated or bool(placements and all(item.workload for item in placements))
    teachers = {teacher.id: teacher for teacher in problem.teachers}
    rooms = {room.id: room for room in problem.rooms}
    groups = {group.id: group for group in problem.groups}
    subgroups = {subgroup.id: subgroup for subgroup in problem.subgroups}
    by_workload: dict[UUID, list[ScheduleEntry]] = defaultdict(list)
    conflicts: list[ScheduleConflict] = []
    for placement in placements:
        entry = placement.entry
        if placement.workload:
            by_workload[placement.workload.id].append(entry)
        elif generated:
            conflicts.append(
                _conflict(
                    "WORKLOAD_NOT_FOUND",
                    "Учебная нагрузка занятия отсутствует в проекте",
                    entry,
                    workload_id=str(entry.workload_id),
                )
            )
        conflicts.extend(_time_conflicts(placement, problem.settings))
        conflicts.extend(_teacher_conflicts(placement, teachers, generated))
        conflicts.extend(_room_conflicts(placement, rooms, generated))
        conflicts.extend(_group_conflicts(placement, groups, subgroups.get(placement.subgroup)))
    for workload in problem.workloads:
        entries = by_workload[workload.id]
        expected, actual = workload.occurrences_per_cycle, len(entries)
        if actual > expected or (complete and actual < expected):
            conflicts.append(
                _conflict(
                    "WORKLOAD_OCCURRENCES",
                    "Количество проведений не соответствует нагрузке",
                    *entries,
                    workload_id=str(workload.id),
                    expected=expected,
                    actual=actual,
                )
            )
    conflicts.extend(_overlap_conflicts(placements))
    conflicts.extend(_extra_conflicts(problem, placements, by_workload, complete))
    unique = {
        (conflict.code, conflict.entry_ids, repr(sorted(conflict.details.items()))): conflict
        for conflict in conflicts
    }
    return [unique[key] for key in sorted(unique)]
