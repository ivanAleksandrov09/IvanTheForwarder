"""Transport implementations. Owner: C. Choose with OUTBOUND_MODE=log|smtp."""

import json
from abc import ABC, abstractmethod
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
    """TODO(owner C): smtplib + email.message.EmailMessage (UTF-8), STARTTLS; sandbox only (Mailtrap/MailHog)."""

    name = "smtp"

    def __init__(self, settings: Settings):
        self.settings = settings

    def send(self, draft: DraftMessage) -> SendResult:
        return SendResult(ok=False, provider=self.name, error="SMTP sender not implemented yet")


def build_sender(settings: Settings) -> Sender:
    if settings.outbound_mode == "smtp":
        return SmtpSender(settings)
    return LogSender(settings.runtime_dir / "outbox.jsonl")
