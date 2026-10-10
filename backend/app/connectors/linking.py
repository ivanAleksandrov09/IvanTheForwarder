"""Link emails to clients automatically. Owner: A.

By address:  exact contact email -> company domain (never free-mail, never ambiguous) -> sender name == contact name.
By content:  link_by_company() matches the company name the LLM found in the email to a client name.
Returns None when unsure: an unlinked email is better than a wrongly linked one.
"""

import re

from app.repository import Repository
from app.schemas import Direction, Email

FREEMAIL = {"gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com", "abv.bg", "mail.bg", "yahoo.com",
            "icloud.com", "proton.me", "protonmail.com", "dir.bg", "gbg.bg", "mail.ru", "yandex.ru"}

_LEGAL = re.compile(r"\b(еоод|оод|еад|ад|ет|gmbh|ltd|llc|srl|doo|dooel|sa|inc|co)\b|a\.ş\.?|d\.o\.o\.?", re.I)


def _norm(name: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w ]", " ", _LEGAL.sub(" ", name.lower()))).strip()


def link_by_company(company_name: str | None, repo: Repository) -> str | None:
    key = _norm(company_name or "")
    if len(key) < 4:
        return None
    hits = set()
    for c in repo.clients.list():
        for n in filter(None, (_norm(c.name), _norm(c.name_latin or ""))):
            if n == key or (len(key) >= 5 and len(n) >= 5 and (key in n or n in key)):
                hits.add(c.id)
    return hits.pop() if len(hits) == 1 else None


def link_client(email: Email, repo: Repository) -> str | None:
    others = [email.from_address] if email.direction == Direction.inbound else [*email.to_addresses, *email.cc_addresses]
    clients = repo.clients.list()
    for addr in others:
        hits = {c.id for c in clients for ct in c.contacts if ct.email == addr}
        if len(hits) == 1:
            return hits.pop()
    for addr in others:
        domain = addr.rsplit("@", 1)[-1]
        if domain in FREEMAIL:
            continue
        hits = {c.id for c in clients for ct in c.contacts if ct.email and ct.email.rsplit("@", 1)[-1] == domain}
        if len(hits) == 1:
            return hits.pop()
    if email.direction == Direction.inbound and email.from_name:
        hits = {c.id for c in clients for ct in c.contacts if _norm(ct.name) == _norm(email.from_name)}
        if len(hits) == 1:
            return hits.pop()
    return None
