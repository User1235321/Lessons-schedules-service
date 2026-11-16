from dataclasses import FrozenInstanceError, replace
from datetime import time
from uuid import uuid4

import pytest

from app.domain.projects.settings import ProjectSettings
from app.domain.scheduling.problem import (
    OptimizationCriterionSnapshot,
    ScheduleProblem,
    WorkloadSnapshot,
    WorkloadTarget,
    WorkloadTargetKind,
)
from app.domain.scheduling.resources import (
    GroupSnapshot,
    RoomSnapshot,
    RoomType,
    StreamSnapshot,
    SubgroupSnapshot,
    SubjectSnapshot,
    TeacherSnapshot,
    TeachingCapability,
    WeeklyWindow,
)
from app.domain.scheduling.schedule import LessonFormat
from app.domain.shared.errors import InvalidValue
from app.domain.shared.week import Weekday


def available() -> WeeklyWindow:
    return WeeklyWindow("ANY", Weekday.MONDAY, time(9), time(18))


def test_snapshot_includes_all_solver_inputs() -> None:
    subject = SubjectSnapshot(uuid4(), "Физика")
    capability = TeachingCapability(subject.id, "LAB")
    teacher = TeacherSnapshot(uuid4(), "Иванов", (capability,), (available(),))
    room = RoomSnapshot(
        uuid4(), "Лаборатория", 30, RoomType.LABORATORY, (available(),), (capability,)
    )
    group = GroupSnapshot(uuid4(), "301", 20)
    subgroup = SubgroupSnapshot(uuid4(), group.id, "301-1", 10)
    stream = StreamSnapshot(uuid4(), "301 + 302", (group.id,))
    workload = WorkloadSnapshot(
        uuid4(),
        WorkloadTarget(WorkloadTargetKind.SUBGROUP, subgroup.id),
        subject.id,
        "LAB",
        LessonFormat.ONSITE,
        2,
        2,
        90,
    )
    criterion = OptimizationCriterionSnapshot("TEACHER_PREFERENCES", 1)
    settings = ProjectSettings.default()
    problem = ScheduleProblem(
        settings=settings,
        subjects=(subject,),
        teachers=(teacher,),
        rooms=(room,),
        groups=(group,),
        subgroups=(subgroup,),
        streams=(stream,),
        workloads=(workload,),
        optimization_criteria=(criterion,),
    )

    assert problem.settings == settings
    assert problem.teachers[0].capabilities == (capability,)
    assert problem.rooms[0].capacity == 30
    assert problem.subgroups[0].group_id == group.id
    assert problem.streams[0].group_ids == (group.id,)
    assert problem.workloads[0].required_teacher_count == 2
    assert problem.optimization_criteria == (criterion,)
    with pytest.raises(FrozenInstanceError):
        problem.workloads = ()


def test_local_input_invariants_reject_invalid_values() -> None:
    subject_id = uuid4()
    capability = TeachingCapability(subject_id, "LECTURE")
    window = available()

    with pytest.raises(InvalidValue):
        WeeklyWindow("ODD", Weekday.MONDAY, time(10), time(9))
    with pytest.raises(InvalidValue):
        TeacherSnapshot(uuid4(), "Иванов", (), (window,))
    with pytest.raises(InvalidValue):
        TeacherSnapshot(uuid4(), "Иванов", (capability,), ())
    with pytest.raises(InvalidValue):
        RoomSnapshot(uuid4(), "101", 0, RoomType.LECTURE, (window,))
    with pytest.raises(InvalidValue):
        GroupSnapshot(uuid4(), "301", 0)
    with pytest.raises(InvalidValue):
        SubgroupSnapshot(uuid4(), uuid4(), "301-1", -1)


def test_workload_requires_correct_counts_and_duration() -> None:
    workload = WorkloadSnapshot(
        uuid4(),
        WorkloadTarget(WorkloadTargetKind.GROUP, uuid4()),
        uuid4(),
        "LECTURE",
        LessonFormat.REMOTE,
        2,
        1,
    )

    assert workload.duration_minutes is None
    for changes in (
        {"occurrences_per_cycle": 0},
        {"required_teacher_count": 0},
        {"required_teacher_count": 2},
        {"duration_minutes": -30},
    ):
        with pytest.raises(InvalidValue):
            replace(workload, **changes)


def test_snapshot_detects_duplicate_ids_and_priorities() -> None:
    group = GroupSnapshot(uuid4(), "301", 20)
    criterion = OptimizationCriterionSnapshot("STUDENT_GAPS", 1)
    problem = ScheduleProblem(ProjectSettings.default(), groups=(group,))

    with pytest.raises(InvalidValue):
        replace(problem, groups=(group, group))
    with pytest.raises(InvalidValue):
        replace(
            problem,
            optimization_criteria=(
                criterion,
                OptimizationCriterionSnapshot("TEACHER_GAPS", 1),
            ),
        )
    with pytest.raises(InvalidValue):
        replace(problem, optimization_criteria=(criterion, criterion))
    inactive = OptimizationCriterionSnapshot("TEACHER_GAPS", 1, is_active=False)
    assert replace(problem, optimization_criteria=(criterion, inactive))


def test_subgroups_cannot_exceed_their_parent_group() -> None:
    group = GroupSnapshot(uuid4(), "301", 20)
    subgroup = SubgroupSnapshot(uuid4(), group.id, "301-1", 21)

    with pytest.raises(InvalidValue):
        ScheduleProblem(ProjectSettings.default(), groups=(group,), subgroups=(subgroup,))


def test_logical_conflicts_are_not_rejected_as_input_errors() -> None:
    workload = WorkloadSnapshot(
        uuid4(),
        WorkloadTarget(WorkloadTargetKind.GROUP, uuid4()),
        uuid4(),
        "LAB",
        LessonFormat.ONSITE,
        2,
        2,
        120,
    )
    problem = ScheduleProblem(ProjectSettings.default(), workloads=(workload,))

    assert problem.workloads == (workload,)
