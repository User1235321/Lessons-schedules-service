from app.domain.shared.errors import AlreadyExists


class EmailAlreadyRegistered(AlreadyExists):
    """Адрес уже занят другой учётной записью (F_Auth_3)."""

    code = "EMAIL_ALREADY_REGISTERED"
