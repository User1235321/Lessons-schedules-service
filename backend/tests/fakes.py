from datetime import UTC, datetime, timedelta

from app.application.auth.ports import MailDeliveryError
from app.domain.auth.user import Email


class FakeClock:
    """Часы, которые тест переводит вперёд."""

    def __init__(self) -> None:
        self.current = datetime.now(UTC)

    def now(self) -> datetime:
        return self.current

    def advance(self, delta: timedelta) -> None:
        self.current += delta


class FakeMailSender:
    def __init__(self) -> None:
        self.messages: list[tuple[Email, str, str]] = []
        self.fail = False

    def send(self, recipient: Email, subject: str, body: str) -> None:
        if self.fail:
            raise MailDeliveryError("Test SMTP failure")
        self.messages.append((recipient, subject, body))
