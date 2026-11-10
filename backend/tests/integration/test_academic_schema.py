"""Ограничения схемы учебных данных, которые страхуют сущности в базе."""

from datetime import UTC, datetime, time
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.persistence.models import (
    ProjectRow,
    StreamRow,
    StudentGroupRow,
    SubgroupRow,
    SubjectRow,
    TeacherAvailabilityRow,
    TeacherCapabilityRow,
    TeacherRow,
    UserRow,
    WorkloadRow,
)

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)


def a_project(session: Session) -> UUID:
    user = UserRow(id=uuid4(), email=f"{uuid4()}@mail.ru", password_hash="h", created_at=NOW)
    project = ProjectRow(
        id=uuid4(),
        owner_id=user.id,
        name="Осень",
        odd_week_days=["MONDAY"],
        even_week_days=["MONDAY"],
        time_mode="HOUR_START",
        duration_mode="INDIVIDUAL",
        created_at=NOW,
        updated_at=NOW,
    )
    session.add(user)
    session.flush()
    session.add(project)
    session.flush()
    return project.id


def test_teacher_cannot_teach_subject_of_another_project(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        project, other = a_project(session), a_project(session)
        teacher = TeacherRow(id=uuid4(), project_id=project, full_name="Петрова")
        foreign = SubjectRow(id=uuid4(), project_id=other, name="Математика")
        session.add_all([teacher, foreign])
        session.flush()
        session.add(
            TeacherCapabilityRow(
                project_id=project, teacher_id=teacher.id, subject_id=foreign.id, lesson_type="LAB"
            )
        )

        with pytest.raises(IntegrityError, match="fk_teacher_capabilities_subject"):
            session.flush()


def test_subgroup_cannot_belong_to_group_of_another_project(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        project, other = a_project(session), a_project(session)
        group = StudentGroupRow(id=uuid4(), project_id=other, name="301", student_count=24)
        session.add(group)
        session.flush()
        session.add(
            SubgroupRow(
                id=uuid4(), project_id=project, group_id=group.id, name="301-1", student_count=12
            )
        )

        with pytest.raises(IntegrityError, match="fk_subgroups_group"):
            session.flush()


def test_subgroup_names_are_unique_in_group_regardless_of_case(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        project = a_project(session)
        group = StudentGroupRow(id=uuid4(), project_id=project, name="301", student_count=24)
        session.add(group)
        session.flush()
        for name in ("301-a", "301-A"):
            session.add(
                SubgroupRow(
                    id=uuid4(), project_id=project, group_id=group.id, name=name, student_count=6
                )
            )

        with pytest.raises(IntegrityError, match="uq_subgroups_group_id_name"):
            session.flush()


@pytest.mark.parametrize(
    ("week", "start", "end", "constraint"),
    [
        ("ODD", time(12), time(9), "ck_teacher_availability_ends_after_start"),
        ("BOTH", time(9), time(12), "ck_teacher_availability_week_known"),
    ],
)
def test_interval_columns_are_checked(
    session_factory: sessionmaker[Session], week: str, start: time, end: time, constraint: str
) -> None:  # F_Valid_1
    with session_factory() as session:
        teacher = TeacherRow(id=uuid4(), project_id=a_project(session), full_name="Петрова")
        session.add(teacher)
        session.flush()
        session.add(
            TeacherAvailabilityRow(
                teacher_id=teacher.id, week=week, day="MONDAY", start_time=start, end_time=end
            )
        )

        with pytest.raises(IntegrityError, match=constraint):
            session.flush()


def a_workload(project: UUID, subject: UUID, **overrides: object) -> WorkloadRow:
    values: dict[str, object] = {
        "id": uuid4(),
        "project_id": project,
        "subject_id": subject,
        "lesson_type": "LECTURE",
        "format": "ONSITE",
        "occurrences_per_cycle": 2,
        "required_teacher_count": 1,
    }
    return WorkloadRow(**(values | overrides))


@pytest.mark.parametrize(
    ("targets", "overrides", "constraint"),
    [
        ((), {}, "ck_workloads_one_target"),
        (("group", "stream"), {}, "ck_workloads_one_target"),
        (("group",), {"required_teacher_count": 2}, "ck_workloads_single_teacher_unless_lab"),
    ],
    ids=["no target", "two targets", "two teachers at lecture"],
)
def test_workload_columns_are_checked(
    session_factory: sessionmaker[Session],
    targets: tuple[str, ...],
    overrides: dict[str, object],
    constraint: str,
) -> None:  # HLD 9.8
    with session_factory() as session:
        project = a_project(session)
        subject = SubjectRow(id=uuid4(), project_id=project, name="Физика")
        group = StudentGroupRow(id=uuid4(), project_id=project, name="301", student_count=24)
        stream = StreamRow(id=uuid4(), project_id=project, name="Поток")
        session.add_all([subject, group, stream])
        session.flush()
        ids = {"group": {"group_id": group.id}, "stream": {"stream_id": stream.id}}
        target = {key: value for name in targets for key, value in ids[name].items()}
        session.add(a_workload(project, subject.id, **target, **overrides))

        with pytest.raises(IntegrityError, match=constraint):
            session.flush()


def test_workload_cannot_target_subgroup_of_another_project(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        project, other = a_project(session), a_project(session)
        subject = SubjectRow(id=uuid4(), project_id=project, name="Физика")
        group = StudentGroupRow(id=uuid4(), project_id=other, name="301", student_count=24)
        session.add_all([subject, group])
        session.flush()
        subgroup = SubgroupRow(
            id=uuid4(), project_id=other, group_id=group.id, name="301-1", student_count=12
        )
        session.add(subgroup)
        session.flush()
        session.add(a_workload(project, subject.id, subgroup_id=subgroup.id))

        with pytest.raises(IntegrityError, match="fk_workloads_subgroup"):
            session.flush()
