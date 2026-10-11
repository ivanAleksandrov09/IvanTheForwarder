import { useEffect, useState, type ReactNode } from "react";
import { LayoutDashboard, Package, Truck, ShieldCheck, Mail, Sparkles, Activity, CreditCard, Settings, CircleHelp, ChevronRight, Search, Bell, Sun, Moon, Download, ArrowUpRight, Menu, X, Radio, ArrowRight, Compass, RefreshCw, ScanSearch, PhoneCall, Boxes, Plug, Share2, Inbox } from "lucide-react";
import { toast } from "sonner";
import { api, unwrap } from "@/api/client";
import type { Shipment, UpdateDraftRequest } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Toaster } from "@/components/ui/sonner";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { KpiCards, PanelHeader, RiskBadge } from "@/components/cargo/common";
import { TruckMap, EventsList } from "@/components/cargo/fleet-events";
import { ClientRiskTable } from "@/components/cargo/clients";
import { MailboxPanel, DraftQueue, type DraftActions } from "@/components/cargo/mailbox";
import { MailboxPanel as MailboxConnect } from "@/components/MailboxPanel";
import { LoadsPanel } from "@/components/LoadsPanel";
import { OnboardingPanel } from "@/components/OnboardingPanel";
import { NetworkPanel } from "@/components/NetworkPanel";
import { CallExtractionPanel } from "@/components/CallExtractionPanel";
import { CompanyName } from "@/components/CompanyName";
import { appNow, cap, useOps } from "@/lib/useOps";
import { formatDateTime, formatMoney } from "@/format";

const navigation = [
  { name: "Overview", icon: LayoutDashboard },
  { name: "Shipments", icon: Package },
  { name: "Fleet tracking", icon: Truck },
  { name: "Client risk", icon: ShieldCheck },
  { name: "Mailbox", icon: Mail },
  { name: "Draft queue", icon: Sparkles },
  { name: "Operational alerts", icon: Activity },
  { name: "Invoices", icon: CreditCard },
  { name: "Loads", icon: Boxes },
  { name: "Call extraction", icon: PhoneCall },
  { name: "Connect email", icon: Inbox },
  { name: "Connect systems", icon: Plug },
  { name: "Share profile", icon: Share2 },
];

const descriptions: Record<string, string> = {
  Overview: "Here's what's happening across your operations today.",
  Shipments: "Keep every shipment moving, from pickup to final delivery.",
  "Fleet tracking": "Live GPS pings and arrival estimates across your road fleet.",
  "Client risk": "Credit exposure and operational risk, explained.",
  Mailbox: "Your operations inbox, with the next response ready.",
  "Draft queue": "Proactive responses, ready for your review.",
  "Operational alerts": "The exceptions that need your attention.",
  Invoices: "Stay on top of receivables and payment follow-ups.",
  Loads: "Load offers matched to your fleet.",
  "Call extraction": "Turn call recordings into reviewed load records.",
  "Connect email": "Connect a mailbox once; Ivan reads and analyzes new mail automatically.",
  "Connect systems": "Tell Ivan which ERP, GPS and email systems you use.",
  "Share profile": "Choose what your public capacity profile shares.",
  Settings: "Manage your workspace preferences.",
};

const SHIPMENT_LABEL: Record<string, string> = { quoted: "Quoted", booked: "Booked", in_transit: "In transit", delivered: "Delivered", cancelled: "Cancelled" };

// Wraps older, unstyled-by-Tailwind panels so their own stylesheet applies.
const Legacy = ({ children }: { children: ReactNode }) => <div className="legacy">{children}</div>;

export default function App() {
  const { data: ops, error, loading, refresh } = useOps();
  const [view, setView] = useState("Overview");
  const [dark, setDark] = useState(false);
  const [menu, setMenu] = useState(false);
  const [modal, setModal] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [selectedShipment, setSelectedShipment] = useState<Shipment | null>(null);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    return () => document.documentElement.classList.remove("dark");
  }, [dark]);

  const navigate = (next: string) => {
    setView(next);
    setMenu(false);
    setModal(null);
  };

  // Runs a backend action, reports the outcome in a toast and reloads the data.
  const run = async (label: string, action: () => Promise<unknown>, success?: string) => {
    setBusy(label);
    try {
      await action();
      if (success) toast.success(success);
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      await refresh();
      setBusy(null);
    }
  };

  const clientName = (id?: string | null) => ops.clients.find((c) => c.id === id)?.name ?? "—";
  const pendingDrafts = ops.drafts.filter((d) => d.status === "pending_review").length;
  const openAlerts = ops.events.filter((e) => !e.handled).length;
  const highRisk = ops.risk.filter((r) => r.level === "high").length;
  const unpaid = ops.invoices.filter((i) => i.status === "issued" || i.status === "partially_paid");
  const counts: Record<string, number> = { Shipments: ops.shipments.length, "Client risk": highRisk, Mailbox: ops.emails.filter((e) => e.direction === "inbound").length, "Draft queue": pendingDrafts, "Operational alerts": openAlerts };

  const actions: DraftActions = {
    busy: busy !== null,
    onApprove: (id) => run("approve", () => unwrap(api.POST("/api/drafts/{draft_id}/approve", { params: { path: { draft_id: id } }, body: { reviewed_by: "operator" } })), "Draft approved and sent"),
    onReject: (id, reason) => run("reject", () => unwrap(api.POST("/api/drafts/{draft_id}/reject", { params: { path: { draft_id: id } }, body: { reviewed_by: "operator", reason } })), "Draft rejected"),
    onSave: (id, patch: UpdateDraftRequest) => run("save", () => unwrap(api.PATCH("/api/drafts/{draft_id}", { params: { path: { draft_id: id } }, body: patch })), "Draft saved"),
  };
  const draftReminder = (clientId: string) =>
    run("draft", () => unwrap(api.POST("/api/drafts/generate", { body: { kind: "payment_reminder", client_id: clientId } })), "Payment reminder drafted for review");
  const scan = () => run("scan", () => unwrap(api.POST("/api/events/scan", {})), "Event scan complete");
  const sync = () => run("sync", () => unwrap(api.POST("/api/connectors/{source}/sync", { params: { path: { source: "email" } } })), "Inbox synced");
  const reset = () => window.confirm("Reset all data to the seed state?") && run("reset", () => unwrap(api.POST("/api/system/reset")), "Data reset");

  const exportData = () => {
    const rows = ops.shipments.map((s) => [s.reference, clientName(s.client_id), `${s.origin.city} → ${s.destination.city}`, s.cargo_description, SHIPMENT_LABEL[s.status] ?? s.status, s.eta_at ?? ""]);
    const csv = "Shipment,Client,Route,Cargo,Status,ETA\n" + rows.map((r) => r.map((v) => `"${String(v).replaceAll('"', '""')}"`).join(",")).join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8;" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "shipments.csv";
    a.click();
    URL.revokeObjectURL(url);
    toast.success("Shipment report exported");
  };

  const llm = ops.health?.llm;
  const q = search.toLowerCase();

  return (
    <div className="app-shell">
      <aside className={`sidebar ${menu ? "open" : ""}`}>
        <Button variant="ghost" size="icon" className="sidebar-close" aria-label="Close navigation" onClick={() => setMenu(false)}><X /></Button>
        <div className="brand"><span className="brand-mark"><Compass size={21} strokeWidth={2.2} /></span>Ivan</div>
        <div className="nav-label">Workspace</div>
        <nav className="nav-list" aria-label="Workspace navigation">
          {navigation.map((n) => (
            <Button variant="ghost" className={`nav-item ${view === n.name ? "active" : ""}`} key={n.name} onClick={() => navigate(n.name)}>
              <n.icon />{n.name}
              {counts[n.name] !== undefined && <span className={`nav-count ${n.name === "Client risk" ? "alert" : ""}`}>{counts[n.name]}</span>}
            </Button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <Button variant="ghost" className={`nav-item ${view === "Settings" ? "active" : ""}`} onClick={() => navigate("Settings")}><Settings />Settings</Button>
          <Button variant="ghost" className="nav-item" onClick={() => setModal("help")}><CircleHelp />Help & support<ArrowUpRight className="ml-auto" /></Button>
          <div className="system-status"><span className="status-dot" />{error ? "Backend unreachable" : "All systems operational"}</div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumbs">
            <Button variant="ghost" size="icon" className="mobile-menu" aria-label="Open navigation" onClick={() => setMenu(true)}><Menu /></Button>
            <span className="subtle workspace-crumb">Workspace</span><ChevronRight size={12} className="subtle workspace-crumb" /><span>{view}</span>
          </div>
          <div className="top-tools">
            {llm && <span className={`badge ${llm.mode === "live" ? "badge-low" : "badge-medium"}`} title={llm.last_error ?? ""}>LLM: {llm.mode} · {llm.model}</span>}
            <Button variant="ghost" className="search-trigger" aria-label="Search workspace" onClick={() => setModal("search")}><Search size={14} /><span>Search anything…</span></Button>
            <Button variant="ghost" size="icon" className="icon-button" title={dark ? "Switch to light mode" : "Switch to dark mode"} aria-label={dark ? "Switch to light mode" : "Switch to dark mode"} onClick={() => setDark(!dark)}>{dark ? <Sun /> : <Moon />}</Button>
            <Button variant="ghost" size="icon" className="icon-button" title="Notifications" aria-label="Notifications" onClick={() => navigate("Operational alerts")}><Bell />{openAlerts > 0 && <span className="notification-dot" />}</Button>
          </div>
        </header>
        <main className="main-content">
          <div className="page-heading">
            <div><h1>{view === "Overview" ? "Operations overview" : view}</h1><p>{descriptions[view]}</p></div>
            <div className="heading-actions">
              <Button variant="outline" disabled={busy !== null} onClick={sync}><RefreshCw />Sync inbox</Button>
              <Button disabled={busy !== null} onClick={scan}><ScanSearch />{busy === "scan" ? "Scanning…" : "Scan for events"}</Button>
              <Button variant="outline" onClick={exportData}><Download />Export</Button>
            </div>
          </div>
          {error && <div className="panel p-4 mb-5 text-danger flex items-center justify-between" role="alert">{error}<Button size="sm" variant="outline" onClick={refresh}>Retry</Button></div>}
          {loading && <p className="subtle">Loading…</p>}

          {view === "Overview" && (
            <>
              <KpiCards ops={ops} onNavigate={navigate} />
              <div className="overview-grid">
                <TruckMap ops={ops} onExpand={() => navigate("Fleet tracking")} />
                <EventsList events={ops.events} onExpand={() => navigate("Operational alerts")} onDraft={() => navigate("Draft queue")} onScan={scan} scanning={busy === "scan"} />
              </div>
              <ClientRiskTable clients={ops.clients} risk={ops.risk} onExpand={() => navigate("Client risk")} onEmail={() => navigate("Mailbox")} onDraftReminder={draftReminder} onChanged={refresh} />
              <MailboxPanel emails={ops.emails} insights={ops.insights} drafts={ops.drafts} clients={ops.clients} mailboxLabel="Operations inbox" onExpand={() => navigate("Mailbox")} actions={actions} />
            </>
          )}
          {view === "Fleet tracking" && <TruckMap ops={ops} expanded />}
          {view === "Operational alerts" && <EventsList events={ops.events} expanded onDraft={() => navigate("Draft queue")} onScan={scan} scanning={busy === "scan"} />}
          {view === "Client risk" && <ClientRiskTable clients={ops.clients} risk={ops.risk} expanded onEmail={() => navigate("Mailbox")} onDraftReminder={draftReminder} onChanged={refresh} />}
          {view === "Mailbox" && <MailboxPanel emails={ops.emails} insights={ops.insights} drafts={ops.drafts} clients={ops.clients} mailboxLabel="Operations inbox" expanded actions={actions} />}
          {view === "Draft queue" && <DraftQueue drafts={ops.drafts} clients={ops.clients} actions={actions} />}

          {view === "Shipments" && (
            <section className="panel table-panel">
              <PanelHeader icon={<Package />} title="Shipments" count={ops.shipments.length} />
              <div className="table-scroll">
                <table>
                  <thead><tr><th>Shipment</th><th>Client / cargo</th><th>Route</th><th>Status</th><th>ETA</th><th></th></tr></thead>
                  <tbody>
                    {ops.shipments.map((s) => (
                      <tr key={s.id} onClick={() => setSelectedShipment(s)} tabIndex={0} onKeyDown={(e) => { if (e.key === "Enter") setSelectedShipment(s); }}>
                        <td className="font-medium">{s.reference}</td>
                        <td><div>{clientName(s.client_id)}</div><div className="small subtle mt-1">{s.cargo_description}</div></td>
                        <td>{s.origin.city} → {s.destination.city}</td>
                        <td><RiskBadge level={SHIPMENT_LABEL[s.status] ?? s.status} /></td>
                        <td>{formatDateTime(s.eta_at ?? s.delivery_planned_at)}</td>
                        <td><ChevronRight size={13} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {ops.shipments.length === 0 && <div className="empty-state">No shipments.</div>}
              </div>
            </section>
          )}

          {view === "Invoices" && (
            <section className="panel table-panel">
              <PanelHeader icon={<CreditCard />} title="Invoices" count={ops.invoices.length} subtitle={`${unpaid.length} unpaid`} />
              <div className="table-scroll">
                <table>
                  <thead><tr><th>Invoice</th><th>Client</th><th>Amount</th><th>Due date</th><th>Status</th><th></th></tr></thead>
                  <tbody>
                    {[...ops.invoices].sort((a, b) => a.due_at.localeCompare(b.due_at)).map((i) => {
                      const overdue = (i.status === "issued" || i.status === "partially_paid") && new Date(i.due_at).getTime() < appNow();
                      return (
                        <tr key={i.id}>
                          <td className="font-medium">{i.number}</td>
                          <td>{clientName(i.client_id)}</td>
                          <td>{formatMoney(i.total)}</td>
                          <td>{formatDateTime(i.due_at)}</td>
                          <td><span className={`badge ${overdue ? "badge-high" : i.status === "paid" ? "badge-low" : "badge-medium"}`}>{overdue ? "Overdue" : cap(i.status)}</span></td>
                          <td>{overdue && <Button variant="ghost" size="sm" onClick={() => draftReminder(i.client_id)}>Draft reminder<ArrowUpRight /></Button>}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                {ops.invoices.length === 0 && <div className="empty-state">No invoices.</div>}
              </div>
            </section>
          )}

          {view === "Loads" && <Legacy><LoadsPanel /></Legacy>}
          {view === "Call extraction" && <Legacy><CallExtractionPanel /></Legacy>}
          {view === "Connect email" && <Legacy><MailboxConnect onSynced={refresh} /></Legacy>}
          {view === "Connect systems" && <Legacy><OnboardingPanel /></Legacy>}
          {view === "Share profile" && <Legacy><NetworkPanel /></Legacy>}

          {view === "Settings" && (
            <section className="panel table-panel">
              <PanelHeader icon={<Settings />} title="Workspace settings" />
              <div className="settings-row"><div><strong>Appearance</strong><span className="subtle small">Workspace color theme</span></div><div className="flex gap-2"><Button variant={!dark ? "secondary" : "ghost"} onClick={() => setDark(false)}><Sun />Light</Button><Button variant={dark ? "secondary" : "ghost"} onClick={() => setDark(true)}><Moon />Dark</Button></div></div>
              <div className="settings-row"><div><strong>Email approvals</strong><span className="subtle small">An operator reviews every response before it is sent</span></div><span className="badge badge-low">Approval required</span></div>
              <div className="settings-row"><div><strong>AI model</strong><span className="subtle small">{llm ? `${llm.model} (${llm.mode})` : "–"}</span></div><span className={`badge ${llm?.mode === "live" ? "badge-low" : "badge-medium"}`}>{llm?.mode ?? "–"}</span></div>
              <div className="settings-row"><div><strong>Reset demo data</strong><span className="subtle small">Restore the seeded data set</span></div><Button variant="outline" disabled={busy !== null} onClick={reset}>Reset data</Button></div>
              <div className="p-5"><Legacy><CompanyName /></Legacy></div>
            </section>
          )}

          <footer className="footer-line"><span><Radio />Auto-refreshing every 5 s<span className="mx-1">·</span>{ops.health?.app_env ?? "–"} data</span><span><Sparkles />A little less admin. A lot more moving.</span></footer>
        </main>
      </div>

      <Toaster position="bottom-right" theme={dark ? "dark" : "light"} />

      <Dialog open={modal !== null} onOpenChange={(open) => { if (!open) setModal(null); }}>
        <DialogContent>
          <DialogTitle>{modal === "search" ? "Search Ivan" : "Help & support"}</DialogTitle>
          <DialogDescription>{modal === "search" ? "Views, clients and shipments" : "How to use this workspace"}</DialogDescription>
          {modal === "search" && (
            <>
              <input className="search-input" autoFocus placeholder="Search shipments or clients…" aria-label="Search" value={search} onChange={(e) => setSearch(e.target.value)} />
              <div className="max-h-80 overflow-auto">
                {navigation.filter((n) => n.name.toLowerCase().includes(q)).map((n) => <Button key={n.name} variant="ghost" className="search-result" onClick={() => navigate(n.name)}><n.icon /><span>{n.name}</span><ChevronRight className="ml-auto" /></Button>)}
                {ops.clients.filter((c) => q.length > 0 && c.name.toLowerCase().includes(q)).map((c) => <Button key={c.id} variant="ghost" className="search-result" onClick={() => navigate("Client risk")}><ShieldCheck />{c.name}</Button>)}
                {ops.shipments.filter((s) => q.length > 0 && `${s.reference} ${s.origin.city} ${s.destination.city} ${clientName(s.client_id)}`.toLowerCase().includes(q)).map((s) => <Button key={s.id} variant="ghost" className="search-result" onClick={() => { setModal(null); setSelectedShipment(s); }}><Package />{s.reference}<span className="subtle text-xs">{s.origin.city} → {s.destination.city}</span></Button>)}
              </div>
            </>
          )}
          {modal === "help" && (
            <>
              <p className="detail-body">Press “Scan for events” to detect delays and overdue invoices. Ivan drafts the follow-ups in the Draft queue; nothing is sent until you approve it. Use “Sync inbox” to pull new email.</p>
              <Button onClick={() => navigate("Operational alerts")}>Open operational alerts<ArrowRight /></Button>
            </>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={selectedShipment !== null} onOpenChange={(open) => { if (!open) setSelectedShipment(null); }}>
        <DialogContent>
          <DialogTitle>{selectedShipment?.reference}</DialogTitle>
          <DialogDescription>{clientName(selectedShipment?.client_id)}</DialogDescription>
          {selectedShipment && (
            <>
              <div className="detail-row"><span className="subtle">Route</span>{selectedShipment.origin.city} → {selectedShipment.destination.city}</div>
              <div className="detail-row"><span className="subtle">Cargo</span>{selectedShipment.cargo_description} · {selectedShipment.weight_kg} kg</div>
              <div className="detail-row"><span className="subtle">Status</span><RiskBadge level={SHIPMENT_LABEL[selectedShipment.status] ?? selectedShipment.status} /></div>
              <div className="detail-row"><span className="subtle">ETA</span>{formatDateTime(selectedShipment.eta_at ?? selectedShipment.delivery_planned_at)}</div>
              <div className="detail-row"><span className="subtle">Price</span>{formatMoney(selectedShipment.price)}</div>
              <Button onClick={() => { setSelectedShipment(null); navigate("Fleet tracking"); }}><Truck />View fleet tracking</Button>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
