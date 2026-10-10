"""Effective company identity: the saved profile if any, else the .env defaults. Owner: lead."""

from app.core.config import Settings
from app.repository import Repository
from app.schemas import CompanyInput, CompanyProfile


def effective(repo: Repository, settings: Settings) -> CompanyInput:
    saved = repo.company.get("company")
    if saved is not None:
        return CompanyInput(**saved.model_dump(exclude={"id"}))
    return CompanyInput(
        name=settings.company_name,
        name_latin=settings.company_name_latin,
        operator_name=settings.operator_name,
        operator_name_latin=settings.operator_name_latin,
    )


def save(repo: Repository, body: CompanyInput) -> CompanyProfile:
    return repo.company.upsert(CompanyProfile(**body.model_dump()))
