from dataclasses import replace
from datetime import UTC, datetime, time, timedelta
from uuid import uuid4

import pytest

from app.domain.scheduling.job import Job, JobProgress, JobStatus, JobType, ResultMode, ResultOptions
from app.domain.scheduling.schedule import (
    CriterionScore,
    LessonFormat,
    Schedule,
    ScheduleEntry,
    ScheduleSource,
    TeacherAssignment,
)
from app.domain.scheduling.solver import (
    ScheduleVariant,
    SolverDiagnostic,
    SolverResult,
    SolverStatus,
)
from app.domain.shared.errors import InvalidValue
from app.domain.shared.ids import JobId, ProjectId, ScheduleEntryId, ScheduleId
from app.domain.shared.week import Weekday

NOW = datetime(2026, 11, 10, tzinfo=UTC)
PROJECT = ProjectId(uuid4())


def imported_schedule() -> Schedule:
    return Schedule(
        id=ScheduleId(uuid4()),
        project_id=PROJECT,
        source=ScheduleSource.IMPORTED,
        entries=(
            ScheduleEntry(
                id=ScheduleEntryId(uuid4()),
                week="ODD",
                weekday=Weekday.MONDAY,
                start_time=time(9),
                end_time=time(10, 40),
                subject_name="Математика",
                room_name="А-101",
                teachers=(TeacherAssignment("Иванов И. И."),),
            ),
        ),
        created_at=NOW,
    )


def queued_job() -> Job:
    return Job(
        id=JobId(uuid4()),
        project_id=PROJECT,
        job_type=JobType.GENERATE,
        status=JobStatus.QUEUED,
        result_options=ResultOptions(),
        created_at=NOW,
    )


def test_single_and_top_n_limit_the_number_of_results() -> None:
    assert ResultOptions().limit == 1
    assert ResultOptions(ResultMode.TOP_N, top_n=5).limit == 5

    for options in (
        {"mode": ResultMode.TOP_N},
        {"mode": ResultMode.TOP_N, "top_n": 0},
        {"mode": ResultMode.TOP_N, "top_n": -1},
        {"mode": ResultMode.SINGLE, "top_n": 1},
    ):
        with pytest.raises(InvalidValue) as error:
            ResultOptions(**options)
        assert error.value.field == "top_n"


def test_imported_schedule_keeps_labels_without_academic_references() -> None:
    schedule = imported_schedule()
    entry = schedule.entries[0]

    assert schedule.job_id is None
    assert schedule.criterion_scores is None
    assert entry.workload_id is None
    assert entry.room_id is None
    assert (entry.subject_name, entry.room_name) == ("Математика", "А-101")
    assert entry.teachers == (TeacherAssignment("Иванов И. И."),)
    with pytest.raises(InvalidValue):
        replace(schedule, job_id=JobId(uuid4()))


def test_generated_variant_requires_provenance_and_workload() -> None:
    imported = imported_schedule()
    values = {
        "source": ScheduleSource.GENERATED,
        "job_id": JobId(uuid4()),
        "result_index": 1,
        "criterion_scores": (CriterionScore("STUDENT_GAPS", 0),),
        "entries": (replace(imported.entries[0], workload_id=uuid4()),),
    }
    generated = replace(imported, **values)

    for missing in (
        {"job_id": None},
        {"result_index": None},
        {"result_index": 0},
        {"criterion_scores": None},
        {"entries": imported.entries},
    ):
        with pytest.raises(InvalidValue):
            replace(generated, **missing)


def test_remote_edit_removes_room_but_preserves_imported_labels() -> None:
    entry = imported_schedule().entries[0]

    with pytest.raises(InvalidValue):
        replace(entry, lesson_format=LessonFormat.REMOTE)

    remote = replace(entry, lesson_format=LessonFormat.REMOTE, room_name=None)
    assert remote.subject_name == entry.subject_name
    assert remote.teachers == entry.teachers
    assert entry.room_name == "А-101"


def test_entry_rejects_repeated_teacher_and_reversed_interval() -> None:
    entry = imported_schedule().entries[0]
    teacher = TeacherAssignment("Иванов И. И.", uuid4())

    with pytest.raises(InvalidValue):
        replace(entry, teachers=(teacher, teacher))
    with pytest.raises(InvalidValue):
        replace(entry, end_time=entry.start_time)


def test_job_may_be_cancelled_before_worker_starts() -> None:
    cancelled = replace(queued_job(), status=JobStatus.CANCELLED, finished_at=NOW)

    assert cancelled.started_at is None
    assert cancelled.finished_at == NOW


def test_job_timestamps_follow_its_status() -> None:
    queued = queued_job()
    running = replace(queued, status=JobStatus.RUNNING, started_at=NOW)
    completed = replace(
        running, status=JobStatus.COMPLETED, finished_at=NOW + timedelta(minutes=1)
    )

    assert completed.started_at == NOW
    for job, changes in (
        (queued, {"started_at": NOW}),
        (queued, {"status": JobStatus.RUNNING}),
        (running, {"finished_at": NOW}),
        (completed, {"finished_at": None}),
        (completed, {"finished_at": NOW - timedelta(seconds=1)}),
    ):
        with pytest.raises(InvalidValue):
            replace(job, **changes)


@pytest.mark.parametrize("percent", [-1, 101, float("nan"), float("inf")])
def test_progress_cannot_report_invalid_percent(percent: float) -> None:
    with pytest.raises(InvalidValue):
        JobProgress(percent)


def test_solver_distinguishes_no_solution_cancellation_and_completed_results() -> None:
    diagnostic = SolverDiagnostic("Нет доступной аудитории", workload_ids=(uuid4(),))
    infeasible = SolverResult(SolverStatus.INFEASIBLE, diagnostics=(diagnostic,))
    cancelled = SolverResult(SolverStatus.CANCELLED)
    variant = ScheduleVariant(imported_schedule().entries, ())
    solved = SolverResult(SolverStatus.SOLVED, variants=(variant,))

    assert infeasible.diagnostics == (diagnostic,)
    assert cancelled.status is SolverStatus.CANCELLED
    assert solved.variants == (variant,)
    with pytest.raises(InvalidValue):
        SolverResult(SolverStatus.SOLVED)
    for status in (SolverStatus.INFEASIBLE, SolverStatus.CANCELLED):
        with pytest.raises(InvalidValue):
            SolverResult(status, variants=(variant,))
