from app.domain.shared.errors import InvalidValue

MAX_NAME_LENGTH = 200


def clean_name(name: str, *, field: str, missing: str) -> str:
    """Название без пробелов по краям. Пустое или слишком длинное — ошибка ввода (F_Valid_1)."""
    cleaned = name.strip()
    if not cleaned:
        raise InvalidValue(missing, field=field)
    if len(cleaned) > MAX_NAME_LENGTH:
        raise InvalidValue(f"Не длиннее {MAX_NAME_LENGTH} символов", field=field)
    return cleaned


def name_key(name: str) -> str:
    """По этому ключу сравниваются названия: без учёта регистра."""
    return name.casefold()


def check_student_count(count: int) -> None:
    if count <= 0:  # F_Valid_1
        raise InvalidValue("Нужно положительное число студентов", field="student_count")
