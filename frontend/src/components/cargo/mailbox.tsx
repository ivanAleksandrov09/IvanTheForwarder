import { useState } from "react";
import { Mail, Sparkles, ArrowUpRight, Check, Pencil, ShieldCheck, X } from "lucide-react";
import type { Client, DraftMessage, Email, EmailInsight, UpdateDraftRequest } from "@/api/types";
import { cap } from "@/lib/useOps";
import { formatDateTime } from "@/format";
import { PanelHeader, RiskBadge } from "./common";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog";

export type DraftActions = {
  busy: boolean;
  onApprove: (id: string) => void;
  onReject: (id: string, reason: string) => void;
  onSave: (id: string, patch: UpdateDraftRequest) => void;
};

const STATUS_BADGE: Record<string, string> = { pending_review: "badge-medium", approved: "badge-low", sent: "badge-low", rejected: "badge-high", failed: "badge-high" };
const STATUS_LABEL: Record<string, string> = { pending_review: "Ready for review", approved: "Approved", sent: "Sent", rejected: "Rejected", failed: "Send failed" };

// One draft with edit / approve / reject. Nothing leaves the system unless the operator presses Approve.
function DraftCard({ draft, clientName, expanded, actions }: { draft: DraftMessage; clientName: string; expanded?: boolean; actions: DraftActions }) {
  const [editing, setEditing] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [subject, setSubject] = useState(draft.subject ?? "");
  const [body, setBody] = useState(draft.body);
  const [reason, setReason] = useState("");
  const pending = draft.status === "pending_review";
  return (
    <div className="draft-content">
      <div className="draft-top">
        <strong>{draft.subject ?? "(no subject)"}</strong>
        <span className={`badge ${STATUS_BADGE[draft.status] ?? "badge-medium"}`}>{STATUS_LABEL[draft.status] ?? draft.status}</span>
      </div>
      <div className="draft-recipient">To: {draft.to_addresses.join(", ") || "—"}{clientName && ` · ${clientName}`} · {cap(draft.kind)} · {draft.language} · {draft.tone}</div>
      <p className={`draft-preview ${expanded ? "expanded" : ""}`}>{draft.body}</p>
      {draft.rationale && <p className="text-xs subtle mt-2">Why: {draft.rationale}</p>}
      {draft.rejection_reason && <p className="text-xs subtle mt-2">Rejected: {draft.rejection_reason}</p>}
      <div className="draft-actions">
        <span className="draft-confidence"><ShieldCheck />{draft.llm?.used_fallback ? "Template fallback" : "AI generated"}</span>
        {pending && (
          <div className="flex gap-2">
            <Button variant="outline" disabled={actions.busy} onClick={() => setRejecting(true)}><X />Reject</Button>
            <Button variant="outline" disabled={actions.busy} onClick={() => setEditing(true)}><Pencil />Edit draft</Button>
            <Button disabled={actions.busy} onClick={() => window.confirm("Approve and send this email?") && actions.onApprove(draft.id)}>
              <Check />Approve draft<ArrowUpRight />
            </Button>
          </div>
        )}
      </div>
      <Dialog open={editing} onOpenChange={setEditing}>
        <DialogContent>
          <DialogTitle>Edit response draft</DialogTitle>
          <DialogDescription>To {draft.to_addresses.join(", ")}</DialogDescription>
          <input className="filter-input w-full" aria-label="Subject" value={subject} onChange={(e) => setSubject(e.target.value)} />
          <textarea className="draft-textarea" aria-label="Email draft" value={body} onChange={(e) => setBody(e.target.value)} />
          <Button className="justify-self-end" onClick={() => { actions.onSave(draft.id, { subject, body }); setEditing(false); }}><Check />Save draft</Button>
        </DialogContent>
      </Dialog>
      <Dialog open={rejecting} onOpenChange={setRejecting}>
        <DialogContent>
          <DialogTitle>Reject draft</DialogTitle>
          <DialogDescription>{draft.subject}</DialogDescription>
          <input className="filter-input w-full" aria-label="Reject reason" placeholder="Reason (optional)" value={reason} onChange={(e) => setReason(e.target.value)} />
          <Button variant="destructive" className="justify-self-end" onClick={() => { actions.onReject(draft.id, reason); setRejecting(false); }}><X />Reject draft</Button>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export function MailboxPanel({ emails, insights, drafts, clients, expanded = false, onExpand, actions, mailboxLabel }: {
  emails: Email[];
  insights: Record<string, EmailInsight>;
  drafts: DraftMessage[];
  clients: Client[];
  expanded?: boolean | undefined;
  onExpand?: (() => void) | undefined;
  actions: DraftActions;
  mailboxLabel: string;
}) {
  const inbox = emails.filter((e) => e.direction === "inbound").sort((a, b) => b.sent_at.localeCompare(a.sent_at)).slice(0, expanded ? 50 : 4);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = inbox.find((e) => e.id === selectedId) ?? inbox[0];
  const clientName = (id?: string | null) => clients.find((c) => c.id === id)?.name ?? "";
  const pending = drafts.filter((d) => d.status === "pending_review");
  const related = selected ? pending.filter((d) => d.client_id && d.client_id === selected.client_id) : [];
  const shownDrafts = related.length > 0 ? related : pending.slice(0, 1);
  const insight = selected ? insights[selected.id]?.extraction : undefined;

  return (
    <section className="panel mail-panel">
      <PanelHeader title="Mailbox & AI drafts" icon={<Mail />} subtitle={mailboxLabel} action={expanded ? undefined : "Open mailbox"} onAction={onExpand} />
      <div className="mail-grid">
        <div className="mail-inbox">
          <div className="mail-subhead"><span className="flex items-center gap-2"><Mail size={11} />Inbox<span className="table-count">{emails.filter((e) => e.direction === "inbound").length}</span></span><span>Latest messages</span></div>
          {inbox.length === 0 && <div className="empty-state">No emails yet. Press “Sync inbox”.</div>}
          {inbox.map((e) => {
            const x = insights[e.id]?.extraction;
            const name = e.from_name ?? e.from_address;
            return (
              <Button key={e.id} variant="ghost" className={`email-row ${selected?.id === e.id ? "selected" : ""}`} onClick={() => setSelectedId(e.id)}>
                <div className="email-sender">
                  <span className="flex items-center gap-2"><span className="status-dot bg-info" />{name}<span className="subtle text-[9px] font-normal">{clientName(e.client_id)}</span></span>
                  <span className="subtle text-[9px] font-normal">{formatDateTime(e.sent_at)}</span>
                </div>
                <div className="email-subject">{e.subject}</div>
                <div className="email-preview">{x?.summary ?? e.body_text.slice(0, 120)}</div>
                <div className="email-tags">{x && <RiskBadge level={cap(x.intent)} />}{x?.urgent && <RiskBadge level="High" />}</div>
              </Button>
            );
          })}
          {expanded && selected && (
            <div className="p-5">
              <strong className="text-xs">{selected.subject}</strong>
              <p className="draft-preview expanded">{selected.body_text}</p>
              {insight && (
                <div className="text-xs subtle grid gap-1">
                  {(["origin", "destination", "cargo_description", "weight_kg", "requested_date", "invoice_number"] as const).map((k) => insight[k] != null && <span key={k}>{cap(k)}: {String(insight[k])}</span>)}
                </div>
              )}
            </div>
          )}
        </div>
        <div>
          <div className="mail-subhead"><span className="flex items-center gap-2"><Sparkles size={12} className="text-primary" />AI draft queue</span><span>{pending.length} awaiting approval</span></div>
          {shownDrafts.length === 0 && <div className="empty-state"><Check className="mx-auto mb-3 text-success" />No drafts awaiting approval.</div>}
          {shownDrafts.map((d) => <DraftCard key={d.id + d.updated_at} draft={d} clientName={clientName(d.client_id)} expanded={expanded} actions={actions} />)}
        </div>
      </div>
    </section>
  );
}

export function DraftQueue({ drafts, clients, actions }: { drafts: DraftMessage[]; clients: Client[]; actions: DraftActions }) {
  const [mode, setMode] = useState<"Pending" | "History">("Pending");
  const pending = drafts.filter((d) => d.status === "pending_review");
  const history = drafts.filter((d) => d.status !== "pending_review");
  const visible = mode === "Pending" ? pending : history;
  const clientName = (id?: string | null) => clients.find((c) => c.id === id)?.name ?? "";
  return (
    <>
      <div className="flex gap-2 mb-5">
        {(["Pending", "History"] as const).map((m) => (
          <Button key={m} variant={mode === m ? "secondary" : "ghost"} onClick={() => setMode(m)}>
            {m}<span className="table-count">{m === "Pending" ? pending.length : history.length}</span>
          </Button>
        ))}
      </div>
      <section className="panel">
        <PanelHeader icon={<Sparkles />} title={mode === "Pending" ? "Drafts awaiting approval" : "Approved, sent and rejected drafts"} subtitle="Drafts are never sent without your approval" />
        {visible.map((d) => (
          <div className="draft-queue-item" key={d.id + d.updated_at}>
            <DraftCard draft={d} clientName={clientName(d.client_id)} expanded actions={actions} />
          </div>
        ))}
        {visible.length === 0 && <div className="empty-state"><Check className="mx-auto mb-3 text-success" />{mode === "Pending" ? "All drafts have been reviewed." : "No history yet."}</div>}
      </section>
    </>
  );
}
