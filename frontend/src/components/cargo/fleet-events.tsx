import { useEffect, useState } from "react";
import { Truck as TruckIcon, ArrowRight, MapPin, Radio, Clock3, ShieldCheck, FileText, CreditCard, Sparkles, Activity, Mail, Gauge } from "lucide-react";
import { api, unwrap } from "@/api/client";
import type { DomainEvent, GpsPing, Shipment, Truck } from "@/api/types";
import { appNow, cap, timeAgo, type Ops } from "@/lib/useOps";
import { PanelHeader, RiskBadge } from "./common";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { TruckMap as LeafletMap } from "@/components/TruckMap";
import { formatDateTime } from "@/format";

type TruckRow = { truck: Truck; shipment?: Shipment | undefined; ping?: GpsPing | undefined };

// Latest GPS ping per truck, fetched from the backend.
function useLatestPings(trucks: Truck[]) {
  const [pings, setPings] = useState<Record<string, GpsPing>>({});
  const key = trucks.map((t) => t.id).join(",");
  useEffect(() => {
    let cancelled = false;
    Promise.all(
      trucks.map((t) =>
        unwrap(api.GET("/api/trucks/{truck_id}/positions", { params: { path: { truck_id: t.id } } })).then((p) => [t.id, p[p.length - 1]] as const),
      ),
    )
      .then((rows) => !cancelled && setPings(Object.fromEntries(rows.filter((r): r is readonly [string, GpsPing] => !!r[1]))))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return pings;
}

const progress = (s?: Shipment): number => {
  if (!s?.picked_up_at || !s.eta_at) return s?.status === "delivered" ? 100 : 5;
  const start = new Date(s.picked_up_at).getTime();
  const end = new Date(s.eta_at).getTime();
  return Math.max(5, Math.min(100, Math.round(((appNow() - start) / Math.max(1, end - start)) * 100)));
};

export function TruckMap({ ops, expanded = false, onExpand }: { ops: Ops; expanded?: boolean | undefined; onExpand?: (() => void) | undefined }) {
  const [selected, setSelected] = useState<TruckRow | null>(null);
  const pings = useLatestPings(ops.trucks);
  const delayedIds = new Set(ops.events.filter((e) => e.type === "shipment_delayed" && !e.handled).map((e) => e.truck_id));
  const rows: TruckRow[] = ops.trucks.map((truck) => ({ truck, shipment: ops.shipments.find((s) => s.id === truck.current_shipment_id), ping: pings[truck.id] }));
  const onRoad = ops.trucks.filter((t) => t.status === "en_route").length;
  const list = rows.map((r) => {
    const delayed = delayedIds.has(r.truck.id);
    const label = delayed ? "Delayed" : r.truck.status === "en_route" ? "On time" : cap(r.truck.status);
    return (
      <div className="truck-row" key={r.truck.id}>
        <Button title={`View ${r.truck.label}`} variant="ghost" className="truck-icon" onClick={() => setSelected(r)}><TruckIcon /></Button>
        <div>
          <div className="truck-label">{r.truck.label}<span className="subtle small">{r.truck.plate_number}</span></div>
          <div className="truck-route">{r.shipment ? <>{r.shipment.origin.city}<ArrowRight />{r.shipment.destination.city}</> : "No active shipment"}</div>
          <div className="route-track"><div className={`route-progress ${delayed ? "delayed" : ""}`} style={{ width: `${progress(r.shipment)}%` }} /></div>
          <div className="truck-location"><span className="flex items-center gap-1"><MapPin size={10} />{r.ping ? `${r.ping.lat.toFixed(2)}, ${r.ping.lon.toFixed(2)}` : "No GPS"}</span><span>{r.ping ? timeAgo(r.ping.recorded_at) : ""}</span></div>
        </div>
        <div className="truck-eta"><RiskBadge level={label} /><strong>{r.shipment?.eta_at ? `ETA ${formatDateTime(r.shipment.eta_at)}` : "—"}</strong><span className="subtle">{r.shipment?.reference ?? ""}</span></div>
      </div>
    );
  });
  return (
    <>
      <section className={expanded ? "" : "panel"}>
        {!expanded && <PanelHeader title="Fleet activity" icon={<TruckIcon />} action="View fleet" onAction={onExpand} />}
        <div className="fleet-legend">
          <span className="legend-item"><span className="status-dot" />{onRoad} on the road</span>
          <span className="legend-item"><span className="status-dot bg-warning" />{delayedIds.size} delayed</span>
          <span className="legend-item ml-auto"><Radio size={11} />GPS live</span>
        </div>
        {expanded && ops.trucks.length > 0 && <div className="panel mt-5 p-3 legacy"><LeafletMap truckIds={ops.trucks.map((t) => t.id)} /></div>}
        <div className={expanded ? "full-fleet mt-5" : ""}>
          {ops.trucks.length === 0 && <div className="empty-state">No trucks in the fleet.</div>}
          {expanded ? list.map((row, i) => <section className="panel" key={i}>{row}</section>) : list}
        </div>
      </section>
      <Dialog open={!!selected} onOpenChange={(open) => { if (!open) setSelected(null); }}>
        <DialogContent>
          <DialogTitle>{selected?.truck.label} · Fleet location</DialogTitle>
          <DialogDescription>{selected?.shipment ? `${selected.shipment.origin.city} to ${selected.shipment.destination.city}` : "No active shipment"}</DialogDescription>
          {selected && (
            <>
              <div className="detail-row"><span className="subtle">Driver</span>{selected.truck.driver_name ?? "–"}</div>
              <div className="detail-row"><span className="subtle">Plate</span>{selected.truck.plate_number}</div>
              <div className="detail-row"><span className="subtle">Last GPS ping</span>{selected.ping ? `${selected.ping.lat.toFixed(3)}, ${selected.ping.lon.toFixed(3)} · ${timeAgo(selected.ping.recorded_at)}` : "No GPS data"}</div>
              {selected.ping && <div className="detail-row"><span className="subtle flex items-center gap-1"><Gauge size={12} />Speed</span>{selected.ping.speed_kmh.toFixed(0)} km/h</div>}
              <div className="detail-row"><span className="subtle">Shipment</span>{selected.shipment?.reference ?? "–"}</div>
              <div className="detail-row"><span className="subtle">Estimated arrival</span>{formatDateTime(selected.shipment?.eta_at)}</div>
              <div className="detail-row"><span className="subtle">Status</span><RiskBadge level={cap(selected.truck.status)} /></div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}

const ICONS: Record<string, typeof Clock3> = { shipment_delayed: Clock3, invoice_overdue: CreditCard, invoice_due_soon: CreditCard, payment_received: CreditCard, email_received: Mail, document_received: FileText, risk_level_changed: ShieldCheck, truck_idle: TruckIcon };
const ICON_CLASS: Record<string, string> = { invoice_overdue: "invoice", invoice_due_soon: "invoice", payment_received: "invoice", document_received: "document", email_received: "document", risk_level_changed: "customs" };
const SEVERITY: Record<string, string> = { info: "Low", low: "Low", medium: "Medium", high: "High", critical: "High" };

export function EventsList({ events, onExpand, expanded = false, onDraft, onScan, scanning }: { events: DomainEvent[]; onExpand?: (() => void) | undefined; expanded?: boolean | undefined; onDraft?: (() => void) | undefined; onScan?: (() => void) | undefined; scanning?: boolean | undefined }) {
  const [selected, setSelected] = useState<DomainEvent | null>(null);
  const shown = expanded ? events : events.slice(0, 4);
  return (
    <>
      <section className="panel">
        <PanelHeader title="Operational alerts" count={events.length} icon={<Activity />} action={expanded ? undefined : "View all"} onAction={onExpand} />
        {shown.length === 0 && (
          <div className="empty-state">
            No alerts yet.
            {onScan && <div className="mt-3"><Button size="sm" disabled={scanning} onClick={onScan}><Sparkles />{scanning ? "Scanning…" : "Scan for events"}</Button></div>}
          </div>
        )}
        {shown.map((event) => {
          const Icon = ICONS[event.type] ?? Activity;
          return (
            <div className="event-row" key={event.id} role="button" tabIndex={0} aria-label={event.title} onClick={() => setSelected(event)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSelected(event); } }}>
              <div className={`event-icon ${ICON_CLASS[event.type] ?? ""}`}><Icon /></div>
              <div className="event-copy">
                <div className="event-top"><strong>{event.title}</strong><span className="event-time">{timeAgo(event.detected_at)}</span></div>
                <p>{event.description}</p>
                {event.draft_ids.length > 0 && <span className="event-action"><Sparkles />Draft queued for review</span>}
              </div>
            </div>
          );
        })}
      </section>
      <Dialog open={!!selected} onOpenChange={(open) => { if (!open) setSelected(null); }}>
        <DialogContent>
          <DialogTitle>{selected?.title}</DialogTitle>
          <DialogDescription>{selected ? cap(selected.type) : ""}</DialogDescription>
          <p className="detail-body">{selected?.description}</p>
          {selected && selected.evidence.length > 0 && <ul className="detail-body list-disc pl-5">{selected.evidence.map((e, i) => <li key={i}>{typeof e === "string" ? e : JSON.stringify(e)}</li>)}</ul>}
          <div className="flex justify-between items-center">
            <RiskBadge level={SEVERITY[selected?.severity ?? "low"] ?? "Low"} />
            {selected && selected.draft_ids.length > 0 && <Button onClick={() => { setSelected(null); onDraft?.(); }}><Sparkles />Review draft</Button>}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
