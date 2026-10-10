"""Emails, documents and connector feeds. Owner: A.

Base emails (data/seed/emails.json) = mailbox history already in the DB at startup.
Feed emails (data/seed/feeds/email_inbox.json) = "new mail" the mock email connector delivers on sync.

TODO(owner A): grow to ~30 base emails (bg/en/ro/tr/ru), threads (thread_id), attachments -> Documents,
               a few messy ones (forwarded chains, signatures, mixed Cyrillic/Latin, windows-1251 artefacts).
"""

import random
from datetime import timedelta

from app.schemas import Direction, Document, DocumentType, Email, Language, ShipmentStatus, SourceType
from app.seed import story
from app.seed.story import OUR_MAILBOX, at

L = Language


def _email(n, client_id, direction, sender, sender_name, to, subject, body, lang, when, shipment_id=None, labels=(), attachments=()):
    eid = f"eml_{n:04d}"
    return Email(
        id=eid,
        message_id=f"<{eid}.{n * 7919}@{sender.split('@')[1]}>",
        thread_id=None,
        mailbox=OUR_MAILBOX,
        direction=direction,
        from_address=sender,
        from_name=sender_name,
        to_addresses=[to],
        subject=subject,
        body_text=body,
        language=lang,
        sent_at=when,
        client_id=client_id,
        shipment_id=shipment_id,
        attachment_document_ids=list(attachments),
        labels=list(labels),
    )


IN, OUT = Direction.inbound, Direction.outbound
PETROV = ("g.petrov@balkansteel.bg", "Георги Петров")
WEBER = ("a.weber@rhein-logistik.de", "Anna Weber")


def _base_emails(shipments_by_client: dict[str, list]) -> list[Email]:
    rhein_fined = shipments_by_client[story.STRICT_CLIENT][2]
    vardar = shipments_by_client["cli_0007"][0]
    return [
        _email(1, story.LATE_PAYER, OUT, OUR_MAILBOX, "Иван Иванов", PETROV[0],
               "Напомняне за плащане – фактура № 0000000801",
               "Здравейте, г-н Петров,\n\nНапомняме, че фактура № 0000000801 на стойност 3 480,00 EUR е с падеж "
               "31.08.2026. Моля, потвърдете датата на плащане.\n\nПоздрави,\nИван Иванов\nСпедиция Витоша ЕООД",
               L.bg, at(days=-40), labels=["reminder"]),
        _email(2, story.LATE_PAYER, IN, *PETROV, OUR_MAILBOX, "RE: Напомняне за плащане – фактура № 0000000801",
               "Здравейте,\n\nПлащането ще бъде направено до края на седмицата.\n\nПоздрави,\nГ. Петров",
               L.bg, at(days=-38), labels=["payment_promise"]),
        _email(3, story.LATE_PAYER, OUT, OUR_MAILBOX, "Иван Иванов", PETROV[0],
               "Повторно напомняне – фактура № 0000000801",
               "Здравейте, г-н Петров,\n\nВсе още не сме получили плащането по фактура № 0000000801. "
               "Моля за спешно потвърждение.\n\nПоздрави,\nИван Иванов",
               L.bg, at(days=-20), labels=["reminder"]),
        _email(4, story.LATE_PAYER, IN, *PETROV, OUR_MAILBOX, "RE: Повторно напомняне – фактура № 0000000801",
               "Имаме временни затруднения с ликвидността. Ще платим следващия месец, съжалявам за забавянето.",
               L.bg, at(days=-19), labels=["payment_promise"]),
        _email(5, story.STRICT_CLIENT, IN, *WEBER, OUR_MAILBOX, "Framework agreement – delivery slot rules",
               "Dear partners,\n\nAs a reminder, delivery slots at our Munich DC are binding. According to §7 of the "
               "framework agreement, late deliveries are charged EUR 150 per started hour beyond the slot, capped at "
               "EUR 600 per delivery. Please inform us proactively about any expected delay.\n\nBest regards,\nAnna Weber",
               L.en, at(days=-60), labels=["contract"]),
        _email(6, story.STRICT_CLIENT, IN, *WEBER, OUR_MAILBOX, f"Penalty notice – {rhein_fined.reference}",
               f"Dear Sir or Madam,\n\nShipment {rhein_fined.reference} arrived after the agreed slot. A penalty according "
               "to §7 will be deducted from your next invoice.\n\nRegards,\nAnna Weber",
               L.en, rhein_fined.delivered_at + timedelta(days=3), shipment_id=rhein_fined.id,
               labels=["penalty"]),
        _email(7, story.STRICT_CLIENT, IN, *WEBER, OUR_MAILBOX, "Transport order SPD-2026-0901 – slot Fri 16.10. 08:00",
               "Hello,\n\nPlease find attached our transport order: 26 pallets gearboxes, 14.2 t, Sofia → Munich DC "
               "(Gate 4). Delivery slot: 16.10.2026, 08:00 CEST. The slot is binding.\n\nThank you,\nAnna Weber",
               L.en, at(days=-2), shipment_id=story.HERO_SHIPMENT, labels=["order"], attachments=["doc_0901"]),
        _email(8, "cli_0003", IN, "m.koleva@trakia-agro.bg", "Мария Колева", OUR_MAILBOX,
               "Запитване: пшеница Стара Загора – Констанца",
               "Здравейте,\n\nТърсим 3 камиона за пшеница (по 24 т) от Стара Загора до пристанище Констанца следващата "
               "седмица. Моля, не комбинирайте нашия товар с ADR пратки.\n\nПоздрави,\nМария Колева",
               L.bg, at(days=-25), labels=["quote_request"]),
        _email(9, "cli_0004", IN, "andrei.popescu@dunareatrans.ro", "Andrei Popescu", OUR_MAILBOX, "Plata facturii",
               "Bună ziua,\n\nPlata pentru ultima factură va fi efectuată săptămâna viitoare.\n\nMulțumesc,\nAndrei Popescu",
               L.ro, at(days=-12), labels=["payment_promise"]),
        _email(10, "cli_0005", IN, "mehmet.yilmaz@anadolutekstil.com.tr", "Mehmet Yılmaz", OUR_MAILBOX,
               "Rate request Bursa – Sofia, 2 trucks/week",
               "Hello,\n\nWe plan 2 full trucks per week Bursa → Sofia from November. Could you send your best rate "
               "and transit time?\n\nBest regards,\nMehmet Yılmaz",
               L.en, at(days=-15), labels=["quote_request"]),
        _email(11, "cli_0006", IN, "e.dimitrova@sofiapharma.bg", "Елена Димитрова", OUR_MAILBOX,
               "Температурен режим 2–8 °C",
               "Здравейте,\n\nНапомням, че за всички наши пратки е задължителен температурен лог 2–8 °C. При отклонение "
               "ще предявим рекламация, както при случая от юли.\n\nПоздрави,\nЕлена Димитрова",
               L.bg, at(days=-9), labels=["requirements"]),
        _email(12, "cli_0007", IN, "b.trajkovski@vardarfood.mk", "Bojan Trajkovski", OUR_MAILBOX,
               f"Missing CMR copy – {vardar.reference}",
               f"Hi,\n\nWe still have not received the signed CMR for {vardar.reference}. We will pay the invoice once "
               "we have it.\n\nBojan",
               L.en, vardar.delivered_at + timedelta(days=6), shipment_id=vardar.id, labels=["documents"]),
    ]


def _feed_emails() -> list[Email]:
    return [
        _email(101, story.LATE_PAYER, IN, *PETROV, OUR_MAILBOX, "Нов товар Перник – Букурещ",
               "Здравейте,\n\nИмаме 22 т арматура за Букурещ, товарене следващия вторник. Можете ли да ни дадете цена "
               "до утре?\n\nПоздрави,\nГ. Петров",
               L.bg, at(minutes=-25), labels=["quote_request"]),
        _email(102, "cli_0005", IN, "mehmet.yilmaz@anadolutekstil.com.tr", "Mehmet Yılmaz", OUR_MAILBOX,
               "Teklif talebi: Bursa – Sofya, 18 ton tekstil",
               "Merhaba,\n\n21 Ekim için Bursa'dan Sofya'ya 18 ton tekstil ürünü için fiyat teklifi rica ediyoruz.\n\n"
               "Saygılarımızla,\nMehmet Yılmaz",
               L.tr, at(minutes=-50), labels=["quote_request"]),
    ]


def _documents(shipments) -> list[Document]:
    docs = []
    started = [s for s in shipments if s.status in (ShipmentStatus.delivered, ShipmentStatus.in_transit)]
    recent = sorted(started, key=lambda s: s.pickup_planned_at)[-12:]
    for s in recent:
        docs.append(Document(
            id=f"doc_cmr{s.id.split('_')[1]}",
            doc_type=DocumentType.cmr,
            filename=f"CMR_{s.reference}.pdf",
            mime_type="application/pdf",
            source=SourceType.documents,
            received_at=s.delivered_at or s.picked_up_at,
            language=Language.en,
            client_id=s.client_id,
            shipment_id=s.id,
            extracted_fields={
                "cmr_number": s.cmr_number or "",
                "place_of_taking_over": s.origin.city,
                "place_of_delivery": s.destination.city,
                "gross_weight_kg": str(s.weight_kg),
            },
            extraction_confidence=0.93,
        ))
    docs.append(Document(
        id="doc_0901", doc_type=DocumentType.transport_order, filename="Transportauftrag_SPD-2026-0901.pdf",
        mime_type="application/pdf", source=SourceType.email, received_at=at(days=-2), language=Language.en,
        client_id=story.STRICT_CLIENT, shipment_id=story.HERO_SHIPMENT, email_id="eml_0007",
        extracted_fields={"delivery_slot": "2026-10-16T06:00:00Z", "pallets": "26", "gross_weight_kg": "14200"},
        extraction_confidence=0.88,
    ))
    docs.append(Document(
        id="doc_0902", doc_type=DocumentType.rate_sheet, filename="Rhein_Logistik_rates_2026.xlsx",
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", source=SourceType.email,
        received_at=at(days=-90), language=Language.en, client_id=story.STRICT_CLIENT,
        extracted_fields={"lane": "BG-DE", "currency": "EUR", "valid_until": "2026-12-31"},
    ))
    return docs


def generate(rng: random.Random, business: dict[str, list]) -> dict[str, list]:
    by_client: dict[str, list] = {}
    for s in business["shipments"]:
        by_client.setdefault(s.client_id, []).append(s)
    return {
        "emails": _base_emails(by_client),
        "documents": _documents(business["shipments"]),
        "call_logs": [],  # STRETCH(owner A)
        "feeds": {"email_inbox": _feed_emails()},
    }
