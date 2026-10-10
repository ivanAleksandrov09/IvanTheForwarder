"""Canned responses for LLM_MODE=mock and for live-mode fallback (demo safety net).

Keyed by task name. A value is either a string or a callable(ctx: dict) -> str, where ctx is the
`mock_context` the caller passed to the LLM client. JSON tasks must return JSON that validates
against the requested schema.

TODO(owner C): add canned drafts for every DraftKind you implement, in bg and en.
TODO(owner B): add canned output for any LLM task you add (e.g. "risk.summary").
"""

import json
from collections.abc import Callable

MockValue = str | Callable[[dict], str]


def _get(ctx: dict, key: str, placeholder: str) -> str:
    v = ctx.get(key)
    return str(v) if v not in (None, "") else placeholder


def _payment_reminder(ctx: dict) -> str:
    lang = ctx.get("language", "en")
    if lang == "bg":
        subject = f"Напомняне за плащане по фактура № {_get(ctx, 'invoice_number', '[НОМЕР]')}"
        body = (
            f"Здравейте, {_get(ctx, 'contact_name', '[ИМЕ]')},\n\n"
            f"Пишем Ви във връзка с фактура № {_get(ctx, 'invoice_number', '[НОМЕР]')} "
            f"на стойност {_get(ctx, 'invoice_total', '[СУМА]')} с падеж {_get(ctx, 'invoice_due', '[ДАТА]')}. "
            f"Към днешна дата плащането не е постъпило ({_get(ctx, 'days_overdue', '[N]')} дни след падежа).\n\n"
            "Моля, потвърдете до края на седмицата на коя дата ще бъде извършено плащането. "
            "Ако вече сте платили, ще Ви бъдем благодарни да ни изпратите копие от платежното нареждане.\n\n"
            f"С уважение,\n{_get(ctx, 'operator_name', '')}\n{_get(ctx, 'company_name', '')}"
        )
    else:
        subject = f"Payment reminder – invoice {_get(ctx, 'invoice_number', '[NUMBER]')}"
        body = (
            f"Dear {_get(ctx, 'contact_name', '[NAME]')},\n\n"
            f"We are writing regarding invoice {_get(ctx, 'invoice_number', '[NUMBER]')} for "
            f"{_get(ctx, 'invoice_total', '[AMOUNT]')}, due on {_get(ctx, 'invoice_due', '[DATE]')}. "
            f"As of today we have not received the payment ({_get(ctx, 'days_overdue', '[N]')} days overdue).\n\n"
            "Please confirm by the end of this week when the payment will be made. If it has already been "
            "sent, we would appreciate a copy of the payment order.\n\n"
            f"Kind regards,\n{_get(ctx, 'operator_name', '')}\n{_get(ctx, 'company_name_latin', '')}"
        )
    return json.dumps(
        {
            "subject": subject,
            "body": body,
            "language": lang,
            "tone": ctx.get("tone", "firm"),
            "rationale": "[MOCK] Invoice is overdue; tone follows the client's payment history.",
        },
        ensure_ascii=False,
    )


def _delay_notice(ctx: dict) -> str:
    lang = ctx.get("language", "en")
    if lang == "bg":
        subject = f"Закъснение на пратка {_get(ctx, 'shipment_reference', '[РЕФ.]')}"
        body = (
            f"Здравейте, {_get(ctx, 'contact_name', '[ИМЕ]')},\n\n"
            f"Искаме проактивно да Ви уведомим, че камион {_get(ctx, 'plate_number', '[НОМЕР]')} с пратка "
            f"{_get(ctx, 'shipment_reference', '[РЕФ.]')} ({_get(ctx, 'route', '[МАРШРУТ]')}) закъснява поради "
            f"{_get(ctx, 'delay_reason', '[ПРИЧИНА]')}. Новото очаквано време на пристигане е "
            f"{_get(ctx, 'eta', '[ЧАС]')}, около {_get(ctx, 'delay_text', '[N]')} след уговорения слот "
            f"({_get(ctx, 'planned', '[ЧАС]')}).\n\n"
            "Следим камиона непрекъснато и ще Ви информираме веднага при промяна. Извиняваме се за неудобството.\n\n"
            f"С уважение,\n{_get(ctx, 'operator_name', '')}\n{_get(ctx, 'company_name', '')}"
        )
    else:
        subject = f"Delay notice – shipment {_get(ctx, 'shipment_reference', '[REF]')}"
        body = (
            f"Dear {_get(ctx, 'contact_name', '[NAME]')},\n\n"
            f"We would like to inform you proactively that truck {_get(ctx, 'plate_number', '[PLATE]')} carrying "
            f"shipment {_get(ctx, 'shipment_reference', '[REF]')} ({_get(ctx, 'route', '[ROUTE]')}) is delayed "
            f"due to {_get(ctx, 'delay_reason', '[REASON]')}. The new estimated arrival is "
            f"{_get(ctx, 'eta', '[TIME]')}, approximately {_get(ctx, 'delay_text', '[N]')} after the agreed slot "
            f"({_get(ctx, 'planned', '[TIME]')}).\n\n"
            "Our dispatcher is monitoring the truck continuously and will update you immediately if the ETA "
            "changes. We apologise for the inconvenience.\n\n"
            f"Kind regards,\n{_get(ctx, 'operator_name', '')}\n{_get(ctx, 'company_name_latin', '')}"
        )
    return json.dumps(
        {
            "subject": subject,
            "body": body,
            "language": lang,
            "tone": ctx.get("tone", "apologetic"),
            "rationale": "[MOCK] Projected ETA is past the promised slot; client is sensitive to delays.",
        },
        ensure_ascii=False,
    )


def _generic(ctx: dict) -> str:
    lang = ctx.get("language", "en")
    return json.dumps(
        {
            "subject": "[MOCK] Draft" if lang != "bg" else "[MOCK] Чернова",
            "body": f"[MOCK] Draft for '{ctx.get('kind', 'generic')}' to {_get(ctx, 'client_name', '[CLIENT]')}.",
            "language": lang,
            "tone": ctx.get("tone", "formal"),
            "rationale": "[MOCK] No canned template for this draft kind yet.",
        },
        ensure_ascii=False,
    )


MOCK_RESPONSES: dict[str, MockValue] = {
    "system.ping": lambda ctx: (
        "Здравейте! Аз съм Иван, AI асистентът на Вашата спедиция (mock режим – без външен API)."
        if ctx.get("language", "bg") == "bg"
        else "Hello! I'm Ivan, your forwarding assistant (mock mode – no external API call)."
    ),
    "draft.payment_reminder": _payment_reminder,
    "draft.delay_notice": _delay_notice,
    "draft.generic": _generic,
}


def mock_response(task: str, ctx: dict | None) -> str:
    ctx = ctx or {}
    value = MOCK_RESPONSES.get(task)
    if value is None and task.startswith("draft."):
        value = _generic
    if value is None:
        return f"[MOCK] No canned response for task '{task}'."
    return value(ctx) if callable(value) else value
