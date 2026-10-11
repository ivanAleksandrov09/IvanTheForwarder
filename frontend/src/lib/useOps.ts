import { useCallback, useEffect, useState } from "react";
import { api, unwrap } from "@/api/client";
import type { Client, DomainEvent, DraftMessage, Email, EmailInsight, HealthResponse, Invoice, RiskProfile, Shipment, Truck } from "@/api/types";

export type Ops = {
  health?: HealthResponse;
  clients: Client[];
  risk: RiskProfile[];
  events: DomainEvent[];
  drafts: DraftMessage[];
  trucks: Truck[];
  shipments: Shipment[];
  invoices: Invoice[];
  emails: Email[];
  insights: Record<string, EmailInsight>;
};

const empty: Ops = { clients: [], risk: [], events: [], drafts: [], trucks: [], shipments: [], invoices: [], emails: [], insights: {} };

/** Loads every collection the dashboard needs from the backend and re-polls it. */
export function useOps() {
  const [data, setData] = useState<Ops>(empty);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const [health, clients, risk, events, drafts, trucks, shipments, invoices, emails, insights] = await Promise.all([
        unwrap(api.GET("/api/system/health")),
        unwrap(api.GET("/api/clients")),
        unwrap(api.GET("/api/risk")),
        unwrap(api.GET("/api/events")),
        unwrap(api.GET("/api/drafts")),
        unwrap(api.GET("/api/trucks")),
        unwrap(api.GET("/api/shipments", { params: { query: {} } })),
        unwrap(api.GET("/api/invoices", { params: { query: {} } })),
        unwrap(api.GET("/api/emails", { params: { query: {} } })),
        unwrap(api.GET("/api/email-insights")),
      ]);
      offsetMs = new Date(health.now).getTime() - Date.now();
      setData({ health, clients, risk, events, drafts, trucks, shipments, invoices, emails, insights: Object.fromEntries(insights.map((i) => [i.email_id, i])) });
      setError(null);
    } catch (err) {
      setError(`Backend unreachable or failed: ${(err as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 5000);
    return () => clearInterval(timer);
  }, [refresh]);

  return { data, error, loading, refresh };
}

// The backend clock can be fixed (demo mode), so "now" comes from /health, not from the browser.
let offsetMs = 0;
export const appNow = () => Date.now() + offsetMs;

export const initials = (name: string) =>
  name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join("");

export const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1).replaceAll("_", " ");

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "–";
  const mins = Math.round((appNow() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  if (mins < 60 * 24) return `${Math.round(mins / 60)} h ago`;
  return `${Math.round(mins / 1440)} d ago`;
}
