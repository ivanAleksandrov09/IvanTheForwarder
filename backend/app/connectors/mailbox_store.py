"""Mailbox credentials entered at runtime (login prompt) or taken from env. Owner: A.

Stored in data/runtime/mailbox.json (gitignored). PLAINTEXT on disk: fine for a demo with a throwaway
mailbox, NOT for production (TODO: OS keyring / encrypted secret store).
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from app.core.config import Settings

# provider -> (imap host, port). "custom" uses whatever the user typed.
PROVIDERS: dict[str, tuple[str, int]] = {
    "gmail": ("imap.gmail.com", 993),
    "outlook": ("outlook.office365.com", 993),
}
_DOMAIN_TO_PROVIDER = {
    "gmail.com": "gmail",
    "googlemail.com": "gmail",
    "outlook.com": "outlook",
    "hotmail.com": "outlook",
    "live.com": "outlook",
    "office365.com": "outlook",
}


@dataclass
class MailboxCredentials:
    username: str
    secret: str  # app password, or OAuth2 access token when auth == "xoauth2"
    host: str
    port: int = 993
    auth: Literal["password", "xoauth2"] = "password"
    provider: str = "custom"

    @classmethod
    def for_provider(cls, username: str, secret: str, provider: str | None = None, auth: str = "password"):
        provider = provider or _DOMAIN_TO_PROVIDER.get(username.rsplit("@", 1)[-1].lower(), "custom")
        if provider not in PROVIDERS:
            raise ValueError(f"unknown provider {provider!r}: give host/port explicitly")
        host, port = PROVIDERS[provider]
        return cls(username=username, secret=secret, host=host, port=port, auth=auth, provider=provider)


def _path(settings: Settings) -> Path:
    return settings.runtime_dir / "mailbox.json"


def save(settings: Settings, creds: MailboxCredentials) -> None:
    path = _path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(creds)), encoding="utf-8")


def is_saved(settings: Settings) -> bool:
    return _path(settings).exists()


def clear(settings: Settings) -> None:
    _path(settings).unlink(missing_ok=True)


def load(settings: Settings) -> MailboxCredentials | None:
    """Runtime-saved credentials win; otherwise IMAP_HOST/IMAP_USER/IMAP_PASSWORD from .env."""
    path = _path(settings)
    if path.exists():
        return MailboxCredentials(**json.loads(path.read_text(encoding="utf-8")))
    if settings.imap_host and settings.imap_user and settings.imap_password:
        return MailboxCredentials(
            username=settings.imap_user, secret=settings.imap_password, host=settings.imap_host, provider="env"
        )
    return None
