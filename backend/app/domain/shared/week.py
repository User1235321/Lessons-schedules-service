from collections.abc import Iterable
from dataclasses import dataclass
from datetime import time
from enum import StrEnum

from app.domain.shared.errors import InvalidValue


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


class Week(StrEnum):
    """Неделя двухнедельного цикла. Значения совпадают с форматом test-data."""

    ODD = "ODD"
    EVEN = "EVEN"
    ANY = "ANY"  # обе недели


@dataclass(frozen=True)
class WeeklyInterval:
    """Промежуток времени в день цикла: когда ресурс доступен или когда ему удобнее (HLD 9.4)."""

    week: Week
    day: Weekday
    start: time
    end: time

    def __post_init__(self) -> None:
        if self.end <= self.start:  # F_Valid_1
            raise InvalidValue("Окончание должно быть позже начала", field="end")


_WEEK_ORDER = {week: index for index, week in enumerate(Week)}
_DAY_ORDER = {day: index for index, day in enumerate(Weekday)}


def ordered_intervals(intervals: Iterable[WeeklyInterval]) -> tuple[WeeklyInterval, ...]:
    """Промежутки без точных повторов, по неделе, дню и времени.

    Пересекающиеся промежутки остаются как есть: это не ошибка ввода (F_Valid_3).
    """
    return tuple(
        sorted(
            set(intervals),
            key=lambda interval: (
                _WEEK_ORDER[interval.week],
                _DAY_ORDER[interval.day],
                interval.start,
                interval.end,
            ),
        )
    )
