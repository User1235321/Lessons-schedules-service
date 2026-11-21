import json
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.bootstrap.api import create_app
from app.domain.scheduling.job import JobMessage, JobProgress, JobStatus, JobType, ResultOptions
from app.domain.scheduling.schedule import CriterionScore
from app.domain.scheduling.solver import ScheduleVariant, SolverResult, SolverStatus
from app.domain.shared.ids import JobId, UserId


def headers(container, user_id) -> dict[str, str]:
    token = container.tokens.issue_access_token(user_id, container.clock.now())
    return {"Authorization": f"Bearer {token}"}


def test_api_creates_reads_and_requests_cancellation(scheduling_context: tuple) -> None:
    container, owner, project = scheduling_context
    client = TestClient(create_app(container))
    auth = headers(container, owner.id)
    created = client.post(
        f"/projects/{project.id}/generation-jobs",
        headers=auth,
        json={"result_mode": "TOP_N", "top_n": 3},
    )
    assert created.status_code == 202
    assert created.json()["status"] == "QUEUED"
    job_id = created.json()["job_id"]
    state = client.get(f"/generation-jobs/{job_id}", headers=auth)
    assert state.status_code == 200
    assert state.json()["progress"] is None
    assert state.json()["project_id"] == str(project.id)
    cancelled = client.post(f"/generation-jobs/{job_id}/cancel", headers=auth)
    assert cancelled.status_code == 202
    with container.uow() as uow:
        message = uow.job_outbox.get_pending_for_update()
        job = uow.jobs.get(project.id, message.job_id)
        assert job.result_options.top_n == 3
    assert container.job_state().is_cancel_requested(message.job_id)


def test_job_queued_log_contains_job_id(scheduling_context: tuple, capsys) -> None:
    container, owner, project = scheduling_context
    client = TestClient(create_app(container))
    capsys.readouterr()

    response = client.post(
        f"/projects/{project.id}/generation-jobs",
        headers=headers(container, owner.id),
        json={"result_mode": "SINGLE"},
    )
    events = [
        json.loads(line)
        for line in capsys.readouterr().out.splitlines()
        if line.startswith("{")
    ]
    queued = [event for event in events if event.get("event") == "generation_job.queued"]

    assert response.status_code == 202
    assert len(queued) == 1
    assert queued[0]["job_id"] == response.json()["job_id"]
    assert queued[0]["request_id"] == response.headers["X-Request-ID"]


def test_api_hides_foreign_jobs_and_projects(scheduling_context: tuple) -> None:
    container, owner, project = scheduling_context
    job = container.create_generation_job().execute(owner.id, project.id, ResultOptions())
    client = TestClient(create_app(container))
    stranger = headers(container, UserId(uuid4()))
    assert (
        client.post(
            f"/projects/{project.id}/generation-jobs",
            headers=stranger,
            json={"result_mode": "SINGLE"},
        ).status_code
        == 404
    )
    assert client.get(f"/generation-jobs/{job.id}", headers=stranger).status_code == 404
    assert client.get(f"/generation-jobs/{job.id}/schedules", headers=stranger).status_code == 404
    assert client.post(f"/generation-jobs/{job.id}/cancel", headers=stranger).status_code == 404
    assert not container.job_state().is_cancel_requested(job.id)


@pytest.mark.parametrize(
    "body",
    [
        {"result_mode": "TOP_N"},
        {"result_mode": "SINGLE", "top_n": 2},
        {"result_mode": "TOP_N", "top_n": True},
        {"result_mode": "TOP_N", "top_n": 0},
        {"result_mode": "TOP_N", "top_n": 2_147_483_648},
        {"result_mode": "SINGLE", "unexpected": True},
    ],
)
def test_api_rejects_invalid_result_options(scheduling_context: tuple, body: dict) -> None:
    container, owner, project = scheduling_context
    client = TestClient(create_app(container))
    response = client.post(
        f"/projects/{project.id}/generation-jobs", headers=headers(container, owner.id), json=body
    )
    assert response.status_code == 422
    with container.uow() as uow:
        assert uow.job_outbox.get_pending_for_update() is None


def test_api_refuses_to_cancel_terminal_job(scheduling_context: tuple) -> None:
    container, owner, project = scheduling_context
    job = container.create_generation_job().execute(owner.id, project.id, ResultOptions())
    with container.uow() as uow:
        uow.jobs.save(job.finish(JobStatus.CANCELLED, container.clock.now()))
        uow.commit()
    client = TestClient(create_app(container))
    response = client.post(
        f"/generation-jobs/{job.id}/cancel", headers=headers(container, owner.id)
    )
    assert response.status_code == 409
    assert response.json()["code"] == "JOB_NOT_CANCELLABLE"


def test_jobs_api_requires_authentication(scheduling_context: tuple) -> None:
    container, _, project = scheduling_context
    client = TestClient(create_app(container))
    assert client.get(f"/generation-jobs/{uuid4()}").status_code == 401
    assert client.get(f"/generation-jobs/{uuid4()}/schedules").status_code == 401
    assert client.post(f"/generation-jobs/{uuid4()}/cancel").status_code == 401
    assert (
        client.post(
            f"/projects/{project.id}/generation-jobs", json={"result_mode": "SINGLE"}
        ).status_code
        == 401
    )


def test_generation_schedules_are_available_after_completion(
    scheduling_context: tuple,
) -> None:
    container, owner, project = scheduling_context
    job = container.create_generation_job().execute(owner.id, project.id, ResultOptions())
    client = TestClient(create_app(container))
    auth = headers(container, owner.id)
    url = f"/generation-jobs/{job.id}/schedules"

    pending = client.get(url, headers=auth)
    assert pending.status_code == 409
    assert pending.json()["code"] == "JOB_RESULTS_UNAVAILABLE"

    assert container.process_job().execute(JobMessage(job.id, project.id, job.job_type))

    response = client.get(url, headers=auth)
    assert response.status_code == 200
    assert len(response.json()) == 1
    schedule = response.json()[0]
    assert schedule["project_id"] == str(project.id)
    assert schedule["job_id"] == str(job.id)
    assert schedule["source"] == "GENERATED"
    assert schedule["result_index"] == 1
    assert schedule["criterion_scores"] == {}
    assert schedule["entries"] == []


def test_generation_schedules_reject_cancelled_job(scheduling_context: tuple) -> None:
    container, owner, project = scheduling_context
    job = container.create_generation_job().execute(owner.id, project.id, ResultOptions())
    container.cancel_generation_job().execute(owner.id, job.id)
    assert container.process_job().execute(JobMessage(job.id, project.id, job.job_type))

    client = TestClient(create_app(container))
    response = client.get(
        f"/generation-jobs/{job.id}/schedules", headers=headers(container, owner.id)
    )
    assert response.status_code == 409
    assert response.json()["code"] == "JOB_RESULTS_UNAVAILABLE"


def test_api_reads_running_progress_and_missing_redis_progress(
    scheduling_context: tuple,
) -> None:
    container, owner, project = scheduling_context
    job = container.create_generation_job().execute(owner.id, project.id, ResultOptions())
    with container.uow() as uow:
        uow.jobs.save(job.start(container.clock.now()))
        uow.commit()

    client = TestClient(create_app(container))
    url = f"/generation-jobs/{job.id}"
    auth = headers(container, owner.id)
    container.job_state().set_progress(job.id, JobProgress(37.5))

    running = client.get(url, headers=auth)
    assert running.status_code == 200
    assert running.json()["status"] == "RUNNING"
    assert running.json()["progress"] == 37.5

    container.job_state().clear(job.id)
    without_progress = client.get(url, headers=auth)
    assert without_progress.status_code == 200
    assert without_progress.json()["status"] == "RUNNING"
    assert without_progress.json()["progress"] is None


def test_api_returns_not_found_for_unknown_jobs(scheduling_context: tuple) -> None:
    container, owner, _ = scheduling_context
    client = TestClient(create_app(container))
    auth = headers(container, owner.id)
    job_id = uuid4()

    assert client.get(f"/generation-jobs/{job_id}", headers=auth).status_code == 404
    assert client.post(f"/generation-jobs/{job_id}/cancel", headers=auth).status_code == 404
    assert client.get(f"/generation-jobs/{job_id}/schedules", headers=auth).status_code == 404


def test_generation_schedules_preserve_top_n_result_order(scheduling_context: tuple) -> None:
    container, owner, project = scheduling_context
    client = TestClient(create_app(container))
    auth = headers(container, owner.id)
    created = client.post(
        f"/projects/{project.id}/generation-jobs",
        headers=auth,
        json={"result_mode": "TOP_N", "top_n": 3},
    )
    assert created.status_code == 202
    job_id = JobId(UUID(created.json()["job_id"]))

    solver = Mock()
    solver.solve.return_value = SolverResult(
        SolverStatus.SOLVED,
        (
            ScheduleVariant((), (CriterionScore("gaps", 2.0),)),
            ScheduleVariant((), (CriterionScore("gaps", 4.0),)),
        ),
    )
    assert container.process_job(solver=solver).execute(
        JobMessage(job_id, project.id, JobType.GENERATE)
    )

    response = client.get(f"/generation-jobs/{job_id}/schedules", headers=auth)
    assert response.status_code == 200
    assert [item["result_index"] for item in response.json()] == [1, 2]
    assert [item["criterion_scores"] for item in response.json()] == [
        {"gaps": 2.0},
        {"gaps": 4.0},
    ]


def test_generation_schedules_reject_failed_job(scheduling_context: tuple) -> None:
    container, owner, project = scheduling_context
    job = container.create_generation_job().execute(owner.id, project.id, ResultOptions())
    with container.uow() as uow:
        uow.jobs.save(job.finish(JobStatus.FAILED, container.clock.now(), "solver error"))
        uow.commit()

    client = TestClient(create_app(container))
    response = client.get(
        f"/generation-jobs/{job.id}/schedules", headers=headers(container, owner.id)
    )
    assert response.status_code == 409
    assert response.json()["code"] == "JOB_RESULTS_UNAVAILABLE"
