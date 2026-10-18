"""Тексты CHECK-ограничений из доменных перечислений, чтобы не дублировать значения руками."""

from collections.abc import Iterable


def _quoted(values: Iterable[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def one_of(column: str, values: Iterable[str]) -> str:
    return f"{column} IN ({_quoted(values)})"


def all_of(column: str, values: Iterable[str]) -> str:
    """Каждый элемент массива из списка допустимых значений."""
    return f"{column} <@ ARRAY[{_quoted(values)}]::varchar[]"
