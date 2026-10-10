"""Transport implementations. Owner: C. Choose with OUTBOUND_MODE=log|smtp."""

import json
import smtplib
import ssl
from abc import ABC, abstractmethod
from email.message import EmailMessage
from pathlib import Path

from app.core import clock
from app.core.config import Settings
from app.schemas import DraftMessage, SendResult


class Sender(ABC):
    name: str

    @abstractmethod
    def send(self, draft: DraftMessage) -> SendResult: ...


class LogSender(Sender):
    """MVP: 'sending' appends the message to data/runtime/outbox.jsonl."""

    name = "log"

    def __init__(self, outbox: Path):
        self.outbox = outbox

    def send(self, draft: DraftMessage) -> SendResult:
        self.outbox.parent.mkdir(parents=True, exist_ok=True)
        with self.outbox.open("a", encoding="utf-8") as f:
            f.write(json.dumps(draft.model_dump(mode="json"), ensure_ascii=False) + "\n")
        return SendResult(ok=True, provider=self.name, sent_at=clock.now(), provider_message_id=f"log-{draft.id}")


class SmtpSender(Sender):
    """SMTP transport for a sandbox such as Mailtrap or MailHog."""

    name = "smtp"

    def __init__(self, settings: Settings):
        self.settings = settings

    def send(self, draft: DraftMessage) -> SendResult:
        if not self.settings.smtp_host or not self.settings.smtp_from:
            return SendResult(ok=False, provider=self.name, error="SMTP requires SMTP_HOST and SMTP_FROM")
        message = EmailMessage()
        message["From"] = self.settings.smtp_from
        message["To"] = ", ".join(draft.to_addresses)
        if draft.cc_addresses:
            message["Cc"] = ", ".join(draft.cc_addresses)
        message["Subject"] = draft.subject or ""
        message.set_content(draft.body, charset="utf-8")
        try:
            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=15) as client:
                client.ehlo()
                client.starttls(context=ssl.create_default_context())
                client.ehlo()
                if self.settings.smtp_user:
                    client.login(self.settings.smtp_user, self.settings.smtp_password)
                client.send_message(message)
        except (smtplib.SMTPException, OSError) as exc:
            return SendResult(ok=False, provider=self.name, error=f"SMTP send failed: {exc}")
        return SendResult(ok=True, provider=self.name, sent_at=clock.now(), provider_message_id=f"smtp-{draft.id}")


def build_sender(settings: Settings) -> Sender:
    if settings.outbound_mode == "smtp":
        return SmtpSender(settings)
    return LogSender(settings.runtime_dir / "outbox.jsonl")
