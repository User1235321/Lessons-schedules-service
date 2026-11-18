import re
from datetime import time
from uuid import UUID

from app.domain.scheduling.constraints import (
    AllowedDaysParameters,
    ClockTimeParameters,
    ConstraintKind,
    ConstraintParameters,
    ConstraintScope,
    ConstraintScopeKind,
    EveryWeekParameters,
    FixedDayParameters,
    MinimumGapParameters,
    RelatedWorkloadParameters,
    TimeRangeParameters,
)
from app.domain.scheduling.resources import WeeklyWindow
from app.domain.shared.errors import InvalidValue
from app.domain.shared.week import Weekday

_TIME_PATTERN = re.compile(r"([01]\d|2[0-3]):[0-5]\d")
_RELATED = {
    ConstraintKind.CONSECUTIVE,
    ConstraintKind.NOT_CONSECUTIVE,
    ConstraintKind.BEFORE,
}


def _fields(values: object, required: set[str], optional: set[str] | None = None) -> dict:
    optional = optional or set()
    if (
        not isinstance(values, dict)
        or required - values.keys()
        or values.keys() - required - optional
    ):
        raise InvalidValue("Неверный набор параметров", field="parameters")
    return values


def _time(value: object) -> time:
    if not isinstance(value, str) or not _TIME_PATTERN.fullmatch(value):
        raise InvalidValue("Укажите время в формате ЧЧ:ММ", field="parameters")
    return time.fromisoformat(value)


def _weekday(value: object) -> Weekday:
    try:
        return Weekday(value)
    except (ValueError, TypeError):
        raise InvalidValue("Неизвестный день недели", field="parameters") from None


def _uuid(value: object) -> UUID:
    try:
        if not isinstance(value, str):
            raise TypeError
        return UUID(value)
    except (ValueError, TypeError, AttributeError):
        raise InvalidValue("Неверный идентификатор нагрузки", field="parameters") from None


def parse_parameters(kind: ConstraintKind, values: object) -> ConstraintParameters:
    if kind in (ConstraintKind.MIN_START_TIME, ConstraintKind.MAX_END_TIME):
        data = _fields(values, {"time"})
        return ClockTimeParameters(_time(data["time"]))
    if kind is ConstraintKind.ALLOWED_DAYS:
        data = _fields(values, {"days"})
        days = data["days"]
        if not isinstance(days, list) or not days:
            raise InvalidValue("Укажите непустой список дней", field="parameters.days")
        parsed = tuple(_weekday(day) for day in days)
        if len(parsed) != len(set(parsed)):
            raise InvalidValue("Дни не должны повторяться", field="parameters.days")
        return AllowedDaysParameters(parsed)
    if kind is ConstraintKind.EVERY_WEEK:
        _fields(values, set())
        return EveryWeekParameters()
    if kind in _RELATED:
        data = _fields(values, {"workload_id"})
        return RelatedWorkloadParameters(_uuid(data["workload_id"]))
    if kind is ConstraintKind.MIN_GAP:
        data = _fields(values, {"workload_id", "minutes"})
        minutes = data["minutes"]
        if type(minutes) is not int or minutes > 2**31 - 1:
            raise InvalidValue("Неверный минимальный интервал", field="parameters.minutes")
        return MinimumGapParameters(_uuid(data["workload_id"]), minutes)
    if kind is ConstraintKind.FIXED_DAY:
        data = _fields(values, {"day"}, {"week"})
        week = data.get("week", "ANY")
        if week not in ("ODD", "EVEN", "ANY"):
            raise InvalidValue("Неизвестная неделя", field="parameters.week")
        return FixedDayParameters(_weekday(data["day"]), week)
    if kind is ConstraintKind.TIME_RANGE:
        data = _fields(values, {"windows"})
        raw = data["windows"]
        if not isinstance(raw, list) or not raw:
            raise InvalidValue("Укажите временные диапазоны", field="parameters.windows")
        windows = []
        for window in raw:
            item = _fields(window, {"week", "day", "start", "end"})
            if item["week"] not in ("ODD", "EVEN", "ANY"):
                raise InvalidValue("Неизвестная неделя", field="parameters.windows")
            windows.append(
                WeeklyWindow(item["week"], _weekday(item["day"]),
                             _time(item["start"]), _time(item["end"]))
            )
        if len(windows) != len(set(windows)):
            raise InvalidValue("Диапазоны не должны повторяться", field="parameters.windows")
        return TimeRangeParameters(tuple(windows))
    raise InvalidValue("Неизвестный тип ограничения", field="constraint_type")


def parameters_to_json(parameters: ConstraintParameters) -> dict[str, object]:
    if isinstance(parameters, ClockTimeParameters):
        return {"time": parameters.value.strftime("%H:%M")}
    if isinstance(parameters, AllowedDaysParameters):
        return {"days": list(parameters.days)}
    if isinstance(parameters, EveryWeekParameters):
        return {}
    if isinstance(parameters, MinimumGapParameters):
        return {"workload_id": str(parameters.workload_id), "minutes": parameters.minutes}
    if isinstance(parameters, RelatedWorkloadParameters):
        return {"workload_id": str(parameters.workload_id)}
    if isinstance(parameters, FixedDayParameters):
        return {"day": parameters.day, "week": parameters.week}
    if isinstance(parameters, TimeRangeParameters):
        return {
            "windows": [
                {
                    "week": window.week,
                    "day": window.day,
                    "start": window.start.strftime("%H:%M"),
                    "end": window.end.strftime("%H:%M"),
                }
                for window in parameters.windows
            ]
        }
    raise InvalidValue("Неизвестные параметры ограничения", field="parameters")


def scope_to_json(scope: ConstraintScope) -> dict[str, str]:
    result = {"type": scope.kind.value}
    if scope.resource_id is not None:
        result["id"] = str(scope.resource_id)
    return result


def scope_from_json(values: dict[str, str]) -> ConstraintScope:
    return ConstraintScope(
        ConstraintScopeKind(values["type"]),
        UUID(values["id"]) if "id" in values else None,
    )
