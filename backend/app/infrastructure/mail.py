import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage

from app.application.auth.ports import MailDeliveryError
from app.domain.auth.user import Email


@dataclass(frozen=True)
class SMTPMailSender:
    host: str
    port: int
    username: str
    password: str = field(repr=False)
    sender: str

    def send(self, recipient: Email, subject: str, body: str) -> None:
        if not self.host or not self.sender:
            raise MailDeliveryError("MAIL_HOST or MAIL_FROM is not configured")

        try:
            message = EmailMessage()
            message["From"] = self.sender
            message["To"] = recipient.value
            message["Subject"] = subject
            message.set_content(body)

            tls = ssl.create_default_context()
            if self.port == 465:
                client = smtplib.SMTP_SSL(self.host, self.port, timeout=5, context=tls)
            else:
                client = smtplib.SMTP(self.host, self.port, timeout=5)
            with client:
                if self.port != 465:
                    client.starttls(context=tls)
                if self.username:
                    client.login(self.username, self.password)
                client.send_message(message, to_addrs=[recipient.value])
        except (OSError, ValueError) as error:
            # SMTP-ответ может содержать адрес или фрагмент письма.
            raise MailDeliveryError(type(error).__name__) from None
