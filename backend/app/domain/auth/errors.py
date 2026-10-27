from app.domain.shared.errors import AlreadyExists, NotAuthenticated


class EmailAlreadyRegistered(AlreadyExists):
    """Адрес уже занят другой учётной записью (F_Auth_3)."""

    code = "EMAIL_ALREADY_REGISTERED"


class InvalidCredentials(NotAuthenticated):
    """Неверный адрес или пароль (F_Auth_5). Для обоих случаев ответ одинаковый."""

    code = "INVALID_CREDENTIALS"
