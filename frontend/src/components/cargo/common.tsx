import { type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { ArrowUpRight, ChevronRight, Truck, FileText, ShieldAlert, Sparkles } from "lucide-react";
import { appNow, type Ops } from "@/lib/useOps";
import { formatMoney } from "@/format";
import type { Money } from "@/api/types";

export function RiskBadge({ level }: { level: string }) {
  return <span className={`badge badge-${level.toLowerCase().replaceAll(" ", "-").replaceAll("_", "-")}`}>{level}</span>;
}

export function PanelHeader({ icon, title, count, subtitle, action, onAction }: { icon?: ReactNode; title: string; count?: number | undefined; subtitle?: string | undefined; action?: string | undefined; onAction?: (() => void) | undefined }) {
  return (
    <div className="panel-header">
      <div>
        <div className="panel-title">{icon}{title}{count !== undefined && <span className="table-count">{count}</span>}</div>
        {subtitle && <div className="panel-subtitle">{subtitle}</div>}
      </div>
      {action && <Button variant="ghost" onClick={onAction} className="text-muted-foreground">{action}<ChevronRight /></Button>}
    </div>
  );
}

export function KpiCards({ ops, onNavigate }: { ops: Ops; onNavigate: (view: string) => void }) {
  const active = ops.shipments.filter((s) => s.status === "in_transit" || s.status === "booked").length;
  const unpaid = ops.invoices.filter((i) => i.status === "issued" || i.status === "partially_paid");
  const now = appNow();
  const overdue = unpaid.filter((i) => new Date(i.due_at).getTime() < now);
  const unpaidTotal: Money = { amount_minor: unpaid.reduce((a, i) => a + i.total.amount_minor, 0), currency: unpaid[0]?.total.currency ?? "EUR" };
  const highRisk = ops.risk.filter((r) => r.level === "high").length;
  const pending = ops.drafts.filter((d) => d.status === "pending_review").length;
  const cards = [
    { title: "Active shipments", value: String(active), small: `${ops.shipments.length} total`, icon: Truck, change: `${ops.trucks.length} trucks`, note: "in fleet", positive: true, view: "Shipments" },
    { title: "Pending invoices", value: formatMoney(unpaidTotal), small: `${unpaid.length} invoices`, icon: FileText, change: `${overdue.length} overdue`, note: "requiring follow-up", positive: overdue.length === 0, view: "Invoices" },
    { title: "High-risk clients", value: String(highRisk), small: `of ${ops.clients.length} clients`, icon: ShieldAlert, change: `${ops.risk.filter((r) => r.level === "medium").length} medium`, note: "risk level", positive: highRisk === 0, view: "Client risk" },
    { title: "AI drafts ready", value: String(pending), icon: Sparkles, change: `${ops.events.filter((e) => !e.handled).length} open alerts`, note: "from event scan", positive: true, view: "Draft queue" },
  ];
  return (
    <div className="kpi-grid">
      {cards.map((c) => (
        <div className="kpi" key={c.title}>
          <div className="kpi-top">
            <span>{c.title}</span>
            <Button title={`View ${c.view.toLowerCase()}`} variant="ghost" size="icon" className="kpi-icon" onClick={() => onNavigate(c.view)}><c.icon /></Button>
          </div>
          <div className="kpi-number">{c.value}{c.small && <small>{c.small}</small>}</div>
          <div className="kpi-bottom">
            <span className={c.positive ? "positive" : "negative"}>{c.change}</span>
            <span>{c.note}</span>
            {c.title === "AI drafts ready" && <ArrowUpRight className="positive" />}
          </div>
        </div>
      ))}
    </div>
  );
}
