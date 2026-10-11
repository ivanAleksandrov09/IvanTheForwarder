import { useState } from "react";
import { ShieldCheck, ChevronRight, ArrowDown, ArrowUpRight, Mail, Search, Pencil, Trash2, Plus, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { api, unwrap } from "@/api/client";
import type { Client, RiskProfile } from "@/api/types";
import { cap, initials, timeAgo } from "@/lib/useOps";
import { formatMoney } from "@/format";
import { PanelHeader, RiskBadge } from "./common";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { ClientForm } from "@/components/ClientForm";

const RISK_LEVELS = ["High", "Medium", "Low"];

type Row = { client: Client; risk?: RiskProfile | undefined };

const levelOf = (r?: RiskProfile) => (r && r.level !== "unknown" ? cap(r.level) : "Unknown");
const incidentOf = (r?: RiskProfile) => {
  const top = r?.factors.filter((f) => f.impact > 0).sort((a, b) => b.impact - a.impact)[0];
  return top?.label ?? "No recent incidents";
};

export function ClientRiskTable({ clients, risk, expanded = false, onExpand, onEmail, onDraftReminder, onChanged }: {
  clients: Client[];
  risk: RiskProfile[];
  expanded?: boolean | undefined;
  onExpand?: (() => void) | undefined;
  onEmail?: (() => void) | undefined;
  onDraftReminder: (clientId: string) => void;
  onChanged: () => void;
}) {
  const [selected, setSelected] = useState<Row | null>(null);
  const [editing, setEditing] = useState<Client | "new" | null>(null);
  const [deleting, setDeleting] = useState<Client | null>(null);
  const [query, setQuery] = useState("");
  const [level, setLevel] = useState("All risks");
  const [descending, setDescending] = useState(true);

  const byClient = new Map(risk.map((r) => [r.client_id, r]));
  const rows: Row[] = clients.map((client) => ({ client, risk: byClient.get(client.id) }));
  const filtered = rows
    .filter((r) => r.client.name.toLowerCase().includes(query.toLowerCase()) && (level === "All risks" || levelOf(r.risk) === level))
    .sort((a, b) => (descending ? (b.risk?.score ?? -1) - (a.risk?.score ?? -1) : (a.risk?.score ?? -1) - (b.risk?.score ?? -1)));
  const shown = expanded ? filtered : filtered.slice(0, 5);

  const deleteClient = async (client: Client) => {
    try {
      await unwrap(api.DELETE("/api/clients/{client_id}", { params: { path: { client_id: client.id } } }));
      toast.success(`${client.name} removed`);
      if (selected?.client.id === client.id) setSelected(null);
      onChanged();
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setDeleting(null);
    }
  };

  return (
    <>
      <section className="panel table-panel">
        <PanelHeader title="Client risk overview" icon={<ShieldCheck />} count={clients.length} action={expanded ? undefined : "View all clients"} onAction={onExpand} />
        {expanded && (
          <div className="flex gap-3 p-4 border-b border-border">
            <div className="flex items-center gap-2">
              <Search size={14} className="text-muted-foreground" />
              <input aria-label="Search clients" placeholder="Search clients…" className="filter-input" value={query} onChange={(e) => setQuery(e.target.value)} />
            </div>
            <select className="filter-select" aria-label="Filter client risk" value={level} onChange={(e) => setLevel(e.target.value)}>
              {["All risks", ...RISK_LEVELS].map((r) => <option key={r}>{r}</option>)}
            </select>
            <Button size="sm" className="ml-auto" onClick={() => setEditing("new")}><Plus />Add client</Button>
          </div>
        )}
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Client</th>
                <th>
                  <Button variant="ghost" className="h-auto p-0 text-[10px] text-muted-foreground" onClick={() => setDescending(!descending)}>
                    Risk score<ArrowDown size={10} className={descending ? "" : "rotate-180"} />
                  </Button>
                </th>
                <th>Risk level</th>
                <th>Overdue</th>
                <th>Main risk factor</th>
                <th className="text-right">Actions</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {shown.map(({ client: c, risk: r }) => (
                <tr key={c.id} tabIndex={0} aria-label={`View ${c.name}`} onClick={() => setSelected({ client: c, risk: r })} onKeyDown={(e) => { if (e.key === "Enter") setSelected({ client: c, risk: r }); }}>
                  <td>
                    <div className="client-name">
                      <div className="client-avatar">{initials(c.name)}</div>
                      <div><strong>{c.name}</strong><small>{c.city}, {c.country}</small></div>
                    </div>
                  </td>
                  <td>
                    <div className="risk-score">
                      <span>{r?.score ?? "–"}<span className="subtle text-[9px]"> / 100</span></span>
                      <div className="risk-meter"><div className={`risk-fill ${levelOf(r).toLowerCase()}`} style={{ width: `${r?.score ?? 0}%` }} /></div>
                    </div>
                  </td>
                  <td><RiskBadge level={levelOf(r)} /></td>
                  <td className="font-medium">{formatMoney(r?.metrics.overdue_amount)}</td>
                  <td className={r?.level === "low" ? "subtle" : ""}>{incidentOf(r)}</td>
                  <td className="text-right whitespace-nowrap">
                    {r && r.metrics.open_overdue_invoices > 0 && (
                      <Button variant="ghost" size="icon" className="h-7 w-7" aria-label={`Draft payment reminder for ${c.name}`} title="Draft payment reminder" onClick={(e) => { e.stopPropagation(); onDraftReminder(c.id); }}>
                        <Sparkles size={13} />
                      </Button>
                    )}
                    <Button variant="ghost" size="icon" className="h-7 w-7" aria-label={`Edit ${c.name}`} onClick={(e) => { e.stopPropagation(); setEditing(c); }}>
                      <Pencil size={13} />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive" aria-label={`Delete ${c.name}`} onClick={(e) => { e.stopPropagation(); setDeleting(c); }}>
                      <Trash2 size={13} />
                    </Button>
                  </td>
                  <td><ChevronRight className="row-arrow" /></td>
                </tr>
              ))}
            </tbody>
          </table>
          {shown.length === 0 && <div className="empty-state">No clients match your search.</div>}
        </div>
        <div className="panel-footer">
          <span>{expanded ? `${filtered.length} clients` : `Showing ${shown.length} of ${clients.length} clients`}<span className="mx-2">·</span>Scores computed {risk[0] ? timeAgo(risk[0].computed_at) : "–"}</span>
          <span className="flex items-center gap-1"><span className="status-dot" />Monitoring active</span>
        </div>
      </section>

      <Dialog open={!!selected} onOpenChange={(open) => { if (!open) setSelected(null); }}>
        <DialogContent>
          <DialogTitle>{selected?.client.name}</DialogTitle>
          <DialogDescription>{selected?.client.city}, {selected?.client.country} · {selected?.client.id}</DialogDescription>
          {selected && (
            <>
              <div className="detail-stat-grid">
                <div><span className="subtle small">Risk score</span><strong>{selected.risk?.score ?? "–"}<span className="subtle text-xs"> / 100</span></strong></div>
                <div><span className="subtle small">Overdue</span><strong>{formatMoney(selected.risk?.metrics.overdue_amount)}</strong></div>
                <div><span className="subtle small">Shipments</span><strong>{selected.risk?.metrics.shipments_total ?? 0}</strong></div>
              </div>
              <div className="detail-row"><span className="subtle">Risk level</span><RiskBadge level={levelOf(selected.risk)} /></div>
              <div className="detail-row"><span className="subtle">Account contact</span>{selected.client.contacts[0]?.name ?? "–"}</div>
              <div className="detail-row"><span className="subtle">Payment terms</span>{selected.client.payment_terms_days} days</div>
              <div className="border-t border-border pt-4">
                <div className="flex items-center gap-2 font-medium"><ShieldCheck size={15} />Risk assessment</div>
                <p className="detail-body text-xs mt-2">{selected.risk?.summary ?? "No risk data yet."}</p>
                {selected.risk && <p className="detail-body text-xs mt-1 subtle">Recommended tone: {selected.risk.recommended_tone} · confidence: {selected.risk.confidence}</p>}
                <ul className="mt-2 grid gap-1 text-xs">
                  {selected.risk?.factors.map((f) => (
                    <li key={f.code}>
                      <span className={f.impact > 0 ? "text-danger" : "text-success"}>{f.impact > 0 ? "+" : ""}{f.impact}</span> <strong>{f.label}</strong> — <span className="subtle">{f.explanation}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="flex items-center justify-between gap-2">
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={() => { setEditing(selected.client); setSelected(null); }}><Pencil size={13} />Edit</Button>
                  <Button variant="outline" size="sm" className="text-destructive" onClick={() => { setDeleting(selected.client); setSelected(null); }}><Trash2 size={13} />Delete</Button>
                </div>
                <div className="flex gap-2">
                  {selected.risk && selected.risk.metrics.open_overdue_invoices > 0 && (
                    <Button variant="outline" size="sm" onClick={() => { onDraftReminder(selected.client.id); setSelected(null); }}><Sparkles />Draft reminder</Button>
                  )}
                  <Button size="sm" onClick={() => { setSelected(null); onEmail?.(); }}><Mail />Open mailbox<ArrowUpRight /></Button>
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={editing !== null} onOpenChange={(open) => { if (!open) setEditing(null); }}>
        <DialogContent className="max-w-3xl">
          <DialogTitle>{editing === "new" ? "Add client" : "Edit client"}</DialogTitle>
          <DialogDescription>Saved to the backend.</DialogDescription>
          {editing && (
            <div className="legacy">
              <ClientForm key={editing === "new" ? "new" : editing.id} client={editing === "new" ? null : editing} onDone={() => { setEditing(null); onChanged(); }} />
            </div>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={!!deleting} onOpenChange={(open) => { if (!open) setDeleting(null); }}>
        <DialogContent>
          <DialogTitle>Remove {deleting?.name}?</DialogTitle>
          <DialogDescription>
            This deletes the client. It is refused while shipments, invoices, payments, incidents or sent drafts belong to the client.
          </DialogDescription>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" size="sm" onClick={() => setDeleting(null)}>Cancel</Button>
            <Button size="sm" variant="destructive" onClick={() => deleting && deleteClient(deleting)}><Trash2 size={13} />Remove client</Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
