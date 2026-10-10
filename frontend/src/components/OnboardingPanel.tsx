import { useEffect, useState } from "react";
import { api, unwrap } from "../api/client";
import type { CompanyInput, OnboardingEmail } from "../api/types";

type Draft = OnboardingEmail & { to: string };

// Tell us your systems; we draft one email per system asking its support team for integration access. Nothing is sent from here.
export function OnboardingPanel() {
  const [form, setForm] = useState<CompanyInput | null>(null);
  const [language, setLanguage] = useState<"bg" | "en">("bg");
  const [emails, setEmails] = useState<Draft[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<number | null>(null);

  useEffect(() => {
    unwrap(api.GET("/api/company")).then(setForm).catch((err: Error) => setError(err.message));
  }, []);

  if (!form) return error ? <div className="error">{error}</div> : null;
  const set = (key: keyof CompanyInput, value: string) => setForm({ ...form, [key]: value });

  const generate = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await unwrap(api.PUT("/api/company", { body: form }));
      const list = await unwrap(api.POST("/api/onboarding/emails", { params: { query: { language } } }));
      setEmails(list.map((m) => ({ ...m, to: "" })));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const update = (i: number, patch: Partial<Draft>) => setEmails(emails.map((m, j) => (j === i ? { ...m, ...patch } : m)));
  const mailto = (m: Draft) => `mailto:${encodeURIComponent(m.to)}?subject=${encodeURIComponent(m.subject)}&body=${encodeURIComponent(m.body)}`;
  const copy = async (m: Draft, i: number) => {
    await navigator.clipboard.writeText(`${m.subject}\n\n${m.body}`);
    setCopied(i);
  };

  return (
    <section className="panel onboarding">
      <h3>Connect your systems</h3>
      <p className="muted">Name the software you use. We draft an email to each vendor's support team asking for integration access. Nothing is sent from here: review it, then send it yourself.</p>
      <form onSubmit={generate}>
        <div className="form-grid">
          <label>Company name<input required value={form.name} onChange={(e) => set("name", e.target.value)} /></label>
          <label>Company name (Latin)<input value={form.name_latin} onChange={(e) => set("name_latin", e.target.value)} /></label>
          <label>Your name<input required value={form.operator_name} onChange={(e) => set("operator_name", e.target.value)} /></label>
          <label>Your name (Latin)<input value={form.operator_name_latin} onChange={(e) => set("operator_name_latin", e.target.value)} /></label>
          <label>ERP / invoicing system<input placeholder="e.g. Zeron V/4" value={form.erp_system} onChange={(e) => set("erp_system", e.target.value)} /></label>
          <label>GPS / tracking system<input placeholder="e.g. Wialon" value={form.gps_system} onChange={(e) => set("gps_system", e.target.value)} /></label>
          <label>Other systems (comma separated)<input placeholder="e.g. freight exchange, accounting" value={form.other_systems} onChange={(e) => set("other_systems", e.target.value)} /></label>
          <label>Email language
            <select value={language} onChange={(e) => setLanguage(e.target.value as "bg" | "en")}>
              <option value="bg">Bulgarian</option>
              <option value="en">English</option>
            </select>
          </label>
        </div>
        <div className="toolbar"><button className="primary" disabled={busy}>{busy ? "…" : "Draft support emails"}</button></div>
      </form>
      {error && <div className="error">{error}</div>}
      {emails.length === 0 && !busy && <p className="muted">Enter at least one system above to draft its email.</p>}
      {emails.map((m, i) => (
        <article className="panel" key={`${m.role}-${m.system}`}>
          <h4>{m.role.toUpperCase()} · {m.system}</h4>
          <label>To (the vendor's support address)<input type="email" placeholder="support@…" value={m.to} onChange={(e) => update(i, { to: e.target.value })} /></label>
          <label>Subject<input value={m.subject} onChange={(e) => update(i, { subject: e.target.value })} /></label>
          <label>Message<textarea rows={14} value={m.body} onChange={(e) => update(i, { body: e.target.value })} /></label>
          <div className="toolbar">
            <button onClick={() => copy(m, i)}>{copied === i ? "Copied" : "Copy"}</button>
            <button className="primary" onClick={() => { window.location.href = mailto(m); }}>Open in mail app</button>
          </div>
        </article>
      ))}
    </section>
  );
}
