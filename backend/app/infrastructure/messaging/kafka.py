from confluent_kafka import KafkaError, KafkaException, Message, Producer

from app.application.scheduling.ports import JobPublishError
from app.domain.scheduling.job import JobMessage
from app.infrastructure.messaging.job_messages import JOBS_TOPIC, encode_job_message


class KafkaJobPublisher:
    def __init__(self, producer: Producer, *, timeout: float = 10) -> None:
        self._producer = producer
        self._timeout = timeout

    def publish(self, message: JobMessage) -> None:
        acknowledged = False
        delivery_error: KafkaError | None = None

        def on_delivery(error: KafkaError | None, _: Message) -> None:
            nonlocal acknowledged, delivery_error
            acknowledged = error is None
            delivery_error = error

        try:
            self._producer.produce(
                JOBS_TOPIC,
                key=str(message.job_id).encode("utf-8"),
                value=encode_job_message(message),
                on_delivery=on_delivery,
            )
            pending = self._producer.flush(self._timeout)
        except (BufferError, KafkaException) as error:
            raise JobPublishError("Не удалось опубликовать задание") from error
        if pending or not acknowledged:
            raise JobPublishError(
                f"Публикация задания не подтверждена: {delivery_error or 'timeout'}"
            )
