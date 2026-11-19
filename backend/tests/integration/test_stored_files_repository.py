from dataclasses import replace
from datetime import UTC, datetime, time, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete

from app.domain.files import StoredFile, StoredFileCategory
from app.domain.projects.project import Project
from app.domain.scheduling.constraints import (
    ClockTimeParameters,
    ConstraintKind,
    ConstraintScope,
    ConstraintScopeKind,
    ExtraConstraintSnapshot,
)
from app.domain.scheduling.job import ResultOptions
from app.domain.scheduling.problem import OptimizationCriterionSnapshot
from app.domain.scheduling.schedule import (
    LessonFormat,
    Schedule,
    ScheduleEntry,
    ScheduleSource,
    TeacherAssignment,
)
from app.domain.shared.errors import AlreadyExists, InvalidValue, NotFound
from app.domain.shared.ids import ProjectId, ScheduleEntryId, ScheduleId, StoredFileId, UserId
from app.domain.shared.week import Weekday
from app.infrastructure.persistence.models.jobs import JobRow
from app.infrastructure.persistence.models.schedules import ScheduleRow


def make_file(project_id: ProjectId, owner_id: UserId, created_at: datetime) -> StoredFile:
    return StoredFile(
        id=StoredFileId(uuid4()),
        project_id=project_id,
        user_id=owner_id,
        category=StoredFileCategory.UPLOAD,
        original_name="расписание.xlsx",
        file_format="xlsx",
        object_key=f"projects/{project_id}/{uuid4()}",
        size_bytes=1024,
        created_at=created_at,
    )


def test_file_metadata_survives_commit_and_is_listed_by_date(scheduling_context: tuple) -> None:
    container, owner, project = scheduling_context
    oldest = make_file(project.id, owner.id, project.created_at)
    newest = replace(
        make_file(project.id, owner.id, project.created_at),
        created_at=project.created_at + timedelta(seconds=1),
    )

    with container.uow() as uow:
        uow.files.add(oldest)
        uow.files.add(newest)
        uow.commit()

    with container.uow() as uow:
        assert uow.files.get(project.id, oldest.id) == oldest
        assert uow.files.get(project.id, newest.id) == newest
        assert uow.files.list_in_project(project.id) == [newest, oldest]


def test_related_project_data_is_restored_together(scheduling_context: tuple) -> None:
    container, owner, project = scheduling_context
    entry = ScheduleEntry(
        id=ScheduleEntryId(uuid4()),
        week="ODD",
        weekday=Weekday.TUESDAY,
        start_time=time(9),
        end_time=time(10, 40),
        subject_name="Алгебра",
        participant_label="Группа 101",
        lesson_type="LECTURE",
        lesson_format=LessonFormat.ONSITE,
        room_name="Аудитория 14",
        teachers=(TeacherAssignment("Петрова"),),
    )
    schedule = Schedule(
        id=ScheduleId(uuid4()),
        project_id=project.id,
        source=ScheduleSource.IMPORTED,
        entries=(entry,),
        created_at=project.created_at,
    )
    constraint = ExtraConstraintSnapshot(
        id=uuid4(),
        kind=ConstraintKind.MIN_START_TIME,
        scope=ConstraintScope(ConstraintScopeKind.PROJECT),
        parameters=ClockTimeParameters(time(9)),
    )
    criterion = OptimizationCriterionSnapshot("STUDENT_GAPS", priority=1, is_active=True)
    file = replace(make_file(project.id, owner.id, project.created_at), schedule_id=schedule.id)

    with container.uow() as uow:
        uow.schedules.add(schedule)
        uow.constraints.add(project.id, constraint)
        uow.criteria.replace(project.id, (criterion,))
        uow.files.add(file)
        uow.commit()

    with container.uow() as uow:
        assert uow.schedules.get(project.id, schedule.id) == schedule
        assert uow.constraints.list_in_project(project.id) == [constraint]
        assert uow.criteria.list_in_project(project.id) == [criterion]
        assert uow.files.get(project.id, file.id) == file


def test_file_links_cannot_reference_another_project(scheduling_context: tuple) -> None:
    container, owner, project = scheduling_context
    other = Project.create(
        project_id=ProjectId(uuid4()),
        owner_id=owner.id,
        name="Другая нагрузка",
        now=project.created_at,
    )
    schedule = Schedule(
        id=ScheduleId(uuid4()),
        project_id=other.id,
        source=ScheduleSource.IMPORTED,
        entries=(),
        created_at=other.created_at,
    )
    with container.uow() as uow:
        uow.projects.add(other)
        uow.commit()
    with container.uow() as uow:
        uow.schedules.add(schedule)
        uow.commit()
    job = container.create_generation_job().execute(owner.id, other.id, ResultOptions())
    file = make_file(project.id, owner.id, project.created_at)

    for field, resource_id in (("schedule_id", schedule.id), ("job_id", job.id)):
        with pytest.raises(InvalidValue) as error, container.uow() as uow:
            uow.files.add(replace(file, **{field: resource_id}))
        assert error.value.field == field

    with container.uow() as uow:
        assert uow.files.list_in_project(project.id) == []


def test_file_owner_must_own_its_project(scheduling_context: tuple) -> None:
    container, owner, project = scheduling_context
    file = replace(make_file(project.id, owner.id, project.created_at), user_id=UserId(uuid4()))

    with pytest.raises(NotFound), container.uow() as uow:
        uow.files.add(file)


def test_duplicate_object_key_is_rejected(scheduling_context: tuple) -> None:
    container, owner, project = scheduling_context
    original = make_file(project.id, owner.id, project.created_at)
    with container.uow() as uow:
        uow.files.add(original)
        uow.commit()

    duplicate = replace(original, id=StoredFileId(uuid4()))
    with pytest.raises(AlreadyExists), container.uow() as uow:
        uow.files.add(duplicate)


def test_file_metadata_remains_after_related_schedule_and_job_are_deleted(
    scheduling_context: tuple,
) -> None:
    container, owner, project = scheduling_context
    schedule = Schedule(
        id=ScheduleId(uuid4()),
        project_id=project.id,
        source=ScheduleSource.IMPORTED,
        entries=(),
        created_at=project.created_at,
    )
    with container.uow() as uow:
        uow.schedules.add(schedule)
        uow.commit()
    job = container.create_generation_job().execute(owner.id, project.id, ResultOptions())
    schedule_file = replace(
        make_file(project.id, owner.id, project.created_at), schedule_id=schedule.id
    )
    job_file = replace(make_file(project.id, owner.id, project.created_at), job_id=job.id)
    with container.uow() as uow:
        uow.files.add(schedule_file)
        uow.files.add(job_file)
        uow.commit()

    with container.session_factory() as session:
        session.execute(delete(ScheduleRow).where(ScheduleRow.id == schedule.id))
        session.execute(delete(JobRow).where(JobRow.id == job.id))
        session.commit()

    with container.uow() as uow:
        assert uow.files.get(project.id, schedule_file.id) == replace(
            schedule_file, schedule_id=None
        )
        assert uow.files.get(project.id, job_file.id) == replace(job_file, job_id=None)


def test_file_changes_are_rolled_back_without_commit(scheduling_context: tuple) -> None:
    container, owner, project = scheduling_context
    file = make_file(project.id, owner.id, project.created_at)
    with container.uow() as uow:
        uow.files.add(file)

    with container.uow() as uow:
        assert uow.files.get(project.id, file.id) is None


def test_deleting_project_removes_file_metadata(scheduling_context: tuple) -> None:
    container, owner, project = scheduling_context
    file = make_file(project.id, owner.id, project.created_at)
    with container.uow() as uow:
        uow.files.add(file)
        uow.commit()
    with container.uow() as uow:
        uow.projects.delete(project.id, owner.id)
        uow.commit()

    with container.uow() as uow:
        assert uow.files.get(project.id, file.id) is None


@pytest.mark.parametrize(
    ("values", "field"),
    [
        ({"original_name": " "}, "original_name"),
        ({"file_format": ""}, "file_format"),
        ({"object_key": ""}, "object_key"),
        ({"size_bytes": -1}, "size_bytes"),
    ],
)
def test_invalid_file_metadata_is_rejected(values: dict, field: str) -> None:
    file = make_file(ProjectId(uuid4()), UserId(uuid4()), datetime.now(UTC))

    with pytest.raises(InvalidValue) as error:
        replace(file, **values)
    assert error.value.field == field
