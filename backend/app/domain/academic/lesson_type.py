from enum import StrEnum


class LessonType(StrEnum):
    """Тип занятия. Значения совпадают с форматом test-data."""

    LECTURE = "LECTURE"
    PRACTICE = "PRACTICE"
    LAB = "LAB"
