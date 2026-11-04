import { useEffect, useMemo, useRef, useState } from "react";
import { MapContainer, TileLayer, GeoJSON, LayersControl, useMap } from "react-leaflet";
import { useQuery } from "@tanstack/react-query";
import L from "leaflet";
import { apiGet } from "@/lib/api";
import { useFilters } from "@/hooks/useFilters";
import { Alert, Card } from "@/components/ui/Card";
import { DataKindBadge, SampleBadge } from "@/components/ui/Badge";
import { formatNumber } from "@/lib/format";

function FlyTo({ bounds }: { bounds: L.LatLngBoundsExpression | null }) {
  const map = useMap();
  const fitted = useRef(false);
  useEffect(() => {
    if (bounds && !fitted.current) {
      map.fitBounds(bounds, { padding: [20, 20] });
      fitted.current = true;
    }
  }, [bounds, map]);
  return null;
}

export function MapPage() {
  const { filters } = useFilters();
  const [opacity, setOpacity] = useState(0.55);
  const city = useQuery({ queryKey: ["city", filters.city], queryFn: () => apiGet<any>("/cities/slug/current", { city: filters.city }) });
  const stations = useQuery({ queryKey: ["stations", filters.city], queryFn: () => apiGet<any>("/air-quality/stations", { city: filters.city }) });
  const spatial = useQuery({
    queryKey: ["spatial", filters],
    queryFn: () => apiGet<any>("/air-quality/spatial-distribution", { city: filters.city, pollutant: filters.pollutant, start: filters.from, end: filters.to }),
  });
  const roads = useQuery({ queryKey: ["roads", filters.city], queryFn: () => apiGet<any>("/roads", { city: filters.city, major_only: "true" }) });
  const parks = useQuery({ queryKey: ["parks", filters.city], queryFn: () => apiGet<any>("/green-spaces", { city: filters.city }) });
  const industry = useQuery({ queryKey: ["industry", filters.city], queryFn: () => apiGet<any>("/industrial", { city: filters.city }) });
  const grid = useQuery({ queryKey: ["grid", filters.city], queryFn: () => apiGet<any>("/grid", { city: filters.city, limit: 5000 }) });

  const cityBounds = useMemo(() => {
    const geometry = city.data?.boundary?.geometry;
    if (!geometry) return null;
    const rings = geometry.type === "MultiPolygon" ? geometry.coordinates.flat() : geometry.coordinates;
    const latlngs = (rings || []).flat().map((c: number[]) => [c[1], c[0]] as [number, number]);
    if (!latlngs.length) return null;
    return L.latLngBounds(latlngs);
  }, [city.data]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <DataKindBadge kind="observed" />
        <SampleBadge />
        {stations.data?.coverage_warning ? <Alert>{stations.data.coverage_warning}</Alert> : null}
      </div>
      <div className="grid gap-3 lg:grid-cols-[1fr_16rem]">
        <div className="h-[70vh] overflow-hidden rounded-xl border border-stone-200">
          <MapContainer center={[28.6139, 77.209]} zoom={11} scrollWheelZoom>
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <LayersControl position="topright">
              <LayersControl.Overlay checked name="City boundary">
                {city.data?.boundary ? <GeoJSON data={city.data.boundary} style={{ color: "#1c1917", weight: 2, fillOpacity: 0.04 }} /> : null}
              </LayersControl.Overlay>
              <LayersControl.Overlay checked name="Monitoring stations">
                {spatial.data ? (
                  <GeoJSON
                    data={spatial.data}
                    pointToLayer={(_f, latlng) => L.circleMarker(latlng, { radius: 9, color: "#7c2d12", fillColor: "#b45309", fillOpacity: 0.9, weight: 2 })}
                    onEachFeature={(feature, layer) => {
                      const p = feature.properties;
                      layer.bindPopup(
                        `<strong>${p.name}</strong><br/>${p.pollutant}: ${p.mean ?? "—"} ${p.unit ?? ""}<br/>n=${p.count}<br/>source: station aggregate<br/>kind: ${p.data_kind}`,
                      );
                    }}
                  />
                ) : null}
              </LayersControl.Overlay>
              <LayersControl.Overlay checked name="Analysis grid">
                {grid.data ? (
                  <GeoJSON
                    data={grid.data}
                    style={(feature) => {
                      const conc = feature?.properties?.mean_concentration;
                      const fill =
                        conc == null ? "#e7e5e4" : conc > 100 ? "#7c2d12" : conc > 80 ? "#c2410c" : conc > 60 ? "#ea580c" : "#d97706";
                      return { color: "#57534e", weight: 0.4, fillColor: fill, fillOpacity: opacity };
                    }}
                    onEachFeature={(feature, layer) => {
                      const p = feature.properties;
                      const estimateNote = p.pollution_assignment === "idw_estimate" ? "IDW estimate, not a measurement" : p.pollution_assignment;
                      layer.bindPopup(
                        `<strong>${p.grid_code}</strong><br/>obs count: ${p.observation_count}<br/>mean conc: ${p.mean_concentration ?? "—"}<br/>NDVI: ${p.mean_ndvi ?? "—"}<br/>built-up %: ${p.built_up_percentage ?? "—"}<br/>${estimateNote}`,
                      );
                    }}
                  />
                ) : null}
              </LayersControl.Overlay>
              <LayersControl.Overlay checked name="Major roads">
                {roads.data ? <GeoJSON data={roads.data} style={{ color: "#44403c", weight: 2 }} /> : null}
              </LayersControl.Overlay>
              <LayersControl.Overlay checked name="Green spaces">
                {parks.data ? <GeoJSON data={parks.data} style={{ color: "#166534", fillColor: "#3f6b4a", fillOpacity: 0.35 }} /> : null}
              </LayersControl.Overlay>
              <LayersControl.Overlay name="Industrial (mapped only)">
                {industry.data ? <GeoJSON data={industry.data} style={{ color: "#7c2d12", fillColor: "#b45309", fillOpacity: 0.4 }} /> : null}
              </LayersControl.Overlay>
            </LayersControl>
            <FlyTo bounds={cityBounds} />
          </MapContainer>
        </div>
        <Card title="Legend and layers">
          <label className="text-xs">
            Grid opacity
            <input className="w-full" type="range" min={0.15} max={0.9} step={0.05} value={opacity} onChange={(e) => setOpacity(Number(e.target.value))} />
          </label>
          <ul className="mt-3 space-y-1 text-sm">
            <li><span className="mr-2 inline-block h-3 w-3 rounded-full bg-clay" /> Station mean (observed)</li>
            <li><span className="mr-2 inline-block h-3 w-3 bg-clay" /> Higher PM2.5 (IDW estimate, not a measurement)</li>
            <li><span className="mr-2 inline-block h-3 w-3 bg-stone-200" /> No concentration assigned</li>
            <li>Basemap: OpenStreetMap</li>
          </ul>
          <p className="mt-3 text-xs text-stone-600">
            {industry.data?.disclaimer} Grid fill uses an IDW estimate only when at least eight stations exist. Station markers remain observed values.
          </p>
          <p className="mt-2 text-xs">Stations loaded: {formatNumber(stations.data?.features?.length, 0)}</p>
        </Card>
      </div>
    </div>
  );
}
