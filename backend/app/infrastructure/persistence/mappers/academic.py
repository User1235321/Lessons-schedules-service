from collections.abc import Iterable
from uuid import UUID

from app.domain.academic.capability import Capability
from app.domain.academic.group import StudentGroup, Subgroup
from app.domain.academic.lesson_type import LessonType
from app.domain.academic.room import Room, RoomType
from app.domain.academic.stream import Stream
from app.domain.academic.subject import Subject
from app.domain.academic.teacher import Teacher
from app.domain.academic.workload import LessonFormat, TargetType, Workload, WorkloadTarget
from app.domain.shared.ids import (
    GroupId,
    ProjectId,
    RoomId,
    StreamId,
    SubgroupId,
    SubjectId,
    TeacherId,
    WorkloadId,
)
from app.domain.shared.week import Week, Weekday, WeeklyInterval
from app.infrastructure.persistence.models import (
    RoomAvailabilityRow,
    RoomCapabilityRow,
    RoomRow,
    StreamRow,
    StudentGroupRow,
    SubgroupRow,
    SubjectRow,
    TeacherAvailabilityRow,
    TeacherCapabilityRow,
    TeacherPreferenceRow,
    TeacherRow,
    WorkloadRow,
)


def subject_to_row(subject: Subject) -> SubjectRow:
    return SubjectRow(id=subject.id, project_id=subject.project_id, name=subject.name)


def subject_to_domain(row: SubjectRow) -> Subject:
    return Subject(id=SubjectId(row.id), project_id=ProjectId(row.project_id), name=row.name)


def capability_rows(
    project_id: ProjectId, owner: dict[str, UUID], capabilities: Iterable[Capability]
) -> list[dict[str, object]]:
    """Строки пар. owner — колонка владельца: {"teacher_id": ...} или {"room_id": ...}."""
    return [
        {
            "project_id": project_id,
            **owner,
            "subject_id": capability.subject_id,
            "lesson_type": str(capability.lesson_type),
        }
        for capability in capabilities
    ]


def interval_rows(
    owner: dict[str, UUID], intervals: Iterable[WeeklyInterval]
) -> list[dict[str, object]]:
    return [
        {
            **owner,
            "week": str(interval.week),
            "day": str(interval.day),
            "start_time": interval.start,
            "end_time": interval.end,
        }
        for interval in intervals
    ]


def _interval(
    row: TeacherAvailabilityRow | TeacherPreferenceRow | RoomAvailabilityRow,
) -> WeeklyInterval:
    return WeeklyInterval(Week(row.week), Weekday(row.day), row.start_time, row.end_time)


def _capabilities(
    rows: Iterable[TeacherCapabilityRow | RoomCapabilityRow],
) -> tuple[Capability, ...]:
    return tuple(Capability(SubjectId(row.subject_id), LessonType(row.lesson_type)) for row in rows)


def teacher_to_domain(row: TeacherRow) -> Teacher:
    return Teacher(
        id=TeacherId(row.id),
        project_id=ProjectId(row.project_id),
        full_name=row.full_name,
        capabilities=_capabilities(row.capabilities),
        availability=tuple(_interval(interval) for interval in row.availability),
        preferences=tuple(_interval(interval) for interval in row.preferences),
    )


def subgroup_row(group: StudentGroup, subgroup: Subgroup) -> dict[str, object]:
    return {
        "id": subgroup.id,
        "project_id": group.project_id,
        "group_id": group.id,
        "name": subgroup.name,
        "student_count": subgroup.student_count,
    }


def group_to_domain(row: StudentGroupRow) -> StudentGroup:
    return StudentGroup(
        id=GroupId(row.id),
        project_id=ProjectId(row.project_id),
        name=row.name,
        student_count=row.student_count,
        subgroups=tuple(_subgroup(subgroup) for subgroup in row.subgroups),
    )


def _subgroup(row: SubgroupRow) -> Subgroup:
    return Subgroup(id=SubgroupId(row.id), name=row.name, student_count=row.student_count)


def room_to_domain(row: RoomRow) -> Room:
    return Room(
        id=RoomId(row.id),
        project_id=ProjectId(row.project_id),
        name=row.name,
        capacity=row.capacity,
        type=RoomType(row.type),
        availability=tuple(_interval(interval) for interval in row.availability),
        capabilities=_capabilities(row.capabilities),
    )


def stream_to_domain(row: StreamRow) -> Stream:
    return Stream(
        id=StreamId(row.id),
        project_id=ProjectId(row.project_id),
        name=row.name,
        group_ids=tuple(GroupId(member.group_id) for member in row.groups),
    )


# Цель нагрузки хранится в одной из трёх колонок, остальные две — NULL
_TARGET_COLUMNS = {
    TargetType.GROUP: "group_id",
    TargetType.SUBGROUP: "subgroup_id",
    TargetType.STREAM: "stream_id",
}


def workload_values(workload: Workload) -> dict[str, object]:
    """Все колонки нагрузки, кроме id и project_id."""
    values: dict[str, object] = {
        "subject_id": workload.subject_id,
        "lesson_type": str(workload.lesson_type),
        "format": str(workload.format),
        "occurrences_per_cycle": workload.occurrences_per_cycle,
        "duration_minutes": workload.duration_minutes,
        "required_teacher_count": workload.required_teacher_count,
    }
    for target_type, column in _TARGET_COLUMNS.items():
        values[column] = workload.target.id if workload.target.type is target_type else None
    return values


def workload_to_domain(row: WorkloadRow) -> Workload:
    target = next(
        WorkloadTarget(target_type, getattr(row, column))
        for target_type, column in _TARGET_COLUMNS.items()
        if getattr(row, column) is not None
    )
    return Workload(
        id=WorkloadId(row.id),
        project_id=ProjectId(row.project_id),
        target=target,
        subject_id=SubjectId(row.subject_id),
        lesson_type=LessonType(row.lesson_type),
        format=LessonFormat(row.format),
        occurrences_per_cycle=row.occurrences_per_cycle,
        duration_minutes=row.duration_minutes,
        required_teacher_count=row.required_teacher_count,
    )
