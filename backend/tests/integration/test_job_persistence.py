from dataclasses import replace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.application.scheduling.delivery import DeliverPendingJob
from app.application.scheduling.ports import JobPublishError
from app.domain.scheduling.job import JobMessage, JobStatus, ResultOptions
from app.domain.shared.errors import AlreadyExists, InvalidValue
from app.domain.shared.ids import ProjectId, UserId
from app.infrastructure.persistence.models.jobs import JobOutboxRow
from app.infrastructure.persistence.repositories.job_outbox import SqlJobOutbox


def test_creation_stores_job_and_outbox_atomically(scheduling_context: tuple) -> None:
    container, owner, project = scheduling_context
    job = container.create_generation_job().execute(owner.id, project.id, ResultOptions())

    with container.uow() as uow:
        assert uow.jobs.get(project.id, job.id) == job
        message = uow.job_outbox.get_pending_for_update()
        assert message == JobMessage(job.id, project.id, job.job_type)
        assert uow.jobs.get_owned(job.id, UserId(uuid4())) is None


def test_failure_to_store_outbox_rolls_back_job(scheduling_context: tuple, monkeypatch) -> None:
    container, owner, project = scheduling_context
    use_case = container.create_generation_job()
    use_case.ids = Mock(new_id=Mock(return_value=uuid4()))
    job_id = use_case.ids.new_id()
    monkeypatch.setattr(SqlJobOutbox, "add", Mock(side_effect=RuntimeError("outbox unavailable")))
    with pytest.raises(RuntimeError, match="outbox unavailable"):
        use_case.execute(owner.id, project.id, ResultOptions())
    with container.uow() as uow:
        assert uow.jobs.get(project.id, job_id) is None


def test_outbox_retries_same_job_after_uncertain_delivery(scheduling_context: tuple) -> None:
    container, owner, project = scheduling_context
    job = container.create_generation_job().execute(owner.id, project.id, ResultOptions())
    publisher = Mock()
    publisher.publish.side_effect = JobPublishError("ack lost")
    delivery = DeliverPendingJob(container.uow(), publisher, container.clock)

    with pytest.raises(JobPublishError):
        delivery.execute()
    with container.session_factory() as session:
        assert session.get(JobOutboxRow, job.id).published_at is None
    publisher.publish.side_effect = None
    assert delivery.execute()
    assert not delivery.execute()
    assert [call.args[0].job_id for call in publisher.publish.call_args_list] == [job.id] * 2


def test_concurrent_dispatchers_skip_locked_message(scheduling_context: tuple) -> None:
    container, owner, project = scheduling_context
    first = container.create_generation_job().execute(owner.id, project.id, ResultOptions())
    second = container.create_generation_job().execute(owner.id, project.id, ResultOptions())
    with container.uow() as left, container.uow() as right:
        assert left.job_outbox.get_pending_for_update().job_id == first.id
        assert right.job_outbox.get_pending_for_update().job_id == second.id


def test_terminal_job_cannot_restart(scheduling_context: tuple) -> None:
    container, owner, project = scheduling_context
    job = container.create_generation_job().execute(owner.id, project.id, ResultOptions())
    completed = job.start(container.clock.now()).finish(JobStatus.COMPLETED, container.clock.now())
    with container.uow() as uow:
        uow.jobs.save(completed)
        uow.commit()
    with pytest.raises(InvalidValue):
        completed.start(container.clock.now())
    with container.uow() as uow:
        assert uow.jobs.get(project.id, job.id) == completed


def test_duplicate_job_raises_already_exists(scheduling_context: tuple) -> None:
    container, owner, project = scheduling_context
    job = container.create_generation_job().execute(owner.id, project.id, ResultOptions())
    with pytest.raises(AlreadyExists), container.uow() as uow:
        uow.jobs.add(job)
    with container.uow() as uow:
        assert uow.jobs.get(project.id, job.id) == job


def test_other_job_integrity_errors_remain_database_errors(scheduling_context: tuple) -> None:
    container, owner, project = scheduling_context
    job = container.create_generation_job().execute(owner.id, project.id, ResultOptions())
    invalid = replace(job, id=container.ids.new_id(), project_id=ProjectId(uuid4()))
    with pytest.raises(IntegrityError), container.uow() as uow:
        uow.jobs.add(invalid)
