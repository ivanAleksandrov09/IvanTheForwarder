"""Call recordings and human-reviewed extraction results."""

from datetime import date

from pydantic import Field

from app.schemas.common import CallLogId, ContractModel, UtcDatetime


class CallRecording(ContractModel):
    id: CallLogId
    filename: str
    audio_path: str
    content_type: str
    uploaded_at: UtcDatetime
    duration_seconds: int | None = Field(default=None, ge=0)
    language: str | None = None
    transcript: str | None = None
    transcription_status: str = "pending"


class CallExtraction(ContractModel):
    call_id: CallLogId
    extracted_at: UtcDatetime
    status: str = "pending_review"
    summary: str
    client_name: str | None = None
    contact_name: str | None = None
    origin: str | None = None
    destination: str | None = None
    pickup_date: date | None = None
    delivery_date: date | None = None
    cargo: str | None = None
    weight_kg: int | None = Field(default=None, ge=0)
    pallets: int | None = Field(default=None, ge=0)
    vehicle: str | None = None
    price_eur: int | None = Field(default=None, ge=0)
    payment_terms: str | None = None
    requirements: list[str] = []
    missing_fields: list[str] = []
    confidence: dict[str, float] = {}
    evidence: dict[str, str] = {}
    transcript: str
    model: str
    load_id: str | None = None


class CallExtractionContent(ContractModel):
    summary: str
    client_name: str | None = None
    contact_name: str | None = None
    origin: str | None = None
    destination: str | None = None
    pickup_date: date | None = None
    delivery_date: date | None = None
    cargo: str | None = None
    weight_kg: int | None = Field(default=None, ge=0)
    pallets: int | None = Field(default=None, ge=0)
    vehicle: str | None = None
    price_eur: int | None = Field(default=None, ge=0)
    payment_terms: str | None = None
    requirements: list[str] = []
    missing_fields: list[str] = []
    confidence: dict[str, float] = {}
    evidence: dict[str, str] = {}


class ConfirmCallRequest(ContractModel):
    origin: str | None = None
    destination: str | None = None
    pickup_date: date | None = None
    cargo: str | None = None
    weight_kg: int | None = Field(default=None, ge=0)
    vehicle: str | None = None
    price_eur: int | None = Field(default=None, ge=0)
