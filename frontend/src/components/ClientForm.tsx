import { useState } from "react";
import { api, unwrap } from "../api/client";
import type { Client, ClientInput, Contact } from "../api/types";

const LANGS = ["bg", "en", "ru", "tr", "ro"] as const;
const blank: ClientInput = { name: "", country: "BG", city: "", preferred_language: "bg", payment_terms_days: 30, contacts: [], accepted_cargo_types: [], refused_cargo_types: [] };

type Props = { client: Client | null; onDone: () => void };

// Add (client = null) or edit a client. Fields not shown here (credit limit, cargo types) are kept as they are.
export function ClientForm({ client, onDone }: Props) {
  const [form, setForm] = useState<ClientInput>(() => {
    if (!client) return blank;
    const { id: _id, created_at: _created, ...rest } = client;
    return rest;
  });
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const set = <K extends keyof ClientInput>(key: K, value: ClientInput[K]) => setForm({ ...form, [key]: value });
  const contacts = form.contacts ?? [];
  const setContact = (i: number, patch: Partial<Contact>) => set("contacts", contacts.map((c, j) => (j === i ? { ...c, ...patch } : c)));

  const run = async (action: () => Promise<unknown>) => {
    setSaving(true);
    setError(null);
    try {
      await action();
      onDone();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const save = (e: React.FormEvent) => {
    e.preventDefault();
    const body: ClientInput = {
      ...form,
      country: form.country.toUpperCase(),
      name_latin: form.name_latin || null,
      vat_number: form.vat_number || null,
      notes: form.notes || null,
      contacts: contacts.map((c) => ({ ...c, role: c.role || null, email: c.email || null, phone: c.phone || null })),
    };
    run(() =>
      client
        ? unwrap(api.PUT("/api/clients/{client_id}", { params: { path: { client_id: client.id } }, body }))
        : unwrap(api.POST("/api/clients", { body })),
    );
  };

  const remove = () => {
    if (client && window.confirm(`Delete ${client.name}?`)) {
      run(() => unwrap(api.DELETE("/api/clients/{client_id}", { params: { path: { client_id: client.id } } })));
    }
  };

  return (
    <form className="panel client-form" onSubmit={save}>
      <h3>{client ? `Edit ${client.name}` : "Add client"}</h3>
      <div className="form-grid">
        <label>Name<input required value={form.name} onChange={(e) => set("name", e.target.value)} /></label>
        <label>Name (Latin, optional)<input value={form.name_latin ?? ""} onChange={(e) => set("name_latin", e.target.value)} /></label>
        <label>VAT number<input value={form.vat_number ?? ""} onChange={(e) => set("vat_number", e.target.value)} /></label>
        <label>City<input required value={form.city} onChange={(e) => set("city", e.target.value)} /></label>
        <label>Country (2 letters)<input required maxLength={2} value={form.country} onChange={(e) => set("country", e.target.value)} /></label>
        <label>Language
          <select value={form.preferred_language} onChange={(e) => set("preferred_language", e.target.value as ClientInput["preferred_language"])}>
            {LANGS.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </label>
        <label>Payment terms (days)<input type="number" min={0} required value={form.payment_terms_days} onChange={(e) => set("payment_terms_days", Number(e.target.value))} /></label>
      </div>
      <label>Internal notes (never sent to the client)<textarea value={form.notes ?? ""} onChange={(e) => set("notes", e.target.value)} /></label>
      <h4>Contacts</h4>
      {contacts.map((c, i) => (
        <div className="form-grid contact" key={i}>
          <input required placeholder="Name" value={c.name} onChange={(e) => setContact(i, { name: e.target.value })} />
          <input placeholder="Role" value={c.role ?? ""} onChange={(e) => setContact(i, { role: e.target.value })} />
          <input type="email" placeholder="Email" value={c.email ?? ""} onChange={(e) => setContact(i, { email: e.target.value })} />
          <input placeholder="Phone (+359…)" value={c.phone ?? ""} onChange={(e) => setContact(i, { phone: e.target.value })} />
          <select value={c.language} onChange={(e) => setContact(i, { language: e.target.value as Contact["language"] })}>
            {LANGS.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
          <button type="button" onClick={() => set("contacts", contacts.filter((_, j) => j !== i))}>Remove</button>
        </div>
      ))}
      <button type="button" onClick={() => set("contacts", [...contacts, { name: "", language: form.preferred_language }])}>Add contact</button>
      {error && <div className="error">{error}</div>}
      <div className="toolbar">
        <button className="primary" disabled={saving}>{saving ? "Saving…" : "Save"}</button>
        <button type="button" onClick={onDone}>Cancel</button>
        {client && <button type="button" disabled={saving} onClick={remove}>Delete</button>}
      </div>
    </form>
  );
}
