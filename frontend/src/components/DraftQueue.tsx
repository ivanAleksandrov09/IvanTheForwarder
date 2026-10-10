import { useState } from "react";
import type { Client, DraftMessage, UpdateDraftRequest } from "../api/types";
import { formatDateTime } from "../format";
import { t, type UiLang } from "../i18n";

type Props = {
  drafts: DraftMessage[];
  clients: Client[];
  lang: UiLang;
  busy: boolean;
  onApprove: (id: string) => void;
  onReject: (id: string, reason: string) => void;
  onSave: (id: string, patch: UpdateDraftRequest) => void;
};

// Human-in-the-loop: nothing is sent unless the operator presses Approve.
export function DraftQueue({ drafts, clients, lang, busy, onApprove, onReject, onSave }: Props) {
  const pending = drafts.filter((d) => d.status === "pending_review");
  const done = drafts.filter((d) => d.status !== "pending_review");
  const clientName = (id?: string | null) => clients.find((c) => c.id === id)?.name ?? "";

  return (
    <div>
      {pending.length === 0 && <p className="muted">{t("empty", lang)}</p>}
      {pending.map((d) => (
        <DraftCard key={d.id} draft={d} client={clientName(d.client_id)} lang={lang} busy={busy} onApprove={onApprove} onReject={onReject} onSave={onSave} />
      ))}
      {done.length > 0 && (
        <>
          <h3>{t("history", lang)}</h3>
          <ul className="history">
            {done.map((d) => (
              <li key={d.id}>
                <span className={`status ${d.status}`}>{d.status}</span> {d.subject} → {d.to_addresses.join(", ")}{" "}
                <span className="muted">{formatDateTime(d.sent_at ?? d.reviewed_at)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function DraftCard({ draft, client, lang, busy, onApprove, onReject, onSave }: { draft: DraftMessage; client: string } & Omit<Props, "drafts" | "clients">) {
  const [subject, setSubject] = useState(draft.subject ?? "");
  const [body, setBody] = useState(draft.body);
  const [reason, setReason] = useState("");
  const dirty = body !== draft.body || subject !== (draft.subject ?? "");
  return (
    <article className="draft">
      <div className="draft-head">
        <span className="tag">{draft.kind}</span>
        <span className="tag">{draft.language}</span>
        <span className="tag">{draft.tone}</span>
        {draft.llm?.used_fallback && <span className="tag warn">fallback</span>}
        <span className="muted">{client}</span>
      </div>
      <div>
        <strong>To:</strong> {draft.to_addresses.join(", ") || "—"}
      </div>
      <input value={subject} onChange={(e) => setSubject(e.target.value)} aria-label="Subject" />
      <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={10} />
      <div className="why">
        <strong>{t("why", lang)}:</strong> {draft.rationale}
      </div>
      <div className="actions">
        {dirty && (
          <button disabled={busy}           onClick={() => onSave(draft.id, { subject, body })}>
            {t("save", lang)}
          </button>
        )}
        <button
          className="primary"
          disabled={busy || dirty}
          onClick={() => window.confirm(t("confirmSend", lang)) && onApprove(draft.id)}
        >
          {t("approve", lang)}
        </button>
        <button disabled={busy} onClick={() => onReject(draft.id, reason)}>
          {t("reject", lang)}
        </button>
      </div>
      <input
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder={t("rejectReason", lang)}
        aria-label={t("rejectReason", lang)}
      />
    </article>
  );
}
