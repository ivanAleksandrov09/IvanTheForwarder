import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { api, unwrap } from "../api/client";
import type { GpsPing } from "../api/types";

export function TruckMap({ truckId }: { truckId: string }) {
  const mapElement = useRef<HTMLDivElement>(null);
  const [pings, setPings] = useState<GpsPing[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    unwrap(api.GET("/api/trucks/{truck_id}/positions", { params: { path: { truck_id: truckId } } }))
      .then(setPings)
      .catch((err: Error) => setError(err.message));
  }, [truckId]);

  useEffect(() => {
    if (!mapElement.current || pings.length === 0) return;
    const map = L.map(mapElement.current).setView([pings[pings.length - 1].lat, pings[pings.length - 1].lon], 6);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "© OpenStreetMap contributors" }).addTo(map);
    const route = pings.map((ping) => [ping.lat, ping.lon] as [number, number]);
    L.polyline(route, { color: "#1f6feb" }).addTo(map);
    L.marker(route[route.length - 1]).addTo(map).bindPopup(`Truck ${truckId}`);
    map.fitBounds(route);
    return () => {
      map.remove();
    };
  }, [pings, truckId]);

  if (error) return <div className="error">{error}</div>;
  if (pings.length === 0) return <p className="muted">No GPS positions available.</p>;
  return <div className="map" ref={mapElement} aria-label={`GPS map for ${truckId}`} />;
}
