from dataclasses import replace
from datetime import time
from uuid import UUID

import pytest

from app.domain.projects.settings import (
    DurationMode,
    ProjectSettings,
    StudyCycle,
    TimeMode,
)
from app.domain.scheduling.constraints import (
    ClockTimeParameters,
    ConstraintKind,
    ConstraintScope,
    ConstraintScopeKind,
    ExtraConstraintSnapshot,
)
from app.domain.scheduling.job import JobProgress, ResultMode, ResultOptions
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
from app.domain.scheduling.solver import SolverStatus
from app.domain.shared.week import Weekday
from app.scheduling.solver import FeasibleScheduleSolver

SUBJECT = UUID(int=1)
GROUP = UUID(int=2)
SECOND_GROUP = UUID(int=3)
TEACHER = UUID(int=4)
SECOND_TEACHER = UUID(int=5)
ROOM = UUID(int=6)
WORKLOAD = UUID(int=7)
SECOND_WORKLOAD = UUID(int=8)
LEFT = UUID(int=9)
RIGHT = UUID(int=10)
STREAM = UUID(int=11)
MONDAY = Weekday.MONDAY


class RecordingControl:
    def __init__(self, cancel_after: int | None = None) -> None:
        self.cancel_after = cancel_after
        self.polls = 0
        self.progress: list[JobProgress] = []

    def is_cancel_requested(self) -> bool:
        self.polls += 1
        return self.cancel_after is not None and self.polls > self.cancel_after

    def report_progress(self, progress: JobProgress) -> None:
        self.progress.append(progress)


def window(
    start: time = time(9),
    end: time = time(10),
    week: str = "ANY",
    day: Weekday = MONDAY,
) -> WeeklyWindow:
    return WeeklyWindow(week, day, start, end)


def settings(
    odd: tuple[Weekday, ...] = (MONDAY,),
    even: tuple[Weekday, ...] = (),
) -> ProjectSettings:
    return ProjectSettings(
        StudyCycle(odd, even),
        TimeMode.hour_start(),
        DurationMode.uniform(60),
    )


def teacher(
    identifier: UUID = TEACHER,
    lesson_type: str = "LECTURE",
    availability: tuple[WeeklyWindow, ...] = (window(),),
) -> TeacherSnapshot:
    return TeacherSnapshot(
        identifier,
        f"Преподаватель {identifier}",
        (TeachingCapability(SUBJECT, lesson_type),),
        availability,
    )


def workload(
    identifier: UUID = WORKLOAD,
    target: UUID = GROUP,
    kind: WorkloadTargetKind = WorkloadTargetKind.GROUP,
    lesson_type: str = "LECTURE",
    lesson_format: LessonFormat = LessonFormat.REMOTE,
    occurrences: int = 1,
    teacher_count: int = 1,
    duration: int | None = None,
) -> WorkloadSnapshot:
    return WorkloadSnapshot(
        identifier,
        WorkloadTarget(kind, target),
        SUBJECT,
        lesson_type,
        lesson_format,
        occurrences,
        teacher_count,
        duration,
    )


def problem(
    *,
    workloads: tuple[WorkloadSnapshot, ...] = (workload(),),
    teachers: tuple[TeacherSnapshot, ...] = (teacher(),),
    rooms: tuple[RoomSnapshot, ...] = (),
    groups: tuple[GroupSnapshot, ...] = (GroupSnapshot(GROUP, "П-101", 20),),
    subgroups: tuple[SubgroupSnapshot, ...] = (),
    streams: tuple[StreamSnapshot, ...] = (),
    project_settings: ProjectSettings | None = None,
) -> ScheduleProblem:
    return ScheduleProblem(
        settings=project_settings or settings(),
        subjects=(SubjectSnapshot(SUBJECT, "Физика"),),
        teachers=teachers,
        rooms=rooms,
        groups=groups,
        subgroups=subgroups,
        streams=streams,
        workloads=workloads,
    )


def solve(
    scheduling_problem: ScheduleProblem,
    options: ResultOptions | None = None,
    control: RecordingControl | None = None,
):
    return FeasibleScheduleSolver().solve(
        scheduling_problem, options or ResultOptions(), control or RecordingControl()
    )


def test_empty_workload_returns_empty_valid_variant() -> None:
    result = solve(problem(workloads=()))

    assert result.status is SolverStatus.SOLVED
    assert len(result.variants) == 1
    assert result.variants[0].entries == ()


def test_repeated_lessons_can_share_one_week_and_follow_each_other() -> None:
    availability = (window(time(9), time(11)),)
    source = problem(
        workloads=(workload(occurrences=2),),
        teachers=(teacher(availability=availability),),
        groups=(GroupSnapshot(GROUP, "П-101", 20, availability),),
    )

    result = solve(source)

    assert result.status is SolverStatus.SOLVED
    entries = result.variants[0].entries
    assert len(entries) == 2
    assert [entry.week for entry in entries] == ["ODD", "ODD"]
    assert [entry.start_time for entry in entries] == [time(9), time(10)]
    assert all(entry.workload_id == WORKLOAD for entry in entries)


def test_even_week_and_individual_duration_follow_project_time_model() -> None:
    availability = (window(time(9, 30), time(10, 45), "EVEN"),)
    project_settings = ProjectSettings(
        StudyCycle((), (MONDAY,)),
        TimeMode.step(30),
        DurationMode.individual(),
    )
    source = problem(
        project_settings=project_settings,
        workloads=(workload(duration=75),),
        teachers=(teacher(availability=availability),),
    )

    result = solve(source)
    entry = result.variants[0].entries[0]

    assert entry.week == "EVEN"
    assert (entry.start_time, entry.end_time) == (time(9, 30), time(10, 45))


def test_onsite_room_is_selected_by_type_capacity_and_availability() -> None:
    bad_capacity = RoomSnapshot(
        UUID(int=20), "Маленькая", 10, RoomType.LECTURE, (window(),)
    )
    wrong_type = RoomSnapshot(
        UUID(int=21), "Практическая", 40, RoomType.PRACTICE_UNIVERSAL, (window(),)
    )
    suitable = RoomSnapshot(ROOM, "Лекционная", 30, RoomType.LECTURE, (window(),))
    source = problem(
        workloads=(workload(lesson_format=LessonFormat.ONSITE),),
        rooms=(bad_capacity, wrong_type, suitable),
    )

    result = solve(source)
    entry = result.variants[0].entries[0]

    assert entry.room_id == ROOM
    assert entry.room_name == "Лекционная"


def test_room_specialization_is_required() -> None:
    capability = (TeachingCapability(SUBJECT, "LAB"),)
    room = RoomSnapshot(
        ROOM, "Лаборатория", 30, RoomType.LABORATORY, (window(),), capability
    )
    source = problem(
        workloads=(workload(lesson_type="LAB", lesson_format=LessonFormat.ONSITE),),
        teachers=(teacher(lesson_type="LAB"),),
        rooms=(room,),
    )

    assert solve(source).status is SolverStatus.SOLVED
    unsupported = replace(room, capabilities=(TeachingCapability(UUID(int=22), "LAB"),))
    assert solve(replace(source, rooms=(unsupported,))).status is SolverStatus.INFEASIBLE


def test_remote_lessons_do_not_require_or_reserve_a_room() -> None:
    result = solve(problem())
    entry = result.variants[0].entries[0]

    assert result.status is SolverStatus.SOLVED
    assert entry.lesson_format is LessonFormat.REMOTE
    assert entry.room_id is None
    assert entry.room_name is None


def test_unqualified_teacher_is_rejected_with_workload_diagnostic() -> None:
    source = problem(teachers=(teacher(lesson_type="PRACTICE"),))

    result = solve(source)

    assert result.status is SolverStatus.INFEASIBLE
    assert result.diagnostics[0].workload_ids == (WORKLOAD,)


def test_subgroups_can_study_simultaneously_if_teachers_differ() -> None:
    left = SubgroupSnapshot(LEFT, GROUP, "1", 10)
    right = SubgroupSnapshot(RIGHT, GROUP, "2", 10)
    source = problem(
        workloads=(
            workload(WORKLOAD, LEFT, WorkloadTargetKind.SUBGROUP),
            workload(SECOND_WORKLOAD, RIGHT, WorkloadTargetKind.SUBGROUP),
        ),
        teachers=(teacher(), teacher(SECOND_TEACHER)),
        subgroups=(left, right),
    )

    result = solve(source)

    assert result.status is SolverStatus.SOLVED
    entries = result.variants[0].entries
    assert len(entries) == 2
    assert {entry.start_time for entry in entries} == {time(9)}
    assert len({entry.teachers[0].teacher_id for entry in entries}) == 2


def test_parent_availability_also_limits_subgroup_placements() -> None:
    source = problem(
        workloads=(workload(target=LEFT, kind=WorkloadTargetKind.SUBGROUP),),
        teachers=(teacher(availability=(window(time(9), time(11)),)),),
        groups=(GroupSnapshot(GROUP, "П-101", 20, (window(time(10), time(11)),)),),
        subgroups=(SubgroupSnapshot(LEFT, GROUP, "1", 10),),
    )

    result = solve(source)

    assert result.variants[0].entries[0].start_time == time(10)


def test_stream_and_its_group_cannot_overlap() -> None:
    source = problem(
        workloads=(
            workload(WORKLOAD, STREAM, WorkloadTargetKind.STREAM),
            workload(SECOND_WORKLOAD, GROUP),
        ),
        teachers=(teacher(), teacher(SECOND_TEACHER)),
        groups=(
            GroupSnapshot(GROUP, "П-101", 20),
            GroupSnapshot(SECOND_GROUP, "П-102", 15),
        ),
        streams=(StreamSnapshot(STREAM, "Общий поток", (GROUP, SECOND_GROUP)),),
    )

    assert solve(source).status is SolverStatus.INFEASIBLE


def test_group_lesson_cannot_overlap_its_subgroup_lesson() -> None:
    source = problem(
        workloads=(
            workload(WORKLOAD, GROUP),
            workload(SECOND_WORKLOAD, LEFT, WorkloadTargetKind.SUBGROUP),
        ),
        teachers=(teacher(), teacher(SECOND_TEACHER)),
        subgroups=(SubgroupSnapshot(LEFT, GROUP, "1", 10),),
    )

    assert solve(source).status is SolverStatus.INFEASIBLE


def test_stream_room_must_hold_all_participating_students() -> None:
    smaller = RoomSnapshot(
        UUID(int=20), "Малая", 30, RoomType.LECTURE, (window(),)
    )
    larger = RoomSnapshot(ROOM, "Поточная", 40, RoomType.LECTURE, (window(),))
    source = problem(
        workloads=(workload(
            target=STREAM,
            kind=WorkloadTargetKind.STREAM,
            lesson_format=LessonFormat.ONSITE,
        ),),
        groups=(
            GroupSnapshot(GROUP, "П-101", 20),
            GroupSnapshot(SECOND_GROUP, "П-102", 15),
        ),
        streams=(StreamSnapshot(STREAM, "Поток", (GROUP, SECOND_GROUP)),),
        rooms=(smaller, larger),
    )

    result = solve(source)

    assert result.status is SolverStatus.SOLVED
    assert result.variants[0].entries[0].room_id == ROOM


def test_lab_requires_multiple_distinct_teachers_in_one_room() -> None:
    lab = RoomSnapshot(ROOM, "Лаборатория", 30, RoomType.LABORATORY, (window(),))
    source = problem(
        workloads=(workload(
            lesson_type="LAB", lesson_format=LessonFormat.ONSITE, teacher_count=2
        ),),
        teachers=(teacher(TEACHER, "LAB"), teacher(SECOND_TEACHER, "LAB")),
        rooms=(lab,),
    )

    result = solve(source)
    entry = result.variants[0].entries[0]

    assert result.status is SolverStatus.SOLVED
    assert {assignment.teacher_id for assignment in entry.teachers} == {
        TEACHER, SECOND_TEACHER
    }
    assert entry.room_id == ROOM


def test_shared_room_cannot_be_used_for_two_simultaneous_lessons() -> None:
    room = RoomSnapshot(ROOM, "Лекционная", 30, RoomType.LECTURE, (window(),))
    source = problem(
        workloads=(
            workload(WORKLOAD, GROUP, lesson_format=LessonFormat.ONSITE),
            workload(SECOND_WORKLOAD, SECOND_GROUP, lesson_format=LessonFormat.ONSITE),
        ),
        teachers=(teacher(), teacher(SECOND_TEACHER)),
        rooms=(room,),
        groups=(
            GroupSnapshot(GROUP, "П-101", 20),
            GroupSnapshot(SECOND_GROUP, "П-102", 20),
        ),
    )

    assert solve(source).status is SolverStatus.INFEASIBLE


def test_backtracking_finds_solution_after_rejecting_first_assignment() -> None:
    source = problem(
        workloads=(
            workload(WORKLOAD, lesson_type="LECTURE"),
            workload(SECOND_WORKLOAD, lesson_type="PRACTICE"),
        ),
        teachers=(
            teacher(TEACHER, "LECTURE", (window(time(9), time(11)),)),
            teacher(SECOND_TEACHER, "PRACTICE", (window(),)),
        ),
    )

    result = solve(source)

    assert result.status is SolverStatus.SOLVED
    starts = {
        entry.workload_id: entry.start_time for entry in result.variants[0].entries
    }
    assert starts == {WORKLOAD: time(10), SECOND_WORKLOAD: time(9)}


def test_top_n_contains_distinct_feasible_arrangements() -> None:
    availability = (window(time(9), time(12)),)
    source = problem(teachers=(teacher(availability=availability),))

    result = solve(source, ResultOptions(ResultMode.TOP_N, 3))

    assert result.status is SolverStatus.SOLVED
    assert len(result.variants) == 3
    assert {
        variant.entries[0].start_time for variant in result.variants
    } == {time(9), time(10), time(11)}


def test_missing_participants_are_reported_as_infeasible() -> None:
    source = problem(workloads=(workload(target=UUID(int=99)),))

    result = solve(source)

    assert result.status is SolverStatus.INFEASIBLE
    assert result.diagnostics[0].workload_ids == (WORKLOAD,)


def test_cancellation_is_checked_inside_candidate_generation() -> None:
    source = problem()
    control = RecordingControl(cancel_after=4)

    result = solve(source, control=control)

    assert result.status is SolverStatus.CANCELLED
    assert result.variants == ()


def test_unsupported_extra_constraints_and_optimization_are_not_ignored() -> None:
    source = problem()
    constraint = ExtraConstraintSnapshot(
        UUID(int=100),
        ConstraintKind.MIN_START_TIME,
        ConstraintScope(ConstraintScopeKind.PROJECT),
        ClockTimeParameters(time(9)),
    )
    with pytest.raises(NotImplementedError, match="#67"):
        solve(replace(source, constraints=(constraint,)))
    with pytest.raises(NotImplementedError, match="#68"):
        solve(replace(
            source,
            optimization_criteria=(OptimizationCriterionSnapshot("STUDENT_GAPS", 1),),
        ))
