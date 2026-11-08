from app.domain.academic.group import StudentGroup, Subgroup
from app.domain.academic.lesson_type import LessonType
from app.domain.academic.subject import Subject
from app.domain.academic.teacher import Capability, Teacher
from app.domain.shared.ids import GroupId, ProjectId, SubgroupId, SubjectId, TeacherId
from app.domain.shared.week import Week, Weekday, WeeklyInterval
from app.infrastructure.persistence.models import (
    StudentGroupRow,
    SubgroupRow,
    SubjectRow,
    TeacherAvailabilityRow,
    TeacherPreferenceRow,
    TeacherRow,
)


def subject_to_row(subject: Subject) -> SubjectRow:
    return SubjectRow(id=subject.id, project_id=subject.project_id, name=subject.name)


def subject_to_domain(row: SubjectRow) -> Subject:
    return Subject(id=SubjectId(row.id), project_id=ProjectId(row.project_id), name=row.name)


def capability_rows(teacher: Teacher) -> list[dict[str, object]]:
    return [
        {
            "project_id": teacher.project_id,
            "teacher_id": teacher.id,
            "subject_id": capability.subject_id,
            "lesson_type": str(capability.lesson_type),
        }
        for capability in teacher.capabilities
    ]


def interval_rows(
    teacher: Teacher, intervals: tuple[WeeklyInterval, ...]
) -> list[dict[str, object]]:
    return [
        {
            "teacher_id": teacher.id,
            "week": str(interval.week),
            "day": str(interval.day),
            "start_time": interval.start,
            "end_time": interval.end,
        }
        for interval in intervals
    ]


def _interval(row: TeacherAvailabilityRow | TeacherPreferenceRow) -> WeeklyInterval:
    return WeeklyInterval(Week(row.week), Weekday(row.day), row.start_time, row.end_time)


def teacher_to_domain(row: TeacherRow) -> Teacher:
    return Teacher(
        id=TeacherId(row.id),
        project_id=ProjectId(row.project_id),
        full_name=row.full_name,
        capabilities=tuple(
            Capability(SubjectId(capability.subject_id), LessonType(capability.lesson_type))
            for capability in row.capabilities
        ),
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
