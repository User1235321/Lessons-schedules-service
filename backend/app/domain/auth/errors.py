from app.domain.shared.errors import AlreadyExists, NotAuthenticated


class EmailAlreadyRegistered(AlreadyExists):
    """Адрес уже занят другой учётной записью (F_Auth_3)."""

    code = "EMAIL_ALREADY_REGISTERED"


class InvalidCredentials(NotAuthenticated):
    """Неверный адрес или пароль (F_Auth_5). Для обоих случаев ответ одинаковый."""

    code = "INVALID_CREDENTIALS"


class InvalidAccessToken(NotAuthenticated):
    """Access-токен подделан, испорчен или истёк. Клиенту нужно обновить его через refresh."""

    code = "INVALID_ACCESS_TOKEN"


class InvalidRefreshToken(NotAuthenticated):
    """Refresh-токен неизвестен, уже обменян, отозван или истёк. Клиенту нужно войти заново."""

    code = "INVALID_REFRESH_TOKEN"
