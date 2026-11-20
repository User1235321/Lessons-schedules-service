from collections.abc import Iterator
from datetime import time

from app.domain.scheduling.constraints import (
    AllowedDaysParameters,
    ClockTimeParameters,
    ConstraintKind,
    EveryWeekParameters,
    ExtraConstraintSnapshot,
    FixedDayParameters,
    MinimumGapParameters,
    RelatedWorkloadParameters,
    TimeRangeParameters,
)
from app.domain.scheduling.resources import WeeklyWindow
from app.domain.scheduling.schedule import ScheduleConflict, ScheduleEntry
from app.domain.shared.week import Weekday

_DAY_NUMBER = {day: index for index, day in enumerate(Weekday)}
_REASONS = {
    ConstraintKind.MIN_START_TIME: "Занятие начинается раньше разрешённого времени",
    ConstraintKind.MAX_END_TIME: "Занятие заканчивается позже разрешённого времени",
    ConstraintKind.ALLOWED_DAYS: "Занятие назначено на день вне разрешённого списка",
    ConstraintKind.EVERY_WEEK: "Нагрузка должна быть представлена на каждой неделе",
    ConstraintKind.CONSECUTIVE: "Занятия должны идти подряд в один день",
    ConstraintKind.NOT_CONSECUTIVE: "Занятия не должны идти подряд",
    ConstraintKind.MIN_GAP: "Интервал между занятиями меньше установленного",
    ConstraintKind.BEFORE: "Нарушен заданный порядок проведения занятий",
    ConstraintKind.FIXED_DAY: "Занятие назначено вне зафиксированного дня или недели",
    ConstraintKind.TIME_RANGE: "Занятие выходит за разрешённые временные интервалы",
}


def covered_by(windows: tuple[WeeklyWindow, ...], entry: ScheduleEntry) -> bool:
    candidates = sorted(
        (
            window
            for window in windows
            if window.week in (entry.week, "ANY") and window.day == entry.weekday
        ),
        key=lambda window: window.start,
    )
    covered_until = entry.start_time
    for window in candidates:
        if window.start > covered_until:
            break
        covered_until = max(covered_until, window.end)
        if covered_until >= entry.end_time:
            return True
    return False


def seconds(value: time) -> float:
    return value.hour * 3600 + value.minute * 60 + value.second + value.microsecond / 1_000_000


def _cycle_seconds(entry: ScheduleEntry, value: time) -> float:
    day = _DAY_NUMBER[entry.weekday] + (7 if entry.week == "EVEN" else 0)
    return day * 86400 + seconds(value)


def _adjacent(left: ScheduleEntry, right: ScheduleEntry) -> bool:
    return (
        left.week == right.week
        and left.weekday == right.weekday
        and (left.end_time == right.start_time or right.end_time == left.start_time)
    )


def _gap(left: ScheduleEntry, right: ScheduleEntry) -> float:
    return max(
        _cycle_seconds(right, right.start_time) - _cycle_seconds(left, left.end_time),
        _cycle_seconds(left, left.start_time) - _cycle_seconds(right, right.end_time),
    )


def _violations(
    constraint: ExtraConstraintSnapshot,
    entries: list[ScheduleEntry],
    related: list[ScheduleEntry],
    complete: bool,
) -> Iterator[tuple[tuple[ScheduleEntry, ...], dict[str, object]]]:
    params = constraint.parameters
    kind = constraint.kind
    if isinstance(params, EveryWeekParameters):
        missing = sorted({"ODD", "EVEN"} - {entry.week for entry in entries})
        if complete and missing:
            yield tuple(entries), {"missing_weeks": missing}
        return
    if kind is ConstraintKind.BEFORE:
        if not complete:
            return
        # При повторениях сравниваются соответствующие проведения в порядке цикла.
        ordered = sorted(
            entries, key=lambda entry: (_cycle_seconds(entry, entry.start_time), entry.id)
        )
        later = sorted(
            related, key=lambda entry: (_cycle_seconds(entry, entry.start_time), entry.id)
        )
        for entry in ordered[len(later) :]:
            yield (entry,), {}
        for entry, other in zip(ordered, later):
            if entry.id == other.id or _cycle_seconds(entry, entry.end_time) > _cycle_seconds(
                other, other.start_time
            ):
                yield (entry, other), {}
        return
    for entry in entries:
        if isinstance(params, ClockTimeParameters):
            violates = (
                entry.start_time < params.value
                if kind is ConstraintKind.MIN_START_TIME
                else entry.end_time > params.value
            )
        elif isinstance(params, AllowedDaysParameters):
            violates = entry.weekday not in params.days
        elif isinstance(params, FixedDayParameters):
            violates = entry.weekday != params.day or params.week not in ("ANY", entry.week)
        elif isinstance(params, TimeRangeParameters):
            violates = not covered_by(params.windows, entry)
        elif isinstance(params, RelatedWorkloadParameters) and kind is ConstraintKind.CONSECUTIVE:
            violates = complete and not any(
                entry.id != other.id and _adjacent(entry, other) for other in related
            )
        elif isinstance(params, RelatedWorkloadParameters):
            for other in related:
                if entry.id != other.id and _adjacent(entry, other):
                    yield (entry, other), {}
            continue
        elif isinstance(params, MinimumGapParameters):
            for other in related:
                if entry.id != other.id and _gap(entry, other) < params.minutes * 60:
                    yield (entry, other), {"minimum_minutes": params.minutes}
            continue
        else:
            continue
        if violates:
            yield (entry,), {}


def constraint_conflicts(
    constraint: ExtraConstraintSnapshot,
    entries: list[ScheduleEntry],
    related: list[ScheduleEntry],
    complete: bool,
) -> Iterator[ScheduleConflict]:
    for affected, details in _violations(constraint, entries, related, complete):
        yield ScheduleConflict(
            constraint.kind.value,
            _REASONS[constraint.kind],
            tuple(sorted({entry.id for entry in affected})),
            {"constraint_id": str(constraint.id), **details},
        )
