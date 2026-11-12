import logging
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor

from confluent_kafka import Consumer, KafkaException, Message, TopicPartition

from app.domain.scheduling.job import JobMessage

logger = logging.getLogger(__name__)


class KafkaJobConsumer:
    def __init__(
        self,
        consumer: Consumer,
        decode: Callable[[bytes], JobMessage],
        process: Callable[[JobMessage], bool],
    ) -> None:
        self._consumer = consumer
        self._decode = decode
        self._process = process
        self._message: Message | None = None
        self._job: JobMessage | None = None
        self._future: Future[bool] | None = None

    def run(self, topic: str, is_stopping: Callable[[], bool]) -> None:
        self._consumer.subscribe([topic], on_assign=self._on_assign)
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                while not is_stopping() or self._future is not None:
                    self._complete(executor, is_stopping())
                    if is_stopping() and self._future is None:
                        break
                    message = self._consumer.poll(0.2)
                    if message is not None:
                        self._receive(message, executor)
        finally:
            self._consumer.close()

    def _on_assign(self, consumer: Consumer, partitions: list[TopicPartition]) -> None:
        consumer.assign(partitions)
        if self._message is not None:
            consumer.pause(partitions)

    def _receive(self, message: Message, executor: ThreadPoolExecutor) -> None:
        if message.error():
            raise KafkaException(message.error())
        try:
            job = self._decode(message.value())
        except ValueError:
            logger.exception("Пропущено некорректное сообщение Kafka")
            self._consumer.commit(message=message, asynchronous=False)
            return
        self._message = message
        self._job = job
        self._consumer.pause(self._consumer.assignment())
        self._future = executor.submit(self._process, job)

    def _complete(self, executor: ThreadPoolExecutor, stopping: bool) -> None:
        if self._future is None or not self._future.done():
            return
        try:
            processed = self._future.result()
        except Exception:
            logger.exception("Ошибка обработки Kafka-сообщения; offset не подтверждён")
            raise
        if not processed:
            self._future = None if stopping else executor.submit(self._process, self._job)
            return
        assignments = self._consumer.assignment()
        if any(
            partition.topic == self._message.topic()
            and partition.partition == self._message.partition()
            for partition in assignments
        ):
            self._consumer.commit(message=self._message, asynchronous=False)
        self._message = None
        self._job = None
        self._future = None
        if assignments:
            self._consumer.resume(assignments)
