import re
from dataclasses import dataclass
from datetime import datetime

from app.domain.shared.errors import InvalidValue
from app.domain.shared.ids import UserId

MAX_EMAIL_LENGTH = 254  # предел длины адреса в SMTP (RFC 5321)

# Только грубая проверка формата. Что адрес настоящий, подтвердит письмо сброса пароля.
_EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


@dataclass(frozen=True)
class Email:
    """Адрес электронной почты, приведённый к нижнему регистру.

    Ivan@Mail.ru и ivan@mail.ru считаются одним адресом, поэтому уникальность
    (F_Auth_3) проверяется по нормализованному значению.
    """

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().lower()
        if len(normalized) > MAX_EMAIL_LENGTH:
            raise InvalidValue(f"Адрес длиннее {MAX_EMAIL_LENGTH} символов", field="email")
        if not _EMAIL_PATTERN.fullmatch(normalized):
            raise InvalidValue("Некорректный адрес электронной почты", field="email")
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value


@dataclass(kw_only=True)
class User:
    """Учётная запись (F_Auth_1). Пароль хранится только в виде хеша (HLD 8)."""

    id: UserId
    email: Email
    password_hash: str
    created_at: datetime
