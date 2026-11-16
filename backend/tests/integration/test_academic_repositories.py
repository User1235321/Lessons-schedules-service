from datetime import UTC, datetime, time, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import Connection, Engine, delete, func, select
from sqlalchemy.orm import sessionmaker

from app.application.academic.changes import project_data_changed
from app.domain.academic.errors import (
    GroupNameTaken,
    SubjectInUse,
    SubjectNameTaken,
)
from app.domain.academic.group import StudentGroup, Subgroup
from app.domain.academic.lesson_type import LessonType
from app.domain.academic.subject import Subject
from app.domain.academic.teacher import Capability, Teacher
from app.domain.auth.user import Email, User
from app.domain.projects.project import Project
from app.domain.projects.settings import DurationMode, ProjectSettings, StudyCycle, TimeMode
from app.domain.shared.errors import InvalidValue, NotFound
from app.domain.shared.ids import GroupId, ProjectId, SubgroupId, SubjectId, TeacherId, UserId
from app.domain.shared.week import Week, Weekday, WeeklyInterval
from app.infrastructure.persistence.models import (
    StudentGroupRow,
    SubgroupRow,
    SubjectRow,
    TeacherAvailabilityRow,
    TeacherCapabilityRow,
    TeacherRow,
    UserRow,
)
from app.infrastructure.persistence.uow import SqlUnitOfWork

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)
MONDAY_MORNING = WeeklyInterval(Week.ODD, Weekday.MONDAY, time(9), time(13))
ANY_TUESDAY = WeeklyInterval(Week.ANY, Weekday.TUESDAY, time(10), time(15))


def stored_project(uow: SqlUnitOfWork) -> Project:
    user = User(
        id=UserId(uuid4()), email=Email(f"{uuid4()}@mail.ru"), password_hash="h", created_at=NOW
    )
    project = Project.create(project_id=ProjectId(uuid4()), owner_id=user.id, name="Осень", now=NOW)
    with uow:
        uow.users.add(user)
        uow.projects.add(project)
        uow.commit()
    return project


def stored_subject(uow: SqlUnitOfWork, project_id: ProjectId, name: str = "Математика") -> Subject:
    subject = Subject(id=SubjectId(uuid4()), project_id=project_id, name=name)
    with uow:
        uow.subjects.add(subject)
        uow.commit()
    return subject


def a_teacher(project_id: ProjectId, subject: Subject, name: str = "Петрова А. В.") -> Teacher:
    return Teacher(
        id=TeacherId(uuid4()),
        project_id=project_id,
        full_name=name,
        capabilities=(Capability(subject.id, LessonType.LECTURE),),
        availability=(MONDAY_MORNING,),
        preferences=(ANY_TUESDAY,),
    )


def stored_teacher(uow: SqlUnitOfWork, teacher: Teacher) -> Teacher:
    with uow:
        uow.teachers.add(teacher)
        uow.commit()
    return teacher


def a_subgroup(name: str, student_count: int = 12) -> Subgroup:
    return Subgroup(id=SubgroupId(uuid4()), name=name, student_count=student_count)


def a_group(project_id: ProjectId, name: str = "301", *subgroups: Subgroup) -> StudentGroup:
    return StudentGroup(
        id=GroupId(uuid4()),
        project_id=project_id,
        name=name,
        student_count=24,
        subgroups=subgroups,
    )


def stored_group(uow: SqlUnitOfWork, group: StudentGroup) -> StudentGroup:
    with uow:
        uow.groups.add(group)
        uow.commit()
    return group


def count(db_connection: Connection, table: type) -> int:
    return db_connection.scalar(select(func.count()).select_from(table)) or 0


def test_academic_change_preserves_concurrent_project_settings(
    migrated_engine: Engine,
) -> None:
    sessions = sessionmaker(bind=migrated_engine, expire_on_commit=False)
    project = stored_project(SqlUnitOfWork(sessions))
    settings = ProjectSettings(
        cycle=StudyCycle((Weekday.MONDAY,), (Weekday.TUESDAY,)),
        time_mode=TimeMode.step(30),
        duration_mode=DurationMode.individual(),
    )
    changed_at = NOW + timedelta(minutes=2)
    subject = Subject(
        id=SubjectId(uuid4()),
        project_id=project.id,
        name="Математика",
    )

    try:
        with SqlUnitOfWork(sessions) as request_a:
            stale_project = request_a.projects.get_owned(project.id, project.owner_id)
            assert stale_project is not None
            assert stale_project.name == "Осень"

            with SqlUnitOfWork(sessions) as request_b:
                updated_project = request_b.projects.get_owned(project.id, project.owner_id)
                assert updated_project is not None
                updated_project.rename("Весна", NOW + timedelta(minutes=1))
                updated_project.change_settings(settings, NOW + timedelta(minutes=1))
                request_b.projects.save(updated_project)
                request_b.commit()

            request_a.subjects.add(subject)
            project_data_changed(request_a, stale_project, changed_at)
            request_a.commit()

        with SqlUnitOfWork(sessions) as check:
            saved = check.projects.get_owned(project.id, project.owner_id)
            assert saved is not None
            assert saved.name == "Весна"
            assert saved.settings == settings
            assert saved.updated_at.replace(tzinfo=None) == changed_at.replace(tzinfo=None)
            assert check.subjects.get(project.id, subject.id) == subject
    finally:
        with migrated_engine.begin() as connection:
            connection.execute(delete(UserRow).where(UserRow.id == project.owner_id))


def test_touch_project_rejects_another_owner(uow: SqlUnitOfWork) -> None:
    project = stored_project(uow)

    with uow, pytest.raises(NotFound):
        uow.projects.touch(project.id, UserId(uuid4()), NOW)


# --- Дисциплины


def test_subjects_are_listed_by_name_within_project(uow: SqlUnitOfWork) -> None:
    project, other = stored_project(uow).id, stored_project(uow).id
    physics = stored_subject(uow, project, "Физика")
    math = stored_subject(uow, project, "алгебра")
    stored_subject(uow, other, "Чужая")

    with uow:
        assert uow.subjects.list_in_project(project) == [math, physics]
        assert uow.subjects.get(project, physics.id) == physics
        assert uow.subjects.get(other, physics.id) is None  # NF_Security_2


def test_subject_name_is_unique_in_project_regardless_of_case(uow: SqlUnitOfWork) -> None:
    project, other = stored_project(uow).id, stored_project(uow).id
    stored_subject(uow, project, "Математика")
    stored_subject(uow, other, "Математика")  # в другом проекте можно

    with uow, pytest.raises(SubjectNameTaken) as error:
        uow.subjects.add(Subject(id=SubjectId(uuid4()), project_id=project, name="математика"))

    assert error.value.details == {"field": "name"}


def test_subject_names_are_unique_after_unicode_casefold(uow: SqlUnitOfWork) -> None:
    project = stored_project(uow).id
    stored_subject(uow, project, "Straße")

    with uow, pytest.raises(SubjectNameTaken):
        uow.subjects.add(Subject(id=SubjectId(uuid4()), project_id=project, name="STRASSE"))


def test_subject_cannot_be_renamed_to_a_taken_name(uow: SqlUnitOfWork) -> None:
    project = stored_project(uow).id
    stored_subject(uow, project, "Математика")
    physics = stored_subject(uow, project, "Физика")

    with uow, pytest.raises(SubjectNameTaken):
        physics.rename("МАТЕМАТИКА")
        uow.subjects.save(physics)


def test_subject_of_another_project_is_neither_saved_nor_deleted(uow: SqlUnitOfWork) -> None:
    project, other = stored_project(uow).id, stored_project(uow).id
    subject = stored_subject(uow, project)

    with uow, pytest.raises(NotFound):
        uow.subjects.save(Subject(id=subject.id, project_id=other, name="Захвачена"))
    with uow, pytest.raises(NotFound):
        uow.subjects.delete(other, subject.id)

    with uow:
        assert uow.subjects.get(project, subject.id) == subject


def test_subject_in_use_is_not_deleted_and_users_are_named(uow: SqlUnitOfWork) -> None:
    project = stored_project(uow).id
    math, physics = stored_subject(uow, project), stored_subject(uow, project, "Физика")
    petrova = stored_teacher(uow, a_teacher(project, math, "Петрова А. В."))

    with uow, pytest.raises(SubjectInUse) as error:
        uow.subjects.delete(project, math.id)

    assert error.value.details == {
        "teachers": [{"id": str(petrova.id), "full_name": "Петрова А. В."}]
    }
    with uow:
        uow.subjects.delete(project, physics.id)
        uow.commit()
    with uow:
        assert uow.subjects.list_in_project(project) == [math]


# --- Преподаватели


def test_teacher_is_stored_with_all_parts(uow: SqlUnitOfWork) -> None:
    project = stored_project(uow).id
    math, physics = stored_subject(uow, project), stored_subject(uow, project, "Физика")
    teacher = Teacher(
        id=TeacherId(uuid4()),
        project_id=project,
        full_name="Иванов И. И.",
        capabilities=(
            Capability(physics.id, LessonType.LAB),
            Capability(physics.id, LessonType.PRACTICE),
            Capability(math.id, LessonType.LECTURE),
        ),
        availability=(MONDAY_MORNING, WeeklyInterval(Week.EVEN, Weekday.MONDAY, time(9), time(18))),
        preferences=(ANY_TUESDAY,),
    )
    stored_teacher(uow, teacher)

    with uow:
        assert uow.teachers.get(project, teacher.id) == teacher
        assert uow.teachers.get_for_update(project, teacher.id) == teacher


def test_teachers_are_listed_by_name_with_their_parts(uow: SqlUnitOfWork) -> None:
    project = stored_project(uow).id
    math = stored_subject(uow, project)
    sidorov = stored_teacher(uow, a_teacher(project, math, "Сидоров"))
    ivanov = stored_teacher(uow, a_teacher(project, math, "иванов"))

    with uow:
        assert uow.teachers.list_in_project(project) == [ivanov, sidorov]


def test_saving_teacher_replaces_parts(uow: SqlUnitOfWork, db_connection: Connection) -> None:
    project = stored_project(uow).id
    math, physics = stored_subject(uow, project), stored_subject(uow, project, "Физика")
    teacher = stored_teacher(uow, a_teacher(project, math))

    with uow:
        stored = uow.teachers.get_for_update(project, teacher.id)
        assert stored is not None
        stored.rename("Петрова-Сидорова А. В.")
        stored.change_capabilities([Capability(physics.id, LessonType.LAB)])
        stored.change_availability([ANY_TUESDAY])
        stored.change_preferences([])
        uow.teachers.save(stored)
        uow.commit()

    with uow:
        assert uow.teachers.get(project, teacher.id) == stored
    assert count(db_connection, TeacherCapabilityRow) == 1
    assert count(db_connection, TeacherAvailabilityRow) == 1


def test_teacher_cannot_use_subject_of_another_project(uow: SqlUnitOfWork) -> None:
    project, other = stored_project(uow).id, stored_project(uow).id
    foreign = stored_subject(uow, other)

    with uow, pytest.raises(InvalidValue) as error:
        uow.teachers.add(a_teacher(project, foreign))

    assert error.value.field == "capabilities"


def test_teacher_of_another_project_is_not_saved(uow: SqlUnitOfWork) -> None:
    project, other = stored_project(uow).id, stored_project(uow).id
    teacher = stored_teacher(uow, a_teacher(project, stored_subject(uow, project)))
    moved = a_teacher(other, stored_subject(uow, other), "Захвачен")
    moved.id = teacher.id

    with uow, pytest.raises(NotFound):
        uow.teachers.save(moved)

    with uow:
        assert uow.teachers.get(project, teacher.id) == teacher


def test_deleted_teacher_takes_parts_along(uow: SqlUnitOfWork, db_connection: Connection) -> None:
    project, other = stored_project(uow).id, stored_project(uow).id
    teacher = stored_teacher(uow, a_teacher(project, stored_subject(uow, project)))

    with uow, pytest.raises(NotFound):
        uow.teachers.delete(other, teacher.id)
    with uow:
        uow.teachers.delete(project, teacher.id)
        uow.commit()

    with uow:
        assert uow.teachers.get(project, teacher.id) is None
    assert count(db_connection, TeacherCapabilityRow) == 0
    assert count(db_connection, TeacherAvailabilityRow) == 0


# --- Группы и подгруппы


def test_group_is_stored_with_subgroups(uow: SqlUnitOfWork) -> None:
    project = stored_project(uow).id
    group = stored_group(uow, a_group(project, "301", a_subgroup("301-2"), a_subgroup("301-1")))
    empty = stored_group(uow, a_group(project, "302"))

    with uow:
        assert uow.groups.get(project, group.id) == group
        assert uow.groups.get_for_update(project, group.id) == group
        assert uow.groups.list_in_project(project) == [group, empty]


def test_group_name_is_unique_in_project_regardless_of_case(uow: SqlUnitOfWork) -> None:
    project = stored_project(uow).id
    stored_group(uow, a_group(project, "301а"))

    with uow, pytest.raises(GroupNameTaken):
        uow.groups.add(a_group(project, "301А"))


def test_group_names_are_unique_after_unicode_casefold(uow: SqlUnitOfWork) -> None:
    project = stored_project(uow).id
    stored_group(uow, a_group(project, "Straße"))

    with uow, pytest.raises(GroupNameTaken):
        uow.groups.add(a_group(project, "STRASSE"))


def test_saving_group_keeps_subgroup_ids(uow: SqlUnitOfWork) -> None:
    project = stored_project(uow).id
    first, second = a_subgroup("301-1"), a_subgroup("301-2")
    group = stored_group(uow, a_group(project, "301", first, second))
    third = a_subgroup("301-2")  # название освободилось вместе со второй подгруппой

    with uow:
        stored = uow.groups.get_for_update(project, group.id)
        assert stored is not None
        stored.rename("301 (бакалавры)")
        stored.change_subgroup(Subgroup(id=first.id, name="301-1", student_count=10))
        stored.remove_subgroup(second.id)
        stored.add_subgroup(third)
        uow.groups.save(stored)
        uow.commit()

    with uow:
        reloaded = uow.groups.get(project, group.id)
    assert reloaded == stored
    assert reloaded is not None
    assert {subgroup.id for subgroup in reloaded.subgroups} == {first.id, third.id}


def test_swapping_subgroup_names_preserves_their_ids(uow: SqlUnitOfWork) -> None:
    project = stored_project(uow).id
    first, second = a_subgroup("301-А"), a_subgroup("301-Б")
    group = stored_group(uow, a_group(project, "301", first, second))
    swapped = StudentGroup(
        id=group.id,
        project_id=project,
        name=group.name,
        student_count=group.student_count,
        subgroups=(
            Subgroup(id=first.id, name=second.name, student_count=first.student_count),
            Subgroup(id=second.id, name=first.name, student_count=second.student_count),
        ),
    )

    with uow:
        assert uow.groups.get_for_update(project, group.id) is not None
        uow.groups.save(swapped)
        uow.commit()

    with uow:
        assert uow.groups.get(project, group.id) == swapped


def test_group_of_another_project_is_neither_saved_nor_deleted(uow: SqlUnitOfWork) -> None:
    project, other = stored_project(uow).id, stored_project(uow).id
    group = stored_group(uow, a_group(project))
    moved = StudentGroup(id=group.id, project_id=other, name="Захвачена", student_count=30)

    with uow, pytest.raises(NotFound):
        uow.groups.save(moved)
    with uow, pytest.raises(NotFound):
        uow.groups.delete(other, group.id)

    with uow:
        assert uow.groups.get(project, group.id) == group


def test_deleted_group_takes_subgroups_along(uow: SqlUnitOfWork, db_connection: Connection) -> None:
    project = stored_project(uow).id
    group = stored_group(uow, a_group(project, "301", a_subgroup("301-1")))

    with uow:
        uow.groups.delete(project, group.id)
        uow.commit()

    assert count(db_connection, SubgroupRow) == 0


# --- Проект целиком


def test_deleting_project_removes_its_academic_data(
    uow: SqlUnitOfWork, db_connection: Connection
) -> None:
    project = stored_project(uow)
    subject = stored_subject(uow, project.id)
    stored_teacher(uow, a_teacher(project.id, subject))
    stored_group(uow, a_group(project.id, "301", a_subgroup("301-1")))

    # Занятая дисциплина уходит вместе с проектом: NO ACTION проверяется после каскада
    with uow:
        uow.projects.delete(project.id, project.owner_id)
        uow.commit()

    for table in (SubjectRow, TeacherRow, TeacherCapabilityRow, StudentGroupRow, SubgroupRow):
        assert count(db_connection, table) == 0
