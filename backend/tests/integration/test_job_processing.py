from concurrent.futures import ThreadPoolExecutor
from datetime import time
from threading import Event
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.application.scheduling.ports import JobStateStoreError
from app.domain.scheduling.job import JobMessage, JobProgress, JobStatus, ResultOptions
from app.domain.scheduling.problem import ScheduleProblem
from app.domain.scheduling.schedule import ScheduleEntry, TeacherAssignment
from app.domain.scheduling.solver import ScheduleVariant, SolverResult, SolverStatus
from app.domain.shared.ids import ScheduleEntryId
from app.domain.shared.week import Weekday
from app.infrastructure.persistence.repositories.jobs import SqlJobRepository


def solved_result() -> SolverResult:
    entry = ScheduleEntry(
        id=ScheduleEntryId(uuid4()),
        workload_id=uuid4(),
        week="ODD",
        weekday=Weekday.MONDAY,
        start_time=time(9),
        end_time=time(10, 40),
        subject_name="Математика",
        teachers=(TeacherAssignment("Иванов", uuid4()), TeacherAssignment("Петров")),
    )
    return SolverResult(SolverStatus.SOLVED, (ScheduleVariant((entry,), ()),))


def prepare(context: tuple, result: SolverResult | None = None):
    container, owner, project = context
    job = container.create_generation_job().execute(owner.id, project.id, ResultOptions())
    solver = Mock()
    solver.solve.return_value = result if result is not None else solved_result()
    source = Mock(load=Mock(return_value=ScheduleProblem(project.settings)))
    process = container.process_job(problems=source, solver=solver)
    return job, process, JobMessage(job.id, project.id, job.job_type)


def current_job(container, job):
    with container.uow() as uow:
        return uow.jobs.get(job.project_id, job.id)


def test_success_and_redelivery_persist_exactly_one_result(scheduling_context: tuple) -> None:
    container, owner, project = scheduling_context
    job, process, message = prepare(scheduling_context)

    def solve(problem, options, control):
        assert current_job(container, job).status is JobStatus.RUNNING
        control.report_progress(JobProgress(42))
        assert container.get_generation_job().execute(owner.id, job.id).progress == JobProgress(42)
        return solved_result()

    process.solver.solve.side_effect = solve
    assert process.execute(message)
    assert process.execute(message)
    assert current_job(container, job).status is JobStatus.COMPLETED
    assert container.job_state().get_progress(job.id) is None
    process.solver.solve.assert_called_once()
    with container.uow() as uow:
        schedules = uow.schedules.list_for_job(project.id, job.id)
        assert len(schedules) == 1
        assert schedules[0].result_index == 1
        assert [teacher.display_name for teacher in schedules[0].entries[0].teachers] == [
            "Иванов",
            "Петров",
        ]


@pytest.mark.parametrize("status", [SolverStatus.INFEASIBLE, SolverStatus.CANCELLED])
def test_solver_outcomes_without_variants(scheduling_context: tuple, status: SolverStatus) -> None:
    container, _, project = scheduling_context
    job, process, message = prepare(scheduling_context, SolverResult(status))
    assert process.execute(message)
    expected = JobStatus.CANCELLED if status is SolverStatus.CANCELLED else JobStatus.COMPLETED
    assert current_job(container, job).status is expected
    with container.uow() as uow:
        assert uow.schedules.list_for_job(project.id, job.id) == []


def test_cancel_before_start_does_not_call_solver(scheduling_context: tuple) -> None:
    container, owner, _ = scheduling_context
    job, process, message = prepare(scheduling_context)
    container.cancel_generation_job().execute(owner.id, job.id)
    assert process.execute(message)
    assert current_job(container, job).status is JobStatus.CANCELLED
    process.problems.load.assert_not_called()
    process.solver.solve.assert_not_called()


def test_concurrent_worker_does_not_repeat_running_calculation(scheduling_context: tuple) -> None:
    container, owner, _ = scheduling_context
    job, process, message = prepare(scheduling_context)
    started, release = Event(), Event()

    def solve(problem, options, control):
        started.set()
        assert release.wait(10)
        return solved_result()

    process.solver.solve.side_effect = solve
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(process.execute, message)
        try:
            assert started.wait(10)
            assert current_job(container, job).status is JobStatus.RUNNING
            assert not container.process_job().execute(message)
            container.cancel_generation_job().execute(owner.id, job.id)
        finally:
            release.set()
        assert future.result(timeout=10)
    assert current_job(container, job).status is JobStatus.CANCELLED
    process.solver.solve.assert_called_once()


def test_orphaned_running_job_fails_without_restarting_solver(scheduling_context: tuple) -> None:
    container, _, _ = scheduling_context
    job, process, message = prepare(scheduling_context)
    with container.uow() as uow:
        uow.jobs.save(job.start(container.clock.now()))
        uow.commit()

    assert process.execute(message)
    assert current_job(container, job).status is JobStatus.FAILED
    assert "аварией" in current_job(container, job).error_message
    process.solver.solve.assert_not_called()


def test_accepted_cancellation_wins_before_result_commit(
    scheduling_context: tuple, monkeypatch
) -> None:
    container, owner, project = scheduling_context
    job, process, message = prepare(scheduling_context)
    get_for_update = SqlJobRepository.get_for_update
    reads = 0

    def cancel_before_final_lock(repository, project_id, job_id):
        nonlocal reads
        reads += 1
        if reads == 2:
            container.cancel_generation_job().execute(owner.id, job.id)
        return get_for_update(repository, project_id, job_id)

    monkeypatch.setattr(SqlJobRepository, "get_for_update", cancel_before_final_lock)
    assert process.execute(message)
    assert current_job(container, job).status is JobStatus.CANCELLED
    with container.uow() as uow:
        assert uow.schedules.list_for_job(project.id, job.id) == []


@pytest.mark.parametrize("failure", ["solver", "redis", "source"])
def test_execution_failures_are_persisted(scheduling_context: tuple, failure: str) -> None:
    container, _, _ = scheduling_context
    job, process, message = prepare(scheduling_context)
    if failure == "solver":
        process.solver.solve.side_effect = RuntimeError("solver failed")
    elif failure == "source":
        process.problems.load.side_effect = RuntimeError("snapshot unavailable")
    else:
        process.state = Mock()
        process.state.is_cancel_requested.side_effect = JobStateStoreError("redis offline")

    assert process.execute(message)
    failed = current_job(container, job)
    assert failed.status is JobStatus.FAILED
    assert failed.error_message
    assert failed.finished_at is not None


def test_result_and_completion_roll_back_together(scheduling_context: tuple, monkeypatch) -> None:
    container, _, project = scheduling_context
    job, process, message = prepare(scheduling_context)
    save = SqlJobRepository.save

    def fail_completion(repository, value):
        if value.status is JobStatus.COMPLETED:
            raise RuntimeError("commit interrupted")
        return save(repository, value)

    monkeypatch.setattr(SqlJobRepository, "save", fail_completion)
    with pytest.raises(RuntimeError, match="commit interrupted"):
        process.execute(message)
    with container.uow() as uow:
        assert uow.schedules.list_for_job(project.id, job.id) == []
        assert uow.jobs.get(project.id, job.id).status is JobStatus.RUNNING
    assert process.execute(message)
    assert current_job(container, job).status is JobStatus.FAILED
    process.solver.solve.assert_called_once()


def test_default_worker_reports_missing_core(scheduling_context: tuple) -> None:
    container, _, _ = scheduling_context
    job, _, message = prepare(scheduling_context)
    assert container.process_job().execute(message)
    failed = current_job(container, job)
    assert failed.status is JobStatus.FAILED
    assert "ещё не реализована" in failed.error_message
