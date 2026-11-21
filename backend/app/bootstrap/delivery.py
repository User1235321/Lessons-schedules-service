import logging
from signal import SIGINT, SIGTERM, signal
from threading import Event

from sqlalchemy.exc import SQLAlchemyError

from app.application.scheduling.ports import JobPublishError
from app.bootstrap.container import build_container
from app.bootstrap.settings import Settings
from app.infrastructure.logging import configure_logging

logger = logging.getLogger(__name__)


def main() -> None:
    settings = Settings()
    configure_logging(settings.log_level)
    stopping = Event()
    signal(SIGINT, lambda *_: stopping.set())
    signal(SIGTERM, lambda *_: stopping.set())
    container = build_container(settings)
    delivery = container.deliver_pending_job()
    try:
        while not stopping.is_set():
            try:
                delivered = delivery.execute()
            except JobPublishError:
                delivered = False
            except SQLAlchemyError as error:
                logger.exception(
                    "Outbox delivery failed",
                    extra={
                        "event": "outbox.delivery.failed",
                        "exception_type": type(error).__name__,
                    },
                )
                delivered = False
            if not delivered:
                stopping.wait(1)
    finally:
        container.close()


if __name__ == "__main__":
    main()
