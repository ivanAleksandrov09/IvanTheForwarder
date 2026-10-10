"""Explainable client risk profile. Every point of score must be traceable to a RiskFactor with evidence."""

from pydantic import Field

from app.schemas.common import ClientId, ContractModel, EvidenceRef, Money, Ratio, UtcDatetime
from app.schemas.enums import CargoType, Confidence, RiskFactorCode, RiskLevel, Tone


class RiskFactor(ContractModel):
    code: RiskFactorCode
    label: str  # short, human-readable, e.g. "Pays late"
    impact: int = Field(ge=-100, le=100)  # points added to the score (negative lowers risk)
    explanation: str  # one sentence WITH the concrete numbers, e.g. "Paid 9 of 10 invoices late, on average 34 days."
    evidence: list[EvidenceRef] = []


class ClientMetrics(ContractModel):
    invoices_total: int = Field(ge=0)
    invoices_paid: int = Field(ge=0)
    avg_payment_delay_days: float | None = None  # positive = late
    max_payment_delay_days: int | None = None
    on_time_payment_rate: Ratio | None = None
    open_overdue_invoices: int = Field(ge=0)
    overdue_amount: Money | None = None
    max_days_overdue: int | None = None
    shipments_total: int = Field(ge=0)
    delayed_shipments: int = Field(ge=0)
    fines_count: int = Field(ge=0)
    fines_total: Money | None = None
    avg_margin_pct: float | None = None  # e.g. 14.5 (percent, display only)
    avg_email_response_hours: float | None = None


class RiskProfile(ContractModel):
    client_id: ClientId  # primary key (one profile per client)
    computed_at: UtcDatetime
    score: int = Field(ge=0, le=100)  # 0 = safe, 100 = very risky
    level: RiskLevel
    confidence: Confidence
    factors: list[RiskFactor]  # sorted by |impact| desc
    metrics: ClientMetrics
    observed_cargo_types: list[CargoType] = []
    recommended_tone: Tone  # used by drafting
    summary: str  # 1-2 sentences, internal only
    scoring_version: str  # e.g. "rules-v0"
