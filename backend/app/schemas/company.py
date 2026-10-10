"""Our own company identity, editable in the app. Falls back to .env until it is set. Owner: lead."""

from typing import Literal

from app.schemas.common import ContractModel


class CompanyInput(ContractModel):
    name: str
    name_latin: str
    operator_name: str
    operator_name_latin: str
    erp_system: str = ""  # onboarding: the systems the company already uses
    gps_system: str = ""
    other_systems: str = ""  # comma separated


class CompanyProfile(CompanyInput):
    id: str = "company"  # single record


class OnboardingEmail(ContractModel):
    """A drafted email to a system's support team asking for integration access. Never sent by the app."""

    role: Literal["erp", "gps", "other"]
    system: str
    subject: str
    body: str
