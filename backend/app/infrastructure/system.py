from datetime import UTC, datetime
from uuid import UUID, uuid4


class SystemClock:
    """Реализует Clock."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class UuidGenerator:
    """Реализует IdGenerator."""

    def new_id(self) -> UUID:
        return uuid4()
