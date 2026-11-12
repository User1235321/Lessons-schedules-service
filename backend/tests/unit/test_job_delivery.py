from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from confluent_kafka import KafkaError

from app.application.scheduling.delivery import DeliverPendingJob
from app.application.scheduling.ports import JobPublishError
from app.domain.scheduling.job import JobMessage, JobType
from app.domain.shared.ids import JobId, ProjectId
from app.infrastructure.messaging.job_messages import decode_job_message, encode_job_message
from app.infrastructure.messaging.kafka import KafkaJobPublisher


def message() -> JobMessage:
    return JobMessage(JobId(uuid4()), ProjectId(uuid4()), JobType.GENERATE)


def test_message_round_trip_preserves_identity() -> None:
    job = message()
    assert decode_job_message(encode_job_message(job)) == job


@pytest.mark.parametrize("payload", [b"null", b"[]", b"{}", b"bad json", b"{}\xff"])
def test_invalid_message_is_rejected(payload: bytes) -> None:
    with pytest.raises(ValueError):
        decode_job_message(payload)


def test_publisher_waits_for_broker_acknowledgement() -> None:
    producer = MagicMock()
    job = message()

    def flush(timeout: float) -> int:
        producer.produce.call_args.kwargs["on_delivery"](None, MagicMock())
        return 0

    producer.flush.side_effect = flush
    KafkaJobPublisher(producer).publish(job)

    assert producer.produce.call_args.kwargs["key"] == str(job.job_id).encode()
    assert decode_job_message(producer.produce.call_args.kwargs["value"]) == job


@pytest.mark.parametrize("failure", ["timeout", "broker", "buffer"])
def test_publisher_reports_uncertain_or_failed_delivery(failure: str) -> None:
    producer = MagicMock()
    producer.flush.return_value = 1
    if failure == "broker":

        def flush(timeout: float) -> int:
            producer.produce.call_args.kwargs["on_delivery"](
                KafkaError(KafkaError._MSG_TIMED_OUT), MagicMock()
            )
            return 0

        producer.flush.side_effect = flush
    if failure == "buffer":
        producer.produce.side_effect = BufferError("full")

    with pytest.raises(JobPublishError):
        KafkaJobPublisher(producer).publish(message())


def test_outbox_is_marked_only_after_successful_publication() -> None:
    uow = MagicMock()
    publisher = MagicMock()
    clock = MagicMock()
    clock.now.return_value = datetime(2026, 11, 12, tzinfo=UTC)
    job = message()
    uow.job_outbox.get_pending_for_update.return_value = job
    publisher.publish.side_effect = JobPublishError("timeout")
    delivery = DeliverPendingJob(uow, publisher, clock)

    with pytest.raises(JobPublishError):
        delivery.execute()
    uow.commit.assert_not_called()
    uow.job_outbox.mark_published.assert_not_called()

    publisher.publish.side_effect = None
    assert delivery.execute()
    assert [call.args[0].job_id for call in publisher.publish.call_args_list] == [job.job_id] * 2
    uow.job_outbox.mark_published.assert_called_once_with(job.job_id, clock.now())
    uow.commit.assert_called_once()


def test_empty_outbox_does_not_publish() -> None:
    uow, publisher = MagicMock(), MagicMock()
    uow.job_outbox.get_pending_for_update.return_value = None
    assert not DeliverPendingJob(uow, publisher, MagicMock()).execute()
    publisher.publish.assert_not_called()
