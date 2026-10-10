import { Fragment, useState } from "react";
import type { Client, RiskProfile } from "../api/types";
import { formatMoney } from "../format";
import { t, type UiLang } from "../i18n";

type Props = {
  clients: Client[];
  risk: RiskProfile[];
  lang: UiLang;
  onDraftReminder: (clientId: string) => void;
  onSelectClient: (clientId: string) => void;
};

// Explainability rule: never show a score without its factors.
export function ClientRiskTable({ clients, risk, lang, onDraftReminder, onSelectClient }: Props) {
  const [open, setOpen] = useState<string | null>(null);
  const byClient = new Map(risk.map((r) => [r.client_id, r]));

  return (
    <table className="risk">
      <thead>
        <tr>
          <th>Client</th>
          <th>Lang</th>
          <th>Risk</th>
          <th>Overdue</th>
          <th />
        </tr>
      </thead>
      <tbody>
        {clients.map((c) => {
          const r = byClient.get(c.id);
          return (
            <Fragment key={c.id}>
              <tr onClick={() => setOpen(open === c.id ? null : c.id)} className="clickable">
                <td onDoubleClick={() => onSelectClient(c.id)}>
                  <strong>{c.name}</strong>
                  <div className="muted">
                    {c.city}, {c.country}
                  </div>
                </td>
                <td>{c.preferred_language}</td>
                <td>
                  {r && (
                    <span className={`level ${r.level}`} title={`confidence: ${r.confidence}`}>
                      {r.score} · {r.level}
                    </span>
                  )}
                </td>
                <td>{formatMoney(r?.metrics.overdue_amount)}</td>
                <td>
                  {r && r.metrics.open_overdue_invoices > 0 && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onDraftReminder(c.id);
                      }}
                    >
                      {t("draftReminder", lang)}
                    </button>
                  )}
                </td>
              </tr>
              {open === c.id && r && (
                <tr className="factors">
                  <td colSpan={5}>
                    <div className="muted">
                      {r.summary} · tone: {r.recommended_tone} · confidence: {r.confidence}
                    </div>
                    <ul>
                      {r.factors.map((f) => (
                        <li key={f.code}>
                          <span className={f.impact > 0 ? "up" : "down"}>
                            {f.impact > 0 ? "+" : ""}
                            {f.impact}
                          </span>{" "}
                          <strong>{f.label}</strong> — {f.explanation}
                        </li>
                      ))}
                    </ul>
                  </td>
                </tr>
              )}
            </Fragment>
          );
        })}
      </tbody>
    </table>
  );
}
