import { useEffect, useState } from "react";
import { api, unwrap } from "../api/client";
import type { ProfileSettingsInput, PublicProfileState } from "../api/types";
import { formatDateTime } from "../format";

const TRAILERS = ["tent", "mega", "reefer", "flatbed", "tanker", "box"] as const;
const CARGO = ["general", "palletized", "refrigerated", "pharma", "adr_dangerous", "oversized", "bulk", "food", "textile", "steel", "grain", "furniture", "automotive"] as const;
const LANGS = ["bg", "en", "ru", "tr", "ro"] as const;

function Checks<T extends string>({ label, options, value, onChange }: { label: string; options: readonly T[]; value: T[]; onChange: (v: T[]) => void }) {
  return (
    <fieldset>
      <legend>{label}</legend>
      {options.map((o) => (
        <label key={o} className="inline">
          <input type="checkbox" checked={value.includes(o)} onChange={(e) => onChange(e.target.checked ? [...value, o] : value.filter((x) => x !== o))} /> {o}
        </label>
      ))}
    </fieldset>
  );
}

// Opt-in: share an aggregate capacity profile (region, max load, trailer/cargo types, fleet size, main lanes) with the central network.
// No client, price, invoice, plate or driver is ever included. The preview is exactly what would be sent.
export function NetworkPanel() {
  const [state, setState] = useState<PublicProfileState | null>(null);
  const [form, setForm] = useState<ProfileSettingsInput | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = (s: PublicProfileState) => {
    setState(s);
    const { id: _id, company_uid: _uid, last_published_at: _at, last_publish_status: _st, ...editable } = s.settings;
    setForm(editable);
  };

  useEffect(() => {
    unwrap(api.GET("/api/network/profile")).then(load).catch((err: Error) => setError(err.message));
  }, []);

  if (!state || !form) return error ? <div className="error">{error}</div> : null;
  const set = <K extends keyof ProfileSettingsInput>(key: K, value: ProfileSettingsInput[K]) => setForm({ ...form, [key]: value });

  const run = async (action: () => Promise<PublicProfileState>) => {
    setBusy(true);
    setError(null);
    try {
      load(await action());
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const save = () => run(() => unwrap(api.PUT("/api/network/profile", { body: form })));
  const publish = () =>
    run(async () => {
      await unwrap(api.PUT("/api/network/profile", { body: form }));
      return unwrap(api.POST("/api/network/publish"));
    });
  const withdraw = () => window.confirm("Stop sharing and ask the network to delete your profile?") && run(() => unwrap(api.POST("/api/network/withdraw")));

  const s = state.settings;
  return (
    <section className="panel network">
      <h3>Share your capacity profile</h3>
      <p className="muted">
        So other companies can find and match with you. Only the summary below is shared: no client names, prices, invoices, truck plates or drivers.
        Leave a field empty to use what we know from your fleet and history. Nothing is sent unless you agree and press Publish.
      </p>
      <label className="consent">
        <input type="checkbox" checked={form.consent} onChange={(e) => set("consent", e.target.checked)} /> I agree to share this profile with the network. I can withdraw at any time.
      </label>
      <div className="form-grid">
        <label>Home region<input placeholder="e.g. Sofia, Bulgaria" value={form.home_region} onChange={(e) => set("home_region", e.target.value)} /></label>
        <label>Countries served (2-letter codes, comma separated)
          <input placeholder="BG, RO, DE" value={form.countries_served.join(", ")} onChange={(e) => set("countries_served", e.target.value.split(",").map((c) => c.trim().toUpperCase()).filter(Boolean))} />
        </label>
        <label>Max load (kg)<input type="number" min={0} value={form.max_load_kg ?? ""} onChange={(e) => set("max_load_kg", e.target.value === "" ? null : Number(e.target.value))} /></label>
        <label>Public notes<input value={form.public_notes} onChange={(e) => set("public_notes", e.target.value)} /></label>
      </div>
      <Checks label="Trailer types" options={TRAILERS} value={form.trailer_types} onChange={(v) => set("trailer_types", v)} />
      <Checks label="Cargo types" options={CARGO} value={form.cargo_types} onChange={(v) => set("cargo_types", v)} />
      <Checks label="Languages" options={LANGS} value={form.languages} onChange={(v) => set("languages", v)} />
      <label className="inline"><input type="checkbox" checked={form.adr} onChange={(e) => set("adr", e.target.checked)} /> Dangerous goods (ADR)</label>
      <label className="consent">
        <input type="checkbox" checked={form.share_contact} onChange={(e) => set("share_contact", e.target.checked)} /> Also share a contact so matches can reach me
      </label>
      {form.share_contact && (
        <div className="form-grid">
          <label>Contact email<input type="email" value={form.contact_email ?? ""} onChange={(e) => set("contact_email", e.target.value || null)} /></label>
          <label>Contact phone (+359…)<input value={form.contact_phone ?? ""} onChange={(e) => set("contact_phone", e.target.value || null)} /></label>
        </div>
      )}
      {error && <div className="error">{error}</div>}
      <div className="toolbar">
        <button disabled={busy} onClick={save}>Save</button>
        <button className="primary" disabled={busy || !form.consent} onClick={publish}>Publish</button>
        {s.last_publish_status && <button disabled={busy} onClick={withdraw}>Withdraw</button>}
      </div>
      {s.last_publish_status && (
        <p className="muted">
          Status: {s.last_publish_status}
          {s.last_published_at ? ` · ${formatDateTime(s.last_published_at)}` : ""}
        </p>
      )}
      <h4>Exactly what would be sent</h4>
      <pre className="preview">{JSON.stringify(state.preview, null, 2)}</pre>
    </section>
  );
}
