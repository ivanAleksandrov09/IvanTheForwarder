import type { DomainEvent } from "../api/types";

export function EventsList({ events }: { events: DomainEvent[] }) {
  if (!events.length) return <p className="muted">No events yet — press “Scan”.</p>;
  return (
    <ul className="events">
      {events.map((e) => (
        <li key={e.id} className={`sev-${e.severity}`}>
          <strong>{e.title}</strong>
          <div className="muted">{e.description}</div>
          {e.draft_ids.length > 0 && <div className="muted">→ draft queued</div>}
        </li>
      ))}
    </ul>
  );
}
