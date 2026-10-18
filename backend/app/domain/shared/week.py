from collections.abc import Iterable
from enum import StrEnum


class Weekday(StrEnum):
    """День недели. Значения совпадают с форматом проекта в test-data."""

    MONDAY = "MONDAY"
    TUESDAY = "TUESDAY"
    WEDNESDAY = "WEDNESDAY"
    THURSDAY = "THURSDAY"
    FRIDAY = "FRIDAY"
    SATURDAY = "SATURDAY"
    SUNDAY = "SUNDAY"


def ordered_weekdays(days: Iterable[Weekday]) -> tuple[Weekday, ...]:
    """Дни без повторов, в порядке недели."""
    chosen = set(days)
    return tuple(day for day in Weekday if day in chosen)
