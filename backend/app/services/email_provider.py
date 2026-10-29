import logging
import smtplib
import uuid
from email.message import EmailMessage
from pathlib import Path

from .. import config

log = logging.getLogger("jobagent.email")


class SendError(Exception):
    def __init__(self, message: str, bounced: bool = False):
        super().__init__(message)
        self.bounced = bounced


class ConsoleProvider:
    name = "console"

    def send(self, to: str, subject: str, body: str, attachments: list[Path]) -> str:
        message_id = f"console-{uuid.uuid4()}"
        log.info("EMAIL (not sent, console provider) to=%s subject=%s attachments=%s\n%s", to, subject, [a.name for a in attachments], body)
        return message_id


class SmtpProvider:
    name = "smtp"

    def send(self, to: str, subject: str, body: str, attachments: list[Path]) -> str:
        msg = EmailMessage()
        msg["From"] = config.SMTP_FROM or config.SMTP_USER
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        for path in attachments:
            data = path.read_bytes()
            maintype, subtype = ("application", "pdf") if path.suffix.lower() == ".pdf" else ("application", "octet-stream")
            msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=path.name)
        try:
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30) as smtp:
                smtp.starttls()
                if config.SMTP_USER:
                    smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
                smtp.send_message(msg)
        except smtplib.SMTPRecipientsRefused as err:
            raise SendError(f"Recipient refused: {err}", bounced=True) from err
        except (smtplib.SMTPException, OSError) as err:
            raise SendError(str(err)) from err
        return msg["Message-ID"] or f"smtp-{uuid.uuid4()}"


def get_email_provider():
    if config.EMAIL_PROVIDER == "smtp" and config.SMTP_HOST:
        return SmtpProvider()
    return ConsoleProvider()
