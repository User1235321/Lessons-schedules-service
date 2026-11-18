from dataclasses import replace
from datetime import time, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.domain.projects.project import Project
from app.domain.scheduling.job import ResultOptions
from app.domain.scheduling.schedule import (
    LessonFormat,
    Schedule,
    ScheduleEntry,
    ScheduleSource,
    TeacherAssignment,
)
from app.domain.shared.errors import AlreadyExists
from app.domain.shared.ids import ProjectId, ScheduleEntryId, ScheduleId
from app.domain.shared.week import Weekday


def test_list_sorts_newest_first_then_by_id(scheduling_context: tuple) -> None:
    container, _, project = scheduling_context
    oldest = Schedule(
        id=ScheduleId(UUID(int=1)),
        project_id=project.id,
        source=ScheduleSource.IMPORTED,
        entries=(),
        created_at=project.created_at,
    )
    newest = replace(
        oldest, id=ScheduleId(UUID(int=3)), created_at=oldest.created_at + timedelta(seconds=1)
    )
    tied = replace(newest, id=ScheduleId(UUID(int=2)))
    with container.uow() as uow:
        for schedule in (oldest, newest, tied):
            uow.schedules.add(schedule)
        uow.commit()
    with container.uow() as uow:
        assert uow.schedules.list_in_project(project.id) == [tied, newest, oldest]


@pytest.mark.parametrize("duplicate", ["id", "result_index"])
def test_duplicate_schedule_raises_already_exists(
    scheduling_context: tuple, duplicate: str
) -> None:
    container, owner, project = scheduling_context
    job = container.create_generation_job().execute(owner.id, project.id, ResultOptions())
    schedule = Schedule(
        id=ScheduleId(uuid4()),
        project_id=project.id,
        source=ScheduleSource.GENERATED,
        entries=(),
        created_at=job.created_at,
        job_id=job.id,
        result_index=1,
        criterion_scores=(),
    )
    with container.uow() as uow:
        uow.schedules.add(schedule)
        uow.commit()
    repeated = replace(
        schedule,
        id=ScheduleId(uuid4()) if duplicate == "result_index" else schedule.id,
        result_index=2 if duplicate == "id" else 1,
    )
    with pytest.raises(AlreadyExists), container.uow() as uow:
        uow.schedules.add(repeated)
    with container.uow() as uow:
        assert uow.schedules.list_for_job(project.id, job.id) == [schedule]


def test_other_schedule_integrity_errors_remain_database_errors(scheduling_context: tuple) -> None:
    container, _, project = scheduling_context
    schedule = Schedule(
        id=ScheduleId(uuid4()),
        project_id=ProjectId(uuid4()),
        source=ScheduleSource.IMPORTED,
        entries=(),
        created_at=project.created_at,
    )
    with pytest.raises(IntegrityError), container.uow() as uow:
        uow.schedules.add(schedule)


def test_imported_schedule_persists_entries_without_academic_references(
    scheduling_context: tuple,
) -> None:
    container, _, project = scheduling_context
    entry = ScheduleEntry(
        id=ScheduleEntryId(uuid4()),
        week="ODD",
        weekday=Weekday.MONDAY,
        start_time=time(9),
        end_time=time(10, 40),
        subject_name="Физика",
        participant_label="Группа 101",
        lesson_type="LAB",
        lesson_format=LessonFormat.ONSITE,
        room_name="Аудитория 12",
        teachers=(TeacherAssignment("Иванова"), TeacherAssignment("Петров")),
    )
    schedule = Schedule(
        id=ScheduleId(uuid4()),
        project_id=project.id,
        source=ScheduleSource.IMPORTED,
        entries=(entry,),
        created_at=project.created_at,
    )

    with container.uow() as uow:
        uow.schedules.add(schedule)
        uow.commit()

    with container.uow() as uow:
        assert uow.schedules.get(project.id, schedule.id) == schedule


def test_generated_schedule_cannot_reference_job_from_another_project(
    scheduling_context: tuple,
) -> None:
    container, owner, project = scheduling_context
    other = Project.create(
        project_id=ProjectId(uuid4()),
        owner_id=owner.id,
        name="Другой проект",
        now=project.created_at,
    )
    with container.uow() as uow:
        uow.projects.add(other)
        uow.commit()

    job = container.create_generation_job().execute(owner.id, project.id, ResultOptions())
    schedule = Schedule(
        id=ScheduleId(uuid4()),
        project_id=other.id,
        source=ScheduleSource.GENERATED,
        entries=(),
        created_at=job.created_at,
        job_id=job.id,
        result_index=1,
        criterion_scores=(),
    )

    with pytest.raises(IntegrityError, match="fk_schedules_project_id_schedule_jobs"):
        with container.uow() as uow:
            uow.schedules.add(schedule)
            uow.commit()
