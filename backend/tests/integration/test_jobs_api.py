from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.bootstrap.api import create_app
from app.domain.scheduling.job import JobMessage, JobStatus, ResultOptions
from app.domain.shared.ids import UserId


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
