import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import timedelta

from app.application.auth.ports import MailDeliveryError, MailSender, PasswordHasher
from app.application.shared.ports import Clock
from app.application.shared.uow import UnitOfWork
from app.domain.auth.errors import InvalidPasswordResetToken
from app.domain.auth.password_reset import PasswordResetToken
from app.domain.auth.user import Email, check_new_password

logger = logging.getLogger(__name__)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass(frozen=True)
class RequestPasswordReset:
    uow: UnitOfWork
    mail: MailSender
    clock: Clock
    ttl_minutes: int
    base_url: str | None

    def execute(self, email_value: str) -> None:
        email = Email(email_value)
        with self.uow:
            user = self.uow.users.get_by_email(email)
            if user is None:
                return
            if self.base_url is None:
                logger.warning(
                    "Password reset URL is not configured",
                    extra={"event": "auth.password_reset.url_missing"},
                )
                return
            token = secrets.token_urlsafe(32)
            self.uow.password_resets.replace(
                PasswordResetToken(
                    user_id=user.id,
                    token_hash=_token_hash(token),
                    expires_at=self.clock.now() + timedelta(minutes=self.ttl_minutes),
                )
            )
            self.uow.commit()

        link = f"{self.base_url.rstrip('/')}/password-reset/confirm#token={token}"
        body = (
            f"Откройте ссылку и задайте новый пароль:\n{link}\n\n"
            f"Срок действия ссылки в минутах: {self.ttl_minutes}.\n"
            "Если вы не запрашивали восстановление пароля, проигнорируйте это письмо."
        )
        try:
            self.mail.send(email, "Восстановление пароля", body)
        except MailDeliveryError as error:
            logger.warning(
                "Password reset email delivery failed: %s", error,
                extra={
                    "event": "auth.password_reset.delivery_failed",
                    "exception_type": type(error).__name__,
                },
            )


@dataclass(frozen=True)
class ConfirmPasswordReset:
    uow: UnitOfWork
    passwords: PasswordHasher
    clock: Clock

    def execute(self, token: str, password: str) -> None:
        check_new_password(password)
        with self.uow:
            stored = self.uow.password_resets.get_for_update(_token_hash(token))
            if stored is None or self.clock.now() >= stored.expires_at:
                raise InvalidPasswordResetToken("Ссылка восстановления недействительна")
            self.uow.users.update_password_hash(stored.user_id, self.passwords.hash(password))
            self.uow.password_resets.remove(stored.user_id)
            self.uow.commit()
