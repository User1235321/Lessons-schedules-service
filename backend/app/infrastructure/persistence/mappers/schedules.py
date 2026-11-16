from app.domain.scheduling.schedule import (
    CriterionScore,
    LessonFormat,
    Schedule,
    ScheduleEntry,
    ScheduleSource,
    TeacherAssignment,
)
from app.domain.shared.ids import JobId, ProjectId, ScheduleEntryId, ScheduleId
from app.domain.shared.week import Weekday
from app.infrastructure.persistence.models.schedules import (
    ScheduleEntryRow,
    ScheduleEntryTeacherRow,
    ScheduleRow,
)


def schedule_to_row(schedule: Schedule) -> ScheduleRow:
    return ScheduleRow(
        id=schedule.id,
        project_id=schedule.project_id,
        source=schedule.source.value,
        job_id=schedule.job_id,
        result_index=schedule.result_index,
        criterion_scores=[
            {"criterion": score.criterion, "value": score.value}
            for score in schedule.criterion_scores
        ]
        if schedule.criterion_scores is not None
        else None,
        created_at=schedule.created_at,
    )


def entry_to_row(entry: ScheduleEntry, schedule_id: ScheduleId, position: int) -> ScheduleEntryRow:
    return ScheduleEntryRow(
        id=entry.id,
        schedule_id=schedule_id,
        position=position,
        workload_id=entry.workload_id,
        subject_name=entry.subject_name,
        participant_label=entry.participant_label,
        lesson_type=entry.lesson_type,
        lesson_format=entry.lesson_format.value if entry.lesson_format else None,
        week=entry.week,
        weekday=entry.weekday.value,
        start_time=entry.start_time,
        end_time=entry.end_time,
        room_id=entry.room_id,
        room_name=entry.room_name,
    )


def entry_to_domain(
    row: ScheduleEntryRow, teachers: list[ScheduleEntryTeacherRow]
) -> ScheduleEntry:
    return ScheduleEntry(
        id=ScheduleEntryId(row.id),
        workload_id=row.workload_id,
        subject_name=row.subject_name,
        participant_label=row.participant_label,
        lesson_type=row.lesson_type,
        lesson_format=LessonFormat(row.lesson_format) if row.lesson_format else None,
        week=row.week,
        weekday=Weekday(row.weekday),
        start_time=row.start_time,
        end_time=row.end_time,
        room_id=row.room_id,
        room_name=row.room_name,
        teachers=tuple(
            TeacherAssignment(teacher.display_name, teacher.teacher_id) for teacher in teachers
        ),
    )


def schedule_to_domain(row: ScheduleRow, entries: tuple[ScheduleEntry, ...]) -> Schedule:
    return Schedule(
        id=ScheduleId(row.id),
        project_id=ProjectId(row.project_id),
        source=ScheduleSource(row.source),
        job_id=JobId(row.job_id) if row.job_id else None,
        result_index=row.result_index,
        entries=entries,
        criterion_scores=tuple(
            CriterionScore(score["criterion"], score["value"]) for score in row.criterion_scores
        )
        if row.criterion_scores is not None
        else None,
        created_at=row.created_at,
    )
