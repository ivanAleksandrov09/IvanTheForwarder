import { Fragment, useCallback, useEffect, useState } from "react";
import { api, unwrap } from "../api/client";
import type { Email, EmailExtraction, MailboxStatus } from "../api/types";
import { formatDateTime } from "../format";

type Provider = "gmail" | "outlook";

// Connect a real mailbox (Gmail/Outlook app password), load it, and let the LLM extract facts from each email.
export function MailboxPanel({ onSynced }: { onSynced: () => void }) {
  const [status, setStatus] = useState<MailboxStatus>();
  const [provider, setProvider] = useState<Provider>("gmail");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [emails, setEmails] = useState<Email[]>([]);
  const [extractions, setExtractions] = useState<Record<string, EmailExtraction>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setStatus(await unwrap(api.GET("/api/connectors/email/mailbox")));
    setEmails(await unwrap(api.GET("/api/emails", { params: { query: {} } })));
  }, []);

  useEffect(() => {
    load().catch((e) => setMessage((e as Error).message));
  }, [load]);

  const run = async (label: string, action: () => Promise<unknown>) => {
    setBusy(label);
    setMessage(null);
    try {
      await action();
      await load();
      onSynced();
    } catch (e) {
      setMessage((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const syncInbox = () => unwrap(api.POST("/api/connectors/{source}/sync", { params: { path: { source: "email" } } }));

  const connect = (e: React.FormEvent) => {
    e.preventDefault();
    run("login", async () => {
      await unwrap(api.POST("/api/connectors/email/login", { body: { provider, email, password } }));
      setPassword("");
      const result = await syncInbox();
      setMessage(`Loaded ${result.upserted} emails.${result.errors.length ? " Errors: " + result.errors.join("; ") : ""}`);
    });
  };

  const extract = (id: string) =>
    run("extract:" + id, async () => {
      const result = await unwrap(api.POST("/api/emails/{email_id}/extract", { params: { path: { email_id: id } } }));
      setExtractions((prev) => ({ ...prev, [id]: result }));
    });

  return (
    <section className="panel mailbox">
      <div className="panel-title">
        <h3>Mailbox {status?.connected ? `· ${status.email}` : "· demo data"}</h3>
        {status?.connected && (
          <div className="toolbar">
            <button disabled={!!busy} onClick={() => run("sync", syncInbox)}>Reload</button>
            <button disabled={!!busy} onClick={() => run("logout", () => unwrap(api.POST("/api/connectors/email/logout")))}>
              Disconnect
            </button>
          </div>
        )}
      </div>
      {!status?.connected && (
        <form onSubmit={connect}>
          <select value={provider} onChange={(e) => setProvider(e.target.value as Provider)} aria-label="Provider">
            <option value="gmail">Gmail</option>
            <option value="outlook">Outlook</option>
          </select>
          <input type="email" required placeholder="Email address" value={email} onChange={(e) => setEmail(e.target.value)} />
          <input type="password" required placeholder="App password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="off" />
          <button className="primary" disabled={!!busy}>{busy === "login" ? "Connecting…" : "Connect & load"}</button>
          <div className="help">
            Use an <strong>app password</strong>, not your normal password (Google Account → Security → 2-Step Verification → App passwords).
            Outlook may require OAuth and not accept this yet. Use a throwaway mailbox: emails are sent to the AI model for extraction.
          </div>
        </form>
      )}
      {message && <div className={message.startsWith("Loaded") ? "muted" : "error"}>{message}</div>}
      <h3>Emails</h3>
      {emails.filter((m) => !status?.connected || m.mailbox === status.email).slice(0, 15).map((m) => {
        const x = extractions[m.id];
        return (
          <div className="timeline-item" key={m.id}>
            <strong>{m.subject}</strong>
            <div className="muted">
              {m.from_name ?? m.from_address} · {formatDateTime(m.sent_at)}
            </div>
            <button disabled={!!busy} onClick={() => extract(m.id)}>{busy === "extract:" + m.id ? "…" : "Extract info"}</button>
            {x && (
              <div className="extract">
                <strong>{x.intent}</strong>{x.urgent ? " · urgent" : ""} — {x.summary}
                <dl>
                  {(["origin", "destination", "cargo_description", "weight_kg", "requested_date", "invoice_number"] as const).map(
                    (k) => x[k] != null && <Fragment key={k}><dt>{k}</dt><dd>{String(x[k])}</dd></Fragment>,
                  )}
                </dl>
              </div>
            )}
          </div>
        );
      })}
    </section>
  );
}
