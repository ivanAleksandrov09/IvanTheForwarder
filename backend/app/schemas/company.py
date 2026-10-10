"""Our own company identity, editable in the app. Falls back to .env until it is set. Owner: lead."""

from app.schemas.common import ContractModel


class CompanyInput(ContractModel):
    name: str
    name_latin: str
    operator_name: str
    operator_name_latin: str


class CompanyProfile(CompanyInput):
    id: str = "company"  # single record
