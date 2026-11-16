from dataclasses import dataclass

from app.application.scheduling.ports import JobPublisher
from app.application.shared.ports import Clock
from app.application.shared.uow import UnitOfWork


@dataclass
class DeliverPendingJob:
    uow: UnitOfWork
    publisher: JobPublisher
    clock: Clock

    def execute(self) -> bool:
        with self.uow:
            message = self.uow.job_outbox.get_pending_for_update()
            if message is None:
                return False
            self.publisher.publish(message)
            self.uow.job_outbox.mark_published(message.job_id, self.clock.now())
            self.uow.commit()
        return True
