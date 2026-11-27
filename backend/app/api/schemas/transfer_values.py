from app.domain.shared.errors import InvalidValue


def check_storage_values(value, field: str = "file") -> None:
    """PostgreSQL хранит UTF-8 без NUL и 32-битные целые для числовых полей проекта."""
    if isinstance(value, dict):
        for name, item in value.items():
            check_storage_values(item, str(name))
    elif isinstance(value, (list, tuple)):
        for item in value:
            check_storage_values(item, field)
    elif isinstance(value, str):
        if "\x00" in value:
            raise InvalidValue("Текст содержит нулевой символ", field=field)
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            raise InvalidValue("Некорректный символ Unicode", field=field) from None
    elif isinstance(value, int) and not -(2**31) <= value < 2**31:
        raise InvalidValue("Значение выходит за диапазон целого числа", field=field)
