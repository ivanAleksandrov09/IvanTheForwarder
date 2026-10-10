"""Locale-aware display formatting for drafts/UI. Storage formats never change (see CONVENTIONS.md)."""

from datetime import datetime

from app.core.clock import to_local
from app.schemas import Language, Money


def format_money(m: Money, lang: Language) -> str:
    whole, cents = divmod(abs(m.amount_minor), 100)
    sign = "-" if m.amount_minor < 0 else ""
    if lang == Language.bg:
        return f"{sign}{whole:,}".replace(",", " ") + f",{cents:02d} {m.currency}"  # 1 250,00 EUR
    return f"{sign}{m.currency} {whole:,}.{cents:02d}"  # EUR 1,250.00


def format_date(dt: datetime, lang: Language) -> str:
    local = to_local(dt)
    if lang == Language.en:
        return local.strftime("%d %b %Y")
    return local.strftime("%d.%m.%Y")


def format_datetime(dt: datetime, lang: Language) -> str:
    local = to_local(dt)
    if lang == Language.en:
        return local.strftime("%d %b %Y, %H:%M")
    return local.strftime("%d.%m.%Y, %H:%M ч.") if lang == Language.bg else local.strftime("%d.%m.%Y %H:%M")
