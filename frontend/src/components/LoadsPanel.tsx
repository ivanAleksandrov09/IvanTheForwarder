import { useEffect, useState } from "react";
import { api, unwrap } from "../api/client";
import type { LoadOffer } from "../api/types";

export function LoadsPanel() {
  const [loads, setLoads] = useState<LoadOffer[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [searching, setSearching] = useState(false);

  const load = () =>
    unwrap(api.GET("/api/loads"))
      .then(setLoads)
      .catch((err) => setError((err as Error).message));

  useEffect(() => {
    load();
  }, []);

  const search = async () => {
    setSearching(true);
    setError(null);
    try {
      setLoads(await unwrap(api.POST("/api/loads/refresh")));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSearching(false);
    }
  };

  return (
    <section className="panel">
      <h2>Load offers</h2>
      <button className="primary" disabled={searching} onClick={search}>
        {searching ? "Searching the web…" : "Search now"}
      </button>
      {error && <div className="error">{error}</div>}
      <table>
        <thead>
          <tr>
            <th>Pickup</th>
            <th>Route</th>
            <th>Cargo</th>
            <th>Weight</th>
            <th>Vehicle</th>
            <th>Price</th>
            <th>Source</th>
          </tr>
        </thead>
        <tbody>
          {loads.map((load) => (
            <tr key={load.id}>
              <td>{load.pickup_date ?? "—"}</td>
              <td>{load.origin} → {load.destination}</td>
              <td>{load.cargo ?? "—"}</td>
              <td>{load.weight_kg === null || load.weight_kg === undefined ? "—" : `${load.weight_kg.toLocaleString()} kg`}</td>
              <td>{load.vehicle ?? "—"}</td>
              <td>{load.price_eur === null || load.price_eur === undefined ? "—" : `€${load.price_eur.toLocaleString()}`}</td>
              <td>
                <a href={load.source_url} target="_blank" rel="noreferrer">{load.source}</a>
                {!load.verified && <span className="muted"> (link not confirmed)</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
