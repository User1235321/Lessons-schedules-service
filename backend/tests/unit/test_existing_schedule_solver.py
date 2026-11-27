from dataclasses import replace
from datetime import UTC, datetime, time
from uuid import uuid4

import pytest

from app.domain.scheduling.constraints import (
    ClockTimeParameters,
    ConstraintKind,
    ConstraintScope,
    ConstraintScopeKind,
    EveryWeekParameters,
    ExtraConstraintSnapshot,
)
from app.domain.scheduling.job import (
    EntryPinField,
    ExistingScheduleInput,
    JobType,
    ScheduleEntryPin,
)
from app.domain.scheduling.problem import OptimizationCriterionSnapshot
from app.domain.scheduling.resources import (
    RoomSnapshot,
    RoomType,
    StreamSnapshot,
    SubjectSnapshot,
    TeachingCapability,
)
from app.domain.scheduling.schedule import (
    LessonFormat,
    Schedule,
    ScheduleEntry,
    ScheduleSource,
    TeacherAssignment,
)
from app.domain.scheduling.solver import SolverStatus
from app.domain.scheduling.validation import validate_schedule
from app.domain.shared.week import Weekday
from app.scheduling.reprocessing import ExistingScheduleSolver, _distance
from tests.unit.test_feasible_solver import (
    GROUP,
    MONDAY,
    ROOM,
    SECOND_TEACHER,
    STREAM,
    TEACHER,
    WORKLOAD,
    RecordingControl,
    problem,
    settings,
    teacher,
    window,
    workload,
)


def entry(start: int = 8) -> ScheduleEntry:
    assigned = teacher()
    return ScheduleEntry(
        id=uuid4(),
        week="ODD",
        weekday=MONDAY,
        start_time=time(start),
        end_time=time(start + 1),
        workload_id=WORKLOAD,
        subject_name="Физика",
        participant_label="П-101",
        lesson_type="LECTURE",
        lesson_format=LessonFormat.REMOTE,
        teachers=(TeacherAssignment(assigned.full_name, TEACHER),),
    )


def schedule(*entries: ScheduleEntry) -> Schedule:
    return Schedule(
        id=uuid4(),
        project_id=uuid4(),
        source=ScheduleSource.IMPORTED,
        entries=entries,
        created_at=datetime.now(UTC),
    )


def test_modes_rank_changes_before_quality_only_for_min_changes():
    original = entry()
    source = ExistingScheduleInput(schedule=schedule(original))
    data = replace(
        problem(teachers=(teacher(availability=(window(time(8), time(10)),)),)),
        optimization_criteria=(OptimizationCriterionSnapshot("EARLY_LATE_CLASSES", 1),),
    )
    solver = ExistingScheduleSolver()
    minimal = solver.solve(source, JobType.REOPTIMIZE_MIN_CHANGES, data, RecordingControl())
    full = solver.solve(source, JobType.REOPTIMIZE_FULL, data, RecordingControl())
    assert minimal.variants[0].entries == (original,)
    assert minimal.variants[0].criterion_scores[0].value == 1
    assert full.variants[0].entries[0].start_time == time(9)
    assert full.variants[0].criterion_scores[0].value == 0
    invalid = replace(source.schedule, entries=(replace(original, weekday=Weekday.SUNDAY),))
    locked = ExistingScheduleInput(schedule=invalid, fixed_entry_ids=(original.id,))
    assert solver.solve(locked, JobType.AUTO_REPAIR, data, RecordingControl()).status is (
        SolverStatus.INFEASIBLE
    )
    assert solver.solve(
        source, JobType.AUTO_REPAIR, data, RecordingControl(cancel_after=0)
    ).status is SolverStatus.CANCELLED


def test_min_changes_uses_quality_to_break_ties():
    original = entry(8)
    assigned = replace(
        teacher(availability=(window(time(9), time(11)),)),
        preferences=(window(time(10), time(11)),),
    )
    data = replace(
        problem(teachers=(assigned,)),
        optimization_criteria=(OptimizationCriterionSnapshot("TEACHER_PREFERENCES", 1),),
    )
    result = ExistingScheduleSolver().solve(
        ExistingScheduleInput(schedule=schedule(original)),
        JobType.REOPTIMIZE_MIN_CHANGES,
        data,
        RecordingControl(),
    )
    assert result.status is SolverStatus.SOLVED
    assert result.variants[0].entries == (replace(original, start_time=time(10), end_time=time(11)),)


def test_change_count_compares_all_five_fields_and_ignores_teacher_order():
    first, second = entry().teachers[0], TeacherAssignment("Другой преподаватель", SECOND_TEACHER)
    original = replace(entry(), lesson_format=LessonFormat.ONSITE, teachers=(first, second))

    for changed in (
        replace(original, week="EVEN"),
        replace(original, weekday=Weekday.TUESDAY),
        replace(original, start_time=time(9), end_time=time(10)),
        replace(original, lesson_format=LessonFormat.REMOTE),
        replace(original, room_id=ROOM, room_name="101"),
        replace(original, teachers=(first,)),
    ):
        assert _distance(original, changed) == 1
    assert _distance(original, replace(original, teachers=(second, first))) == 0


@pytest.mark.parametrize(
    ("field", "expected_week", "expected_day", "expected_start"),
    [
        (EntryPinField.DAY, "ODD", MONDAY, 9),
        (EntryPinField.TIME, "ODD", Weekday.TUESDAY, 8),
    ],
)
def test_auto_repair_pins_only_requested_field(field, expected_week, expected_day, expected_start):
    original = entry(8)
    available = (
        window(time(9), time(10), week="ODD"),
        window(time(8), time(9), week="ODD", day=Weekday.TUESDAY),
        window(time(8), time(9), week="EVEN"),
    )
    data = problem(
        teachers=(teacher(availability=available),),
        project_settings=settings(odd=(MONDAY, Weekday.TUESDAY), even=(MONDAY,)),
    )
    source = ExistingScheduleInput(
        schedule=schedule(original), pins=(ScheduleEntryPin(original.id, (field,)),)
    )

    result = ExistingScheduleSolver().solve(source, JobType.AUTO_REPAIR, data, RecordingControl())

    assert result.status is SolverStatus.SOLVED
    expected = replace(
        original,
        week=expected_week,
        weekday=expected_day,
        start_time=time(expected_start),
        end_time=time(expected_start + 1),
    )
    assert result.variants[0].entries == (expected,)


def test_auto_repair_keeps_pinned_occurrence_and_moves_only_one_neighbor():
    neighbor, pinned, independent = entry(9), entry(9), entry(11)
    data = problem(
        workloads=(workload(occurrences=3),),
        teachers=(teacher(availability=(window(time(9), time(12)),)),),
    )
    source = ExistingScheduleInput(
        schedule=schedule(neighbor, pinned, independent),
        pins=(ScheduleEntryPin(pinned.id, (EntryPinField.DAY, EntryPinField.TIME)),),
    )

    result = ExistingScheduleSolver().solve(source, JobType.AUTO_REPAIR, data, RecordingControl())

    assert result.status is SolverStatus.SOLVED
    variant = result.variants[0]
    assert variant.entries == (
        replace(neighbor, start_time=time(10), end_time=time(11)),
        pinned,
        independent,
    )
    assert not validate_schedule(replace(source.schedule, entries=variant.entries), data)


def test_auto_repair_can_change_format_with_both_day_and_time_pinned():
    original = replace(entry(9), lesson_format=LessonFormat.ONSITE, room_id=ROOM, room_name="101")
    source = ExistingScheduleInput(
        schedule=schedule(original),
        pins=(ScheduleEntryPin(original.id, (EntryPinField.DAY, EntryPinField.TIME)),),
    )

    result = ExistingScheduleSolver().solve(
        source, JobType.AUTO_REPAIR, problem(), RecordingControl()
    )

    assert result.status is SolverStatus.SOLVED
    assert result.variants[0].entries == (
        replace(original, lesson_format=LessonFormat.REMOTE, room_id=None, room_name=None),
    )


def test_auto_repair_explains_when_pinned_day_has_no_placements():
    original = replace(entry(9), weekday=Weekday.SUNDAY)
    source = ExistingScheduleInput(
        schedule=schedule(original), pins=(ScheduleEntryPin(original.id, (EntryPinField.DAY,)),)
    )

    result = ExistingScheduleSolver().solve(
        source, JobType.AUTO_REPAIR, problem(), RecordingControl()
    )

    assert result.status is SolverStatus.INFEASIBLE
    assert not result.variants
    (diagnostic,) = result.diagnostics
    assert diagnostic.workload_ids == (WORKLOAD,)
    assert str(original.id) in diagnostic.message
    assert "DAY" in diagnostic.message


def test_auto_repair_reports_infeasible_when_pinned_occurrences_overlap():
    first, second = entry(9), entry(9)
    source = ExistingScheduleInput(
        schedule=schedule(first, second),
        pins=tuple(
            ScheduleEntryPin(item.id, (EntryPinField.DAY, EntryPinField.TIME))
            for item in (first, second)
        ),
    )
    data = problem(
        workloads=(workload(occurrences=2),),
        teachers=(teacher(availability=(window(time(9), time(11)),)),),
    )

    result = ExistingScheduleSolver().solve(source, JobType.AUTO_REPAIR, data, RecordingControl())

    assert result.status is SolverStatus.INFEASIBLE
    assert not result.variants
    assert result.diagnostics[0].workload_ids == (WORKLOAD,)
    assert "фиксации" in result.diagnostics[0].message


def test_import_without_workload_id_can_match_unique_workload():
    original = replace(entry(9), workload_id=None)
    source = ExistingScheduleInput(schedule=schedule(original))
    result = ExistingScheduleSolver().solve(
        source, JobType.REOPTIMIZE_MIN_CHANGES, problem(), RecordingControl()
    )
    assert result.status is SolverStatus.SOLVED
    assert result.variants[0].entries[0].workload_id == WORKLOAD


def test_import_without_workload_data_does_not_produce_invalid_generated_schedule():
    original = replace(entry(9), workload_id=None)
    source = ExistingScheduleInput(schedule=schedule(original))
    result = ExistingScheduleSolver().solve(
        source, JobType.REOPTIMIZE_FULL, problem(workloads=()), RecordingControl()
    )
    assert result.status is SolverStatus.INFEASIBLE
    assert result.diagnostics
    assert not result.variants


def test_reprocessing_uses_actual_format_instead_of_requiring_workload_default():
    original = entry(9)
    source = ExistingScheduleInput(schedule=schedule(original))
    data = problem(workloads=(workload(lesson_format=LessonFormat.ONSITE),))
    result = ExistingScheduleSolver().solve(
        source, JobType.REOPTIMIZE_MIN_CHANGES, data, RecordingControl()
    )
    assert result.status is SolverStatus.SOLVED
    assert result.variants[0].entries[0].lesson_format is LessonFormat.REMOTE


def test_reprocessing_maximizes_teacher_preferences():
    original = entry(9)
    data = replace(
        problem(teachers=(replace(
            teacher(availability=(window(time(9), time(11)),)),
            preferences=(window(time(10), time(11)),),
        ),)),
        optimization_criteria=(OptimizationCriterionSnapshot("TEACHER_PREFERENCES", 1),),
    )
    result = ExistingScheduleSolver().solve(
        ExistingScheduleInput(schedule=schedule(original)),
        JobType.REOPTIMIZE_FULL, data, RecordingControl(),
    )
    assert result.variants[0].entries[0].start_time == time(10)
    assert result.variants[0].criterion_scores[0].value == 1


def test_import_checks_known_workload_occurrences_and_every_week():
    data = replace(
        problem(
            workloads=(workload(occurrences=2),),
            project_settings=settings(even=(MONDAY,)),
        ),
        constraints=(ExtraConstraintSnapshot(
            uuid4(), ConstraintKind.EVERY_WEEK,
            ConstraintScope(ConstraintScopeKind.WORKLOAD, WORKLOAD),
            EveryWeekParameters(),
        ),),
    )
    assert {item.code for item in validate_schedule(schedule(entry(9)), data)} == {
        "EVERY_WEEK", "WORKLOAD_OCCURRENCES",
    }
    assert "EVERY_WEEK" not in {
        item.code for item in validate_schedule(
            schedule(entry(9)), data, partial_assignment=True
        )
    }


def test_import_checks_capabilities_without_workload():
    other_subject = uuid4()
    assigned = replace(
        teacher(), capabilities=(TeachingCapability(other_subject, "PRACTICE"),)
    )
    room = RoomSnapshot(
        ROOM, "Аудитория", 30, RoomType.PRACTICE_SPECIALIZED, (window(),),
        (TeachingCapability(other_subject, "PRACTICE"),),
    )
    original = replace(
        entry(9), workload_id=None, lesson_type="PRACTICE", lesson_format=LessonFormat.ONSITE,
        room_name=room.name, teachers=(TeacherAssignment(assigned.full_name),),
    )
    data = problem(workloads=(), teachers=(assigned,), rooms=(room,))
    data = replace(data, subjects=(*data.subjects, SubjectSnapshot(other_subject, "История")))
    assert {item.code for item in validate_schedule(schedule(original), data)} == {
        "TEACHER_NOT_QUALIFIED", "ROOM_SPECIALIZATION",
    }
    unknown = replace(original, subject_name="Неизвестная дисциплина")
    assert not validate_schedule(schedule(unknown), data)
    ambiguous = replace(
        data, subjects=(*data.subjects, SubjectSnapshot(uuid4(), "Физика"))
    )
    assert not validate_schedule(schedule(original), ambiguous)


def test_import_checks_stream_constraints_without_workload():
    original = replace(entry(9), workload_id=None, participant_label="Поток")
    data = replace(
        problem(workloads=(), streams=(StreamSnapshot(STREAM, "Поток", (GROUP,)),)),
        constraints=(ExtraConstraintSnapshot(
            uuid4(), ConstraintKind.MIN_START_TIME,
            ConstraintScope(ConstraintScopeKind.STREAM, STREAM),
            ClockTimeParameters(time(10)),
        ),),
    )
    assert {item.code for item in validate_schedule(schedule(original), data)} == {
        "MIN_START_TIME",
    }
