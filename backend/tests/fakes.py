from datetime import UTC, datetime, timedelta


class FakeClock:
    """Часы, которые тест переводит вперёд."""

    def __init__(self) -> None:
        self.current = datetime.now(UTC)

    def now(self) -> datetime:
        return self.current

    def advance(self, delta: timedelta) -> None:
        self.current += delta
