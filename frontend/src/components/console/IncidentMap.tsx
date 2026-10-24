import { useEffect, useMemo, useRef } from "react";
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMap } from "react-leaflet";
import type { IncidentSummary } from "../../api/types";
import { priorityTone, sentence } from "../../lib/format";

const BOSTON: [number, number] = [42.35, -71.08];

function Viewport({ incidents, selectedId }: { incidents: IncidentSummary[]; selectedId: string | null }) {
  const map = useMap();
  const located = useMemo(() => incidents.filter((i) => i.lat !== null && i.lng !== null), [incidents]);
  const key = located.map((i) => i.id).join(",");
  const fitted = useRef("");

  useEffect(() => {
    if (!located.length || fitted.current === key) return;
    fitted.current = key;
    const points = located.map((i) => [i.lat!, i.lng!] as [number, number]);
    if (points.length === 1) map.setView(points[0], 15);
    else map.fitBounds(points, { padding: [40, 40], maxZoom: 15 });
  }, [key, located, map]);

  useEffect(() => {
    const target = located.find((i) => i.id === selectedId);
    if (target) map.panTo([target.lat!, target.lng!]);
  }, [selectedId, located, map]);
  return null;
}

/** Incidents on a darkened OpenStreetMap: crimson 80+, warn 50-79, grey below 50, sized by calls. */
export function IncidentMap({
  incidents,
  selectedId,
  onSelect,
}: {
  incidents: IncidentSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <MapContainer center={BOSTON} zoom={13} className="h-full w-full" scrollWheelZoom aria-label="Incident map">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {incidents
        .filter((i) => i.lat !== null && i.lng !== null)
        .map((incident) => {
          const tone = priorityTone(incident.top_priority);
          const selected = incident.id === selectedId;
          return (
            <CircleMarker
              key={incident.id}
              center={[incident.lat!, incident.lng!]}
              radius={8 + Math.min(14, incident.call_count * 1.2)}
              pathOptions={{ className: `mk mk-${tone}${selected ? " mk-selected" : ""}` }}
              eventHandlers={{ click: () => onSelect(incident.id) }}
            >
              <Tooltip direction="top" offset={[0, -6]}>
                {sentence(incident.type)} · {incident.call_count} calls · priority {incident.top_priority}
              </Tooltip>
            </CircleMarker>
          );
        })}
      <Viewport incidents={incidents} selectedId={selectedId} />
    </MapContainer>
  );
}
