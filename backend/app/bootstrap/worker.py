import logging
from signal import SIGINT, SIGTERM, signal
from threading import Event

from confluent_kafka import Consumer

from app.bootstrap.container import build_container
from app.bootstrap.settings import Settings
from app.infrastructure.messaging.job_messages import JOBS_TOPIC, decode_job_message
from app.worker.consumer import KafkaJobConsumer


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    stopping = Event()
    signal(SIGINT, lambda *_: stopping.set())
    signal(SIGTERM, lambda *_: stopping.set())
    container = build_container(Settings())
    consumer = Consumer(
        {
            "bootstrap.servers": container.settings.kafka_bootstrap_servers,
            "group.id": "scheduler-worker",
            "enable.auto.commit": False,
            "enable.auto.offset.store": False,
            "auto.offset.reset": "earliest",
        }
    )
    worker = KafkaJobConsumer(consumer, decode_job_message, container.process_job().execute)
    try:
        worker.run(JOBS_TOPIC, stopping.is_set)
    finally:
        container.close()


if __name__ == "__main__":
    main()
