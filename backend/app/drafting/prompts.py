"""User-message templates per DraftKind. Owner: C. (Role/tone/language rules live in llm/system_prompt.py.)"""

import json

from app.schemas import DraftKind

TASK_INSTRUCTIONS: dict[DraftKind, str] = {
    DraftKind.payment_reminder: (
        "Draft a payment reminder email for the overdue invoice in CONTEXT. State invoice number, amount, "
        "due date and days overdue. Ask for a concrete payment date. If tone is firm, be direct but polite."
    ),
    DraftKind.delay_notice: (
        "Draft a proactive delay notice email about the shipment in CONTEXT, sent BEFORE the client asks. "
        "State the reason (only if given), the new ETA and the original slot, and what we are doing about it."
    ),
    DraftKind.status_update: (
        "Draft a short routine status update email about the shipment in CONTEXT, sent proactively while the truck is "
        "on the road. Say it is on its way, the route, roughly how many km remain (`km_remaining`, a straight-line "
        "estimate: say 'approximately'), whether the truck is moving, and the ETA versus the agreed slot. "
        "Never give coordinates, never name a place that is not in CONTEXT, never guess why a truck is stopped, "
        "and do not promise an arrival time other than `eta`."
    ),
    DraftKind.quote_reply: "Reply to the quote request in CONTEXT. Confirm the requested lane and cargo facts, and state the next step.",
    DraftKind.invoice: "Draft a short cover email for the invoice in CONTEXT. State the invoice number, amount and due date.",
    DraftKind.cmr: "Draft a short cover email for the CMR in CONTEXT. State the shipment reference and CMR number.",
    DraftKind.generic: "Draft a concise business email based only on CONTEXT and the operator instructions.",
}


def build_prompt(kind: DraftKind, context: dict, instructions: str | None) -> str:
    task = TASK_INSTRUCTIONS.get(kind, "Draft a short business email based on CONTEXT.")
    parts = [
        f"TASK: {task}",
        f"LANGUAGE: {context['language']}",
        f"TONE: {context['tone']}",
        "CONTEXT (the only facts you may use):",
        json.dumps(context, ensure_ascii=False, indent=2),
    ]
    if context.get("recent_emails"):
        parts.append(
            "`recent_emails` is earlier correspondence with this client (oldest first). Use it only as background: "
            "stay consistent with it, refer to earlier promises or requests when relevant, never quote it at length "
            "and never take new facts (amounts, dates) from it."
        )
    if instructions:
        parts.append(f"OPERATOR INSTRUCTIONS: {instructions}")
    parts.append("In `rationale`, explain to the operator in English why this message and this tone (1-2 sentences).")
    return "\n".join(parts)
