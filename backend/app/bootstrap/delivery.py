import logging
from signal import SIGINT, SIGTERM, signal
from threading import Event

from sqlalchemy.exc import SQLAlchemyError

from app.application.scheduling.ports import JobPublishError
from app.bootstrap.container import build_container
from app.bootstrap.settings import Settings

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    stopping = Event()
    signal(SIGINT, lambda *_: stopping.set())
    signal(SIGTERM, lambda *_: stopping.set())
    container = build_container(Settings())
    delivery = container.deliver_pending_job()
    try:
        while not stopping.is_set():
            try:
                delivered = delivery.execute()
            except (JobPublishError, SQLAlchemyError):
                logger.exception("Не удалось доставить задание из Outbox")
                delivered = False
            if not delivered:
                stopping.wait(1)
    finally:
        container.close()


if __name__ == "__main__":
    main()
