"""Builds a DraftMessage: gather context -> LLM (validated JSON) -> queue as pending_review. Owner: C."""

from app.core import clock
from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.core.formatting import format_date, format_datetime, format_money
from app.core.ids import new_id
from app.drafting.prompts import build_prompt
from app.llm import LLMClient
from app.repository import Repository
from app.risk.scoring import get_profile
from app.schemas import (
    DraftChannel,
    DraftContent,
    DraftKind,
    DraftMessage,
    DraftStatus,
    GenerateDraftRequest,
    InvoiceStatus,
    Language,
)


def _context(req: GenerateDraftRequest, repo: Repository) -> tuple[dict, list[str], dict]:
    """Returns (context for the LLM, recipient addresses, resolved ids). Only facts we hold go in here."""
    s = get_settings()
    now = clock.now()
    client = repo.clients.require(req.client_id)
    profile = get_profile(client.id, repo, now)
    language = req.language or client.preferred_language
    tone = req.tone or profile.recommended_tone
    contact = next((c for c in client.contacts if c.email), None)

    ctx: dict = {
        "kind": req.kind.value,
        "language": language.value,
        "tone": tone.value,
        "company_name": s.company_name,
        "company_name_latin": s.company_name_latin,
        "operator_name": s.operator_name if language == Language.bg else s.operator_name_latin,
        "client_name": client.name,
        "contact_name": contact.name if contact else None,
        "today": format_date(now, language),
    }
    ids: dict = {"invoice_id": req.invoice_id, "shipment_id": req.shipment_id}

    if req.kind == DraftKind.payment_reminder:
        inv = repo.invoices.get(req.invoice_id) if req.invoice_id else None
        if inv is None:  # default: oldest unpaid invoice past due
            open_ = repo.invoices.list(
                client_id=client.id,
                where=lambda i: i.status in (InvoiceStatus.issued, InvoiceStatus.partially_paid) and i.due_at < now,
            )
            inv = min(open_, key=lambda i: i.due_at) if open_ else None
        if inv is None:
            raise NotFoundError(f"no overdue invoice for {client.id}")
        ids["invoice_id"] = inv.id
        ctx |= {
            "invoice_number": inv.number,
            "invoice_total": format_money(inv.total, language),
            "invoice_issued": format_date(inv.issued_at, language),
            "invoice_due": format_date(inv.due_at, language),
            "days_overdue": (now.date() - inv.due_at.date()).days,
        }

    if req.kind == DraftKind.delay_notice:
        shp = repo.shipments.require(req.shipment_id) if req.shipment_id else None
        if shp is None:
            raise NotFoundError("delay_notice needs shipment_id")
        truck = repo.trucks.get(shp.truck_id) if shp.truck_id else None
        event = repo.events.get(req.event_id) if req.event_id else None
        delay_min = int((shp.eta_at - shp.delivery_planned_at).total_seconds() // 60) if shp.eta_at else None
        ctx |= {
            "shipment_reference": shp.reference,
            "route": f"{shp.origin.city} → {shp.destination.city}",
            "plate_number": truck.plate_number if truck else None,
            "planned": format_datetime(shp.delivery_planned_at, language),
            "eta": format_datetime(shp.eta_at, language) if shp.eta_at else None,
            "delay_text": f"{delay_min // 60}h {delay_min % 60:02d}min" if delay_min else None,
            "delay_reason": (event.data.get("reason") if event else None),
        }
        # TODO(owner C): show destination-local times (Munich = Europe/Berlin), not Sofia time

    # TODO(owner C): quote_reply / invoice / cmr contexts (+ attach Document ids)
    return ctx, ([contact.email] if contact else []), ids


def generate_draft(req: GenerateDraftRequest, repo: Repository, llm: LLMClient) -> DraftMessage:
    ctx, to, ids = _context(req, repo)
    content, meta = llm.complete_json(
        task=f"draft.{req.kind.value}",
        prompt=build_prompt(req.kind, ctx, req.instructions),
        schema=DraftContent,
        mock_context=ctx,
    )
    now = clock.now()
    draft = DraftMessage(
        id=new_id("drf"),
        kind=req.kind,
        channel=DraftChannel.email,
        status=DraftStatus.pending_review,
        language=content.language,
        tone=content.tone,
        client_id=req.client_id,
        shipment_id=ids["shipment_id"],
        invoice_id=ids["invoice_id"],
        event_id=req.event_id,
        to_addresses=to,
        subject=content.subject,
        body=content.body,
        rationale=content.rationale,
        created_at=now,
        updated_at=now,
        llm=meta,
    )
    return repo.drafts.upsert(draft)
