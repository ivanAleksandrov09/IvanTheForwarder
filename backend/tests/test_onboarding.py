"""Onboarding: systems saved in the company profile -> one drafted integration-request email per system."""

COMPANY = {"name": "Спедиция Тест ЕООД", "name_latin": "Test Forwarding Ltd", "operator_name": "Петър Петров", "operator_name_latin": "Peter Petrov",
           "erp_system": "Zeron V/4", "gps_system": "Wialon", "other_systems": "Speditor.net, Trans.eu"}


def test_one_email_per_system_in_english(client):
    assert client.put("/api/company", json=COMPANY).status_code == 200
    emails = client.post("/api/onboarding/emails", params={"language": "en"}).json()
    assert [(e["role"], e["system"]) for e in emails] == [("erp", "Zeron V/4"), ("gps", "Wialon"), ("other", "Speditor.net"), ("other", "Trans.eu")]
    erp = emails[0]
    assert "Zeron V/4" in erp["subject"] and "Test Forwarding Ltd" in erp["subject"]
    assert "Peter Petrov" in erp["body"] and "invoices" in erp["body"] and "API" in erp["body"]
    assert "[ACCOUNT NUMBER]" in erp["body"]  # we never invent an account number
    assert "current position" in emails[1]["body"]


def test_bulgarian_uses_bulgarian_names_and_text(client):
    client.put("/api/company", json=COMPANY)
    erp = client.post("/api/onboarding/emails", params={"language": "bg"}).json()[0]
    assert "Спедиция Тест ЕООД" in erp["subject"] and "Петър Петров" in erp["body"] and "Здравейте" in erp["body"]


def test_no_systems_no_emails_and_bad_language_rejected(client):
    client.put("/api/company", json=COMPANY | {"erp_system": "", "gps_system": "", "other_systems": " , "})
    assert client.post("/api/onboarding/emails").json() == []
    assert client.post("/api/onboarding/emails", params={"language": "xx"}).status_code == 422


def test_systems_are_saved_with_the_company(client):
    client.put("/api/company", json=COMPANY)
    saved = client.get("/api/company").json()
    assert saved["erp_system"] == "Zeron V/4" and saved["other_systems"] == "Speditor.net, Trans.eu"
