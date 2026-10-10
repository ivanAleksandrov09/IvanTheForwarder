import { useCallback, useEffect, useState } from "react";
import { api, unwrap } from "./api/client";
import type { Client, DomainEvent, DraftMessage, HealthResponse, RiskProfile, UpdateDraftRequest } from "./api/types";
import { ClientRiskTable } from "./components/ClientRiskTable";
import { DraftQueue } from "./components/DraftQueue";
import { EventsList } from "./components/EventsList";
import { t, type UiLang } from "./i18n";

// Hello-world dashboard: clients + explainable risk, events, approval queue.
// TODO(owner C): routing (Dashboard / Client detail / Map), truck map, client emails timeline.
export default function App() {
  const [lang] = useState<UiLang>("en");
  const [health, setHealth] = useState<HealthResponse>();
  const [clients, setClients] = useState<Client[]>([]);
  const [risk, setRisk] = useState<RiskProfile[]>([]);
  const [events, setEvents] = useState<DomainEvent[]>([]);
  const [drafts, setDrafts] = useState<DraftMessage[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const [h, c, r, e, d] = await Promise.all([
        unwrap(api.GET("/api/system/health")),
        unwrap(api.GET("/api/clients")),
        unwrap(api.GET("/api/risk")),
        unwrap(api.GET("/api/events")),
        unwrap(api.GET("/api/drafts")),
      ]);
      setHealth(h);
      setClients(c);
      setRisk(r);
      setEvents(e);
      setDrafts(d);
      setError(null);
    } catch (err) {
      setError(`Backend unreachable or failed: ${(err as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 5000); // TODO(owner C): SSE instead of polling (stretch)
    return () => clearInterval(timer);
  }, [refresh]);

  const run = async (label: string, action: () => Promise<unknown>) => {
    setBusy(label);
    try {
      await action();
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="app">
      <header>
        <h1>
          Ivan <span className="muted">· AI assistant for forwarders</span>
        </h1>
        <div className="toolbar">
          {health && (
            <span className={`badge ${health.llm.mode}`} title={health.llm.last_error ?? ""}>
              LLM: {health.llm.mode} · {health.llm.model}
            </span>
          )}
          <button disabled={!!busy} onClick={() => run("sync", () => unwrap(api.POST("/api/connectors/{source}/sync", { params: { path: { source: "email" } } })))}>
            {t("syncInbox", lang)}
          </button>
          <button className="primary" disabled={!!busy} onClick={() => run("scan", () => unwrap(api.POST("/api/events/scan", {})))}>
            {busy === "scan" ? "…" : t("scan", lang)}
          </button>
          <button disabled={!!busy} onClick={() => run("reset", () => unwrap(api.POST("/api/system/reset")))}>
            {t("reset", lang)}
          </button>
        </div>
      </header>
      {error && <div className="error">{error}</div>}
      {loading && <p className="muted">{t("loading", lang)}</p>}
      {error && <button onClick={refresh}>{t("retry", lang)}</button>}
      <main>
        <section>
          <h2>{t("clients", lang)}</h2>
          <ClientRiskTable
            clients={clients}
            risk={risk}
            lang={lang}
            onDraftReminder={(client_id) =>
              run("draft", () => unwrap(api.POST("/api/drafts/generate", { body: { kind: "payment_reminder", client_id } })))
            }
          />
          <h2>{t("events", lang)}</h2>
          <EventsList events={events} />
        </section>
        <section>
          <h2>{t("queue", lang)}</h2>
          <DraftQueue
            drafts={drafts}
            clients={clients}
            lang={lang}
            busy={!!busy}
            onApprove={(id) =>
              run("approve", () => unwrap(api.POST("/api/drafts/{draft_id}/approve", { params: { path: { draft_id: id } }, body: { reviewed_by: "operator" } })))
            }
            onReject={(id, reason) =>
              run("reject", () => unwrap(api.POST("/api/drafts/{draft_id}/reject", { params: { path: { draft_id: id } }, body: { reviewed_by: "operator", reason } })))
            }
            onSave={(id, patch: UpdateDraftRequest) =>
              run("save", () => unwrap(api.PATCH("/api/drafts/{draft_id}", { params: { path: { draft_id: id } }, body: patch })))
            }
          />
        </section>
      </main>
    </div>
  );
}
