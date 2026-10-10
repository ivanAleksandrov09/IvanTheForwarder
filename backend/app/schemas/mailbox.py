"""Mailbox login and LLM email extraction. Owner: lead."""

from datetime import date

from pydantic import Field

from app.schemas.common import ContractModel, EmailAddress, UtcDatetime
from app.schemas.enums import EmailIntent, Language, MailboxProvider


class MailboxLoginRequest(ContractModel):
    provider: MailboxProvider | None = None  # null = detect from the email domain
    email: EmailAddress
    password: str  # Gmail/Outlook app password


class MailboxStatus(ContractModel):
    connected: bool  # true = real mailbox active, false = mock connector
    email: EmailAddress | None = None
    provider: MailboxProvider | None = None
    last_sync_at: UtcDatetime | None = None
    last_error: str | None = None


class EmailExtraction(ContractModel):
    """JSON the LLM returns for one email. Unknown = null, never guessed."""

    intent: EmailIntent
    summary: str = Field(description="one sentence, in English")
    language: Language | None = None
    origin: str | None = None
    destination: str | None = None
    cargo_description: str | None = None
    weight_kg: int | None = Field(default=None, ge=0)
    requested_date: date | None = None  # pickup/delivery/payment date mentioned
    invoice_number: str | None = None
    urgent: bool = False
