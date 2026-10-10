"""Manual add / edit / delete of clients."""

NEW = {"name": "Нов Клиент ЕООД", "country": "BG", "city": "Варна", "preferred_language": "bg", "payment_terms_days": 14,
       "contacts": [{"name": "Мария Иванова", "email": "m.ivanova@novklient.bg", "language": "bg"}]}


def test_create_edit_delete_client(client):
    r = client.post("/api/clients", json=NEW)
    assert r.status_code == 200
    created = r.json()
    cid = created["id"]
    assert cid.startswith("cli_") and created["created_at"] and cid in [c["id"] for c in client.get("/api/clients").json()]

    edited = client.put(f"/api/clients/{cid}", json=NEW | {"city": "Бургас", "payment_terms_days": 30}).json()
    assert edited["city"] == "Бургас" and edited["payment_terms_days"] == 30
    assert edited["id"] == cid and edited["created_at"] == created["created_at"]

    assert client.delete(f"/api/clients/{cid}").status_code == 204
    assert client.get(f"/api/clients/{cid}").status_code == 404


def test_invalid_client_is_rejected(client):
    assert client.post("/api/clients", json=NEW | {"country": "bulgaria"}).status_code == 422
    assert client.post("/api/clients", json=NEW | {"contacts": [{"name": "x", "email": "not-an-email", "language": "bg"}]}).status_code == 422
    assert client.put("/api/clients/cli_nope", json=NEW).status_code == 404


def test_client_with_shipments_cannot_be_deleted(client):
    r = client.delete("/api/clients/cli_0001")
    assert r.status_code == 409 and "shipments" in r.json()["detail"]
    assert client.get("/api/clients/cli_0001").status_code == 200


def test_delete_unlinks_emails_and_documents(client):
    from app.deps import get_repo

    cid = client.post("/api/clients", json=NEW).json()["id"]
    repo = get_repo()
    email = repo.emails.list()[0]
    repo.emails.upsert(email.model_copy(update={"client_id": cid}))
    assert client.delete(f"/api/clients/{cid}").status_code == 204
    assert repo.emails.get(email.id).client_id is None
