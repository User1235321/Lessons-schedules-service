from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock
from uuid import UUID, uuid4

from confluent_kafka import Consumer, Producer, TopicPartition
from confluent_kafka.admin import AdminClient, NewTopic
from fastapi.testclient import TestClient

from app.application.scheduling.delivery import DeliverPendingJob
from app.bootstrap.api import create_app
from app.domain.scheduling.job import JobProgress, JobStatus
from app.domain.scheduling.problem import ScheduleProblem
from app.domain.scheduling.solver import ScheduleVariant, SolverResult, SolverStatus
from app.infrastructure.messaging.job_messages import JOBS_TOPIC, decode_job_message
from app.infrastructure.messaging.kafka import KafkaJobPublisher
from app.worker.consumer import KafkaJobConsumer


def test_fastapi_outbox_kafka_worker_redis_chain(
    scheduling_context: tuple,
    kafka_servers: str,
) -> None:
    container, owner, project = scheduling_context
    admin = AdminClient({"bootstrap.servers": kafka_servers})
    admin.create_topics([NewTopic(JOBS_TOPIC, num_partitions=1, replication_factor=1)])[
        JOBS_TOPIC
    ].result(15)
    client = TestClient(create_app(container))
    token = container.tokens.issue_access_token(owner.id, container.clock.now())
    created = client.post(
        f"/projects/{project.id}/generation-jobs",
        json={"result_mode": "SINGLE"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert created.status_code == 202
    job_id = UUID(created.json()["job_id"])
    source = Mock(load=Mock(return_value=ScheduleProblem(project.settings)))
    solver = Mock()

    def solve(problem, options, control):
        control.report_progress(JobProgress(75))
        assert container.job_state().get_progress(job_id) == JobProgress(75)
        return SolverResult(SolverStatus.SOLVED, (ScheduleVariant((), ()),))

    solver.solve.side_effect = solve
    process = container.process_job(problems=source, solver=solver)
    stopping, finished = Event(), Event()
    handled = []

    def handle(message):
        processed = process.execute(message)
        if processed:
            handled.append(message)
            if len(handled) == 2:
                stopping.set()
                finished.set()
        return processed

    group_id = f"test-scheduler-{uuid4()}"
    consumer = Consumer(
        {
            "bootstrap.servers": kafka_servers,
            "group.id": group_id,
            "enable.auto.commit": False,
            "enable.auto.offset.store": False,
            "auto.offset.reset": "earliest",
        }
    )
    worker = KafkaJobConsumer(consumer, decode_job_message, handle)
    publisher = KafkaJobPublisher(
        Producer(
            {
                "bootstrap.servers": kafka_servers,
                "enable.idempotence": True,
                "acks": "all",
            }
        )
    )
    delivery = DeliverPendingJob(container.uow(), publisher, container.clock)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(worker.run, JOBS_TOPIC, stopping.is_set)
        try:
            assert delivery.execute()
            with container.uow() as uow:
                job = uow.jobs.get(project.id, job_id)
            from app.domain.scheduling.job import JobMessage

            publisher.publish(JobMessage(job.id, job.project_id, job.job_type))
            assert finished.wait(30)
        finally:
            stopping.set()
        future.result(timeout=10)
    solver.solve.assert_called_once()
    assert [message.job_id for message in handled] == [job_id, job_id]
    with container.uow() as uow:
        assert uow.jobs.get(project.id, job_id).status is JobStatus.COMPLETED
        assert len(uow.schedules.list_for_job(project.id, job_id)) == 1
    verifier = Consumer({"bootstrap.servers": kafka_servers, "group.id": group_id})
    try:
        assert verifier.committed([TopicPartition(JOBS_TOPIC, 0)], timeout=10)[0].offset == 2
    finally:
        verifier.close()
