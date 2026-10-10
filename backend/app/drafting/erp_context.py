"""A client's current standing (open invoices, active loads, trucks) as LLM context, from whatever is in the repository
(seed data, Zeron/ERP sync, manual entries). Facts only; no margins, risk scores or internal notes."""

from datetime import datetime

from app.core.formatting import format_datetime, format_date, format_money
from app.repository import Repository
from app.schemas import InvoiceStatus, Language, Money, ShipmentStatus

MAX_LOADS = 5


def account_summary(repo: Repository, client_id: str, language: Language, now: datetime) -> dict:
    open_invoices = repo.invoices.list(client_id=client_id, where=lambda i: i.status in (InvoiceStatus.issued, InvoiceStatus.partially_paid))
    loads = repo.shipments.list(client_id=client_id, where=lambda s: s.status in (ShipmentStatus.booked, ShipmentStatus.in_transit))
    summary: dict = {}
    if open_invoices:
        totals: dict[str, int] = {}
        for inv in open_invoices:
            totals[inv.total.currency] = totals.get(inv.total.currency, 0) + inv.total.amount_minor
        summary["open_invoices"] = {
            "count": len(open_invoices),
            "total": [format_money(Money.of(amount, cur), language) for cur, amount in totals.items()],
            "overdue_count": sum(1 for i in open_invoices if i.due_at < now),
            "oldest_due": format_date(min(i.due_at for i in open_invoices), language),
        }
    if loads:
        plates = {t.id: t.plate_number for t in repo.trucks.list()}
        summary["active_loads"] = [
            {
                "reference": s.reference,
                "route": f"{s.origin.city} → {s.destination.city}",
                "status": s.status.value,
                "eta": format_datetime(s.eta_at, language) if s.eta_at else None,
                "truck": plates.get(s.truck_id) if s.truck_id else None,
            }
            for s in sorted(loads, key=lambda s: s.delivery_planned_at)[:MAX_LOADS]
        ]
    return summary
