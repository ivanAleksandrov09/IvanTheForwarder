import { useEffect, useState } from "react";
import { api, unwrap } from "../api/client";
import type { Client, Email, Incident, Invoice, RiskProfile } from "../api/types";
import { formatDateTime, formatMoney } from "../format";

type Props = {
  client: Client;
  risk?: RiskProfile;
  onBack: () => void;
  onDraftReminder: (clientId: string, invoiceId?: string) => void;
};

export function ClientDetail({ client, risk, onBack, onDraftReminder }: Props) {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [emails, setEmails] = useState<Email[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      unwrap(api.GET("/api/invoices", { params: { query: { client_id: client.id } } })),
      unwrap(api.GET("/api/emails", { params: { query: { client_id: client.id } } })),
      unwrap(api.GET("/api/incidents", { params: { query: { client_id: client.id } } })),
    ])
      .then(([nextInvoices, nextEmails, nextIncidents]) => {
        setInvoices(nextInvoices);
        setEmails(nextEmails);
        setIncidents(nextIncidents);
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }, [client.id]);

  return (
    <section className="detail">
      <button onClick={onBack}>Back to clients</button>
      <div className="detail-header">
        <div>
          <h2>{client.name}</h2>
          <p className="muted">{client.city}, {client.country} · Preferred language: {client.preferred_language}</p>
        </div>
        {risk && <span className={`level ${risk.level}`}>{risk.score} · {risk.level}</span>}
      </div>
      {error && <div className="error">{error}</div>}
      {risk && (
        <article className="panel">
          <h3>Explainable risk profile</h3>
          <p>{risk.summary} · Recommended tone: {risk.recommended_tone} · Confidence: {risk.confidence}</p>
          <ul>
            {risk.factors.map((factor) => (
              <li key={factor.code}>
                <strong>{factor.label}</strong> ({factor.impact > 0 ? "+" : ""}{factor.impact}) - {factor.explanation}
                {factor.evidence.length > 0 && <span className="muted"> Evidence: {factor.evidence.map((e) => `${e.entity_type}/${e.entity_id}`).join(", ")}</span>}
              </li>
            ))}
          </ul>
        </article>
      )}
      <div className="detail-grid">
        <article className="panel">
          <div className="panel-title"><h3>Invoices</h3><button onClick={() => onDraftReminder(client.id)}>Draft reminder</button></div>
          {invoices.length === 0 ? <p className="muted">No invoices.</p> : invoices.map((invoice) => (
            <div className="timeline-item" key={invoice.id}>
              <strong>#{invoice.number}</strong> · {formatMoney(invoice.total)} · {invoice.status}
              <div className="muted">Due {formatDateTime(invoice.due_at)}</div>
              {invoice.status !== "paid" && <button onClick={() => onDraftReminder(client.id, invoice.id)}>Draft for this invoice</button>}
            </div>
          ))}
        </article>
        <article className="panel">
          <h3>Email timeline</h3>
          {emails.length === 0 ? <p className="muted">No emails.</p> : emails.map((email) => (
            <div className="timeline-item" key={email.id}>
              <strong>{email.subject}</strong>
              <div className="muted">{email.direction} · {formatDateTime(email.sent_at)} · {email.from_address}</div>
              <p>{email.body_text}</p>
            </div>
          ))}
        </article>
      </div>
      <article className="panel">
        <h3>Incidents and evidence</h3>
        {incidents.length === 0 ? <p className="muted">No incidents recorded.</p> : incidents.map((incident) => (
          <div className="timeline-item" key={incident.id}>
            <strong>{incident.type}</strong> · {incident.severity} · {formatDateTime(incident.occurred_at)}
            <div>{incident.description}</div>
          </div>
        ))}
      </article>
    </section>
  );
}
