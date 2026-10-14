class DomainError(Exception):
    """Нарушено правило предметной области. Про HTTP здесь ничего не известно.

    В ``details`` кладём только значения, которые переводятся в JSON:
    строки, числа, логические значения, списки и словари из них.
    """

    code = "DOMAIN_ERROR"

    def __init__(self, message: str, **details: object) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class NotFound(DomainError):
    """Объекта нет или он принадлежит другому пользователю (NF_Security_2)."""

    code = "NOT_FOUND"


class AlreadyExists(DomainError):
    code = "ALREADY_EXISTS"


class InvalidValue(DomainError):
    """Локально некорректное значение (F_Valid_1). Поле указывается всегда (F_Valid_2)."""

    code = "INVALID_VALUE"

    def __init__(self, message: str, *, field: str, **details: object) -> None:
        super().__init__(message, field=field, **details)
        self.field = field
