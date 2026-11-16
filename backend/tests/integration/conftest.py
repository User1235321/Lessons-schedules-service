from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from redis import Redis
from sqlalchemy import Engine, delete
from testcontainers.community.redis import RedisContainer
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import LogMessageWaitStrategy

from app.bootstrap.container import Container, build_container
from app.bootstrap.settings import Settings
from app.domain.auth.user import Email, User
from app.domain.projects.project import Project
from app.domain.shared.ids import ProjectId, UserId
from app.infrastructure.persistence.database import create_session_factory
from app.infrastructure.persistence.models import UserRow


@pytest.fixture(scope="session")
def redis_client(database_url: str) -> Iterator[Redis]:
    with RedisContainer("redis:7-alpine") as redis:
        client = redis.get_client(decode_responses=True, socket_timeout=1)
        try:
            yield client
        finally:
            client.close()


@pytest.fixture(scope="session")
def kafka_servers(database_url: str) -> Iterator[str]:
    kafka = DockerContainer("apache/kafka:3.9.1").with_exposed_ports(9092)
    configuration = {
        "KAFKA_NODE_ID": "1",
        "KAFKA_PROCESS_ROLES": "broker,controller",
        "KAFKA_LISTENERS": "PLAINTEXT://:9092,CONTROLLER://:9093,BROKER://:29092",
        "KAFKA_CONTROLLER_LISTENER_NAMES": "CONTROLLER",
        "KAFKA_LISTENER_SECURITY_PROTOCOL_MAP": "PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT,BROKER:PLAINTEXT",
        "KAFKA_CONTROLLER_QUORUM_VOTERS": "1@localhost:9093",
        "KAFKA_INTER_BROKER_LISTENER_NAME": "BROKER",
        "KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR": "1",
        "KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS": "0",
    }
    for key, value in configuration.items():
        kafka.with_env(key, value)
    kafka.with_command(
        [
            "sh",
            "-c",
            (
                "while [ ! -f /tmp/listeners ]; do sleep 0.1; done; "
                'export KAFKA_ADVERTISED_LISTENERS="$(cat /tmp/listeners)"; exec /etc/kafka/docker/run'
            ),
        ]
    )
    try:
        kafka.start()
        servers = f"{kafka.get_container_host_ip()}:{kafka.get_exposed_port(9092)}"
        kafka.exec(
            [
                "sh",
                "-c",
                'printf "%s" "$1" > /tmp/listeners',
                "sh",
                f"PLAINTEXT://{servers},BROKER://localhost:29092",
            ]
        )
        LogMessageWaitStrategy("Kafka Server started").with_startup_timeout(60).wait_until_ready(
            kafka
        )
        yield servers
    finally:
        kafka.stop()


@pytest.fixture
def scheduling_context(
    migrated_engine: Engine,
    redis_client: Redis,
) -> Iterator[tuple[Container, User, Project]]:
    container = replace(
        build_container(Settings()),
        engine=migrated_engine,
        session_factory=create_session_factory(migrated_engine),
        redis=redis_client,
    )
    now = datetime.now(UTC)
    owner = User(
        id=UserId(uuid4()),
        email=Email(f"jobs-{uuid4()}@example.org"),
        password_hash="unused",
        created_at=now,
    )
    project = Project.create(
        project_id=ProjectId(uuid4()), owner_id=owner.id, name="Расписание", now=now
    )
    with container.uow() as uow:
        uow.users.add(owner)
        uow.projects.add(project)
        uow.commit()
    try:
        yield container, owner, project
    finally:
        with migrated_engine.begin() as connection:
            connection.execute(delete(UserRow).where(UserRow.id == owner.id))
