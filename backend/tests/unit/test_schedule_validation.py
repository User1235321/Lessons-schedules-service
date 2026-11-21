from dataclasses import replace
from datetime import UTC, datetime, time
from uuid import UUID

import pytest

from app.domain.projects.settings import DurationMode, ProjectSettings, TimeMode
from app.domain.scheduling.constraints import (
    AllowedDaysParameters,
    ClockTimeParameters,
    ConstraintKind,
    ConstraintParameters,
    ConstraintScope,
    ConstraintScopeKind,
    EveryWeekParameters,
    ExtraConstraintSnapshot,
    FixedDayParameters,
    MinimumGapParameters,
    RelatedWorkloadParameters,
    TimeRangeParameters,
)
from app.domain.scheduling.problem import (
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
    TeacherSnapshot,
    TeachingCapability,
    WeeklyWindow,
)
from app.domain.scheduling.schedule import (
    LessonFormat,
    Schedule,
    ScheduleEntry,
    ScheduleSource,
    TeacherAssignment,
)
from app.domain.scheduling.validation import validate_schedule
from app.domain.shared.ids import JobId, ProjectId, ScheduleEntryId, ScheduleId
from app.domain.shared.week import Weekday

MONDAY = Weekday.MONDAY
TUESDAY = Weekday.TUESDAY
PARENT = UUID(int=1)
LEFT = UUID(int=2)
RIGHT = UUID(int=3)
OTHER_GROUP = UUID(int=4)
STREAM = UUID(int=5)
FIRST = UUID(int=6)
SECOND = UUID(int=7)
TEACHER = UUID(int=8)
ROOM = UUID(int=9)
SUBJECT = UUID(int=10)


def lesson(workload_id: UUID = FIRST, start: int = 9, **changes) -> ScheduleEntry:
    return replace(
        ScheduleEntry(
            id=ScheduleEntryId(workload_id),
            workload_id=workload_id,
            week="ODD",
            weekday=MONDAY,
            start_time=time(start),
            end_time=time(start + 1),
        ),
        **changes,
    )


def schedule(*entries: ScheduleEntry) -> Schedule:
    return Schedule(
        id=ScheduleId(UUID(int=30)),
        project_id=ProjectId(UUID(int=31)),
        entries=entries,
        source=ScheduleSource.GENERATED,
        job_id=JobId(UUID(int=32)),
        result_index=1,
        criterion_scores=(),
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def problem() -> ScheduleProblem:
    return ScheduleProblem(
        settings=replace(
            ProjectSettings.default(),
            duration_mode=DurationMode.uniform(60),
            time_mode=TimeMode.step(30),
        ),
        groups=(GroupSnapshot(PARENT, "1", 25), GroupSnapshot(OTHER_GROUP, "2", 20)),
        subgroups=(
            SubgroupSnapshot(LEFT, PARENT, "1A", 12),
            SubgroupSnapshot(RIGHT, PARENT, "1B", 13),
        ),
        streams=(StreamSnapshot(STREAM, "1+2", (PARENT, OTHER_GROUP)),),
        workloads=tuple(
            WorkloadSnapshot(
                identifier,
                WorkloadTarget(WorkloadTargetKind.SUBGROUP, subgroup),
                SUBJECT,
                "LECTURE",
                LessonFormat.REMOTE,
                1,
                1,
            )
            for identifier, subgroup in ((FIRST, LEFT), (SECOND, RIGHT))
        ),
    )


def test_participant_overlap_respects_subgroups_streams_and_half_open_intervals(
    problem: ScheduleProblem,
) -> None:
    left, right = problem.workloads
    concurrent = schedule(lesson(FIRST), lesson(SECOND))
    assert "GROUP_OVERLAP" not in {c.code for c in validate_schedule(concurrent, problem)}
    for target in (
        WorkloadTarget(WorkloadTargetKind.SUBGROUP, LEFT),
        WorkloadTarget(WorkloadTargetKind.GROUP, PARENT),
        WorkloadTarget(WorkloadTargetKind.STREAM, STREAM),
    ):
        scoped = replace(problem, workloads=(left, replace(right, target=target)))
        group_conflicts = [
            c for c in validate_schedule(concurrent, scoped) if c.code == "GROUP_OVERLAP"
        ]
        assert len(group_conflicts) == 1
        assert group_conflicts[0].entry_ids == (FIRST, SECOND)
        for other in (lesson(SECOND, 10), lesson(SECOND, week="EVEN")):
            codes = {c.code for c in validate_schedule(schedule(lesson(), other), scoped)}
            assert "GROUP_OVERLAP" not in codes


def test_group_subgroup_and_stream_availability(problem: ScheduleProblem) -> None:
    parent, other = problem.groups
    left, right = problem.subgroups
    unavailable = (WeeklyWindow("ANY", MONDAY, time(10), time(12)),)
    available = (WeeklyWindow("ANY", MONDAY, time(9), time(10)),)
    first, second = problem.workloads
    problem = replace(
        problem,
        groups=(
            replace(parent, availability=unavailable),
            replace(other, availability=unavailable),
        ),
        subgroups=(replace(left, availability=unavailable), replace(right, availability=available)),
        workloads=(
            first,
            replace(second, target=WorkloadTarget(WorkloadTargetKind.STREAM, STREAM)),
        ),
    )
    conflicts = validate_schedule(schedule(lesson(), lesson(SECOND)), problem)
    unavailable_ids = {
        (item.entry_ids[0], item.details["participant_id"])
        for item in conflicts
        if item.code == "GROUP_UNAVAILABLE"
    }
    assert unavailable_ids == {
        (FIRST, str(PARENT)),
        (FIRST, str(LEFT)),
        (SECOND, str(PARENT)),
        (SECOND, str(OTHER_GROUP)),
    }


def test_resource_availability_combines_adjacent_windows(problem: ScheduleProblem) -> None:
    window = WeeklyWindow("ANY", MONDAY, time(9), time(9, 30))
    rest = WeeklyWindow("ODD", MONDAY, time(9, 30), time(10))
    capability = (TeachingCapability(SUBJECT, "LECTURE"),)
    teacher = TeacherSnapshot(TEACHER, "Аня", capability, (window, rest))
    problem = replace(problem, teachers=(teacher,))
    entries = schedule(
        lesson(teachers=(TeacherAssignment("Аня", TEACHER),)),
        lesson(SECOND, week="EVEN", teachers=(TeacherAssignment("Аня", TEACHER),)),
    )
    conflicts = validate_schedule(entries, problem)
    assert [item.entry_ids for item in conflicts if item.code == "TEACHER_UNAVAILABLE"] == [
        (SECOND,),
    ]


def test_room_teacher_timing_and_workload_conflicts(problem: ScheduleProblem) -> None:
    availability = (WeeklyWindow("EVEN", MONDAY, time(9), time(10)),)
    capability = (TeachingCapability(UUID(int=11), "PRACTICE"),)
    first, second = problem.workloads
    problem = replace(
        problem,
        rooms=(
            RoomSnapshot(ROOM, "Зал", 10, RoomType.PRACTICE_SPECIALIZED, availability, capability),
        ),
        teachers=(TeacherSnapshot(TEACHER, "Аня", capability, availability),),
        workloads=(replace(first, occurrences_per_cycle=2), second),
    )
    invalid = lesson(
        weekday=Weekday.SUNDAY,
        start_time=time(9, 15),
        end_time=time(11),
        lesson_format=LessonFormat.ONSITE,
        room_id=ROOM,
        teachers=(TeacherAssignment("Аня", TEACHER), TeacherAssignment("Кирилл")),
    )
    codes = {c.code for c in validate_schedule(schedule(invalid, lesson(SECOND)), problem)}
    assert {
        "NON_STUDY_DAY",
        "START_TIME_STEP",
        "LESSON_DURATION",
        "TEACHER_COUNT",
        "TEACHER_UNAVAILABLE",
        "TEACHER_NOT_QUALIFIED",
        "ROOM_UNAVAILABLE",
        "ROOM_TYPE",
        "ROOM_SPECIALIZATION",
        "ROOM_CAPACITY_CONFLICT",
        "WORKLOAD_OCCURRENCES",
    } <= codes
    remote = replace(invalid, lesson_format=LessonFormat.REMOTE, room_id=None)
    assert not any(c.code.startswith("ROOM_") for c in validate_schedule(schedule(remote), problem))


@pytest.mark.parametrize(
    ("room_type", "lesson_type", "requires_capabilities"),
    [
        (RoomType.LECTURE, "LECTURE", False),
        (RoomType.PRACTICE_UNIVERSAL, "PRACTICE", False),
        (RoomType.PRACTICE_SPECIALIZED, "PRACTICE", True),
        (RoomType.LABORATORY, "LAB", True),
    ],
)
def test_room_specialization_rule_matches_generation(
    problem: ScheduleProblem,
    room_type: RoomType,
    lesson_type: str,
    requires_capabilities: bool,
) -> None:
    available = (WeeklyWindow("ANY", MONDAY, time(9), time(10)),)
    room = RoomSnapshot(ROOM, "Аудитория", 30, room_type, available)
    workload = replace(
        problem.workloads[0], lesson_type=lesson_type, lesson_format=LessonFormat.ONSITE
    )
    source = replace(problem, workloads=(workload,), rooms=(room,))
    entry = lesson(lesson_type=lesson_type, lesson_format=LessonFormat.ONSITE, room_id=ROOM)

    missing = validate_schedule(schedule(entry), source)
    assert ("ROOM_SPECIALIZATION" in {c.code for c in missing}) is requires_capabilities

    if requires_capabilities:
        supported_room = replace(
            room, capabilities=(TeachingCapability(SUBJECT, lesson_type),)
        )
        supported = validate_schedule(schedule(entry), replace(source, rooms=(supported_room,)))
        assert "ROOM_SPECIALIZATION" not in {c.code for c in supported}


def test_lab_count_individual_duration_and_excess_occurrences(problem: ScheduleProblem) -> None:
    first, second = problem.workloads
    problem = replace(
        problem,
        settings=replace(problem.settings, duration_mode=DurationMode.individual()),
        workloads=(
            replace(first, lesson_type="LAB", required_teacher_count=2, duration_minutes=45),
            second,
        ),
    )
    one = lesson(teachers=(TeacherAssignment("Преподаватель"),))
    duplicate = replace(one, id=ScheduleEntryId(UUID(int=99)), week="EVEN")
    conflicts = validate_schedule(schedule(one, duplicate), problem)
    counts = [c.details for c in conflicts if c.code == "WORKLOAD_OCCURRENCES"]
    assert {item["actual"] for item in counts} == {0, 2}
    assert sum(c.code == "TEACHER_COUNT" for c in conflicts) == 2
    assert sum(c.code == "LESSON_DURATION" for c in conflicts) == 2


@pytest.mark.parametrize(
    ("kind", "params", "second_start"),
    [
        (ConstraintKind.MIN_START_TIME, ClockTimeParameters(time(9, 30)), 11),
        (ConstraintKind.MAX_END_TIME, ClockTimeParameters(time(9, 30)), 11),
        (ConstraintKind.ALLOWED_DAYS, AllowedDaysParameters((TUESDAY,)), 11),
        (ConstraintKind.EVERY_WEEK, EveryWeekParameters(), 11),
        (ConstraintKind.CONSECUTIVE, RelatedWorkloadParameters(SECOND), 11),
        (ConstraintKind.NOT_CONSECUTIVE, RelatedWorkloadParameters(SECOND), 10),
        (ConstraintKind.MIN_GAP, MinimumGapParameters(SECOND, 61), 11),
        (ConstraintKind.BEFORE, RelatedWorkloadParameters(SECOND), 8),
        (ConstraintKind.FIXED_DAY, FixedDayParameters(MONDAY, "EVEN"), 11),
        (
            ConstraintKind.TIME_RANGE,
            TimeRangeParameters((WeeklyWindow("ANY", MONDAY, time(7), time(8)),)),
            11,
        ),
    ],
)
def test_each_extra_constraint_reports_its_reason_and_scope(
    problem: ScheduleProblem,
    kind: ConstraintKind,
    params: ConstraintParameters,
    second_start: int,
) -> None:
    identifier = UUID(int=42)
    scoped = ExtraConstraintSnapshot(
        identifier, kind, ConstraintScope(ConstraintScopeKind.WORKLOAD, FIRST), params
    )
    source, other = lesson(), lesson(SECOND, second_start)
    conflicts = validate_schedule(schedule(source, other), replace(problem, constraints=(scoped,)))
    extra = [conflict for conflict in conflicts if conflict.code == kind.value]
    assert len(extra) == 1
    assert FIRST in extra[0].entry_ids
    assert extra[0].message
    assert extra[0].details["constraint_id"] == str(identifier)
