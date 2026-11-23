from dataclasses import replace
from datetime import UTC, datetime, time
from uuid import uuid4

from app.domain.scheduling.constraints import (
    ConstraintKind,
    ConstraintScope,
    ConstraintScopeKind,
    EveryWeekParameters,
    ExtraConstraintSnapshot,
)
from app.domain.scheduling.job import ExistingScheduleInput, JobType
from app.domain.scheduling.problem import OptimizationCriterionSnapshot
from app.domain.scheduling.schedule import LessonFormat, Schedule, ScheduleEntry, ScheduleSource
from app.domain.scheduling.schedule import TeacherAssignment
from app.domain.scheduling.solver import SolverStatus
from app.domain.scheduling.validation import validate_schedule
from app.domain.shared.week import Weekday
from app.scheduling.reprocessing import ExistingScheduleSolver
from tests.unit.test_feasible_solver import (
    MONDAY,
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
