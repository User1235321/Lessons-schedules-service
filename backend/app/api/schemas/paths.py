from collections.abc import Iterator
from contextlib import contextmanager

from app.domain.shared.errors import InvalidValue


@contextmanager
def inside(prefix: str) -> Iterator[None]:
    """Поле в ошибке домена — путь в JSON запроса, например time_mode.step_minutes (F_Valid_2)."""
    try:
        yield
    except InvalidValue as error:
        raise InvalidValue(error.message, field=f"{prefix}.{error.field}") from error
