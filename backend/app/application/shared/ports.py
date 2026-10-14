from datetime import datetime
from typing import Protocol
from uuid import UUID


class Clock(Protocol):
    """Текущее время в UTC. Бизнес-логика не вызывает datetime.now() сама (HLD 15.3)."""

    def now(self) -> datetime: ...


class IdGenerator(Protocol):
    """Источник новых идентификаторов (HLD 15.3)."""

    def new_id(self) -> UUID: ...
