from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from uuid import UUID

from app.domain.projects.settings import DurationModeKind, ProjectSettings, TimeModeKind
from app.domain.scheduling.constraint_validation import (
    applies_to_workload,
    constraint_conflicts,
    covered_by,
    seconds,
)
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
    room_allows_lesson,
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
    stream_id: UUID | None = None

    @property
    def lesson_type(self) -> str | None:
        return self.entry.lesson_type or (self.workload.lesson_type if self.workload else None)

    @property
    def lesson_format(self) -> LessonFormat | None:
        return self.entry.lesson_format or (self.workload.lesson_format if self.workload else None)

    def matches(self, scope: ConstraintScope, subgroups: dict[UUID, SubgroupSnapshot]) -> bool:
        if scope.kind is ConstraintScopeKind.STREAM and self.workload is None:
            return scope.resource_id == self.stream_id
        return applies_to_workload(
            scope, self.workload, self.groups, self.subgroup, subgroups, self.entry.workload_id
        )


def _conflict(
    code: str, message: str, *entries: ScheduleEntry, **details: object
) -> ScheduleConflict:
    return ScheduleConflict(code, message, tuple(sorted({entry.id for entry in entries})), details)


def _label(value: str | None) -> str | None:
    return " ".join(value.casefold().split()) if value and value.strip() else None


def _identities(pairs: Iterator[tuple[UUID, str | None]]) -> dict[str, set[UUID]]:
    result: dict[str, set[UUID]] = defaultdict(set)
    for resource_id, name in pairs:
        label = _label(name)
        if label is not None:
            result[label].add(resource_id)
    return result


def _identity(
    resource_id: UUID | None, name: str | None, identities: dict[str, set[UUID]]
) -> UUID | str | None:
    if resource_id is not None:
        return resource_id
    label = _label(name)
    if label is None:
        return None
    matches = identities.get(label, set())
    if len(matches) == 1:
        return next(iter(matches))
    return label if not matches else None


def _participant_targets(problem: ScheduleProblem):
    targets = defaultdict(list)
    groups = {group.id: group for group in problem.groups}
    for group in problem.groups:
        targets[_label(group.name)].append(((group.id,), None, group.student_count, None))
    for subgroup in problem.subgroups:
        group = groups.get(subgroup.group_id)
        if group is not None:
            targets[_label(f"{group.name} / {subgroup.name}")].append(
                ((group.id,), subgroup.id, subgroup.student_count, None)
            )
    for stream in problem.streams:
        group_ids = tuple(dict.fromkeys(stream.group_ids))
        if group_ids and all(group_id in groups for group_id in group_ids):
            targets[_label(stream.name)].append(
                (
                    group_ids, None,
                    sum(groups[group_id].student_count for group_id in group_ids), stream.id,
                )
            )
    return targets


def resolve_workload(entry: ScheduleEntry, problem: ScheduleProblem) -> WorkloadSnapshot | None:
    if entry.workload_id is not None:
        return next(
            (workload for workload in problem.workloads if workload.id == entry.workload_id),
            None,
        )
    if not (entry.subject_name and entry.participant_label and entry.lesson_type):
        return None
    subjects = {subject.id: subject.name for subject in problem.subjects}
    groups = {group.id: group.name for group in problem.groups}
    participants = {
        WorkloadTargetKind.GROUP: groups,
        WorkloadTargetKind.SUBGROUP: {
            subgroup.id: f"{groups[subgroup.group_id]} / {subgroup.name}"
            for subgroup in problem.subgroups
            if subgroup.group_id in groups
        },
        WorkloadTargetKind.STREAM: {stream.id: stream.name for stream in problem.streams},
    }
    matches = [
        workload
        for workload in problem.workloads
        if workload.lesson_type == entry.lesson_type
        and _label(subjects.get(workload.subject_id)) == _label(entry.subject_name)
        and _label(participants[workload.target.kind].get(workload.target.resource_id))
        == _label(entry.participant_label)
    ]
    return matches[0] if len(matches) == 1 else None


def _placements(schedule: Schedule, problem: ScheduleProblem) -> Iterator[_Placement]:
    workloads = {workload.id: workload for workload in problem.workloads}
    groups = {group.id: group for group in problem.groups}
    subgroups = {subgroup.id: subgroup for subgroup in problem.subgroups}
    streams = {stream.id: stream for stream in problem.streams}
    targets = _participant_targets(problem)
    for entry in schedule.entries:
        workload = workloads.get(entry.workload_id)
        if entry.workload_id is None and schedule.source is ScheduleSource.IMPORTED:
            workload = resolve_workload(entry, problem)
        if workload is None:
            matches = targets.get(_label(entry.participant_label), ())
            if len(matches) == 1:
                yield _Placement(entry, None, *matches[0])
            else:
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


def _subject_id(placement: _Placement, subjects: dict[str, set[UUID]]) -> UUID | None:
    if placement.workload is not None:
        return placement.workload.subject_id
    identifier = _identity(None, placement.entry.subject_name, subjects)
    return identifier if isinstance(identifier, UUID) else None


def _teacher_conflicts(
    placement: _Placement,
    teachers: dict[UUID, TeacherSnapshot],
    teacher_names: dict[str, set[UUID]],
    subject_id: UUID | None,
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
        teacher_id = assignment.teacher_id
        if not generated and teacher_id is None:
            teacher_id = _identity(None, assignment.display_name, teacher_names)
        teacher = teachers.get(teacher_id)
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
            subject_id is not None
            and placement.lesson_type
            and not any(
                capability.subject_id == subject_id
                and capability.lesson_type == placement.lesson_type
                for capability in teacher.capabilities
            )
        ):
            yield _conflict(
                "TEACHER_NOT_QUALIFIED",
                "Преподаватель не ведёт эту дисциплину и тип занятия",
                entry,
                teacher_id=str(teacher.id),
                subject_id=str(subject_id),
            )


def _room_conflicts(
    placement: _Placement,
    rooms: dict[UUID, RoomSnapshot],
    room_names: dict[str, set[UUID]],
    subject_id: UUID | None,
    generated: bool,
) -> Iterator[ScheduleConflict]:
    entry = placement.entry
    if placement.lesson_format is LessonFormat.REMOTE:
        if entry.room_id is not None or entry.room_name is not None:
            yield _conflict("REMOTE_ROOM", "Дистанционное занятие не занимает аудиторию", entry)
        return
    room_id = entry.room_id
    if not generated and room_id is None:
        room_id = _identity(None, entry.room_name, room_names)
    room = rooms.get(room_id)
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
        subject_id is not None
        and placement.lesson_type
        and not room_allows_lesson(room, subject_id, placement.lesson_type)
    ):
        yield _conflict(
            "ROOM_SPECIALIZATION",
            "Аудитория не предназначена для этой дисциплины и типа занятия",
            entry,
            room_id=str(room.id),
            subject_id=str(subject_id),
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


def _overlap_conflicts(
    placements: list[_Placement], problem: ScheduleProblem
) -> Iterator[ScheduleConflict]:
    teacher_names = _identities(iter(
        [(teacher.id, teacher.full_name) for teacher in problem.teachers]
        + [
            (teacher.teacher_id, teacher.display_name)
            for placement in placements
            for teacher in placement.entry.teachers
            if teacher.teacher_id is not None
        ]
    ))
    room_names = _identities(iter(
        [(room.id, room.name) for room in problem.rooms]
        + [
            (placement.entry.room_id, placement.entry.room_name)
            for placement in placements
            if placement.entry.room_id is not None
        ]
    ))
    participant_targets = _participant_targets(problem)
    by_resource: dict[tuple[str, UUID | str, str, Weekday], list[_Placement]] = defaultdict(list)
    for placement in placements:
        entry = placement.entry
        resources = {("GROUP_OVERLAP", group_id) for group_id in placement.groups}
        participant_label = _label(entry.participant_label)
        if not placement.groups and participant_label and not participant_targets.get(participant_label):
            resources.add(("GROUP_OVERLAP", participant_label))
        resources.update(
            ("TEACHER_OVERLAP", _identity(teacher.teacher_id, teacher.display_name, teacher_names))
            for teacher in entry.teachers
        )
        if placement.lesson_format is not LessonFormat.REMOTE:
            resources.add(("ROOM_OVERLAP", _identity(entry.room_id, entry.room_name, room_names)))
        for code, resource_id in resources:
            if resource_id is not None:
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
    partial_assignment: bool,
) -> Iterator[ScheduleConflict]:
    subgroups = {subgroup.id: subgroup for subgroup in problem.subgroups}
    expected = {workload.id: workload.occurrences_per_cycle for workload in problem.workloads}

    def workload_complete(workload_id: UUID | None) -> bool:
        return workload_id in expected and (
            len(by_workload.get(workload_id, ())) >= expected[workload_id]
        )
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
        available = complete
        if not partial_assignment and scope.kind is ConstraintScopeKind.WORKLOAD:
            available = available or (
                workload_complete(scope.resource_id)
                and (
                    not isinstance(params, (RelatedWorkloadParameters, MinimumGapParameters))
                    or workload_complete(params.workload_id)
                )
            )
        yield from constraint_conflicts(constraint, selected, related, available)


def validate_schedule(
    schedule: Schedule, problem: ScheduleProblem, *, partial_assignment: bool = False
) -> list[ScheduleConflict]:
    placements = list(_placements(schedule, problem))
    generated = schedule.source is ScheduleSource.GENERATED
    complete = not partial_assignment and (
        generated or bool(placements and all(item.workload is not None for item in placements))
    )
    teachers = {teacher.id: teacher for teacher in problem.teachers}
    rooms = {room.id: room for room in problem.rooms}
    subjects = _identities((subject.id, subject.name) for subject in problem.subjects)
    teacher_names = _identities((teacher.id, teacher.full_name) for teacher in problem.teachers)
    room_names = _identities((room.id, room.name) for room in problem.rooms)
    groups = {group.id: group for group in problem.groups}
    subgroups = {subgroup.id: subgroup for subgroup in problem.subgroups}
    by_workload: dict[UUID, list[ScheduleEntry]] = defaultdict(list)
    conflicts: list[ScheduleConflict] = []
    for placement in placements:
        entry = placement.entry
        if placement.workload is not None:
            by_workload[placement.workload.id].append(entry)
        if placement.workload is None and generated:
            conflicts.append(
                _conflict(
                    "WORKLOAD_NOT_FOUND",
                    "Учебная нагрузка занятия отсутствует в проекте",
                    entry,
                    workload_id=str(entry.workload_id),
                )
            )
        conflicts.extend(_time_conflicts(placement, problem.settings))
        subject_id = _subject_id(placement, subjects)
        conflicts.extend(
            _teacher_conflicts(placement, teachers, teacher_names, subject_id, generated)
        )
        conflicts.extend(_room_conflicts(placement, rooms, room_names, subject_id, generated))
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
    conflicts.extend(_overlap_conflicts(placements, problem))
    conflicts.extend(_extra_conflicts(problem, placements, by_workload, complete, partial_assignment))
    unique = {
        (conflict.code, conflict.entry_ids, repr(sorted(conflict.details.items()))): conflict
        for conflict in conflicts
    }
    return [unique[key] for key in sorted(unique)]
