import { Fragment, useCallback, useEffect, useState } from "react";
import { api, unwrap } from "../api/client";
import type { Client, Email, EmailInsight, MailboxStatus } from "../api/types";
import { formatDateTime } from "../format";

type Provider = "gmail" | "outlook";
const FIELDS = ["origin", "destination", "cargo_description", "weight_kg", "requested_date", "invoice_number"] as const;

// Connect a mailbox once. After that everything is automatic: new mail is fetched every minute, the AI analyzes it in the
// background, identifies the client and fills in the details. This panel only displays the results.
export function MailboxPanel({ onSynced }: { onSynced: () => void }) {
  const [status, setStatus] = useState<MailboxStatus>();
  const [provider, setProvider] = useState<Provider>("gmail");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [emails, setEmails] = useState<Email[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [insights, setInsights] = useState<Record<string, EmailInsight>>({});
  const [connecting, setConnecting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [st, em, cl, ins] = await Promise.all([
      unwrap(api.GET("/api/connectors/email/mailbox")),
      unwrap(api.GET("/api/emails", { params: { query: {} } })),
      unwrap(api.GET("/api/clients")),
      unwrap(api.GET("/api/email-insights")),
    ]);
    setStatus(st);
    setEmails(em);
    setClients(cl);
    setInsights(Object.fromEntries(ins.map((i) => [i.email_id, i])));
  }, []);

  useEffect(() => {
    const tick = () => load().catch(() => undefined); // quiet background refresh
    tick();
    const timer = setInterval(tick, 4000);
    return () => clearInterval(timer);
  }, [load]);

  const connect = async (e: React.FormEvent) => {
    e.preventDefault();
    setConnecting(true);
    setMessage(null);
    try {
      await unwrap(api.POST("/api/connectors/email/login", { body: { provider, email, password } }));
      setPassword("");
      await unwrap(api.POST("/api/connectors/{source}/sync", { params: { path: { source: "email" } } })); // analysis continues in the background
      await load();
      onSynced();
    } catch (err) {
      setMessage((err as Error).message);
    } finally {
      setConnecting(false);
    }
  };

  const disconnect = async () => {
    await unwrap(api.POST("/api/connectors/email/logout"));
    await load();
    onSynced();
  };

  const clientName = (id?: string | null) => clients.find((c) => c.id === id)?.name;
  const mine = emails.filter((m) => !status?.connected || m.mailbox === status.email).slice(0, 15);
  const pending = mine.filter((m) => m.direction === "inbound" && !insights[m.id]).length;

  return (
    <section className="panel mailbox">
      <div className="panel-title">
        <h3>
          Mailbox {status?.connected ? `· ${status.email}` : "· demo data"}
          {status?.connected && pending > 0 && <span className="muted"> · analyzing {pending}…</span>}
        </h3>
        {status?.connected && <button onClick={disconnect}>Disconnect</button>}
      </div>
      {!status?.connected && (
        <form onSubmit={connect}>
          <select value={provider} onChange={(e) => setProvider(e.target.value as Provider)} aria-label="Provider">
            <option value="gmail">Gmail</option>
            <option value="outlook">Outlook</option>
          </select>
          <input type="email" required placeholder="Email address" value={email} onChange={(e) => setEmail(e.target.value)} />
          <input type="password" required placeholder="App password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="off" />
          <button className="primary" disabled={connecting}>{connecting ? "Connecting…" : "Connect"}</button>
          <div className="help">
            Use an <strong>app password</strong>, not your normal password (Google Account → Security → 2-Step Verification → App passwords).
            Outlook may require OAuth and not accept this yet. Use a throwaway mailbox: email text is sent to the AI model.
          </div>
        </form>
      )}
      {(message || status?.last_error) && <div className="error">{message ?? status?.last_error}</div>}
      <h3>Emails</h3>
      {mine.map((m) => {
        const x = insights[m.id]?.extraction;
        const client = clientName(m.client_id);
        return (
          <div className="timeline-item" key={m.id}>
            <strong>{m.subject}</strong>
            <div className="muted">
              {m.from_name ?? m.from_address} · {formatDateTime(m.sent_at)}
              {client ? ` · ${client}` : status?.connected && x ? " · client not recognised" : ""}
            </div>
            {status?.connected && m.direction === "inbound" && !x && <div className="muted">Analyzing…</div>}
            {x && (
              <div className="extract">
                <strong>{x.intent}</strong>{x.urgent ? " · urgent" : ""} — {x.summary}
                <dl>
                  {FIELDS.map((k) => x[k] != null && (
                    <Fragment key={k}><dt>{k}</dt><dd>{String(x[k])}</dd></Fragment>
                  ))}
                </dl>
              </div>
            )}
          </div>
        );
      })}
    </section>
  );
}
