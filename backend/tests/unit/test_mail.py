from smtplib import SMTPDataError
from unittest.mock import patch

import pytest

from app.application.auth.ports import MailDeliveryError
from app.domain.auth.user import Email
from app.infrastructure.mail import SMTPMailSender


@pytest.fixture
def sender() -> SMTPMailSender:
    return SMTPMailSender("smtp.example.org", 587, "mail-user", "secret", "service@example.org")


def test_smtp_sender_uses_starttls_before_authentication_and_sends_message(
    sender: SMTPMailSender,
) -> None:
    with patch("app.infrastructure.mail.smtplib.SMTP") as smtp:
        client = smtp.return_value
        client.__enter__.return_value = client
        sender.send(Email("student@example.org"), "Восстановление пароля", "Ссылка")

    smtp.assert_called_once_with("smtp.example.org", 587, timeout=5)
    assert [call[0] for call in client.method_calls] == ["starttls", "login", "send_message"]
    client.login.assert_called_once_with("mail-user", "secret")
    assert client.send_message.call_args.kwargs["to_addrs"] == ["student@example.org"]
    message = client.send_message.call_args.args[0]
    assert message["From"] == "service@example.org"
    assert message["To"] == "student@example.org"
    assert message["Subject"] == "Восстановление пароля"
    assert message.get_content() == "Ссылка\n"


def test_smtp_error_excludes_sensitive_server_response(sender: SMTPMailSender) -> None:
    with patch("app.infrastructure.mail.smtplib.SMTP") as smtp:
        smtp.return_value.send_message.side_effect = SMTPDataError(554, b"private message")
        with pytest.raises(MailDeliveryError, match="^SMTPDataError$"):
            sender.send(Email("student@example.org"), "Восстановление пароля", "Ссылка")
