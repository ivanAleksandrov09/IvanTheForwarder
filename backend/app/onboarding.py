"""Onboarding: one editable email per system asking its support team for integration access. Fixed templates: no AI call, so
nothing can be invented and nothing costs money. Owner: lead."""

from app.schemas import CompanyInput, OnboardingEmail

# what we ask each kind of system for
DATA = {
    "en": {
        "erp": "invoices (issue date, due date, amount, payment status), clients/counterparties with their contacts, and orders/shipments",
        "gps": "the list of vehicles, the current position of each (latitude, longitude, speed, time), the position history, and how often positions update",
        "other": "[THE DATA WE NEED, e.g. orders, documents, positions]",
    },
    "bg": {
        "erp": "фактури (дата на издаване, падеж, сума, статус на плащане), клиенти/контрагенти с техните контакти и поръчки/превози",
        "gps": "списък на превозните средства, текуща позиция на всяко (ширина, дължина, скорост, час), история на позициите и колко често се обновяват",
        "other": "[ДАННИТЕ, КОИТО ни трябват, напр. поръчки, документи, позиции]",
    },
}

TEXT = {
    "en": {
        "subject": "API / integration access request – {system} – {company}",
        "body": (
            "Hello {system} support team,\n\n"
            "We are {company} and we use {system}. We are setting up an assistant that prepares customer emails and payment "
            "reminders, and we would like to connect it to our {system} data in read-only mode.\n\n"
            "Could you please tell us:\n"
            "1. Does {system} offer an API or web services? If so, please send the technical documentation.\n"
            "2. How does authentication work, and how can we get access credentials (ideally a read-only user or key)?\n"
            "3. Is there a test environment?\n"
            "4. Can the following be read through it: {data}?\n"
            "5. Is there any extra cost, licence term or rate limit for API access?\n"
            "6. If there is no API: which scheduled export formats (XML, Excel, CSV) do you recommend?\n\n"
            "Our account / contract number: [ACCOUNT NUMBER]\n"
            "Please also tell us who our technical contact should be.\n\n"
            "Thank you,\n{name}\n{company}"
        ),
    },
    "bg": {
        "subject": "Заявка за достъп до API / интеграция – {system} – {company}",
        "body": (
            "Здравейте, екип по поддръжка на {system},\n\n"
            "Ние сме {company} и използваме {system}. Въвеждаме асистент, който подготвя имейли до клиенти и напомняния за "
            "плащане, и бихме искали да го свържем с данните ни в {system} само за четене.\n\n"
            "Моля, информирайте ни:\n"
            "1. Предлага ли {system} API или уеб услуги? Ако да, изпратете техническата документация.\n"
            "2. Как се удостоверява достъпът и как можем да получим данни за достъп (най-добре потребител или ключ само за четене)?\n"
            "3. Има ли тестова среда?\n"
            "4. Могат ли през него да се четат: {data}?\n"
            "5. Има ли допълнителна цена, лицензни условия или ограничения на заявките за достъп до API?\n"
            "6. Ако няма API: кои формати за автоматичен експорт (XML, Excel, CSV) препоръчвате?\n\n"
            "Номер на клиентска сметка / договор: [НОМЕР]\n"
            "Моля, посочете и кой да бъде нашият технически контакт.\n\n"
            "Благодаря Ви,\n{name}\n{company}"
        ),
    },
}


def build_emails(company: CompanyInput, language: str) -> list[OnboardingEmail]:
    """One email per system the user named (ERP, GPS, and each comma-separated 'other')."""
    systems = [("erp", company.erp_system), ("gps", company.gps_system)]
    systems += [("other", s) for s in company.other_systems.split(",")]
    bg = language == "bg"
    values = {
        "company": company.name if bg else (company.name_latin or company.name),
        "name": company.operator_name if bg else (company.operator_name_latin or company.operator_name),
    }
    emails = []
    for role, system in systems:
        system = system.strip()
        if not system:
            continue
        fields = values | {"system": system, "data": DATA[language][role]}
        text = TEXT[language]
        emails.append(OnboardingEmail(role=role, system=system, subject=text["subject"].format(**fields), body=text["body"].format(**fields)))
    return emails
