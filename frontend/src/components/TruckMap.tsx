import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { api, unwrap } from "../api/client";
import type { GpsPing } from "../api/types";

type TruckRoute = { truckId: string; pings: GpsPing[] };

export function TruckMap({ truckIds }: { truckIds: string[] }) {
  const mapElement = useRef<HTMLDivElement>(null);
  const [routes, setRoutes] = useState<TruckRoute[]>([]);
  const [error, setError] = useState<string | null>(null);
  const truckIdsKey = truckIds.join(",");

  useEffect(() => {
    Promise.all(
      truckIds.map((truckId) =>
        unwrap(api.GET("/api/trucks/{truck_id}/positions", { params: { path: { truck_id: truckId } } })).then((pings) => ({
          truckId,
          pings,
        })),
      ),
    )
      .then(setRoutes)
      .catch((err: Error) => setError(err.message));
  }, [truckIdsKey]);

  useEffect(() => {
    const activeRoutes = routes.filter((route) => route.pings.length > 0);
    if (!mapElement.current || activeRoutes.length === 0) return;
    const allPoints = activeRoutes.flatMap((route) => route.pings.map((ping) => [ping.lat, ping.lon] as [number, number]));
    const map = L.map(mapElement.current).setView(allPoints[allPoints.length - 1], 6);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "© OpenStreetMap contributors" }).addTo(map);
    const colors = ["#1f6feb", "#d92d20", "#067647", "#f79009", "#7f56d9", "#c11574"];
    activeRoutes.forEach((route, index) => {
      const points = route.pings.map((ping) => [ping.lat, ping.lon] as [number, number]);
      const color = colors[index % colors.length];
      L.polyline(points, { color, weight: 4, opacity: 0.75 }).addTo(map);
      const latest = route.pings[route.pings.length - 1];
      L.circleMarker([latest.lat, latest.lon], {
        radius: 11,
        color: "#ffffff",
        weight: 3,
        fillColor: color,
        fillOpacity: 1,
      }).addTo(map).bindPopup(`<strong>${route.truckId}</strong><br>${latest.speed_kmh.toFixed(0)} km/h`);
    });
    map.fitBounds(L.latLngBounds(allPoints), { padding: [24, 24] });
    return () => {
      map.remove();
    };
  }, [routes]);

  if (error) return <div className="error">{error}</div>;
  if (routes.every((route) => route.pings.length === 0)) return <p className="muted">No GPS positions available.</p>;
  const colors = ["#1f6feb", "#d92d20", "#067647", "#f79009", "#7f56d9", "#c11574"];
  return (
    <div className="map-wrap">
      <div className="map" ref={mapElement} aria-label="GPS map for all trucks" />
      <div className="map-legend">
        {routes.filter((route) => route.pings.length > 0).map((route, index) => (
          <span key={route.truckId}>
            <i style={{ backgroundColor: colors[index % colors.length] }} /> {route.truckId}
          </span>
        ))}
      </div>
    </div>
  );
}
