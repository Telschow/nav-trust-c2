import * as maplibregl from "maplibre-gl";
import type { FeatureCollection } from "geojson";
import "maplibre-gl/dist/maplibre-gl.css";
// Vite bundles the worker with its imports and gives us a URL for it
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { Info, Maximize2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { localToLonLat, sectorRing } from "../geo";
import { coveredByVehicleTag } from "../labelPlacement";
import { heardAgeS, markerView, tickWhileNoLink } from "../markers";
import { backendLost, isNoLink } from "../store";
import type { ConsoleState } from "../store";
import { LINK_TONE, TONE, vehicleColor } from "../tone";

maplibregl.setWorkerUrl(workerUrl);

const STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      maxzoom: 19,
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    },
  },
  layers: [
    {
      id: "osm",
      type: "raster",
      source: "osm",
      // OSM tiles are light; darken them here so markers and polygons keep their own colours
      paint: { "raster-brightness-max": 0.34, "raster-saturation": -0.55, "raster-contrast": 0.1 },
    },
  ],
};

interface Props {
  state: ConsoleState;
  /** the server clock, advancing between messages (null until known) */
  now: number | null;
  focus: { vehicleId: string; n: number } | null;
}

const EMPTY: FeatureCollection = { type: "FeatureCollection", features: [] };

export function MapView({ state, now, focus }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markers = useRef(new Map<string, { marker: maplibregl.Marker; el: HTMLElement }>());
  const sectorTags = useRef<maplibregl.Marker[]>([]);
  const fitted = useRef(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!container.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      style: STYLE,
      center: [8.5531, 47.4025],
      zoom: 14,
      attributionControl: { compact: true },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.on("load", () => {
      map.addSource("sectors", { type: "geojson", data: EMPTY });
      map.addSource("trails", { type: "geojson", data: EMPTY });
      map.addLayer({ id: "sectors-fill", type: "fill", source: "sectors", paint: { "fill-color": ["get", "color"], "fill-opacity": ["case", ["get", "done"], 0.04, 0.13] } });
      map.addLayer({ id: "sectors-line", type: "line", source: "sectors", paint: { "line-color": ["get", "color"], "line-width": 1.6, "line-opacity": ["case", ["get", "done"], 0.4, 0.85] } });
      map.addLayer({ id: "trails", type: "line", source: "trails", layout: { "line-cap": "round", "line-join": "round" }, paint: { "line-color": ["get", "color"], "line-width": 2.4, "line-opacity": 0.8 } });
      setReady(true);
    });
    mapRef.current = map;
    const current = markers.current;
    return () => {
      current.forEach(({ marker }) => marker.remove());
      current.clear();
      map.remove();
      mapRef.current = null;
      setReady(false);
    };
  }, []);

  // sectors: polygons coloured by the vehicle that currently owns them, plus a label each
  const sectorFeatures = useMemo(() => {
    const origin = state.origin;
    if (!origin) return [];
    return Object.entries(state.fleet).flatMap(([vehicleId, sectors]) =>
      sectors.map((s) => ({ vehicleId, sector: s, origin })),
    );
  }, [state.fleet, state.origin]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const source = map.getSource("sectors") as maplibregl.GeoJSONSource | undefined;
    source?.setData({
      type: "FeatureCollection",
      features: sectorFeatures.map(({ vehicleId, sector, origin }) => ({
        type: "Feature",
        properties: { color: vehicleColor(vehicleId), id: sector.id, done: state.doneSectors.includes(sector.id) },
        geometry: { type: "Polygon", coordinates: [sectorRing(origin, sector)] },
      })),
    });
    sectorTags.current.forEach((m) => m.remove());
    sectorTags.current = sectorFeatures.map(({ vehicleId, sector, origin }) => {
      const el = document.createElement("div");
      el.className = "sector-tag";
      el.style.setProperty("--tone", vehicleColor(vehicleId));
      el.textContent = `${sector.id} · ${vehicleId}${state.doneSectors.includes(sector.id) ? " · done" : ""}`;
      const [lon, lat] = localToLonLat(origin, (sector.west + sector.east) / 2, sector.north - 40);
      return new maplibregl.Marker({ element: el }).setLngLat([lon, lat]).addTo(map);
    });
    if (!fitted.current && sectorFeatures.length > 0) {
      const b = new maplibregl.LngLatBounds();
      sectorFeatures.forEach(({ sector, origin }) => sectorRing(origin, sector).forEach((c) => b.extend(c)));
      map.fitBounds(b, { padding: 70, duration: 0, maxZoom: 16 });
      fitted.current = true;
    }
  }, [sectorFeatures, state.doneSectors, ready]);

  // trails
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    (map.getSource("trails") as maplibregl.GeoJSONSource | undefined)?.setData({
      type: "FeatureCollection",
      features: Object.entries(state.trails)
        .filter(([, coords]) => coords.length > 1)
        .map(([vehicleId, coordinates]) => ({
          type: "Feature",
          properties: { color: vehicleColor(vehicleId) },
          geometry: { type: "LineString", coordinates },
        })),
    });
  }, [state.trails, ready]);

  // only changes while some vehicle has no link, so a healthy fleet is not redrawn on a timer
  const tickNow = tickWhileNoLink(state.links, now);

  // vehicle markers
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    for (const [vehicleId, pos] of Object.entries(state.positions)) {
      const view = markerView(
        vehicleId,
        state.vehicles[vehicleId],
        isNoLink(state, vehicleId),
        heardAgeS(state.links[vehicleId], tickNow),
        backendLost(state),
      );
      let entry = markers.current.get(vehicleId);
      if (!entry) {
        const el = document.createElement("div");
        el.className = "vehicle-marker";
        el.innerHTML = `<div class="dot"></div><div class="tag"></div>`;
        entry = { marker: new maplibregl.Marker({ element: el, anchor: "center" }).setLngLat([pos.lon_deg, pos.lat_deg]).addTo(map), el };
        markers.current.set(vehicleId, entry);
      }
      entry.marker.setLngLat([pos.lon_deg, pos.lat_deg]);
      entry.el.style.setProperty("--tone", view.tone);
      entry.el.classList.toggle("untrusted", view.dashed);
      const tag = entry.el.querySelector(".tag");
      if (tag) {
        tag.textContent = view.tag;
        tag.setAttribute("data-lines", String(view.tag.split("\n").length));
      }
    }
  }, [state.positions, state.vehicles, state.links, state.connected, state.resync, tickNow, ready]);

  // a sector label a vehicle tag would partly cover is hidden whole, so none is left clipped
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const declutter = () => {
      const labels = Array.from(map.getContainer().querySelectorAll<HTMLElement>(".sector-tag"));
      const tags = Array.from(map.getContainer().querySelectorAll<HTMLElement>(".vehicle-marker .tag"));
      const covered = coveredByVehicleTag(
        labels.map((l) => l.getBoundingClientRect()),
        tags.map((t) => t.getBoundingClientRect()),
      );
      labels.forEach((l, i) => l.classList.toggle("covered", covered[i] ?? false));
    };
    map.on("render", declutter);
    declutter();
    return () => {
      map.off("render", declutter);
    };
    // also after the labels or tags change, which can happen without the map being redrawn
  }, [ready, sectorFeatures, state.doneSectors, state.positions, state.vehicles, state.links, tickNow]);

  // focus a vehicle when its card is clicked
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !focus) return;
    const pos = state.positions[focus.vehicleId];
    if (pos) map.flyTo({ center: [pos.lon_deg, pos.lat_deg], zoom: Math.max(map.getZoom(), 15.5), duration: 700 });
    // only when the user asks again, not on every position update
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus?.n, ready]);

  const fit = () => {
    const map = mapRef.current;
    if (!map || sectorFeatures.length === 0) return;
    const b = new maplibregl.LngLatBounds();
    sectorFeatures.forEach(({ sector, origin }) => sectorRing(origin, sector).forEach((c) => b.extend(c)));
    map.fitBounds(b, { padding: 70, duration: 600, maxZoom: 16 });
  };

  return (
    <div className="panel relative h-full overflow-hidden p-0">
      {/* MapLibre sets position: relative on its container, so give it a sized wrapper */}
      <div className="absolute inset-0">
        <div ref={container} className="h-full w-full" />
      </div>
      <button
        type="button"
        onClick={fit}
        className="absolute right-[10px] top-[82px] grid size-[29px] place-items-center rounded-[3px] border border-line bg-panel/95 text-muted hover:text-text focus-visible:outline-2 focus-visible:outline-accent"
        aria-label="Fit survey area"
        title="Fit survey area"
      >
        <Maximize2 className="size-3.5" />
      </button>
      <Legend />
      {!state.origin && (
        <div className="absolute inset-x-0 top-4 mx-auto w-fit rounded-[3px] border border-line bg-panel/95 px-4 py-1.5 text-xs text-muted">
          Waiting for the survey area origin from the backend...
        </div>
      )}
    </div>
  );
}

function Legend() {
  const [open, setOpen] = useState(false);
  return (
    <div className="absolute left-3 top-3 rounded-[3px] border border-line bg-panel/95 text-[11px] text-muted backdrop-blur">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 px-3 py-2 font-medium text-faint hover:text-text focus-visible:outline-2 focus-visible:outline-accent"
      >
        <Info className="size-3.5" aria-hidden /> Map key
      </button>
      {open && (
        <div className="flex flex-col gap-1 px-3.5 pb-3">
          {(["GREEN", "AMBER", "RED"] as const).map((s) => (
            <span key={s} className="flex items-center gap-2">
              <span className="size-2.5 rounded-full" style={{ background: TONE[s].hex }} />
              {s === "GREEN" ? "Position trusted" : s === "AMBER" ? "Position degraded" : "Position not trusted"}
            </span>
          ))}
          <span className="flex items-center gap-2">
            <span className="size-2.5 rounded-full" style={{ background: LINK_TONE }} />
            No link: position and state are last known, not current
          </span>
          <span className="mt-1 flex items-center gap-2">
            <span className="size-3 rounded-full border border-dashed border-muted" />
            Dashed ring: do not rely on this position
          </span>
          <span className="text-faint">Sector colour = vehicle assigned</span>
          <span className="text-faint">Faded sector, "done" = already flown</span>
        </div>
      )}
    </div>
  );
}
