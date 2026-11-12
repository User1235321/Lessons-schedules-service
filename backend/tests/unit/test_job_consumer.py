from threading import Event
from unittest.mock import Mock
from uuid import uuid4

import pytest
from confluent_kafka import TopicPartition

from app.domain.scheduling.job import JobMessage, JobType
from app.domain.shared.ids import JobId, ProjectId
from app.worker.consumer import KafkaJobConsumer


def consumer_fixture():
    consumer = Mock()
    consumer.assignment.return_value = [TopicPartition("schedule.jobs", 0)]
    message = Mock()
    message.error.return_value = None
    message.value.return_value = b"payload"
    message.topic.return_value = "schedule.jobs"
    message.partition.return_value = 0
    job = JobMessage(JobId(uuid4()), ProjectId(uuid4()), JobType.GENERATE)
    return consumer, message, job


def test_consumer_keeps_polling_and_commits_only_after_processing() -> None:
    consumer, message, job = consumer_fixture()
    release, stopping = Event(), Event()
    polls = 0

    def poll(timeout):
        nonlocal polls
        polls += 1
        if polls == 1:
            return message
        if polls >= 4:
            consumer.commit.assert_not_called()
            release.set()
        stopping.wait(0.001)
        return None

    def process(received):
        assert received == job
        assert release.wait(5)
        stopping.set()
        return True

    consumer.poll.side_effect = poll
    KafkaJobConsumer(consumer, lambda _: job, process).run("schedule.jobs", stopping.is_set)
    assert polls >= 4
    consumer.commit.assert_called_once_with(message=message, asynchronous=False)
    consumer.close.assert_called_once()


def test_busy_job_is_retried_without_confirming_offset() -> None:
    consumer, message, job = consumer_fixture()
    stopping = Event()
    received = False
    attempts = 0

    def poll(timeout):
        nonlocal received
        if not received:
            received = True
            return message
        stopping.wait(0.001)
        return None

    def process(received):
        nonlocal attempts
        attempts += 1
        consumer.commit.assert_not_called()
        if attempts == 1:
            return False
        stopping.set()
        return True

    consumer.poll.side_effect = poll
    KafkaJobConsumer(consumer, lambda _: job, process).run("schedule.jobs", stopping.is_set)
    assert attempts == 2
    consumer.commit.assert_called_once()


def test_processing_failure_leaves_message_uncommitted() -> None:
    consumer, message, job = consumer_fixture()
    consumer.poll.side_effect = [message] + [None] * 10000
    process = Mock(side_effect=RuntimeError("database offline"))
    with pytest.raises(RuntimeError, match="database offline"):
        KafkaJobConsumer(consumer, lambda _: job, process).run("schedule.jobs", lambda: False)
    consumer.commit.assert_not_called()
    consumer.close.assert_called_once()
