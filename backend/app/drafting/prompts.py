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
    if instructions:
        parts.append(f"OPERATOR INSTRUCTIONS: {instructions}")
    parts.append("In `rationale`, explain to the operator in English why this message and this tone (1-2 sentences).")
    return "\n".join(parts)
